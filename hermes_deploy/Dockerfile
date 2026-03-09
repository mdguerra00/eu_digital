FROM python:3.11-slim

# Dependências de sistema
RUN apt-get update && apt-get install -y \
    git curl ripgrep ffmpeg build-essential \
    && rm -rf /var/lib/apt/lists/*

# Clonar hermes-agent
WORKDIR /opt
RUN git clone --depth=1 https://github.com/NousResearch/hermes-agent.git hermes

# Instalar hermes e dependências
WORKDIR /opt/hermes
RUN pip install --upgrade pip && \
    pip install -e ".[all]" 2>/dev/null || \
    pip install openai python-dotenv httpx rich tenacity pyyaml requests \
                jinja2 pydantic>=2.0 croniter fire prompt_toolkit && \
    pip install -e "."

# Copiar nossos arquivos de configuração
COPY config.yaml     /opt/hermes-config/config.yaml
COPY SOUL.md         /opt/hermes-config/SOUL.md
COPY skills/         /opt/hermes-config/skills/
COPY cron/           /opt/hermes-config/cron/
COPY daemon.py       /opt/hermes-config/daemon.py
COPY start.sh        /start.sh
RUN chmod +x /start.sh

# Hermes guarda tudo em HERMES_HOME (Railway pode montar volume aqui)
ENV HERMES_HOME=/data/hermes

EXPOSE 8080

CMD ["/start.sh"]
