-- Migração idempotente para a tabela creator_messages
-- Usada para comunicação Criador → Agente via Supabase
--
-- Aplicar com:
--   psql $DATABASE_URL -f create_creator_messages.sql
-- ou via Supabase Dashboard > SQL Editor

CREATE TABLE IF NOT EXISTS creator_messages (
    id              BIGSERIAL PRIMARY KEY,
    agent_name      TEXT        NOT NULL,
    message         TEXT        NOT NULL,
    priority        TEXT        NOT NULL DEFAULT 'normal'
                        CHECK (priority IN ('normal', 'high', 'urgent')),
    status          TEXT        NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'processed')),
    author          TEXT        NOT NULL DEFAULT 'Criador',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    read_at         TIMESTAMPTZ,
    processed_at    TIMESTAMPTZ,
    cycle_number    INTEGER
);

-- Índices para consultas comuns
CREATE INDEX IF NOT EXISTS idx_creator_messages_agent_status
    ON creator_messages (agent_name, status, created_at ASC);

-- Habilitar Row Level Security (RLS) — acesso apenas via service role
ALTER TABLE creator_messages ENABLE ROW LEVEL SECURITY;

-- Política: service role tem acesso total
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'creator_messages'
          AND policyname = 'service_role_all'
    ) THEN
        CREATE POLICY service_role_all ON creator_messages
            FOR ALL
            TO service_role
            USING (true)
            WITH CHECK (true);
    END IF;
END
$$;

-- Comentários de documentação
COMMENT ON TABLE  creator_messages             IS 'Canal de mensagens do Criador para o agente. Lido a cada ciclo do agente.';
COMMENT ON COLUMN creator_messages.priority    IS 'normal | high | urgent. urgent = processado imediatamente no próximo ciclo.';
COMMENT ON COLUMN creator_messages.status      IS 'pending = ainda não processado; processed = já lido pelo agente.';
COMMENT ON COLUMN creator_messages.cycle_number IS 'Número do ciclo em que a mensagem foi processada (preenchido pelo agente).';
