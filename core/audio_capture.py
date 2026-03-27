"""
audio_capture.py — Dual-source audio capture: microphone + system/meeting audio.

On Windows with VB-Cable:
  - CABLE Output  → captures Google Meet audio (other participants)
  - Microphone    → captures your own voice
  Both streams are mixed together in real-time into one audio feed.

Without VB-Cable:
  - Falls back to microphone only.

Usage:
    capture = AudioCapture()
    capture.start()
    capture.stop()
"""

import threading
import wave
import logging
import time
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from core.config import config

logger = logging.getLogger(__name__)


class AudioCapture:
    """
    Captures audio from two devices simultaneously (mic + system/VB-Cable)
    and mixes them into a single stream for transcription.
    """

    def __init__(
        self,
        device_index: Optional[int] = None,
        sample_rate: int = None,
        chunk_seconds: int = None,
        on_chunk: Optional[Callable[[np.ndarray, float], None]] = None,
    ):
        self.sample_rate = sample_rate or config.AUDIO_SAMPLE_RATE
        self.chunk_seconds = chunk_seconds or config.AUDIO_CHUNK_SECONDS
        self.on_chunk      = on_chunk
        self._manual_device = device_index if device_index is not None and device_index >= 0 else None

        self._stop_event   = threading.Event()
        self._mic_frames:    list[bytes] = []
        self._system_frames: list[bytes] = []
        self._mixed_frames:  list[bytes] = []

        self._mic_buffer:    bytes = b""
        self._system_buffer: bytes = b""
        self._buffer_lock    = threading.Lock()

        self._recording_path: Optional[Path] = None
        self._pa = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self, save_recording: bool = True) -> None:
        """Start capturing from mic + system audio simultaneously."""
        try:
            import pyaudio
        except ImportError:
            raise RuntimeError("pyaudio not installed. Run: pip install pyaudio")

        self._pa = pyaudio.PyAudio()
        self._stop_event.clear()

        devices = self._list_devices()
        mic_idx, system_idx = self._resolve_devices(devices)

        logger.info(f"Microphone device:   index={mic_idx} ({self._device_name(devices, mic_idx)})")
        if system_idx is not None:
            logger.info(f"System audio device: index={system_idx} ({self._device_name(devices, system_idx)})")
        else:
            logger.warning("No system/VB-Cable device found — capturing microphone only.")
            logger.warning("Install VB-Cable and set Google Meet speaker to 'CABLE Input' to capture all participants.")

        if save_recording:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._recording_path = config.RECORDINGS_DIR / f"meeting_{ts}.wav"

        # Start microphone capture thread
        mic_thread = threading.Thread(
            target=self._capture_device,
            args=(mic_idx, "mic"),
            daemon=True,
        )
        mic_thread.start()

        # Start system audio capture thread (if available)
        if system_idx is not None:
            sys_thread = threading.Thread(
                target=self._capture_device,
                args=(system_idx, "system"),
                daemon=True,
            )
            sys_thread.start()

        # Start mixer thread that combines both buffers and fires callbacks
        mixer_thread = threading.Thread(target=self._mixer_loop, daemon=True)
        mixer_thread.start()

        logger.info("Audio capture started (dual-source mix).")

    def stop(self) -> Optional[Path]:
        """Stop capture, save WAV, return path."""
        self._stop_event.set()
        time.sleep(0.5)  # let threads flush

        if self._pa:
            self._pa.terminate()

        path = self._save_session_wav()
        logger.info(f"Audio capture stopped. Recording: {path}")
        return path

    def list_devices(self) -> list[dict]:
        """Return all available audio input devices."""
        try:
            import pyaudio
        except ImportError:
            raise RuntimeError("pyaudio not installed.")
        pa = pyaudio.PyAudio()
        devices = self._list_devices(pa)
        pa.terminate()
        return devices

    # ── Device discovery ───────────────────────────────────────────────────────

    def _list_devices(self, pa=None) -> list[dict]:
        """List input devices. Uses self._pa if no pa passed."""
        _pa = pa or self._pa
        devices = []
        for i in range(_pa.get_device_count()):
            info = _pa.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                devices.append({
                    "index":       i,
                    "name":        info["name"],
                    "sample_rate": int(info["defaultSampleRate"]),
                    "channels":    int(info["maxInputChannels"]),
                })
        return devices

    def _resolve_devices(self, devices: list[dict]) -> tuple[int, Optional[int]]:
        """
        Returns (mic_index, system_audio_index).
        Respects AUDIO_SYSTEM_DEVICE_INDEX from .env if set.
        system_audio_index is None if VB-Cable is not found.
        """
        mic_idx    = None
        system_idx = None

        # If a system device index is explicitly set in .env, use it directly
        if config.AUDIO_DEVICE_INDEX >= 0:
            system_idx = config.SYSTEM_DEVICE_INDEX
            logger.info(f"Using system audio device from config: index={system_idx}")
        else:
            # Auto-detect VB-Cable / loopback / stereo mix
            system_keywords = [
                "cable output", "vb-audio", "virtual cable",
                "stereo mix", "what u hear", "wave out mix",
                "loopback", "monitor",
            ]
            for device in devices:
                name_lower = device["name"].lower()
                if any(kw in name_lower for kw in system_keywords):
                    system_idx = device["index"]
                    logger.info(f"Auto-detected system audio: '{device['name']}' (index {device['index']})")
                    break

        mic_keywords = [
            "microphone", "mic", "headset", "webcam",
            "realtek", "usb audio", "built-in", "array",
        ]

        if self._manual_device is not None:
            mic_idx = self._manual_device
        else:
            for device in devices:
                name_lower = device["name"].lower()
                if device["index"] == system_idx:
                    continue
                if any(kw in name_lower for kw in mic_keywords):
                    mic_idx = device["index"]
                    break
            if mic_idx is None:
                mic_idx = -1

        return mic_idx, system_idx

    def _device_name(self, devices: list[dict], index: int) -> str:
        if index is None or index < 0:
            return "default"
        for d in devices:
            if d["index"] == index:
                return d["name"]
        return f"index {index}"

    # ── Capture threads ────────────────────────────────────────────────────────

    def _capture_device(self, device_index: int, label: str) -> None:
        """Continuously read audio from one device into its buffer."""
        import pyaudio
        chunk_size = 1024

        try:
            stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index if device_index >= 0 else None,
                frames_per_buffer=chunk_size,
            )
        except Exception as e:
            logger.error(f"Could not open {label} device (index={device_index}): {e}")
            return

        logger.info(f"{label} stream opened.")

        while not self._stop_event.is_set():
            try:
                raw = stream.read(chunk_size, exception_on_overflow=False)
                with self._buffer_lock:
                    if label == "mic":
                        self._mic_buffer    += raw
                        self._mic_frames.append(raw)
                    else:
                        self._system_buffer += raw
                        self._system_frames.append(raw)
            except OSError as e:
                logger.warning(f"{label} read error: {e}")
                time.sleep(0.05)

        stream.stop_stream()
        stream.close()

    # ── Mixer loop ─────────────────────────────────────────────────────────────

    def _mixer_loop(self) -> None:
        """
        Every chunk_seconds, take whatever is in both buffers,
        mix them by averaging, and fire the on_chunk callback.
        """
        frames_needed = self.sample_rate * self.chunk_seconds * 2  # bytes (int16 = 2 bytes)

        while not self._stop_event.wait(timeout=self.chunk_seconds):
            with self._buffer_lock:
                mic_data    = self._mic_buffer
                system_data = self._system_buffer
                self._mic_buffer    = b""
                self._system_buffer = b""

            mixed = _mix_audio(mic_data, system_data)
            if mixed is not None and len(mixed) > 0:
                self._mixed_frames.append(
                    (mixed * 32768).astype(np.int16).tobytes()
                )
                if self.on_chunk:
                    self.on_chunk(mixed, time.time())

        # Flush remaining buffers after stop
        with self._buffer_lock:
            mic_data    = self._mic_buffer
            system_data = self._system_buffer

        mixed = _mix_audio(mic_data, system_data)
        if mixed is not None and len(mixed) > 0:
            self._mixed_frames.append(
                (mixed * 32768).astype(np.int16).tobytes()
            )
            if self.on_chunk:
                self.on_chunk(mixed, time.time())

    # ── Save WAV ───────────────────────────────────────────────────────────────

    def _save_session_wav(self) -> Optional[Path]:
        if not self._mixed_frames or not self._recording_path:
            return None
        with wave.open(str(self._recording_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(b"".join(self._mixed_frames))
        return self._recording_path


# ── Audio mixing utility ───────────────────────────────────────────────────────

def _mix_audio(mic_bytes: bytes, system_bytes: bytes) -> Optional[np.ndarray]:
    """
    Mix two raw int16 PCM byte strings into one float32 array.
    If only one source has data, return that source alone.
    Pads the shorter source with silence if lengths differ.
    """
    has_mic    = len(mic_bytes) > 0
    has_system = len(system_bytes) > 0

    if not has_mic and not has_system:
        return None

    def to_float(raw: bytes) -> np.ndarray:
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

    if has_mic and not has_system:
        return to_float(mic_bytes)

    if has_system and not has_mic:
        return to_float(system_bytes)

    mic_arr    = to_float(mic_bytes)
    system_arr = to_float(system_bytes)

    # Pad shorter array with silence
    length = max(len(mic_arr), len(system_arr))
    if len(mic_arr) < length:
        mic_arr = np.pad(mic_arr, (0, length - len(mic_arr)))
    if len(system_arr) < length:
        system_arr = np.pad(system_arr, (0, length - len(system_arr)))

    # Mix: average both sources, then clip to [-1, 1]
    mixed = (mic_arr + system_arr) / 2.0
    return np.clip(mixed, -1.0, 1.0)


# ── CLI helper ─────────────────────────────────────────────────────────────────

def list_audio_devices():
    """Print all available audio input devices."""
    capture = AudioCapture()
    devices = capture.list_devices()
    print("\nAvailable audio input devices:")
    print("-" * 60)
    for d in devices:
        print(f"  [{d['index']}] {d['name']}  ({d['sample_rate']} Hz)")
    print()
    return devices


if __name__ == "__main__":
    list_audio_devices()
