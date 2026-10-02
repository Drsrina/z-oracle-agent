# AEGIS-REBOT — Operator Console Frontend

Console de Operações interativo com interface cyberpunk / glassmorphism moderna para monitoramento e interação com o agente conversacional **AEGIS-REBOT**.

---

## ✨ Funcionalidades

- **Chat Operacional**: Interação direta com o bot via mutações GraphQL (`enviarMensagem`).
- **Painel de Decisão em Tempo Real**: Visualização da confiança sintética, thresholds, fatores positivos/negativos e status de escalonamento humano.
- **Inspector de Metadados**:
  - `logGuardrail`: Verificação de sanitização e mascaramento de PII.
  - `logRoteamento`: Identificação de rota, intenção e latência.
  - `logRag`: Chunks e artigos de base de conhecimento consultados.
  - `logGeracao`: Modelo LLM utilizado e veredito estruturado.
- **Terminal de Logs Técnicos (Sidebar)**: Stream visual de eventos e status de conexão.
- **Tema Dinâmico**: Alternância rápida entre Dark Cyberpunk e Light Minimalist.
- **Proxy Reverso Integrado**: Express middleware que elimina problemas de CORS ao dialogar com a API backend GraphQL.

---

## 🚀 Como Executar

### 1. Via Docker Compose (Recomendado)

Na raiz do projeto principal:
```bash
docker compose up -d
```
Acesse no navegador: `http://localhost:3000`

### 2. Execução Local Standalone

```bash
cd frontend
npm install
npm start
```

O servidor subirá por padrão na porta `3000`, apontando para a API em `http://localhost:8000`.

### Variáveis de Ambiente Suportadas

| Variável | Padrão | Descrição |
|---|---|---|
| `PORT` | `3000` | Porta onde o servidor Node.js escutará |
| `API_URL` | `http://localhost:8000` | URL base do backend FastAPI / GraphQL |
