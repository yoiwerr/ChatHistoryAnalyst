# ChatHistoryAnalyst (ChatLab)

AI-powered chat history analysis engine. Three core skills:
1. **Tone Imitation** — mimic a person's speaking style and predict their next reply
2. **Emotion Analysis** — score (0-100), dominant emotion label, reasoning
3. **Atmosphere Analysis** — power dynamics, communication posture, suggestions

All skills use LangChain agents backed by a RAG system (PGVector with two stores: psychology knowledge + chat history).

## Tech Stack

| Layer | Tech |
|-------|------|
| Language | Python 3.12, managed with `uv` |
| Backend | FastAPI + Uvicorn |
| Frontend | Streamlit (pink/ivory theme) |
| LLM | Qwen via DashScope (`qwen3-max` for analysis, `qwen3-omni-flash` for OCR) |
| Agent FW | LangChain (`create_agent`) |
| Vector DB | PostgreSQL + pgvector (two collections) |
| Embeddings | DashScope `text-embedding-v3` |
| Web Search | Tavily Search |
| Observability | LangSmith |

## Quick Start

```bash
# Prerequisites: PostgreSQL with pgvector extension, Python 3.12, uv

# Install deps
uv sync

# Import psychology reference data (one-time)
python import_knowledge.py

# Terminal 1: Backend API (port 8000)
uvicorn src.main:app --reload

# Terminal 2: Frontend (port 8501)
streamlit run front/frontend.py
```

## Architecture

```
Browser (Streamlit :8501)
        │
        ▼
FastAPI (:8000) ── src/main.py
        │
        ├── src/schemas.py         Pydantic request/response models
        ├── src/core_llm.py        LLM instances (base_llm, vision_llm)
        │
        ▼
    Skill Agents (src/skills/)
        │
        ├── skill01_imitate.py     Agent: search history + psych → mimic reply
        ├── skill02_emotion.py     Agent: search history + psych → JSON emotion report
        └── skill03_atmosphere.py  Agent: search history + psych → JSON atmosphere report
        │
        ▼
    Tools (src/tools.py)
        ├── search_psychology_knowledge(query)       → knowledge_store (permanent)
        ├── search_chat_history(query, target_person) → chat_history_store (persistent)
        └── web_search(query)                        → Tavily
        │
        ▼
    PGVector (src/rag_function.py)
        ├── knowledge_store   collection="psychology_knowledge"  (from data/*.txt)
        └── chat_history_store collection="chat_history"         (from imported chats)
```

## File Map

| File | Role |
|------|------|
| `src/main.py` | FastAPI app — 8 endpoints for import, analysis, memory, knowledge mgmt |
| `src/core_llm.py` | Creates `base_llm` (qwen3-max) and `vision_llm` (qwen3-omni-flash) |
| `src/schemas.py` | Pydantic models: ChatMessage, AnalysisRequest, EmotionResponse, AtmosphereResponse |
| `src/tools.py` | Three LangChain `@tool`s available to all agents + RELEVANCE_THRESHOLD |
| `src/rag_function.py` | PGVector store management, dedup, chunking, dimension checking, import |
| `src/skills/skill01_imitate.py` | Agent: imitates tone, returns `{"reply": "..."}` |
| `src/skills/skill02_emotion.py` | Agent: structured JSON output, regex-extracted from LLM response |
| `src/skills/skill03_atmosphere.py` | Agent: same pattern, atmosphere/power-dynamics JSON |
| `front/frontend.py` | Streamlit UI: file upload, chat preview, analysis cards, emotion gauge |
| `import_knowledge.py` | One-shot script to chunk and import `data/*.txt` into knowledge_store |
| `data/*.txt` | Chinese psychology reference: attachment, communication, personality, relationships |
| `docs/rag-roadmap.md` | RAG evolution plan (HyDE, rerank, GraphRAG, etc.) |
| `pyproject.toml` | Dependencies and project metadata |
| `.env` | API keys + DB creds (gitignored, see `.env.example` for template) |
| `Dockerfile` | Single Python 3.12 image for both API and Streamlit |
| `docker-compose.yml` | Orchestrates nginx + api + streamlit + postgres (pgvector) |
| `nginx/nginx.conf` | Reverse proxy: `/` → portfolio, `/chatlab` → Streamlit, `/api` → FastAPI |
| `portfolio/index.html` | Project gallery homepage (ChatLab card + placeholder slots) |
| `scripts/deploy.sh` | One-click server deployment script |
| `TODO.md` | Server setup steps for the user to complete |

## Key Conventions

- **Agent pattern**: `create_agent(model, tools, system_prompt=...)` — all three skills follow this
- **JSON extraction**: LLM responses use `re.search(r'\{.*\}', raw, re.DOTALL)` to safely extract JSON
- **PGVector stores**: Two separate collections, dimension checked at startup (`check_dimension_mismatch()`)
- **Dedup**: Chat messages deduplicated by (content, sender, timestamp) before insert
- **Chunking**: Knowledge files chunked at 500 chars with 50-char overlap
- **Relevance threshold**: 0.3 for all tool searches

## Progress

**Phase**: [阶段一: 需求对齐] → [阶段二: 架构设计] → [阶段三: 精确执行] ← we are here → [阶段四: 脱水沉淀]

**Done:**
- Three skill agents working with RAG tools
- FastAPI backend with 8 endpoints
- Streamlit frontend with file upload, OCR, and analysis display
- PGVector dual-store RAG with psychology knowledge base
- Knowledge import pipeline (`import_knowledge.py`)
- Docker Compose deployment (nginx + api + streamlit + postgres)
- Portfolio homepage at `/`, ChatLab at `/chatlab`
- Database host configurable via `DB_HOST` env var

**In progress (uncommitted changes as of 2026-05-22):**
- `src/main.py` — API enhancements
- `src/rag_function.py` — RAG improvements
- `src/tools.py` — tool refinements
- `src/skills/*` — skill prompt tuning
- `README.md` — documentation updates
- Deployment files added (Dockerfile, docker-compose.yml, nginx, portfolio, scripts)

**Next:**
- Push to GitHub
- Deploy to server (follow `TODO.md`)
- Frontend optimization (阶段三 continued)
- Feature extensions and upgrades
- 阶段四: solidify, polish, document

---

## Session Update

### 2026-05-22
- **What I did**: Dockerized the project for deployment. Created Docker Compose stack (nginx + Streamlit + FastAPI + PostgreSQL/pgvector), portfolio homepage, deploy script.
- **What changed** (files): Added Dockerfile, docker-compose.yml, nginx/nginx.conf, portfolio/index.html, scripts/deploy.sh, .dockerignore, TODO.md. Modified src/rag_function.py (DB_HOST/DB_PORT env vars), .env.example. Updated CLAUDE.md.
- **What's next**: User to follow TODO.md for server setup and deployment. Push to GitHub first.
- **Blockers / notes**: Server firewall/安全组 must open port 80. No domain yet — using IP.
