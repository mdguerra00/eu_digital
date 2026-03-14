#!/bin/bash
set -e

echo "[HERMES] Iniciando setup..."

HERMES_HOME="${HERMES_HOME:-/data/hermes}"
mkdir -p "$HERMES_HOME/skills" "$HERMES_HOME/cron" "$HERMES_HOME/sessions" "$HERMES_HOME/logs"

# ── Credenciais (OpenAI direto, sem proxy) ───────────────────────────────────
echo "[HERMES] Configurando provider OpenAI (modelo: ${MODEL:-gpt-4.1-mini})"
cat > "$HERMES_HOME/.env" << EOF
OPENAI_API_KEY=${OPENAI_API_KEY}
MODEL=${MODEL:-gpt-4.1-mini}
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
