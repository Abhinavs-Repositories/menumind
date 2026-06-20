---
title: MenuMind API
emoji: 🍽️
colorFrom: red
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# MenuMind

Chat with restaurant menus. A RAG pipeline (Gemini embeddings → Qdrant retrieval
→ Groq generation) behind a streaming FastAPI backend and an Expo mobile app.

```
Expo app (mobile/)  ──GET /menus──▶  FastAPI (api/)  ──▶  Qdrant (vectors)
                    ──POST /chat──▶                  ──▶  Gemini (embeddings)
                    ◀═══ SSE stream ═══               ──▶  Groq  (LLM, streamed)
```

All services run on free tiers: Google AI Studio (Gemini), Qdrant Cloud, Groq,
and Hugging Face Spaces (this backend).

## Backend API

| Method | Route     | Description                                            |
|--------|-----------|--------------------------------------------------------|
| GET    | `/health` | Liveness check                                         |
| GET    | `/menus`  | Distinct restaurant names available to chat with       |
| POST   | `/chat`   | `{question, restaurant}` → SSE stream (`sources`, `token`…, `done`) |

### Run locally

```bash
# from the repo root, with .env populated (see .env.example)
pip install -r api/requirements.txt
uvicorn api.main:app --reload --port 8000
curl -N -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"question":"What desserts are there?","restaurant":"Taj"}'
```

### Ingesting menus

```bash
python scripts/reingest_all.py          # re-embed parsed menus, tagged by restaurant
```

## Deploy the backend to Hugging Face Spaces (free)

1. Create a new **Space** → SDK **Docker** → blank.
2. In **Settings → Variables and secrets**, add these *secrets*:
   `GOOGLE_API_KEY`, `GROQ_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`,
   `QDRANT_COLLECTION_NAME` (and optionally `ALLOWED_ORIGINS`).
3. Push this repo to the Space's git remote (the `Dockerfile` and this README's
   front matter drive the build; `app_port: 7860`):
   ```bash
   git remote add space https://huggingface.co/spaces/<user>/<space-name>
   git push space mobile-app:main
   ```
4. Wait for the build, then verify: `curl https://<user>-<space-name>.hf.space/menus`

## Mobile app

See [mobile/](mobile/). Set `EXPO_PUBLIC_API_URL` to the backend URL, then:

```bash
cd mobile
EXPO_PUBLIC_API_URL=https://<user>-<space-name>.hf.space npx expo start
```
