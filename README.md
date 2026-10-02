<div align="center">

# Z-Oracle Agent
### Agente de Atendimento com IA — BetAgent

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-5.0-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LlamaIndex](https://img.shields.io/badge/LlamaIndex-RAG-7C3AED?style=for-the-badge)](https://www.llamaindex.ai)
[![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)
[![Redis](https://img.shields.io/badge/Upstash-Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://upstash.com)
[![Supabase](https://img.shields.io/badge/Supabase-Logger-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com)
[![Docker](https://img.shields.io/badge/Cloud_Run-Deploy-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://cloud.google.com/run)

> **Agente conversacional de nível produção** para a plataforma de apostas **BetAgent** (`betagent.bet.br`).
> Interface de chat via **Streamlit + GraphQL**. Aplica guardrails de segurança, roteamento semântico e
> responde com LLM + RAG — tudo em português brasileiro.

</div>

---

## Fluxo Arquitetural

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Z-Oracle Agent — Pipeline Completo                     │
└─────────────────────────────────────────────────────────────────────────────┘

  Interface Streamlit (Chat UI)
         │
         │  POST /graphql  mutation enviarMensagem
         ▼
  ┌──────────────────┐
  │  api/graphql     │  ◄── Protocolo GraphQL (Strawberry)
  │  schema.py       │       Buffer + Debounce 15s
  └────────┬─────────┘
           │  asyncio.create_task → debounce_e_processar()
           ▼
  ┌──────────────────────────────────────────────────────────┐
  │   Pipeline de Processamento (igual ao webhook original)  │
  ├──────────────────────────────────────────────────────────┤
  │  [PASSO 1]  infrastructure/redis_client.py               │
  │             obter_estado(telefone)  →  EstadoConversa    │
  │             TTL 24h | Upstash Redis TLS                  │
  │                                                          │
  │  [PASSO 2]  core/guardrail.py                            │
  │             avaliar_injecao_prompt()  →  LLM-as-a-Judge  │
  │             sanitizar_pii()           →  LGPD            │
  │             Modelo: gemini-1.5-flash (3s timeout)        │
  │                                                          │
  │  [PASSO 3]  core/router.py                               │
  │             FASE 1: Regex → CPF / Saudações (custo zero) │
  │             FASE 2: SentenceTransformer → Dot Product    │
  │             Modelo: all-MiniLM-L6-v2 | Threshold: 0.45  │
  │                                                          │
  │  [PASSO 4]  core/agent.py                                │
  │             Tool injection por rota autorizada           │
  │             LLM direto (sem AgentWorkflow) se sem tools  │
  │             LLM: gemini-2.5-flash | RAG: top_k=3        │
  │                                                          │
  │  [PASSO 5]  infrastructure/redis_client.py               │
  │             guardar_estado() → Upstash Redis             │
  │                                                          │
  │  [PASSO 6]  infrastructure/supabase_logger.py            │
  │             registar_log_assincrono() → Supabase         │
  └──────────────────────────────────────────────────────────┘
           │
           ▼  Query obterHistorico()
  ┌──────────────────┐
  │  Streamlit       │  ◄── Polling GraphQL a cada 3s
  │  frontend.py     │       Stream de digitação humanizado
  └──────────────────┘
```

---

## Roteamento Semântico

O roteador opera em **duas fases em cascata**, priorizando custo zero antes de usar embeddings:

```
Mensagem recebida
       │
       ▼
┌──────────────────────────────────────────────────────┐
│  FASE 1 — Determinística (0ms, 0 custo)              │
│                                                      │
│  CPF detectado?  ──► COLETA_DADOS                    │
│  (\d{11})                                            │
│                                                      │
│  Saudação exata? ──► BATE_PAPO                       │
│  ("oi", "olá", "sim", "ok"...)                       │
└──────────────────────────────┬───────────────────────┘
                               │ nenhum match
                               ▼
┌──────────────────────────────────────────────────────┐
│  FASE 2 — Vetorial (~5ms)                            │
│                                                      │
│  ┌─────────────────────┬──────────────────────────┐  │
│  │ Rota                │ Ferramentas injetadas     │  │
│  ├─────────────────────┼──────────────────────────┤  │
│  │ BATE_PAPO           │ nenhuma (LLM direto)      │  │
│  │ DUVIDA_TECNICA      │ consultar_manual (RAG)    │  │
│  │ TRANSACAO_FINANCEIRA│ realizar_deposito/saque   │  │
│  │ PROBLEMA / ESCALAR  │ transferir_para_humano    │  │
│  └─────────────────────┴──────────────────────────┘  │
│                                                      │
│  Fallback se falhar: DUVIDA_TECNICA                  │
└──────────────────────────────────────────────────────┘
```

---

## Estrutura do Projeto

```
Z-Oracle Agent/
│
├── api/
│   ├── main.py                 # FastAPI — Orchestrator (endpoints: /health, /api/ingerir, /graphql)
│   └── graphql_schema.py       # GraphQL (Strawberry) — Protocolo principal da UI
│
├── core/
│   ├── agent.py                # LLM + RAG Engine (Gemini 2.5 Flash | LlamaIndex AgentWorkflow)
│   ├── router.py               # Semantic Router + Sentiment Classifier (all-MiniLM-L6-v2)
│   └── guardrail.py            # Segurança: LLM-as-Judge + Mascaramento PII/LGPD
│
├── infrastructure/
│   ├── redis_client.py         # Sessões via Upstash Redis (TCP/TLS) + fallback in-memory
│   └── supabase_logger.py      # Logger analítico real (tabela logs_atendimento)
│
├── frontend.py                 # UI Streamlit — Chat com stream de digitação + polling GraphQL
├── cloudbuild.yaml             # CI/CD: Cloud Build → Artifact Registry → Cloud Run
├── Dockerfile                  # Python 3.11-slim + modelo pré-baked (all-MiniLM-L6-v2)
├── docker-compose.yml          # Dev local: API + Redis (chaves via .env)
├── .env.example                # Template das variáveis de ambiente
└── requirements.txt            # Dependências Python completas e sincronizadas
```

---

## Estado da Conversa (`EstadoConversa`)

```
┌──────────────────────────────────────────────────────┐
│  EstadoConversa  (Pydantic v2 BaseModel)             │
├──────────────────────────────────────────────────────┤
│  session_id              str   → ID gerado pelo UI   │
│  cpf                     str?  → CPF validado        │
│  etapa                   str   → máquina de estados  │
│  tentativas_resolucao    int                         │
│  perfil_sentimental      str   → Neutro/Irritado/... │
│  dados_transacao_pendente dict → saque/depósito       │
│  resumo_acumulado        str   → sumário LLM (antigo)│
│  mensagens_recentes      List[3] → janela deslizante │
│  buffer_pendente         List  → debounce GraphQL    │
│  ultimo_timestamp        float → controle debounce   │
└──────────────────────────────────────────────────────┘

  Máquina de Estados:
  INICIO ──► TRIAGEM ──► COLETA ──► RESOLUCAO ──► ENCERRADO
                                  └──► AGUARDANDO_CONFIRMACAO

  Redis Key:   betagent:session:{session_id}
  TTL:         86400s (24 horas)
  Servidor:    Upstash (produção) | localhost (dev)
```

---

## API Reference

### `GET /health`
```json
{ "status": "online", "timestamp": 1735000000.0 }
```

### `POST /api/ingerir` *(Admin)*
```json
{ "texto_conhecimento": "Nova regra: saques acima de R$ 5.000 requerem selfie..." }
```
> Substitui o RAG engine em memória em tempo real. Sem autenticação — uso interno.

### `POST /graphql` — Mutation principal
```graphql
mutation {
  enviarMensagem(telefone: "+5511999999999", texto: "como funciona o saque?") {
    status
    mensagem
    aguarde
  }
}
```

### `POST /graphql` — Query de histórico
```graphql
query {
  obterHistorico(telefone: "+5511999999999") {
    role
    content
  }
}
```

---

## Variáveis de Ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `GEMINI_API_KEY` | **Sim** | Chave Google AI Studio (LLM principal + guardrail + sumarização) |
| `REDIS_URL` | **Sim** | Upstash TCP: `rediss://default:SENHA@HOST.upstash.io:6379` |
| `SUPABASE_URL` | Não | URL do projeto Supabase para logs analíticos |
| `SUPABASE_ANON_KEY` | Não | Chave anon do Supabase |

---

## Como Executar

### Desenvolvimento Local

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar variáveis de ambiente (editar .env)
# GEMINI_API_KEY e REDIS_URL são obrigatórias

# 3. Iniciar com o script pronto
.1Testes\iniciar_servidor.bat
# OU manualmente:
uvicorn api.main:app --reload --port 8000
streamlit run frontend.py
```

### Produção com Docker Compose (Dev)

```bash
# Preencher .env antes
docker-compose up --build
```

### Deploy Cloud Run (Produção)

```bash
# Pré-requisitos: secrets criados no GCP Secret Manager
gcloud builds submit --config cloudbuild.yaml
```

> O `Dockerfile` pré-instala o modelo `all-MiniLM-L6-v2` na imagem.
> O container não precisa baixar o modelo a cada restart.

---

## Padrões de Design

| Padrão | Onde | Motivo |
|---|---|---|
| **Lazy Loading Singleton** | `router.py`, `agent.py` | Boot da API em < 0.1s; modelo carrega na 1ª mensagem |
| **Tool Injection por Rota** | `graphql_schema.py` + `agent.py` | LLM não alucina ferramentas indisponíveis |
| **LLM Direto sem AgentWorkflow** | `agent.py` | Evita erro 400 do Gemini quando lista de tools está vazia |
| **Rolling Window Memory** | `redis_client.py` | Context window sempre limitado em conversas longas |
| **Fail-Open Guardrail** | `guardrail.py` | Timeout de segurança não pune usuário legítimo |
| **Debounce 15s** | `graphql_schema.py` | Agrupa mensagens rápidas antes de processar |
| **Pydantic v2 para Estado** | `redis_client.py` | Serialização tipada previne corrupção de sessão |
| **Closures para Tools** | `agent.py` | Estado da sessão acessível sem expô-lo ao LLM |

---

## Limitações Conhecidas

```
⚠  asyncio.create_task() do debounce → pode ser morto em Cloud Run scale-to-zero
   Solução futura: migrar para Cloud Tasks

⚠  index_cache_v5/ não persiste no Cloud Run → RAG reindexado em cada cold start

⚠  /api/ingerir → Sem autenticação (uso interno somente)

⚠  Sem testes automatizados → nenhum diretório tests/ configurado

⚠  FutureWarning: google.generativeai deprecado → migrar para google.genai futuramente
```

---

## Stack Completa

```
fastapi>=0.110.0            uvicorn>=0.29.0
pydantic>=2.6.0             python-dotenv>=1.0.0
strawberry-graphql>=0.300.0 redis>=5.0.3
llama-index-core>=0.10.20   llama-index-llms-gemini
llama-index-embeddings-huggingface  llama-index-readers-web
google-generativeai>=0.5.0  sentence-transformers>=2.5.0
numpy>=1.26.0               validate-docbr>=1.10.0
supabase>=2.3.0             streamlit>=1.32.0
```

---

<div align="center">

**Z-Oracle Agent** — Construído para BetAgent | Português Brasileiro | Python 3.11

</div>
