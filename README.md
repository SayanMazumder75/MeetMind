# 🎙️ AI Meeting Notes App

A real-time AI-powered meeting transcription and summarization tool built in Python.  
Record your Google Meet (or any meeting), get a live transcript, auto-generated summary, action items, and export to PDF/Word/Google Docs.

---

## 📐 Architecture

```
Google Meet Audio (VB-Cable / PulseAudio)
        ↓
  Audio Capture System  (PyAudio — core/audio_capture.py)
        ↓
  Speech Recognition    (Whisper / AssemblyAI / Google — core/transcriber.py)
        ↓
  Live Transcript       (core/transcriber.py → LiveTranscript)
        ↓
  NLP Summarization     (HuggingFace / OpenAI / Claude — core/summarizer.py)
        ↓
  Meeting Notes Dashboard  (Streamlit — dashboard/app.py)
```

---

## 🗂️ Project Structure

```
ai_meeting_notes/
├── main.py                    # CLI entry point
├── requirements.txt
├── .env.example               # Copy to .env and fill in values
│
├── core/
│   ├── config.py              # Central config (reads .env)
│   ├── audio_capture.py       # Real-time audio capture (PyAudio)
│   ├── transcriber.py         # Speech-to-text (Whisper / AssemblyAI / Google)
│   ├── summarizer.py          # NLP summarization (HuggingFace / OpenAI / Claude)
│   └── session.py             # Coordinates all components, saves sessions
│
├── dashboard/
│   └── app.py                 # Streamlit web dashboard
│
├── exports/
│   ├── export_pdf.py          # Export to PDF
│   ├── export_docx.py         # Export to Word .docx
│   └── export_google_docs.py  # Export to Google Docs
│
└── data/
    ├── recordings/            # Saved WAV files
    ├── transcripts/           # Session JSON files
    └── summaries/             # Exported PDF/DOCX files
```

---

## ⚙️ Setup

### 1. Install Python dependencies

```bash
# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows

pip install -r requirements.txt

# Download spaCy English model (for entity/topic extraction)
python -m spacy download en_core_web_sm
```

### 2. Configure audio routing

**Windows (Google Meet → VB-Cable):**
1. Download & install [VB-Cable](https://vb-audio.com/Cable/)
2. In Windows Sound Settings → Playback → set "CABLE Input" as default
3. In Google Meet → Settings → Audio → Microphone → select "CABLE Output"
4. The app will auto-detect VB-Cable

**Linux (PulseAudio loopback):**
```bash
# Load the loopback module
pactl load-module module-loopback latency_msec=1
# Or use pavucontrol to route the Meet tab audio to a monitor source
```

**Quick test (microphone fallback):**
If you just want to test, skip the above — the app will capture from your default microphone.

### 3. Create your .env file

```bash
cp .env.example .env
# Edit .env with your settings
```

Minimum config (free, local, no API keys needed):
```
SPEECH_ENGINE=whisper
WHISPER_MODEL=base
SUMMARIZER=transformers
```

---

## 🚀 Running the App

### Option A — Streamlit dashboard (recommended)

```bash
streamlit run dashboard/app.py
# Opens at http://localhost:8501
```

Or via the CLI:
```bash
python main.py dashboard
```

### Option B — Command line

```bash
# Start recording (Ctrl+C to stop)
python main.py record

# Record for 5 minutes
python main.py record --duration 300

# List available audio devices
python main.py devices

# Transcribe a WAV file
python main.py transcribe path/to/audio.wav

# Summarize a saved transcript
python main.py summarize data/transcripts/session_20260317_143000.json

# List all saved sessions
python main.py sessions
```

---

## 🤖 Engine Options

### Speech Recognition

| Engine | Cost | Accuracy | Speaker ID | Setup |
|--------|------|----------|------------|-------|
| `whisper` | Free (local) | Excellent | No | `pip install openai-whisper` |
| `assemblyai` | Paid API | Excellent | ✅ Yes | API key in .env |
| `google` | Free tier | Good | No | `pip install SpeechRecognition` |

**Recommendation:** Start with `whisper` + `base` model. If you need speaker labels, upgrade to `assemblyai`.

### Summarization

| Engine | Cost | Quality | Setup |
|--------|------|---------|-------|
| `transformers` | Free (local) | Good | `pip install transformers` (downloads ~1.5 GB model) |
| `openai` | Paid API | Excellent | `OPENAI_API_KEY` in .env |
| `claude` | Paid API | Excellent | `ANTHROPIC_API_KEY` in .env |

**Recommendation:** Start with `transformers`. For higher quality, use `claude` or `openai`.

---

## 📤 Export Options

From the dashboard sidebar or after a CLI session:

- **PDF** — nicely formatted, includes summary + full transcript
- **Word (.docx)** — editable document with styled sections
- **Google Docs** — requires OAuth setup (see exports/export_google_docs.py)

---

## 🔧 Advanced Features (from your notes)

These are marked with ✓ in your notebook as planned enhancements:

| Feature | Status | How to enable |
|---------|--------|---------------|
| Speaker identification | Partial — AssemblyAI backend | Set `SPEECH_ENGINE=assemblyai` |
| Highlight important sentences | ✅ Implemented | Auto in summarizer |
| Meeting reminders | Planned | Add to session.py |
| Translate to another language | Planned | Add HuggingFace `translation` pipeline |
| Ask AI questions about meeting | Planned | Add RAG on transcript using OpenAI / Claude |

---

## 🐛 Troubleshooting

**`portaudio` not found (PyAudio install fails on Linux):**
```bash
sudo apt-get install portaudio19-dev python3-pyaudio
pip install pyaudio
```

**Whisper model download is slow:**
The `base` model is ~140 MB. `medium` is ~1.4 GB. Use `tiny` for fast testing.

**No transcript appearing:**
1. Run `python main.py devices` to check your audio device index
2. Set `AUDIO_DEVICE_INDEX=<index>` in your .env
3. Make sure audio is actually being routed through VB-Cable / PulseAudio

**`transformers` model download is slow:**
BART-large-cnn is ~1.5 GB. For a faster/smaller model, try:
```
SUMMARIZER_MODEL=sshleifer/distilbart-cnn-12-6
```

---

## 📚 Libraries Used

- [OpenAI Whisper](https://github.com/openai/whisper) — speech recognition
- [HuggingFace Transformers](https://huggingface.co/facebook/bart-large-cnn) — summarization
- [spaCy](https://spacy.io/) — entity & topic extraction
- [Streamlit](https://streamlit.io/) — dashboard
- [PyAudio](https://people.csail.mit.edu/hubert/pyaudio/) — audio capture
- [fpdf2](https://pyfpdf.github.io/fpdf2/) — PDF export
- [python-docx](https://python-docx.readthedocs.io/) — Word export
