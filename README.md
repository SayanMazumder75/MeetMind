# 🎙️ AI Meeting Notes App (Lightweight Edition)

Real-time meeting transcription and summarization — supports **Hindi**, **Bengali**, and English.  
Uses **AssemblyAI** for speech recognition and **Claude** for summarization.  
**No GPU needed. No 4 GB model downloads. Works in minutes.**

---

## ⚡ What Changed (vs Original)

| | Before | After |
|---|---|---|
| Install size | ~4 GB (Whisper + PyTorch + BART) | ~50 MB |
| Hindi/Bengali accuracy | Poor | Excellent |
| First run time | 10–30 min (model download) | < 1 min |
| Requires GPU | Optional but helpful | No |
| Summarizer | HuggingFace BART (local, 1.5 GB) | Claude API (cloud) |
| Speech engine | Local Whisper | AssemblyAI (cloud) |

---

## 🗂️ Architecture

```
Meeting Audio (Mic / VB-Cable / PulseAudio)
        ↓
  Audio Capture     (PyAudio — core/audio_capture.py)
        ↓
  AssemblyAI API    (Hindi / Bengali / English → English text)
        ↓
  Live Transcript   (core/transcriber.py → LiveTranscript)
        ↓
  Claude API        (Summarize + extract action items in English)
        ↓
  Dashboard         (Streamlit — dashboard/app.py)
```

---

## ⚙️ Setup (5 minutes)

### 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

### 2. Get API keys (both free tiers available)

| Service | Get key | Free tier |
|---------|---------|-----------|
| AssemblyAI | https://www.assemblyai.com | 100 hours/month |
| Anthropic (Claude) | https://console.anthropic.com | $5 free credit |

### 3. Configure .env

```bash
cp .env.example .env
```

Edit `.env` — minimum config for Hindi meetings:

```env
SPEECH_ENGINE=assemblyai
ASSEMBLYAI_API_KEY=your_key_here

LANGUAGE_CODE=hi          # hi=Hindi, bn=Bengali, en=English
TRANSLATE_TO_ENGLISH=true

SUMMARIZER=claude
ANTHROPIC_API_KEY=your_key_here
```

### 4. Configure audio routing (to capture Google Meet)

**Windows:**
1. Install [VB-Cable](https://vb-audio.com/Cable/)
2. Windows Sound Settings → set "CABLE Input" as default playback
3. Google Meet → Settings → Audio → Microphone → "CABLE Output"

**Linux:**
```bash
pactl load-module module-loopback latency_msec=1
```

**Just testing?** Skip audio routing — the app will use your microphone.

---

## 🚀 Running

### Streamlit Dashboard (recommended)

```bash
streamlit run dashboard/app.py
# Opens at http://localhost:8501
```

### Command line

```bash
# Start recording (Ctrl+C to stop)
python main.py record

# Record for 10 minutes
python main.py record --duration 600

# List audio devices
python main.py devices

# Transcribe a saved WAV file
python main.py transcribe path/to/audio.wav

# Summarize a saved transcript
python main.py summarize data/transcripts/session_xxx.json

# View all saved sessions
python main.py sessions
```

---

## 🌐 Language Support

AssemblyAI supports 99+ languages. Set `LANGUAGE_CODE` in your `.env`:

| Language | Code |
|----------|------|
| Hindi | `hi` |
| Bengali | `bn` |
| English | `en` |
| Tamil | `ta` |
| Telugu | `te` |
| Marathi | `mr` |
| Gujarati | `gu` |
| Auto-detect | `auto` |

With `TRANSLATE_TO_ENGLISH=true`, transcripts are automatically translated to English  
before summarization — no extra step needed.

---

## 🤖 Engine Options

### Speech Recognition

| Engine | Cost | Hindi/Bengali | Speaker ID | Size |
|--------|------|--------------|------------|------|
| `assemblyai` ✅ | Paid API | Excellent | ✅ Yes | 0 MB |
| `whisper` (tiny) | Free (local) | Poor | No | ~75 MB |

### Summarization

| Engine | Cost | Hindi/Bengali | Size |
|--------|------|--------------|------|
| `claude` ✅ | Paid API | Excellent | 0 MB |
| `simple` | Free | No | 0 MB |

---

## 📤 Export Options

- **PDF** — formatted meeting notes
- **Word (.docx)** — editable document
- **Google Docs** — requires OAuth setup

---

## 🐛 Troubleshooting

**PyAudio install fails on Linux:**
```bash
sudo apt-get install portaudio19-dev python3-pyaudio
pip install pyaudio
```

**AssemblyAI error "invalid API key":**
Check your key at https://www.assemblyai.com/app

**Hindi transcript looks wrong:**
Make sure `LANGUAGE_CODE=hi` is set in `.env`.  
If the meeting mixes Hindi and English (Hinglish), set `LANGUAGE_CODE=auto`.

**No transcript appearing:**
```bash
python main.py devices   # find your device index
# then set AUDIO_DEVICE_INDEX=<number> in .env
```