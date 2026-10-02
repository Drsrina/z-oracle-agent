<div align="center">

# Z-Oracle Atendee
### Agente Cognitivo de Atendimento com IA, Roteamento Semântico e Blindagem Antialucinação

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-5.0-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LlamaIndex](https://img.shields.io/badge/LlamaIndex-RAG-7C3AED?style=for-the-badge)](https://www.llamaindex.ai)
[![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)
[![Redis](https://img.shields.io/badge/Redis-7.0-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Docker](https://img.shields.io/badge/Docker-Self--Hosted-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com)

> **Agente conversacional de nível produção** projetado para operações de alta escala e missão crítica (plataforma **BetAgent**).
> Equipado com o console de operações **Z-Oracle** (interface web cyberpunk com painel de decisão em tempo real),
> aplica guardrails de segurança multicamadas, roteamento semântico vetorial e blindagem ativa antialucinação via **Tool Scoping**.

</div>

---

## Fluxo Arquitetural

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Z-Oracle — Pipeline Completo                        │
└─────────────────────────────────────────────────────────────────────────────┘

  Interfaces de Atendimento:
  [A] Z-Oracle Operator Console (Cyberpunk Web - Node.js/Express :3000)
  [B] Streamlit Client (Python Puro :8501)
         │
         │  POST /graphql  mutation enviarMensagem
         ▼
  ┌──────────────────┐
  │  api/graphql     │  ◄── Protocolo GraphQL (Strawberry)
  │  schema.py       │       Buffer + Debounce de 15 segundos
  └────────┬─────────┘
           │  asyncio.create_task → debounce_e_processar()
           ▼
  ┌──────────────────────────────────────────────────────────┐
  │   Pipeline Cognitivo de Processamento                    │
  ├──────────────────────────────────────────────────────────┤
  │  [PASSO 1]  infrastructure/redis_client.py               │
  │             obter_estado(telefone)  →  EstadoConversa    │
  │             TTL 24h | Redis Local / Upstash              │
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
  │             Classificação de Sentimento + Matriz Cynefin │
  │                                                          │
  │  [PASSO 4]  core/agent.py                                │
  │             Tool Scoping: injeção restritiva por rota    │
  │             LLM direto (sem AgentWorkflow) se sem tools  │
  │             LLM: gemini-2.5-flash | RAG pgvector: top_k=3│
  │                                                          │
  │  [PASSO 5]  infrastructure/redis_client.py               │
  │             guardar_estado() → Redis Local / Upstash     │
  │                                                          │
  │  [PASSO 6]  infrastructure/database.py                   │
  │             registar_log_assincrono() → PostgreSQL       │
  └──────────────────────────────────────────────────────────┘
           │
           ▼  Query obterHistorico() / Polling
  ┌──────────────────────────────────────────────┐
  │  Z-Oracle Console (:3000) / Streamlit (:8501)│  ◄── Polling GraphQL + Metadata Inspector
  └──────────────────────────────────────────────┘
```

---

## 🧠 Triagem Semântica & Blindagem Antialucinação (Deep Dive)

### O Problema: "Cérebro Dividido" e Alucinação por Excesso de Ferramentas
Em agentes conversacionais ingênuos, todas as ferramentas (RAG, depósitos, saques, consultas bancárias, cancelamentos) ficam disponíveis para o LLM em todas as mensagens. Isso gera falhas graves:
1. **Tool Overfitting / Alucinação de Funções**: Ao receber um simples *"Olá, bom dia"*, o LLM tenta acionar consultas de banco ou buscar o termo *"bom dia"* na base de conhecimento.
2. **Latência Excessiva**: Avaliar schemas de dezenas de ferramentas simultaneamente aumenta o consumo de tokens e o tempo de resposta em 3x a 5x.
3. **Execução Acidental**: O LLM pode acionar uma mutação financeira sensível sem que o usuário tenha manifestado intenção clara.

### A Solução: Arquitetura em Cascata de 2 Fases

O módulo [`core/router.py`](file:///c:/Users/Drysrina/Desktop/Code/Z-Oracle%20Atendee/core/router.py) intercepta a requisição **antes** do LLM principal e aplica uma classificação em cascata:

```
Mensagem Recebida
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ FASE 1: Roteamento Determinístico (0ms, Custo Zero)   │
│ ├─ CPF detectado? (\d{11})     ──► COLETA_DADOS        │
│ └─ Saudação exata? ("oi", ...) ──► BATE_PAPO           │
└──────────────────────────┬─────────────────────────────┘
                           │ Nenhum match
                           ▼
┌────────────────────────────────────────────────────────┐
│ FASE 2: Roteamento Vetorial C-Compiled (~5ms)          │
│ Modelo: all-MiniLM-L6-v2 (Embedding de 384 dimensões)  │
│ Operação: NumPy Dot Product (vetor normalizado)        │
│                                                        │
│ ┌──────────────────────┬─────────────────────────────┐ │
│ │ Rota                 │ Ferramentas Injetadas       │ │
│ ├──────────────────────┼─────────────────────────────┤ │
│ │ BATE_PAPO            │ Nenhuma (LLM puro direto)   │ │
│ │ DUVIDA_TECNICA       │ consultar_manual (RAG)      │ │
│ │ TRANSACAO_FINANCEIRA │ manual, deposito, saque     │ │
│ │ PROBLEMA / ESCALAR   │ transferir_para_humano      │ │
│ └──────────────────────┴─────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

### Tool Scoping: Firewall Dinâmico de Ferramentas
O agente nunca recebe ferramentas além do escopo delimitado pelo router:
- Na rota **`BATE_PAPO`**, o LLM é chamado com `ferramentas_permitidas=[]`. Sem ferramentas registradas, é **matematicamente impossível** que o modelo alucine uma consulta técnica ou transação financeira.
- Na rota **`DUVIDA_TECNICA`**, a IA é obrigada a responder com embasamento no RAG da base de conhecimento oficial.
- Na rota **`COLETA_DADOS`**, a mensagem nem sequer é enviada ao LLM: é validada matematicamente pelo `validate-docbr` e salva na sessão, garantindo 100% de conformidade e zero custo de inferência.

### Sentimento Vetorial & Framework Cynefin
O router não utiliza listas rígidas de palavrões. Em vez disso, projeta a frase no espaço vetorial de sentimentos para capturar **ironia, sarcasmo e agressividade velada**:
- **Cynefin CLARO** (bate-papo / dúvida simples): Confiança sintética mínima exigida de **60%**.
- **Cynefin COMPLICADO** (regras e transações): Confiança mínima de **75%**.
- **Cynefin COMPLEXO / CAÓTICO** (3+ tentativas frustradas ou sentimentos irritados): O bot suspende o atendimento autônomo e aciona imediatamente o **Handoff Humano**.

---

## ⚡ Mecanismo de Debounce & Buffer de Mensagens (15s)

Usuários reais em mensageiros (WhatsApp, Telegram, Webchats) não enviam mensagens em um único bloco formal. Eles costumam enviar pensamentos picados em várias mensagens curtas consecutivas:
```text
Usuário: "olá" (00:01)
Usuário: "fiz um depósito via pix" (00:03)
Usuário: "e ainda não caiu na minha conta" (00:07)
```
Em bots comuns, isso dispara 3 requisições concorrentes ao LLM, gerando respostas desconexas e custos triplicados.

O Z-Oracle resolve isso via **Debounce Inteligente de 15 segundos**:
1. Cada mensagem recebida via mutação GraphQL `enviarMensagem` é empilhada no `buffer_pendente` da sessão no Redis.
2. Uma task assíncrona (`asyncio.create_task`) agenda o processamento para daqui a 15 segundos.
3. Se uma nova mensagem chegar antes do tempo expirar, o timestamp de corte é renovado.
4. Quando o usuário para de digitar, todas as mensagens são **unificadas em um único prompt contextual**, garantindo que a IA compreenda o problema completo de uma só vez.

---

## Estrutura do Projeto

```
Z-Oracle Atendee/
│
├── api/
│   ├── main.py                 # FastAPI — Gateway assíncrono (/health, /api/ingerir, /graphql)
│   └── graphql_schema.py       # Strawberry GraphQL — Buffer de debounce 15s e mutações
│
├── core/
│   ├── agent.py                # LLM & RAG Engine (Gemini 2.5 Flash, Tool Injection por Rota)
│   ├── router.py               # Semantic Router C-Compiled + Sentimento Vetorial + Cynefin
│   ├── guardrail.py            # Segurança: LLM-as-a-Judge (Prompt Injection) + Sanitização LGPD
│   └── clarificador.py         # Extrator de intenções, CPFs e dados contextuais
│
├── docker/
│   └── postgres/init.sql       # Script de inicialização PostgreSQL + pgvector + match_documents
│
├── docs/
│   └── arquitetura.md          # Relatório técnico completo de arquitetura de software
│
├── frontend/                   # Z-Oracle Operator Console (Cyberpunk Web - Node.js/Express)
│   ├── index.html              # Interface visual com painel de decisão e metadata inspector
│   ├── style.css               # Design system glassmorphism, orbs e neon tokens
│   ├── index.js                # Servidor Express com proxy reverso anti-CORS
│   └── Dockerfile              # Imagem leve baseada em Node 18 Alpine
│
├── infrastructure/
│   ├── database.py             # Pool nativo PostgreSQL (asyncpg) com upsert e busca vetorial
│   ├── redis_client.py         # Sessões stateful Redis + Modelo Pydantic v2 EstadoConversa
│   └── supabase_logger.py      # Logger analítico unificado (PostgreSQL com fallback)
│
├── tests/
│   └── test_rag.py             # Bateria de testes de recuperação e grounding RAG
│
├── tools/
│   └── vectorizer/             # Pipeline offline de vetorização da base de conhecimento
│
├── frontend.py                 # Interface alternativa Streamlit com digitação humanizada
├── cloudbuild.yaml             # CI/CD: Cloud Build → Artifact Registry → Cloud Run
├── Dockerfile                  # Python 3.11-slim com all-MiniLM-L6-v2 pré-embarcado
├── docker-compose.yml          # Stack fullstack self-hosted (API + Frontend + Redis + PostgreSQL)
├── .env.example                # Template das variáveis de ambiente
└── requirements.txt            # Dependências Python completas e sincronizadas
```

---

## 🛡️ Segurança Multicamadas & Guardrails (LGPD + LLM-as-a-Judge)

O agente implementa proteção ativa contra engenharia social e vazamento de dados:

1. **Camada 1 — Sanitização Determinística de PII (LGPD)**:
   - Expressões regulares pré-compiladas identificam CPFs (`\d{3}\.\d{3}\.\d{3}-\d{2}`) e números de cartões de crédito internacionais.
   - Os dados são ofuscados (`***1234`) **antes** de serem gravados em logs analíticos ou enviados para provedores externos de LLM.
2. **Camada 2 — Firewall Ativo contra Prompt Injection (LLM-as-a-Judge)**:
   - Um modelo ultrarrápido (`gemini-1.5-flash`) atua exclusivamente como avaliador de segurança com prompt blindado.
   - Detecta tentativas de *jailbreak*, comandos para ignorar instruções anteriores e extração de regras internas.
   - **Timeout estrito de 3 segundos com Fail-Open**: Se a API de segurança oscilar, a requisição não trava o usuário legítimo.

---

## 💾 Gestão de Memória: Janela Deslizante & Rolling Summary

Em conversas longas, enviar todo o histórico acumula custos exponenciais e atinge os limites de contexto (Context Window Exhaustion).

O Z-Oracle adota uma estratégia híbrida:
- **Janela Deslizante Imediata**: As **últimas 3 interações** são mantidas em texto integral para fluidez conversacional imediata.
- **Rolling Summary em Background**: Quando o diálogo atinge o limiar configurado, uma task assíncrona aciona um modelo de sumarização via threadpool (`run_in_threadpool`), compactando as mensagens antigas em um resumo estruturado no Redis.
- **Zero Latência Adicional**: A compressão roda em segundo plano sem adicionar um único milissegundo de espera para o usuário final.

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
  Servidor:    Redis 7 Local (Docker Compose) / Upstash TCP (Nuvem)
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
| `REDIS_URL` | **Sim** | Local: `redis://redis_db:6379/0` (ou `redis://localhost:6379/0`) \| Nuvem: Upstash TCP |
| `DATABASE_URL` | **Recomendada** | PostgreSQL: `postgresql://postgres:postgres@postgres_db:5432/zoracle` (pgvector) |
| `SUPABASE_URL` | Não | Opcional se usar PostgreSQL nativo (URL do projeto Supabase) |
| `SUPABASE_ANON_KEY` | Não | Opcional (Chave anon do Supabase) |

---

## Como Executar

### 1. Implantação Self-Hosted Completa (Docker Compose) 🐳

Stack 100% self-hosted em containers locais, sem dependência de contas pagas no Upstash ou Supabase:

```bash
# 1. Copie e preencha as variáveis de ambiente mínimas (.env)
cp .env.example .env

# 2. Suba todos os serviços em segundo plano
docker compose up --build -d
```

Serviços disponíveis após a inicialização:
- **Operator Console UI (Frontend)**: [http://localhost:3000](http://localhost:3000) (Login padrão: `adm123` / `adm123`)
- **FastAPI / GraphQL Playground (Backend)**: [http://localhost:8000/graphql](http://localhost:8000/graphql)
- **Redis Local**: `localhost:6379`
- **PostgreSQL Local + pgvector**: `localhost:5432` (db: `zoracle`)

---

### 2. Desenvolvimento Local (Python Manual)

```bash
# 1. Instalar dependências Python
pip install -r requirements.txt

# 2. Iniciar a API Backend
uvicorn api.main:app --reload --port 8000

# 3. Escolha uma das interfaces:
# Opção A: Console Cyberpunk Web (Node.js)
cd frontend && npm install && npm start # Acessa em http://localhost:3000

# Opção B: Interface Streamlit (Python puro)
streamlit run frontend.py # Acessa em http://localhost:8501
```

---

### 3. Pipeline de Vetorização de Base de Conhecimento (Offline) 🧠

Para processar artigos ou bases de conhecimento institucionais e gerar embeddings para o RAG:

```bash
cd tools/vectorizer
pip install -r requirements.txt

# Executa o pipeline com dataset de exemplo ou customizado
python pipeline_vetorizacao.py --input-csv dados.csv --output-pkl embeddings.pkl
```

---

### 4. Deploy no Google Cloud Run (Produção Serverless) ☁️

```bash
# Pré-requisitos: secrets configurados no GCP Secret Manager
gcloud builds submit --config cloudbuild.yaml
```

> O `Dockerfile` pré-instala o modelo `all-MiniLM-L6-v2` na imagem, dispensando downloads repetitivos em cold starts.

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

**Z-Oracle Atendee** — Construído para BetAgent | Português Brasileiro | Python 3.11

</div>
