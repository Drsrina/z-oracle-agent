-- ==============================================================
-- Z-Oracle Atendee — PostgreSQL + pgvector Initialization Script
-- Auto-executado pelo Docker no primeiro boot do banco
-- ==============================================================

-- 1. Extensões essenciais
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 2. Tabela de Logs Analíticos do Atendimento
CREATE TABLE IF NOT EXISTS logs_atendimento (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    sessao_id TEXT,
    telefone TEXT,
    rota TEXT,
    input_sanitizado TEXT,
    resposta TEXT,
    tools_usadas TEXT[],
    confianca TEXT,
    motivo TEXT,
    model TEXT,
    route_score DOUBLE PRECISION,
    sentiment TEXT DEFAULT 'Neutro',
    sentiment_score DOUBLE PRECISION,
    latencia_ms INTEGER,
    latency_route INTEGER
);

CREATE INDEX IF NOT EXISTS idx_logs_created_at ON logs_atendimento(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_telefone ON logs_atendimento(telefone);
CREATE INDEX IF NOT EXISTS idx_logs_rota ON logs_atendimento(rota);

-- 3. Tabela de Sessões de Usuário
CREATE TABLE IF NOT EXISTS sessoes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT UNIQUE NOT NULL,
    etapa TEXT DEFAULT 'INICIO',
    cpf TEXT,
    resumo_acumulado TEXT,
    dados_coletados JSONB DEFAULT '{}'::jsonb,
    tentativas_resolucao INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessoes_session_id ON sessoes(session_id);

-- 4. Tabela de Mensagens do Histórico Persistente
CREATE TABLE IF NOT EXISTS mensagens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sessao_id UUID REFERENCES sessoes(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mensagens_sessao_id ON mensagens(sessao_id);

-- 5. Tabela de Base de Conhecimento com Vetores (RAG)
-- Modelo all-MiniLM-L6-v2 produz embeddings de dimensão 384
CREATE TABLE IF NOT EXISTS base_conhecimento (
    id SERIAL PRIMARY KEY,
    url TEXT,
    titulo TEXT,
    categoria TEXT,
    subcategoria TEXT,
    conteudo_texto TEXT NOT NULL,
    embedding vector(384),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índice vetorial com operador de similaridade por cosseno (<=>)
CREATE INDEX IF NOT EXISTS idx_base_conhecimento_embedding 
ON base_conhecimento USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 6. Função RPC de busca vetorial similar ao Supabase match_documents
CREATE OR REPLACE FUNCTION match_documents (
    query_embedding vector(384),
    match_threshold float DEFAULT 0.40,
    match_count int DEFAULT 3
)
RETURNS TABLE (
    id int,
    titulo text,
    conteudo_texto text,
    similarity float
)
LANGUAGE sql STABLE
AS $$
    SELECT
        base_conhecimento.id,
        base_conhecimento.titulo,
        base_conhecimento.conteudo_texto,
        1 - (base_conhecimento.embedding <=> query_embedding) AS similarity
    FROM base_conhecimento
    WHERE 1 - (base_conhecimento.embedding <=> query_embedding) > match_threshold
    ORDER BY similarity DESC
    LIMIT match_count;
$$;

-- 7. Tabela de Controle de Versão do Esquema (Schema Migrations)
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    version VARCHAR(50) UNIQUE NOT NULL,
    description TEXT NOT NULL,
    applied_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO schema_migrations (version, description)
VALUES ('001_initial_schema', 'Tabelas essenciais: logs_atendimento, sessoes, mensagens, base_conhecimento (pgvector) e match_documents')
ON CONFLICT (version) DO NOTHING;
