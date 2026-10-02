# CLAUDE.md — Z-Oracle Atendee (BetAgent AI Agent)

## Project Overview

Z-Oracle Atendee is a production-grade **AI customer service agent** for the Brazilian betting platform **BetAgent** (`betagent.bet.br`). It receives messages via a **Streamlit chat interface** (GraphQL protocol), routes them semantically, applies security guardrails, and responds using an LLM + RAG pipeline. All code comments, docstrings, variable names, and prompts are in **Portuguese (Brazilian)**.

> **Note:** There is no WhatsApp integration. The current interface is Streamlit + GraphQL only.

---

## Architecture

```
Streamlit UI (frontend.py)
    │  POST /graphql (mutation enviarMensagem)
    ▼
[api/graphql_schema.py]  ← Buffer + Debounce 15s (asyncio)
    │
    ├── core/guardrail.py    (LLM-as-Judge: Gemini 1.5 Flash + PII masking)
    ├── core/router.py       (semantic routing + sentiment: all-MiniLM-L6-v2)
    ├── core/agent.py        (LLM: Gemini 2.5 Flash | RAG: LlamaIndex)
    └── infrastructure/
        ├── redis_client.py       (Upstash Redis TCP/TLS — session state)
        └── supabase_logger.py    (Supabase — analytics logs)
```

### Request Flow (GraphQL Debounce)

1. **UI sends** message → GraphQL mutation → appended to `buffer_pendente` in Redis
2. **Debounce 15s** — `asyncio.create_task()` waits; if no new messages arrive, processes
3. **Security** — `verificar_seguranca()`: LLM-as-Judge + PII masking
4. **Routing** — `classificar_rota()`: deterministic regex → vector similarity
5. **Agent** — tool injection by route; direct LLM call if no tools (avoids Gemini 400 error)
6. **Persist** — save to Upstash Redis immediately via `guardar_estado()`
7. **Log** — async insert to Supabase `logs_atendimento` table
8. **UI polls** — `obterHistorico()` query every 3s; new assistant messages streamed with typing effect

---

## Directory Structure

```
Z-Oracle Atendee/
├── api/
│   ├── main.py              # FastAPI app (endpoints: /health, /api/ingerir, mounts /graphql)
│   └── graphql_schema.py    # Strawberry GraphQL schema — main protocol (debounce 15s)
├── core/
│   ├── agent.py             # LLM agent + RAG (Gemini 2.5 Flash, lazy settings init)
│   ├── router.py            # Semantic router + sentiment (all-MiniLM-L6-v2 singleton)
│   └── guardrail.py         # Security: injection detection (Gemini 1.5 Flash) + LGPD
├── infrastructure/
│   ├── database.py          # Native PostgreSQL client (asyncpg) with pooling & pgvector
│   ├── redis_client.py      # Redis session CRUD + EstadoConversa Pydantic model
│   └── supabase_logger.py   # Unified DB Logger (PostgreSQL native with Supabase fallback)
├── frontend/                # Modern Cyberpunk / Glassmorphism Operator Console UI (Node.js)
├── tools/vectorizer/        # Knowledge Base vectorization pipeline (sentence-transformers)
├── docker/postgres/init.sql # PostgreSQL + pgvector schema and initialization
├── frontend.py              # Streamlit UI — alternative GraphQL client
├── cloudbuild.yaml          # CI/CD: Cloud Build → Cloud Run Service
├── Dockerfile               # Python 3.11-slim + pre-baked all-MiniLM-L6-v2 model
├── docker-compose.yml       # Fullstack self-hosted (API + Frontend + Redis + PostgreSQL)
├── .env.example             # Template (safe to commit)
├── .gitignore               # Excludes .env, .venv, index_cache*/, logs
└── requirements.txt         # All dependencies (synchronized with actual code)
```

---

## Key Modules

### `api/graphql_schema.py` — Main Protocol
- Strawberry GraphQL router mounted at `/graphql`
- **`mutation enviarMensagem`**: appends to `buffer_pendente`, sets `ultimo_timestamp`, fires `debounce_e_processar()` as background task
- **`query obterHistorico`**: returns `mensagens_recentes` for a given `telefone`
- **Debounce 15s**: `asyncio.sleep(15)` — processes only if `ultimo_timestamp` unchanged
- Routes: same logic as `api/main.py` webhook (COLETA_DADOS, BATE_PAPO, DUVIDA_TECNICA, TRANSACAO_FINANCEIRA, PROBLEMA, ESCALAR)

### `core/agent.py` — LLM + RAG Engine
- **LLM:** Gemini `models/gemini-2.5-flash`, `temperature=0.1`, `max_tokens=600`
- **Settings:** Lazy init via `_inicializar_settings()` — runs AFTER `load_dotenv()`, avoids `DefaultCredentialsError`
- **No-tools path:** when `tools_disponiveis=[]`, uses `Settings.llm.achat()` directly **instead of** `AgentWorkflow` — fixes Gemini 400 error "Function calling config set without function_declarations"
- **Embeddings:** HuggingFace `all-MiniLM-L6-v2` (local, no API cost)
- **RAG source:** `https://betagent.bet.br/info/BettingRules` (HTML parsed via `HTMLNodeParser`)
- **Cache:** `./index_cache_v5/` — loaded on first call, persisted to disk (not persistent in Cloud Run)
- **Tools (closures):** `tool_consultar_manual`, `tool_transferir_humano`, `tool_realizar_deposito`, `tool_realizar_saque`, `tool_efetivar_transacao_pendente`
- **Sentiment handoff:** if `perfil_sentimental == "Irritado"` for 3+ turns → proactive transfer

### `core/router.py` — Semantic Router
- **Phase 1 (deterministic):** regex for CPF (`\d{3}\.?\d{3}\.?\d{3}-?\d{2}`) and exact-match greetings
- **Phase 2 (vector ~5ms):** `all-MiniLM-L6-v2` normalized dot product
- **Routes enum `Rota`:** `BATE_PAPO`, `COLETA_DADOS`, `DUVIDA_TECNICA`, `TRANSACAO_FINANCEIRA`, `PROBLEMA`, `ESCALAR`
- **Sentiment enum `Sentimento`:** `IRRITADO`, `SATISFEITO`, `NEUTRO`
- **Singleton + Lazy Loading:** `RouterEngine` class — model loads on first message only
- Threshold: `0.45` | Fallback: `DUVIDA_TECNICA`

### `core/guardrail.py` — Security
- **LLM Judge:** Gemini `gemini-1.5-flash`, `temperature=0.0`, JSON mode, 3s timeout
- **Fast path:** messages < 15 chars bypass LLM judge
- **Fail-open:** API timeout → message allowed through (legitimate user not penalized)
- **PII masking:** CPF → `***.X.X-**` | credit cards → `**** **** **** XXXX`

### `infrastructure/redis_client.py` — Session State
- **Connection:** `redis.ConnectionPool.from_url(REDIS_URL)` with TLS auto-detect for `rediss://`
- **Upstash (prod):** `rediss://default:PASS@HOST.upstash.io:6379`
- **Dev fallback:** `redis://localhost:6379/0`
- **In-memory fallback:** `_in_memory_db` dict if Redis unavailable (NOT production-safe)
- **`EstadoConversa` (Pydantic v2):** `session_id`, `cpf`, `etapa`, `perfil_sentimental`, `dados_transacao_pendente`, `mensagens_recentes[3]`, `resumo_acumulado`, `buffer_pendente`, `ultimo_timestamp`
- **CPF validation:** `validate_docbr.CPF().validate()` — mathematical check
- **Rolling memory:** `precisa_sumarizar()` → `executar_sumarizacao_llm()` → Gemini 1.5 Flash → 3 sentences

### `infrastructure/supabase_logger.py` — Analytics
- **Client:** lazy init via `create_client(SUPABASE_URL, SUPABASE_ANON_KEY)`
- **Table:** `logs_atendimento` (telefone, rota, input, resposta, tools[])
- **Graceful fallback:** any exception → log to console, never blocks main flow

### `frontend.py` — Streamlit UI
- Generates session ID: `+55119{uuid_hex[:7]}`
- **State management:** `historico_confirmado` (backend source of truth) + `msgs_locais_pendentes` (optimistic local, cleared when assistant replies)
- **Polling:** `streamlit_autorefresh` every 3s (or manual `st.rerun()` fallback)
- **Stream:** `write_stream(stream_resposta())` — humanized word-by-word typing effect
- **Sidebar:** inject text into RAG via `/api/ingerir`

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | **Yes** | Google AI Studio key — LLM, guardrail, summarizer |
| `REDIS_URL` | **Yes** | Upstash: `rediss://default:PASS@HOST.upstash.io:6379` |
| `SUPABASE_URL` | No | Supabase project URL |
| `SUPABASE_ANON_KEY` | No | Supabase anon key |

---

## Running the Project

### Local Development
```bash
pip install -r requirements.txt
# Edit .env with real keys
.1Testes\iniciar_servidor.bat   # Windows — starts Docker Redis + FastAPI + Streamlit
# OR manually:
uvicorn api.main:app --reload --port 8000
streamlit run frontend.py
```

### Production (Cloud Run)
```bash
# Secrets must exist in GCP Secret Manager first
gcloud builds submit --config cloudbuild.yaml
```

---

## Code Conventions

- **Language:** All comments, docstrings, variable names, log messages in **Portuguese (Brazilian)**
- **Typing:** Full type hints on all function signatures
- **Logging:** `logging.getLogger("betagent_{module}")` per module
- **Error handling:** Never bare `except: pass`; always log with `exc_info=True` for critical paths
- **Pydantic v2:** Use `model_dump_json()` and `model_validate_json()` (not v1 API)
- **Singletons:** Module-level `_variable = None` + lazy init function pattern
- **No-tools LLM:** Call `Settings.llm.achat()` directly when `tools_disponiveis=[]`
- **Background tasks:** Use `asyncio.create_task()` in GraphQL; FastAPI `BackgroundTasks` in REST endpoints

---

## Known Limitations

- **`asyncio.create_task()` debounce** may be killed on Cloud Run scale-to-zero → future: Cloud Tasks
- **`index_cache_v5/`** not persistent in Cloud Run → RAG reindexed on cold start
- **`/api/ingerir`** has no authentication — admin-only by network policy intent
- **No tests** — no `tests/` directory configured
- **`FutureWarning`** from `google.generativeai` — deprecated, migrate to `google.genai` when convenient
- **In-memory fallback** in `redis_client.py` is NOT safe for multi-instance production deployments

---

## GCP Deploy Checklist

```bash
# 1. Create Artifact Registry repo
gcloud artifacts repositories create zoracle-artifacts \
  --repository-format=docker --location=us-central1

# 2. Create secrets in Secret Manager
gcloud secrets create GEMINI_API_KEY --data-file=-  <<< "your_key"
gcloud secrets create REDIS_URL --data-file=-       <<< "rediss://..."
gcloud secrets create SUPABASE_URL --data-file=-    <<< "https://..."
gcloud secrets create SUPABASE_ANON_KEY --data-file=- <<< "eyJ..."

# 3. Create Supabase table
-- In Supabase SQL Editor:
create table logs_atendimento (
  id uuid default gen_random_uuid() primary key,
  created_at timestamptz default now(),
  telefone text, rota text, input text, resposta text, tools text[]
);

# 4. Deploy
gcloud builds submit --config cloudbuild.yaml
```
