# SnapStudy — Your Private AI Tutor, Powered On-Device

> Snapdragon® AI Lab Build & Present Challenge Submission

SnapStudy turns your own study documents into a private AI tutor using Retrieval-Augmented Generation (RAG) and on-device AI. All processing — text extraction, embedding, vector search, and inference — runs locally on your device.

---

## Problem

Students have large amounts of study material but generic AI assistants don't provide answers grounded in their actual curriculum. Uploading private documents (personal notes, exam prep) to cloud AI services raises legitimate privacy concerns.

## Solution

SnapStudy processes your documents locally and creates a private AI tutor that answers questions using your own material, with source citations showing exactly which document and page each answer came from.

---

## Features

| Feature | Description |
|---|---|
| 📄 Document Library | Upload PDF, DOCX, PPTX, TXT, MD files. Processed entirely on-device. |
| 🤖 AI Tutor | Ask questions, get grounded answers with source citations |
| 🎯 Quiz Lab | Generate quizzes from your material (MC, T/F, short answer) |
| 🔄 Smart Revision | Adaptive revision sessions targeting your weakest topics |
| 📊 Analytics | Topic mastery scores, learning progress charts |
| ⚡ On-Device AI | Real benchmark measurements — no fabricated numbers |
| 🔒 Privacy-First | Study materials stay on your device |

---

## Architecture

```
STUDENT
   │
   ▼
┌──────────────────────────────────┐
│           SnapStudy              │
│   React UI ↔ FastAPI Backend     │
└──────────────┬───────────────────┘
               │
    ┌──────────┴──────────┐
    ▼                     ▼
Study Documents      Student Query
    │                     │
    ▼                     ▼
Text Extraction       Embedding Model
(PyMuPDF/DOCX/PPTX)  (sentence-transformers
    │                  all-MiniLM-L6-v2)
    ▼                     │
512-word Chunks           ▼
    │               FAISS Vector DB
    └──────────┬──────────┘
               ▼
         Top-K Retrieval
         (cosine similarity)
               │
               ▼
      Local AI Model
      ┌──────────────────────┐
      │  mock (demo/dev)     │
      │  Ollama (local LLM)  │
      │  ONNX Runtime        │
      │  Qualcomm AI Hub     │
      └──────────────────────┘
               │
               ▼
  Grounded Answer + Source Citations
               │
    ┌──────────┴──────────┐
    ▼                     ▼
 Student             Analytics
 (answer)        (mastery tracking)
```

**Stack:**
- Backend: Python 3.11+, FastAPI, SQLAlchemy, SQLite
- Embeddings: sentence-transformers (all-MiniLM-L6-v2) — runs fully on-device
- Vector DB: FAISS (local, no external service)
- Frontend: React 19, TypeScript, Tailwind CSS, Recharts
- Document parsing: PyMuPDF, python-docx, python-pptx

---

## Installation

### Prerequisites
- Python 3.11+
- Node.js 18+
- Git

### 1. Clone and install backend dependencies

```bash
git clone <repo-url>
cd snapstudy

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env to configure AI_PROVIDER (see Model Setup below)
```

### 3. Install and build frontend

```bash
cd frontend
npm install
npm run build
cd ..
```

### 4. Load demo data and start

```bash
# Load demo study material (Computer Science Fundamentals)
python scripts/create_demo_data.py

# Start the server
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 in your browser.

For development (frontend hot-reload):
```bash
# Terminal 1 — backend
python -m uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend dev server
cd frontend
npm run dev
# Open http://localhost:5173
```

---

## Model Setup

### Default: Mock mode (demo/dev — no real AI)

```env
AI_PROVIDER=mock
EMBEDDING_PROVIDER=sentence_transformers
```

The mock provider uses rule-based responses. Real sentence-transformer embeddings still run locally, so RAG retrieval works correctly. Generation responses are clearly labelled as mock.

### Option 1: Ollama (recommended for real answers)

Install Ollama from https://ollama.com, then:

```bash
ollama pull llama3.2:3b   # ~2GB
# or
ollama pull phi3:mini     # ~2.3GB
```

Set in `.env`:
```env
AI_PROVIDER=local_llm
LOCAL_LLM_URL=http://localhost:11434
LOCAL_LLM_MODEL=llama3.2:3b
```

Ollama runs the model entirely on your local machine.

### Option 2: ONNX Runtime

For ONNX-exported quantized models:

```bash
pip install onnxruntime
# For GPU/DirectML on Windows:
pip install onnxruntime-directml
```

```env
AI_PROVIDER=onnx
ONNX_LLM_PATH=./models/llm.onnx
ONNX_EMBED_PATH=./models/embeddings.onnx
```

On Snapdragon, ONNX Runtime can use `QNNExecutionProvider` (requires Qualcomm QNN SDK) or `DmlExecutionProvider` (DirectML) for NPU/GPU acceleration.

### Option 3: Qualcomm AI Hub

See the section below.

---

## Qualcomm AI Hub Integration

The AI model abstraction layer (`backend/models/`) is designed to slot in a Qualcomm AI Hub model with minimal code changes.

**Integration file:** `backend/models/qualcomm_ai_hub.py`

**Steps to connect a real AI Hub model:**

1. Register at https://aihub.qualcomm.com
2. Get your API token
3. Compile a model:
   ```python
   import qai_hub as hub
   hub.configure(api_token="your_token")
   
   # Example: compile Llama 3.2 1B for Snapdragon X Elite
   job = hub.submit_compile_job(
       model=...,  # your PyTorch model
       device=hub.Device("Snapdragon X Elite"),
       input_specs={"input_ids": ((1, 512), "int32")},
   )
   compiled_model = job.get_target_model()
   ```
4. Set in `.env`:
   ```env
   AI_PROVIDER=qualcomm_ai_hub
   QAI_HUB_API_TOKEN=your_token_here
   QAI_HUB_MODEL_ID=your_compiled_model_id
   QAI_HUB_DEVICE=snapdragon-x-elite
   ```
5. Update `qualcomm_ai_hub.py`'s `_run_inference()` method with your model's specific input/output tensor names.

**Why this architecture matters:** swapping providers requires only a `.env` change — the entire application (RAG pipeline, quiz generation, mastery tracking) continues to work unchanged.

---

## Snapdragon Optimization

SnapStudy is architected for Snapdragon-powered devices:

| Optimization | Implementation |
|---|---|
| **On-device embeddings** | sentence-transformers runs locally, no cloud API |
| **Local vector search** | FAISS runs in-process, no network overhead |
| **NPU acceleration path** | ONNX Runtime + QNNExecutionProvider or Qualcomm AI Hub |
| **DirectML support** | ONNX Runtime DmlExecutionProvider for Snapdragon GPU |
| **Quantization ready** | INT4/INT8 ONNX models supported via onnxruntime |
| **Memory efficient** | Chunked processing, model loaded once and cached |
| **Real benchmarking** | Benchmark page shows actual measured latency and memory |

On a Snapdragon X Elite device with Ollama or an ONNX INT4 model, inference latency for 128-token generation is typically in the range of 1–3 seconds for 3B parameter models. Embedding (384-dim, MiniLM) runs in under 50ms per chunk.

---

## Privacy

| Data type | Where it goes |
|---|---|
| Uploaded documents | Saved to `data/uploads/` on your device |
| Extracted text | Stored in local SQLite DB (`data/snapstudy.db`) |
| Embeddings | FAISS index at `data/vector_db/` on your device |
| AI generation (mock) | Processed entirely on-device, no external calls |
| AI generation (Ollama) | Processed on-device by the locally running Ollama server |
| AI generation (AI Hub) | Sent to Qualcomm AI Hub API — review their privacy policy |
| Analytics/quiz data | Local SQLite only |

**Claim:** When using `AI_PROVIDER=mock` or `AI_PROVIDER=local_llm`, no study content leaves your device. This is verifiable by inspecting the network traffic.

---

## Running Tests

```bash
python -m pytest tests/ -v
```

Test coverage includes:
- Document extraction (PDF, DOCX, PPTX, TXT)
- Text chunking and cleaning
- AI model interface (mock provider)
- FAISS vector indexing and search
- RAG answer generation
- Quiz generation and evaluation
- Topic mastery calculation
- All API endpoints
- End-to-end: upload → process → ask → grounded answer

---

## Demo Mode

The app ships with a 15KB Computer Science Fundamentals study guide covering:
- Database Management (normalization, SQL, ACID)
- Data Structures (arrays, trees, sorting algorithms)
- Operating Systems (processes, scheduling, memory)
- Computer Networks (OSI model, TCP/UDP, IP)

```bash
python scripts/create_demo_data.py
```

Or click "Load Demo Data" in the Dashboard.

**Demo questions to try:**
- "What is database normalization?"
- "What are the normal forms?"
- "Explain merge sort"
- "What is the difference between TCP and UDP?"
- "What causes a deadlock?"

---

## Limitations

- Quiz generation quality depends on the AI provider. Mock mode produces template-based questions; a real LLM produces contextual questions.
- The sentence-transformer embedding model is 90MB and downloads automatically on first run (requires internet on first launch only).
- Voice feature requires `VOICE_ENABLED=true` and additional library installation (`SpeechRecognition`, `pyttsx3`).
- ONNX LLM generation requires a separately exported model file — only embedding works out of the box via the sentence-transformers provider.
- The Qualcomm AI Hub adapter requires the `qai-hub` SDK and a valid API token.

---

## Future Improvements

- NPU-accelerated models via Qualcomm AI Hub (Llama 3.2, Phi-3 Mini)
- Multilingual tutoring support
- Handwriting recognition for scanned notes
- Camera-based question input
- Spaced repetition scheduling
- Collaborative study sessions
- Export quiz results as PDF
- Offline-first PWA packaging

---

## Project Structure

```
snapstudy/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── api/                       # Route handlers
│   │   ├── documents.py           # Upload, list, delete, summarize
│   │   ├── tutor.py               # RAG Q&A, conversations
│   │   ├── quiz.py                # Quiz generation and evaluation
│   │   ├── analytics.py           # Dashboard, mastery, revision, benchmark
│   │   └── voice.py               # Optional voice endpoints
│   ├── services/
│   │   ├── document_processor.py  # Text extraction + chunking
│   │   ├── rag_service.py         # FAISS indexing + RAG pipeline
│   │   ├── quiz_service.py        # Quiz generation + evaluation
│   │   ├── mastery_service.py     # Adaptive learning + analytics
│   │   ├── benchmark_service.py   # Real inference benchmarking
│   │   └── voice_service.py       # STT/TTS (optional)
│   ├── models/
│   │   ├── base.py                # AIModel abstract interface
│   │   ├── mock_model.py          # Demo/dev provider
│   │   ├── local_llm.py           # Ollama provider
│   │   ├── onnx_model.py          # ONNX Runtime provider
│   │   ├── qualcomm_ai_hub.py     # Qualcomm AI Hub adapter
│   │   ├── sentence_transformer_model.py  # Local embeddings
│   │   └── factory.py             # Provider selection
│   ├── database/
│   │   ├── models.py              # SQLAlchemy ORM models
│   │   └── connection.py          # Engine + session management
│   └── config/
│       └── settings.py            # Pydantic settings from .env
├── frontend/                      # React + TypeScript + Tailwind
│   └── src/
│       ├── pages/                 # Dashboard, Library, Tutor, Quiz, etc.
│       ├── components/            # Reusable UI components
│       ├── services/api.ts        # Axios API client
│       └── types/index.ts         # TypeScript types
├── data/
│   ├── demo/                      # Demo study material
│   ├── uploads/                   # Uploaded documents
│   └── vector_db/                 # FAISS index
├── models/                        # ONNX model files (add your own)
├── scripts/
│   ├── create_demo_data.py        # Load demo content
│   └── start.py                   # Startup helper
├── tests/                         # Pytest test suite (79 tests)
├── requirements.txt
├── .env.example
└── README.md
```

---

## License

MIT License. Original code created for the Snapdragon® AI Lab Build & Present Challenge.

Sample study material (demo_study_material.txt) is original content created for this project.
