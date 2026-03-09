"""
daemon.py — Loop autônomo do hermes-agent para Railway.

Não depende do CLI interativo do hermes. Importa diretamente o
scheduler de cron e o mantém rodando como processo principal.
"""
import os
import sys
import time
import logging
import signal
from pathlib import Path
from dotenv import load_dotenv

# ── Configuração de ambiente ─────────────────────────────────────────────────
HERMES_HOME = os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))
os.environ["HERMES_HOME"] = HERMES_HOME

env_file = Path(HERMES_HOME) / ".env"
if env_file.exists():
    load_dotenv(env_file)

# ── Path do hermes-agent clonado ─────────────────────────────────────────────
HERMES_SRC = Path("/opt/hermes")
if HERMES_SRC.exists() and str(HERMES_SRC) not in sys.path:
    sys.path.insert(0, str(HERMES_SRC))

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("hermes-daemon")

# ── Graceful shutdown ─────────────────────────────────────────────────────────
_running = True

def _handle_signal(sig, frame):
    global _running
    log.info(f"Sinal {sig} recebido. Encerrando...")
    _running = False

signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT,  _handle_signal)


# ── Iniciar scheduler ─────────────────────────────────────────────────────────
def main():
    log.info("Hermes daemon iniciado.")
    log.info(f"HERMES_HOME = {HERMES_HOME}")

    try:
        from cron.scheduler import CronScheduler
        scheduler = CronScheduler()
        scheduler.start()          # thread background: tick() a cada 60s
        log.info("CronScheduler ativo — verificando jobs a cada 60s.")

        while _running:
            time.sleep(5)

        scheduler.stop()
        log.info("Daemon encerrado.")

    except ImportError as e:
        log.error(f"Falha ao importar CronScheduler: {e}")
        log.error("Verifique se o hermes-agent está instalado em /opt/hermes")
        sys.exit(1)
    except Exception as e:
        log.exception(f"Erro inesperado no daemon: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
