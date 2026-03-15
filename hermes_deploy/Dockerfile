FROM python:3.11-slim

# Dependências de sistema
RUN apt-get update && apt-get install -y \
    git curl ripgrep ffmpeg build-essential \
    && rm -rf /var/lib/apt/lists/*

# Clonar hermes-agent (com submódulos — mini-swe-agent é necessário)
WORKDIR /opt
RUN git clone --depth=1 --recurse-submodules https://github.com/NousResearch/hermes-agent.git hermes

# Instalar hermes e dependências
WORKDIR /opt/hermes
RUN pip install --upgrade pip && \
    pip install mini-swe-agent && \
    pip install -e ".[all]" 2>/dev/null || \
    pip install openai python-dotenv httpx rich tenacity pyyaml requests \
                jinja2 pydantic>=2.0 croniter fire prompt_toolkit && \
    pip install -e "."

# Copiar nossos arquivos de configuração
# Paths relativos à raiz do repo (build context do Railway)
COPY hermes_deploy/config.yaml     /opt/hermes-config/config.yaml
COPY hermes_deploy/SOUL.md         /opt/hermes-config/SOUL.md
COPY hermes_deploy/MEMORY.md       /opt/hermes-config/MEMORY.md
COPY hermes_deploy/skills/         /opt/hermes-config/skills/
COPY hermes_deploy/cron/           /opt/hermes-config/cron/
COPY hermes_deploy/daemon.py       /opt/hermes-config/daemon.py
COPY hermes_deploy/start.sh        /start.sh
RUN chmod +x /start.sh

# Hermes guarda tudo em HERMES_HOME (Railway pode montar volume aqui)
ENV HERMES_HOME=/data/hermes

# Railway injeta PORT dinamicamente; daemon.py escuta nessa porta
CMD ["/start.sh"]
