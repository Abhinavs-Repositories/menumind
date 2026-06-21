
# 🍽️ MenuMind

**Chat with any restaurant menu.** Upload a menu PDF or photo, and MenuMind turns
it into a searchable knowledge base you can ask natural questions of — *"How much
is the butter chicken?"*, *"What vegan options are there?"*, *"When's breakfast
served?"* — and get grounded, streamed answers with the source pages cited.

A full-stack, free-tier RAG application: a **Gemini-vision menu parser**, a
**retrieval pipeline** (Gemini embeddings → Qdrant → Groq generation), a
**streaming FastAPI backend**, an **Expo / React Native app** (iOS · Android ·
web), and a **retrieval evaluation suite** that keeps the whole thing honest.

```
┌──────────────────────┐         ┌───────────────────────────────┐        ┌──────────────────┐
│  Expo app (mobile/)  │         │       FastAPI  (api/)         │        │   Cloud services │
│  iOS · Android · web │         │                               │        │  (free tiers)    │
│                      │  GET /menus ───────────────▶ list ─────┼──────▶ │  Qdrant  vectors │
│  • pick a menu       │         │                               │        │  Gemini  embeds  │
│  • ask a question    │  POST /chat ──────────────────────────┼──────▶ │  Groq    LLM     │
│  • upload a menu     │  ◀═══════ SSE: sources, tokens…, done ═┤        │                  │
│                      │  POST /ingest ── parse+embed+upsert ───┼──────▶ │  Gemini  vision  │
└──────────────────────┘         └───────────────────────────────┘        └──────────────────┘
```

---

## How it works

MenuMind is two flows over one vector store.

**1. Ingestion — a menu becomes searchable**

```
PDF / image ─▶ Gemini Flash vision ─▶ Markdown + structured JSON ─▶ chunks
            ─▶ Gemini embeddings (768-d) ─▶ Qdrant upsert (tagged by restaurant)
```

Menus are messy — multi-column layouts, dot-leader pricing, no table borders. The
[menu_parser/](menu_parser/) uses **Gemini 2.5 Flash vision**, parsing
**page-by-page** with a strict schema so each item stays bound to its price and a
single dense page can't blow up the response. Output is split into element-level
chunks ([chunker.py](chunker.py)), embedded with
**`gemini-embedding-001`** ([embedder.py](embedder.py)), and upserted into
**Qdrant** with a `restaurant` payload field ([ingestor.py](ingestor.py)).

**2. Retrieval — a question becomes an answer**

```
question ─▶ embed query ─▶ Qdrant search (filtered by restaurant)
         ─▶ build context ─▶ Groq LLM (streamed) ─▶ answer + cited source pages
```

[rag.py](rag.py) embeds the query, retrieves the top matching chunks scoped to the
selected restaurant, builds a context window, and streams an answer from
**Groq (`llama-3.3-70b-versatile`)** with a strict "answer only from the context"
system prompt. The API surfaces this as Server-Sent Events so the app renders
tokens as they arrive.

### Stack

| Layer            | Tech                                                    | Tier  |
|------------------|--------------------------------------------------------|-------|
| Mobile / web app | Expo SDK 56, React Native 0.85, Expo Router, TypeScript | free  |
| Backend API      | FastAPI + Uvicorn, Server-Sent Events                  | free  |
| Menu parsing     | Google Gemini 2.5 Flash (vision)                       | free  |
| Embeddings       | Google `gemini-embedding-001` (768-d)                  | free  |
| Vector store     | Qdrant Cloud (cosine)                                  | free  |
| LLM generation   | Groq `llama-3.3-70b-versatile` (streamed)             | free  |
| Backend hosting  | Hugging Face Spaces (Docker)                           | free  |

Every dependency runs on a free tier — the only paid step is optional native
app-store publishing.

---

## Repository layout

```
menumind/
├── api/                FastAPI app (main.py) + its requirements.txt
├── mobile/             Expo / React Native app (see mobile/README.md)
├── menu_parser/        Gemini-vision PDF/image → Markdown + JSON parser
├── evals/              Retrieval + answer-quality evaluation suite
├── scripts/            deploy_hf.py, reingest_all.py, compare_outputs.py, generate_icons.py
├── menu_inputs/        Sample menu PDFs
│
├── parser.py           Orchestrates a parse run → writes markdown + json
├── chunker.py          Splits parsed menus into element-level chunks
├── embedder.py         Gemini embeddings (with rate-limit backoff)
├── ingestor.py         Qdrant collection management + upsert
├── ingest_service.py   In-memory parse→embed→upsert for uploads (/ingest)
├── rag.py              The retrieval + generation engine (MenuRAG)
├── config.py           Pydantic settings, loaded from .env
├── cli.py              Run any pipeline stage from the terminal
├── Dockerfile          Backend image for Hugging Face Spaces (port 7860)
└── README.md           ← you are here (also the HF Space landing page)
```

---

## Quick start (local)

**Prerequisites:** Python 3.11+, Node 20+, and free API keys for
[Google AI Studio](https://aistudio.google.com/apikey),
[Qdrant Cloud](https://cloud.qdrant.io), and [Groq](https://console.groq.com).

### 1. Backend

```bash
# from the repo root
python -m venv venv && source venv/Scripts/activate   # Windows Git Bash; use bin/activate on macOS/Linux
pip install -r api/requirements.txt

cp .env.example .env        # then fill in the keys below
uvicorn api.main:app --reload --port 8000
```

Smoke-test it:

```bash
curl localhost:8000/menus
curl -N -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"question":"What desserts are there?","restaurant":"Taj"}'
```

### 2. Mobile app

```bash
cd mobile
npm install
EXPO_PUBLIC_API_URL=http://localhost:8000 npx expo start
```

Press `w` for web, `i` / `a` for a simulator, or scan the QR code with **Expo Go**.
Point `EXPO_PUBLIC_API_URL` at your deployed Space to use the cloud backend. See
[mobile/README.md](mobile/README.md) for more.

### 3. Add a menu

Either upload one from the app's **Add menu** screen (it calls `POST /ingest`), or
ingest from the CLI:

```bash
python cli.py pipeline menu_inputs/PunjabGrill.pdf --restaurant "Punjab Grill"
# parse → chunk → embed → ingest, in one command
```

---

## Backend API

| Method | Route               | Description                                                        |
|--------|---------------------|-------------------------------------------------------------------|
| GET    | `/health`           | Liveness check                                                     |
| GET    | `/menus`            | Distinct restaurant names available to chat with                  |
| POST   | `/chat`             | `{question, restaurant, history?}` → **SSE** (`sources`, `token`…, `done`) |
| POST   | `/ingest`           | Upload a menu (`file`, `restaurant`) → background parse/embed/ingest job |
| GET    | `/ingest/{job_id}`  | Poll an ingest job's status                                        |

`POST /ingest` can be protected with an `INGEST_API_KEY` secret (sent as the
`X-Ingest-Key` header); if unset, it's open for local dev.

---

## Evaluation suite

Retrieval quality is measured, not assumed. [evals/](evals/) runs the **live**
pipeline against a gold question set and reports where things stand.

- **Metrics:** Hit@k, MRR, nDCG@k, context-recall, rerank lift, latency, plus an
  **LLM-as-judge** for answer faithfulness / relevance / correctness.
- **Gold sets:** a hand-verified curated set + an auto-generated synthetic set
  (questions tied back to their source chunk).
- **Relevance** is judged by whether the answer facts actually appear in a
  retrieved chunk — robust to re-ingestion / chunk-id drift.

```bash
python -m evals.generate_synthetic        # build the synthetic gold set from live chunks
python -m evals.run_eval                   # retrieval + generation + judge
python -m evals.run_eval --no-generate     # retrieval-only (fast, cheapest)
```

Each run writes a timestamped `evals/results/<ts>/` with `report.md`,
`summary.json`, and per-query `results.jsonl`. Current baseline: the relevant
chunk lands in the top-5 essentially every time (**Hit@5 ≈ 100%, MRR ≈ 0.95**).
See [evals/README.md](evals/README.md) for the full methodology.

---

## Deploy the backend (Hugging Face Spaces, free)

The repo doubles as a Docker Space — the YAML front matter at the top of this file
and the [Dockerfile](Dockerfile) drive the build (listens on port `7860`).

**Scripted (recommended):**

```bash
huggingface-cli login                              # one-time: stores a WRITE token
python scripts/deploy_hf.py --space menumind-api   # pushes code + sets secrets from .env
```

The script creates/updates the Space, copies your `GOOGLE_API_KEY`, `GROQ_API_KEY`,
and `QDRANT_*` values in as repository secrets, uploads only the backend files, and
waits for the build. When it's live, your API is at
`https://<user>-<space>.hf.space`.

**Manual:** create a Docker Space, add the same secrets under *Settings → Variables
and secrets*, then `git push` this repo to the Space remote.

---

## Configuration

Copy [.env.example](.env.example) to `.env`. The backend reads these (via
[config.py](config.py)):

| Variable                 | Required | Default                      | Purpose                         |
|--------------------------|----------|------------------------------|---------------------------------|
| `GOOGLE_API_KEY`         | ✅       | —                            | Gemini embeddings + vision parse |
| `GROQ_API_KEY`           | ✅       | —                            | LLM answer generation            |
| `QDRANT_URL`             | ✅       | —                            | Qdrant Cloud cluster URL         |
| `QDRANT_API_KEY`         | ✅       | —                            | Qdrant Cloud auth                |
| `QDRANT_COLLECTION_NAME` |          | `menu_embeddings`            | Collection to read/write         |
| `INGEST_API_KEY`         |          | *(unset → open)*             | Protects `POST /ingest`          |
| `ALLOWED_ORIGINS`        |          | `*`                          | CORS allow-list for the app      |
| `GROQ_MODEL`             |          | `llama-3.3-70b-versatile`    | Generation model                 |
| `EMBEDDING_MODEL`        |          | `models/gemini-embedding-001`| Embedding model                  |
| `VISION_MODEL`           |          | `gemini-2.5-flash`           | Menu-parsing vision model        |

Retrieval tuning knobs (`RAG_TOP_K`, `RAG_TOP_K_RERANK`, `RAG_MIN_SCORE`,
`RAG_MAX_CONTEXT_CHARS`) also live in [config.py](config.py) — change them and
re-run the eval to see the effect.

> The mobile app uses a separate `EXPO_PUBLIC_API_URL` env var pointing at the
> backend. (Note: the `SUPABASE_*` / `DATABASE_URL` lines in `.env.example` are
> not used by the current backend.)

---

## CLI

Every pipeline stage is runnable standalone via [cli.py](cli.py):

```bash
python cli.py parse    menu_inputs/cafe.pdf            # PDF → markdown + json
python cli.py chunk    parse_output/raw_markdown/cafe_raw.md
python cli.py embed    chunks.json
python cli.py ingest   embeddings.json --collection my_menu
python cli.py ask      "What vegetarian dishes are there?" --restaurant "Cafe Mocha"
python cli.py pipeline menu_inputs/cafe.pdf --restaurant "Cafe Mocha"   # all of the above
```

---

## Notes & limitations

- **Free-tier rate limits** are the main operational constraint: Gemini
  `generate_content` (~20/day on the free tier), Gemini embeddings (~100/min, with
  automatic backoff), and Groq daily token budgets. Fine for personal use and
  evaluation; upgrade tiers for production load.
- Retrieval is scoped to **one restaurant at a time** (selected in the app).
- Native app-store distribution (Apple $99/yr, Google $25 one-time) is the only
  non-free piece and is deferred — Expo Go and the web build cover testing for free.

---

Built as a real, evolving product — not a throwaway demo.
