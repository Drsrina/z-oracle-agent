<div align="center">

# Z-Oracle Atendee
### Cognitive Customer Support Agent with AI, Semantic Routing & Anti-Hallucination Shielding

[![Language: English](https://img.shields.io/badge/Language-English-blue?style=for-the-badge)](README.en.md)
[![Language: Português](https://img.shields.io/badge/Language-Português-green?style=for-the-badge)](README.md)

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-5.0-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LlamaIndex](https://img.shields.io/badge/LlamaIndex-RAG-7C3AED?style=for-the-badge)](https://www.llamaindex.ai)
[![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)
[![Redis](https://img.shields.io/badge/Redis-7.0-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Docker](https://img.shields.io/badge/Docker-Self--Hosted-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com)
[![License: BSL 1.1](https://img.shields.io/badge/License-BSL_1.1-blueviolet?style=for-the-badge)](LICENSE)

> **Production-grade conversational agent** designed for high-scale, mission-critical customer operations (serving the **BetAgent** platform).
> Equipped with the **Z-Oracle Operations Console** (sober enterprise web console with real-time decision inspection),
> it enforces multi-layer security guardrails, local CPU-only vector semantic routing, and deterministic anti-hallucination shielding via **Tool Scoping**.

</div>

---

## 💡 Humanized Introduction: Why Does Z-Oracle Exist?

Anyone who has ever needed urgent customer support in a fintech, sports betting platform, or high-volume e-commerce service knows the classic frustration: you send quick, fragmented messages on chat or WhatsApp explaining that a transaction didn't go through, and you are greeted by a rigid, robotic decision tree that completely ignores context — or even worse, a naive AI chatbot that hallucinates non-existent rules, promises unrealistic deadlines, and "forgets" what you said two seconds ago.

In high-volume digital platforms, **user trust is the most fragile and valuable asset**. When a customer contacts support regarding a financial or account issue, they bring genuine urgency and anxiety. In that moment:
* Cold or confusing answers trigger immediate churn and account cancellations;
* Hallucinated business rules (such as wrong withdrawal timeframes or unauthorized balance releases) create severe legal liabilities and regulatory penalties;
* Slow chatbots that take dozens of seconds to answer break conversation flow and overload human teams with duplicated tickets.

### The Fallacy of "Naive AI Chatbots"
With the explosion of Large Language Models (LLMs), many companies rushed to plug raw prompt templates directly into cloud APIs. This superficial approach creates catastrophic failures in production:
1. **The "Split-Brain" Problem:** Providing dozens of tools simultaneously to an LLM causes it to invoke withdrawal APIs or search full knowledge manuals just to reply to a simple *"Good morning!"*.
2. **Exponential Cost and Latency:** Every fragmented mobile chat message triggers a heavy cloud inference, burning hundreds of thousands of tokens unnecessarily and generating exorbitant API bills.
3. **Prompt Injection Vulnerabilities:** Malicious actors easily coax unshielded bots into ignoring system guidelines and leaking confidential policies.

---

## 🎯 Central Objective of Z-Oracle

**Z-Oracle Atendee** was not designed to be merely another text generator. Its mission is to **act as the most disciplined, empathetic, and reliable Tier-1 Customer Success operator possible**.

The system is built on three core pillars:

1. **Active Empathy with Investigative Rigor:** It actively listens to the user, waits for them to complete their thought (grouping rapid message bursts inside an intelligent 15-second debounce buffer), and only issues resolutions after asking targeted clarifying questions (2-step protocol), treating the user's issue with genuine diligence and respect.
2. **Absolute Anti-Hallucination Shielding:** The agent is strictly forbidden from guessing business rules. If information is not proven within the vector knowledge base (RAG) or validated by an authorized tool, it transparently states its boundaries and triggers an escalation to human staff.
3. **High Efficiency & Local Computing Sovereignty:** Employs deterministic C/NumPy-compiled calculations running 100% on-premise within the container for semantic triage and sentiment classification in **~6 milliseconds**. Cloud-based generative LLMs are only invoked when cognitive reasoning is genuinely required, reducing token consumption by over 65% and sanitizing sensitive personal data (LGPD/GDPR) before any external network transit.

---

## 📚 In-Depth Technical Documentation (For Recruiters & Engineers)

For engineering leaders, system architects, and **technical recruiters**, this repository provides a comprehensive suite of architectural whitepapers and specifications in the [`docs/`](./docs/README.md) directory:

| Document | Topic & Focus | Why Review It? |
| :--- | :--- | :--- |
| 📊 **[docs/benchmark-recursos.md](./docs/benchmark-recursos.md)** | **Hardware Footprint & Sizing** | Empirical measurements and capacity modeling of RAM/CPU across 3 operational scenarios (Standby 367MB, Normal Load 522MB, Burst Peak 958MB) and hosting costs (< $5/mo). |
| 🏛️ **[docs/arquitetura.md](./docs/arquitetura.md)** | **Software Architecture & Resilience** | Details async orchestration, Redis 15-second distributed debounce buffer, webhook isolation, and full technology matrix. |
| ⚡ **[docs/roteadorsemantico.md](./docs/roteadorsemantico.md)** | **Benchmark & 100% Local Inference** | Empirical proof of CPU-only embedding execution (`all-MiniLM-L6-v2` + NumPy dot product) with **6.35 ms** latency and **zero external API dependencies**. |
| 🧠 **[docs/governanca-cognitiva.md](./docs/governanca-cognitiva.md)** | **Cognitive Governance & Minto BLUF** | Full v4 specification: Cynefin domains, hidden telemetry verdict, continuous reflection, and direct BLUF responses. |
| 🛡️ **[docs/diretrizes.md](./docs/diretrizes.md)** | **Conversational Governance & Compliance** | Agent behavioral manual: 2-step investigative protocol, anti-drift anchor, LGPD/GDPR mathematical data masking, and FCR/CSAT target metrics. |
| 🔮 **[docs/pesquisa.md](./docs/pesquisa.md)** | **Epistemologia & Resolution Oracle** | In-depth exploration of transition from probabilistic inference to First Principles reasoning, Cynefin complexity matrix, TRIZ-GPT, GraphRAG, and multi-agent coordination. |
| 🧭 **[docs/README.md](./docs/README.md)** | **Documentation Hub** | Executive index, reader personas, and technical interview cheat sheet. |

---

## Architectural Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Z-Oracle — End-to-End Pipeline                       │
└─────────────────────────────────────────────────────────────────────────────┘

  Client Interfaces:
  [A] Z-Oracle Operator Console (Enterprise Web - Node.js/Express :3000)
  [B] Streamlit Client (Pure Python :8501)
         │
         │  POST /graphql  mutation enviarMensagem
         ▼
  ┌──────────────────┐
  │  api/graphql     │  ◄── GraphQL Protocol (Strawberry)
  │  schema.py       │       15-Second Intelligent Debounce Buffer
  └────────┬─────────┘
           │  asyncio.create_task → debounce_e_processar()
           ▼
  ┌──────────────────────────────────────────────────────────┐
  │   Cognitive Processing Pipeline                          │
  ├──────────────────────────────────────────────────────────┤
  │  [STEP 1]   infrastructure/redis_client.py               │
  │             obter_estado(sessionId)  →  EstadoConversa   │
  │             TTL 24h | Local Redis / Upstash              │
  │                                                          │
  │  [STEP 2]   core/guardrail.py                            │
  │             avaliar_injecao_prompt()  →  LLM-as-a-Judge  │
  │             sanitizar_pii()           →  LGPD/GDPR       │
  │             Model: gemini-1.5-flash (3s timeout)         │
  │                                                          │
  │  [STEP 3]   core/router.py                               │
  │             PHASE 1: Regex → Tax IDs / Greetings (0 cost)│
  │             PHASE 2: SentenceTransformer → Dot Product   │
  │             Model: all-MiniLM-L6-v2 | Threshold: 0.45    │
  │             Sentiment Classification + Cynefin Matrix    │
  │                                                          │
  │  [STEP 4]   core/agent.py                                │
  │             Tool Scoping: Strict injection per route     │
  │             Direct LLM call if no tools (avoids 400s)    │
  │             LLM: gemini-2.5-flash | RAG pgvector: top_k=3│
  │                                                          │
  │  [STEP 5]   infrastructure/redis_client.py               │
  │             guardar_estado() → Local Redis / Upstash     │
  │                                                          │
  │  [STEP 6]   infrastructure/database.py                   │
  │             registar_log_assincrono() → PostgreSQL       │
  └──────────────────────────────────────────────────────────┘
           │
           ▼  Query obterHistorico() / Polling
  ┌──────────────────────────────────────────────┐
  │  Z-Oracle Console (:3000) / Streamlit (:8501)│  ◄── Polling GraphQL + Metadata Inspector
  └──────────────────────────────────────────────┘
```

---

## 🧠 Semantic Triage & Anti-Hallucination Shielding (Deep Dive)

### The Problem: "Split-Brain" and Hallucinations from Tool Overload
In conventional agent frameworks, every tool (RAG search, balance inquiries, deposit/withdrawal APIs, account closures) is continuously exposed to the LLM on every turn. This leads to critical failures:
1. **Tool Overfitting / Function Hallucination**: Upon receiving a simple *"Hello, good morning"*, the model attempts to invoke database queries or searches the knowledge manual for the keyword *"morning"*.
2. **Excessive Latency & Token Waste**: Parsing schemas for dozens of tools increases prompt tokens and inference latency by 3x to 5x.
3. **Accidental Financial Execution**: The LLM may trigger a state mutation before the user has unambiguously confirmed their intent.

### The Solution: 2-Phase Cascading Architecture

The [`core/router.py`](file:///c:/Users/Drysrina/Desktop/Code/Z-Oracle%20Atendee/core/router.py) module intercepts incoming requests **before** the main LLM and executes an ultra-fast classification cascade:

```
Incoming User Message
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ PHASE 1: Deterministic Routing (0ms, Zero Cost)        │
│ ├─ Tax ID (CPF) detected? (\d{11}) ──► DATA_COLLECTION │
│ └─ Exact greeting? ("hi", "oi", ..)──► CASUAL_CHAT     │
└──────────────────────────┬─────────────────────────────┘
                           │ No match
                           ▼
┌────────────────────────────────────────────────────────┐
│ PHASE 2: C-Compiled Vector Routing (~5ms)              │
│ Model: all-MiniLM-L6-v2 (384-dimensional Embeddings)   │
│ Math: NumPy Dot Product (normalized unit vectors)      │
│                                                        │
│ ┌──────────────────────┬─────────────────────────────┐ │
│ │ Route                │ Authorized Injected Tools   │ │
│ ├──────────────────────┼─────────────────────────────┤ │
│ │ CASUAL_CHAT          │ None (Direct LLM response)  │ │
│ │ TECHNICAL_QUESTION   │ search_knowledge (RAG)      │ │
│ │ FINANCIAL_TRANSACTION│ manual, deposit, withdrawal │ │
│ │ ESCALATION / ISSUE   │ transfer_to_human           │ │
│ └──────────────────────┴─────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

### Tool Scoping: Dynamic Tool Firewall
The cognitive agent is strictly barred from accessing tools outside the scope defined by the router:
- On **`BATE_PAPO` (Casual Chat)**, the LLM is invoked with `ferramentas_permitidas=[]`. With no function declarations registered, it is **mathematically impossible** for the model to hallucinate a financial operation or technical search.
- On **`DUVIDA_TECNICA` (Technical Query)**, the LLM is bounded to Grounding via RAG queries against verified documentation.
- On **`COLETA_DADOS` (Data Collection)**, the message bypasses the LLM entirely: it is validated mathematically via algorithmic checksums and saved to the session state, incurring zero inference cost.

### Vector Sentiment & The Cynefin Framework
Instead of brittle keyword blocklists, the router projects messages into an emotional vector space to identify **subtle sarcasm, veiled aggression, or acute distress**:
- **Cynefin CLEAR** (casual chat / simple FAQ): Minimum synthetic confidence threshold of **60%**.
- **Cynefin COMPLICATED** (rule verification, financial transactions): Minimum threshold of **75%**.
- **Cynefin COMPLEX / CHAOTIC** (3+ failed resolution attempts or high irritation): Autonomous handling is suspended and an immediate **Human Handoff** is initiated.

### ⚡ 100% Local, Offline Execution (~6ms Benchmark)
Unlike architectures that rely on external API roundtrips for classification, Z-Oracle's Semantic Router executes **entirely on local CPU**:
1. **Pre-baked into Docker Layers**: The `all-MiniLM-L6-v2` model (~90 MB) is downloaded during container build. Zero cold-start download delays.
2. **CPU-Only PyTorch Inference**: Highly optimized matrix math runs directly on CPU threads.
3. **RAM-Cached Embeddings**: Route vectors are pre-computed at application startup. Matching runs as a single **NumPy matrix multiplication** measured at **~6.3 ms**.
4. **Zero Dependency**: Triage and firewall functions operate continuously even under network partition; external LLM calls occur only when explicitly warranted.

---

## ⚡ 15-Second Intelligent Debounce & Message Buffer

Real-world messaging users (WhatsApp, Telegram, live webchat) do not write single, structured essays. They typically send rapid, fragmented bursts:
```text
User: "hey" (00:01)
User: "i made a pix deposit" (00:03)
User: "and it hasn't credited my account" (00:07)
```
Naive bots treat this as three independent incoming requests, spawning concurrent LLM calls that yield conflicting answers and 3x cost.

Z-Oracle solves this via an **Asynchronous 15-second Debounce Buffer**:
1. Every message sent via the GraphQL mutation `enviarMensagem` is pushed into the session's `buffer_pendente` in Redis.
2. A background task (`asyncio.create_task`) schedules execution 15 seconds into the future.
3. If a new message arrives before expiration, the execution window is renewed.
4. When typing ceases, all messages are **concatenated into a unified contextual prompt**, allowing the LLM to understand the complete issue in one coherent pass.

---

## 📊 Operational Resource Benchmark (RAM, CPU & Latency)

Z-Oracle Atendee was engineered for high efficiency with minimal hardware overhead. The table below outlines empirical measurements taken directly from the Docker container environment alongside mathematical modeling under peak stress:

| Metric / Component | 🟢 Scenario 1: Standby (Idle) | 🟡 Scenario 2: Typical Load (10 req/s) | 🔴 Scenario 3: Peak / Burst Stress (80-100 req/s) |
| :--- | :--- | :--- | :--- |
| **Incoming Traffic** | 0 msgs/s (Standby 24/7) | ~10 msgs/s (~600 msgs/min) | 80 to 100 msgs/s (~5,400 msgs/min) |
| **Debounce Effect (15s)** | N/A (Zero buffer) | 150 msgs grouped into ~10 turns | 1,300 msgs grouped into ~75 turns |
| **Backend API (RAM)** | **~313 MiB** | **~410 MiB** | **~680 MiB** |
| **Backend API (CPU)** | **~0.4% - 0.8% of 1 vCPU** | **~18% - 28% of 1 vCPU** | **~140% - 180% (1.4 to 1.8 vCPUs)** |
| **Redis 7 Alpine (RAM)** | **~6.6 MiB** | **~15 MiB** | **~48 MiB** |
| **Redis 7 Alpine (CPU)** | **~0.5% of 1 vCPU** | **~2% of 1 vCPU** | **~10% - 14% of 1 vCPU** |
| **PostgreSQL 16 (RAM)** | **~30.4 MiB** | **~75 MiB** | **~195 MiB** |
| **PostgreSQL 16 (CPU)** | **~0.0% of 1 vCPU** | **~5% of 1 vCPU** | **~35% - 50% of 1 vCPU** |
| **Frontend Node (RAM/CPU)** | **~17 MiB** / 0.0% | **~22 MiB** / 1.0% | **~35 MiB** / 4.0% |
| **TOTAL UNIFIED STACK** | **~367 MiB RAM \| ~1% CPU** | **~522 MiB RAM \| ~25-35% CPU** | **~958 MiB RAM \| ~1.9-2.4 vCPUs** |

> 📖 **Full Engineering Report:** For sizing mathematical models, SIMD contention analysis, and cloud sizing specifications (AWS/GCP/Hetzner), see the comprehensive whitepaper in **[`docs/benchmark-recursos.md`](./docs/benchmark-recursos.md)**.

---

## Project Structure

```
Z-Oracle Atendee/
│
├── api/
│   ├── main.py                 # FastAPI — Async gateway (/health, /api/ingerir, /graphql)
│   └── graphql_schema.py       # Strawberry GraphQL — 15s debounce buffer & mutations
│
├── core/
│   ├── agent.py                # LLM & RAG Engine (Gemini 2.5 Flash, Route Tool Scoping)
│   ├── router.py               # C-Compiled Semantic Router + Vector Sentiment + Cynefin
│   ├── guardrail.py            # Security: LLM-as-a-Judge (Prompt Injection) + PII Sanitization
│   └── clarificador.py         # Entity extraction (tax IDs, names) and anti-drift anchor
│
├── docker/
│   └── postgres/init.sql       # PostgreSQL + pgvector schema, procedures & schema_migrations
│
├── docs/                       # Technical Documentation & Whitepapers Hub
│   ├── benchmark-recursos.md   # Hardware consumption & capacity sizing across 3 scenarios
│   ├── arquitetura.md          # Comprehensive architectural and resilience whitepaper
│   ├── roteadorsemantico.md    # Local vector inference benchmark (6.35 ms)
│   ├── governanca-cognitiva.md # v4 cognitive specification (Cynefin, Minto BLUF & Telemetry)
│   ├── diretrizes.md           # Conversational rules of engagement, 2-step gate & LGPD/GDPR
│   └── pesquisa.md             # Cognitive thesis (First Principles, TRIZ & GraphRAG)
│
├── frontend/                   # Z-Oracle Operator Console (Enterprise Web - Node.js/Express)
│   ├── index.html              # Clean enterprise console UI with decision metrics & inspector
│   ├── style.css               # Corporate design system, Inter/JetBrains Mono typography
│   ├── index.js                # Express server with reverse-proxy (anti-CORS)
│   └── Dockerfile              # Lightweight Node 18 Alpine image
│
├── infrastructure/
│   ├── database.py             # Native asyncpg PostgreSQL pool with vector similarity
│   ├── redis_client.py         # Redis session persistence + Pydantic v2 EstadoConversa
│   └── supabase_logger.py      # Unified analytics logger (PostgreSQL with cloud fallback)
│
├── tests/
│   └── test_rag.py             # Grounding and RAG retrieval verification test suite
│
├── tools/
│   └── vectorizer/             # Offline knowledge base processing & embedding pipeline
│
├── frontend.py                 # Alternative Streamlit client with word-by-word streaming
├── cloudbuild.yaml             # CI/CD: Cloud Build → Artifact Registry → Cloud Run
├── Dockerfile                  # Python 3.11-slim with pre-baked all-MiniLM-L6-v2 model
├── docker-compose.yml          # Self-hosted fullstack stack (API + Frontend + Redis + PostgreSQL)
├── .env.example                # Environment variable configuration template
└── requirements.txt            # Synchronized production Python dependencies
```

---

## 🛡️ Multi-Layer Security & Guardrails (LGPD/GDPR + LLM-as-a-Judge)

Active defenses against social engineering, jailbreaks, and data exfiltration:

1. **Layer 1 — Deterministic PII Sanitization (LGPD / GDPR)**:
   - Pre-compiled regular expressions detect tax IDs (CPFs) and credit card numbers.
   - Information is masked (`***1234`) **prior** to being committed to analytical logs or transmitted to cloud LLM providers.
2. **Layer 2 — Active Prompt Injection Firewall (LLM-as-a-Judge)**:
   - An ultra-fast model (`gemini-1.5-flash`) acts as an isolated security adjudicator with hardened system prompts.
   - Detects jailbreak attempts, "ignore previous instructions" exploits, and system prompt leakage.
   - **Strict 3-second timeout with Fail-Open policy**: If the security evaluator times out, legitimate user conversations are never stalled.

---

## 💾 Memory Management: Sliding Window & Rolling Summary

In extended dialogues, re-sending full conversation histories leads to context exhaustion and quadratic token costs.

Z-Oracle implements a hybrid memory architecture:
- **Immediate Sliding Window**: The **last 3 message pairs** are preserved verbatim to maintain conversational rhythm.
- **Background Rolling Summary**: When history exceeds operational thresholds, an async threadpool task compresses earlier exchanges into a concise, structured state summary stored in Redis.
- **Zero Latency Penalty**: Context summarization occurs in background threads without adding a single millisecond to the user's response time.

---

## Conversational State Model (`EstadoConversa`)

```
┌──────────────────────────────────────────────────────┐
│  EstadoConversa  (Pydantic v2 BaseModel)             │
├──────────────────────────────────────────────────────┤
│  session_id              str   → Generated UI session│
│  cpf                     str?  → Validated Tax ID    │
│  etapa                   str   → Finite State Machine│
│  tentativas_resolucao    int   → Resolution attempts │
│  perfil_sentimental      str   → Neutral/Upset/...   │
│  dados_transacao_pendente dict → Staged transactions │
│  resumo_acumulado        str   → Compressed summary  │
│  mensagens_recentes      List[3] → Sliding window    │
│  buffer_pendente         List  → Debounce buffer     │
│  ultimo_timestamp        float → Debounce timestamp  │
└──────────────────────────────────────────────────────┘

  Finite State Machine:
  INICIO ──► TRIAGEM ──► COLETA ──► RESOLUCAO ──► ENCERRADO
                                  └──► AGUARDANDO_CONFIRMACAO

  Redis Key:   betagent:session:{session_id}
  TTL:         86400s (24 hours)
  Hosting:     Redis 7 Local (Docker Compose) / Upstash TCP (Cloud)
```

---

## API Reference

### `GET /health`
```json
{ "status": "online", "timestamp": 1735000000.0 }
```

### `POST /api/ingerir` *(Admin / Internal)*
```json
{ "texto_conhecimento": "Policy update: withdrawals above $5,000 require facial verification..." }
```
> Ingests and vectorizes knowledge into memory/database dynamically.

### `POST /graphql` — Core Message Mutation
```graphql
mutation {
  enviarMensagem(telefone: "+5511999999999", texto: "how do withdrawals work?") {
    status
    mensagem
    aguarde
  }
}
```

### `POST /graphql` — History Query
```graphql
query {
  obterHistorico(telefone: "+5511999999999") {
    role
    content
  }
}
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | **Yes** | Google AI Studio Key (Main LLM + Guardrail + Summarization) |
| `REDIS_URL` | **Yes** | Local: `redis://redis_db:6379/0` (or `redis://localhost:6379/0`) \| Cloud: Upstash TCP |
| `DATABASE_URL` | **Recommended** | PostgreSQL: `postgresql://postgres:postgres@postgres_db:5432/zoracle` (pgvector) |
| `SUPABASE_URL` | Optional | Supabase project URL (optional when running native PostgreSQL) |
| `SUPABASE_ANON_KEY` | Optional | Supabase anonymous API key |

---

## How to Run

### 1. Full Self-Hosted Deployment (Docker Compose) 🐳

Complete local containerized stack with zero cloud SaaS account dependencies:

```bash
# 1. Copy and configure minimum environment variables (.env)
cp .env.example .env

# 2. Start all services in the background
docker compose up --build -d
```

Services online after initialization:
- **Operator Console UI (Frontend)**: [http://localhost:3000](http://localhost:3000) (Default login: `adm123` / `adm123`)
- **LibreDB Studio (Web SQL IDE)**: [http://localhost:5555](http://localhost:5555) (Visual PostgreSQL database manager)
- **FastAPI / GraphQL Playground (Backend)**: [http://localhost:8000/graphql](http://localhost:8000/graphql)
- **Local Redis**: `localhost:6379`
- **Local PostgreSQL + pgvector**: `localhost:5432` (db: `zoracle`)

> **Connecting LibreDB Studio to PostgreSQL:**
> In LibreDB Studio at `http://localhost:5555`, create a **PostgreSQL** connection using the internal Docker URL:
> `postgresql://postgres:postgres@postgres_db:5432/zoracle`
> (or Host: `postgres_db`, Port: `5432`, User: `postgres`, Password: `postgres`, Database: `zoracle`).

---

### 2. Manual Local Development (Python)

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Launch FastAPI backend
uvicorn api.main:app --reload --port 8000

# 3. Choose your preferred frontend:
# Option A: Cyberpunk Web Console (Node.js)
cd frontend && npm install && npm start # Accessible at http://localhost:3000

# Option B: Streamlit Interface (Pure Python)
streamlit run frontend.py # Accessible at http://localhost:8501
```

---

### 3. Knowledge Base Vectorization Pipeline (Offline) 🧠

To ingest and compute embeddings from corporate help center documents:

```bash
cd tools/vectorizer
pip install -r requirements.txt

# Run the pipeline with sample or custom CSV data
python pipeline_vetorizacao.py --input seu_arquivo.csv --output saida/
```

---

### 4. Deploying to Google Cloud Run (Serverless Production) ☁️

```bash
# Pre-requisite: secrets configured in GCP Secret Manager
gcloud builds submit --config cloudbuild.yaml
```

---

## Design Patterns

| Pattern | Location | Purpose |
|---|---|---|
| **Lazy Loading Singleton** | `router.py`, `agent.py` | Sub-0.1s API startup; neural models load upon initial message |
| **Tool Scoping per Route** | `graphql_schema.py` + `agent.py` | Eliminates tool overfitting and unpermitted API calls |
| **Direct LLM Fallback** | `agent.py` | Bypasses AgentWorkflow when tools are empty, preventing Gemini 400 errors |
| **Sliding Window Memory** | `redis_client.py` | Bounds context token consumption across long dialogues |
| **Fail-Open Guardrail** | `guardrail.py` | Ensures external security timeouts never penalize legitimate users |
| **15-Second Debounce** | `graphql_schema.py` | Groups fragmented rapid messages into a single cognitive request |
| **Pydantic v2 Session State** | `redis_client.py` | Strict typed serialization prevents corrupted conversational state |
| **Closures for Tools** | `agent.py` | Provides tools with access to state without exposing internal fields to LLM |

---

## Known Limitations

```
⚠  asyncio.create_task() debounce → can be interrupted if Cloud Run scales to zero (Cloud Tasks recommended for serverless)
⚠  index_cache_v5/ is local to disk → persistent pgvector is recommended for multi-instance deployments
⚠  /api/ingerir → Internal-only endpoint (requires network perimeter security / private VPC)
⚠  Automated tests → Current suite covers RAG grounding (tests/test_rag.py); full debounce E2E in progress
⚠  FutureWarning: google.generativeai is deprecated → migrate to google.genai in upcoming releases
```

---

## 📄 License

This repository is licensed under the **Business Source License 1.1 (BSL 1.1)**. Refer to [`LICENSE`](./LICENSE) for full legal text and conditions.

- **Free / Permitted Uses:** Technical evaluation, local benchmarking, integration testing, academic research, and non-commercial educational purposes.
- **Commercial / Production Use:** Direct commercial operations (operating this agent in production for commercial customer service, reselling, or offering it as a hosted/managed SaaS) requires an express Commercial License from the author.
- **Automatic Open Source Transition:** On **January 1, 2030**, this version of the software automatically transitions to the **Apache License, Version 2.0**.

---

<div align="center">

**Z-Oracle Atendee** — Built for BetAgent | Production AI Customer Experience | Python 3.11

</div>
