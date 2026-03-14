#!/bin/bash
set -e

echo "[HERMES] Iniciando setup..."

HERMES_HOME="${HERMES_HOME:-/data/hermes}"
mkdir -p "$HERMES_HOME/skills" "$HERMES_HOME/cron" "$HERMES_HOME/sessions" "$HERMES_HOME/logs"

# ── LiteLLM Proxy (Anthropic → OpenAI-compatible) ───────────────────────────
# Se ANTHROPIC_API_KEY está definida, inicia um proxy local que converte
# requests OpenAI-format para a API da Anthropic. Hermes só fala OpenAI.
LITELLM_PORT=4010

if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "[HERMES] ANTHROPIC_API_KEY detectada — iniciando proxy LiteLLM na porta $LITELLM_PORT..."

    # Config do litellm proxy
    cat > /tmp/litellm_config.yaml << LITELLM_EOF
model_list:
  - model_name: "anthropic/claude-sonnet-4-20250514"
    litellm_params:
      model: "anthropic/claude-sonnet-4-20250514"
      api_key: "${ANTHROPIC_API_KEY}"
  - model_name: "anthropic/claude-haiku-4-5-20251001"
    litellm_params:
      model: "anthropic/claude-haiku-4-5-20251001"
      api_key: "${ANTHROPIC_API_KEY}"
  - model_name: "claude-sonnet-4-20250514"
    litellm_params:
      model: "anthropic/claude-sonnet-4-20250514"
      api_key: "${ANTHROPIC_API_KEY}"
LITELLM_EOF

    litellm --config /tmp/litellm_config.yaml --port $LITELLM_PORT --host 127.0.0.1 &
    LITELLM_PID=$!

    # Espera o proxy ficar pronto
    for i in $(seq 1 30); do
        if curl -s http://127.0.0.1:$LITELLM_PORT/health > /dev/null 2>&1; then
            echo "[HERMES] LiteLLM proxy pronto (PID=$LITELLM_PID)"
            break
        fi
        sleep 1
    done

    # Hermes vai usar o proxy local como "OpenAI"
    export OPENAI_API_KEY="sk-litellm-local"
    export OPENAI_BASE_URL="http://127.0.0.1:$LITELLM_PORT/v1"
    export LLM_BASE_URL="http://127.0.0.1:$LITELLM_PORT/v1"
else
    echo "[HERMES] Sem ANTHROPIC_API_KEY — usando provider direto (OpenAI/Perplexity)"
fi

# ── Credenciais ──────────────────────────────────────────────────────────────
cat > "$HERMES_HOME/.env" << EOF
OPENAI_API_KEY=${OPENAI_API_KEY}
OPENAI_BASE_URL=${OPENAI_BASE_URL:-${LLM_BASE_URL:-}}
LLM_BASE_URL=${LLM_BASE_URL:-}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
MODEL=${MODEL:-anthropic/claude-sonnet-4-20250514}
SUPABASE_URL=${SUPABASE_URL:-}
SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY:-}
SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY:-}
PERPLEXITY_API_KEY=${PERPLEXITY_API_KEY:-}
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-}
TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID:-}
HERMES_HOME=${HERMES_HOME}
EOF

# ── Configuração ─────────────────────────────────────────────────────────────
cp /opt/hermes-config/config.yaml "$HERMES_HOME/config.yaml"
cp /opt/hermes-config/SOUL.md     "$HERMES_HOME/SOUL.md"

# Skills: copia apenas se ainda não existe (preserva o que o agente criou)
for skill_file in /opt/hermes-config/skills/*.md; do
    fname=$(basename "$skill_file")
    if [ ! -f "$HERMES_HOME/skills/$fname" ]; then
        cp "$skill_file" "$HERMES_HOME/skills/"
        echo "[HERMES] Skill instalada: $fname"
    fi
done

# Cron jobs: sempre atualiza (nossos jobs são a fonte da verdade)
for cron_file in /opt/hermes-config/cron/*.yaml; do
    cp "$cron_file" "$HERMES_HOME/cron/"
    echo "[HERMES] Cron job instalado: $(basename $cron_file)"
done

echo "[HERMES] Setup concluído. Iniciando daemon autônomo..."
echo "[HERMES] HERMES_HOME=$HERMES_HOME"

# Rodar o daemon autônomo (unbuffered para Railway ver os logs em tempo real)
exec python -u /opt/hermes-config/daemon.py
