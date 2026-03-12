"""
daemon.py — Loop autônomo do hermes-agent para Railway.

Scheduler de cron autossuficiente. Lê jobs YAML de $HERMES_HOME/cron/
e os executa via CLI do hermes-agent instalado em /opt/hermes.
Não depende de nenhuma classe interna do repo clonado.
"""
import glob
import logging
import os
import shutil
import signal
import subprocess
import sys
import time
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from dotenv import load_dotenv

try:
    import yaml
except ImportError:
    yaml = None

try:
    from croniter import croniter
except ImportError:
    croniter = None

# ── Configuração de ambiente ─────────────────────────────────────────────────
HERMES_HOME = os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))
os.environ["HERMES_HOME"] = HERMES_HOME

env_file = Path(HERMES_HOME) / ".env"
if env_file.exists():
    load_dotenv(env_file)

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
signal.signal(signal.SIGINT, _handle_signal)


# ── CronScheduler autossuficiente ────────────────────────────────────────────
class CronScheduler:
    def __init__(self, cron_dir: str = None):
        self.cron_dir = cron_dir or str(Path(HERMES_HOME) / "cron")
        self.jobs: list = []
        self.next_runs: dict = {}
        self._load_jobs()

    def _load_jobs(self):
        if not yaml:
            log.error("PyYAML não instalado. Instale: pip install pyyaml")
            return

        pattern = str(Path(self.cron_dir) / "*.yaml")
        for filepath in glob.glob(pattern):
            try:
                with open(filepath) as f:
                    job = yaml.safe_load(f)
                if job and job.get("enabled", True):
                    self.jobs.append(job)
                    log.info(f"Job carregado: {job['name']} ({job['schedule']})")
            except Exception as e:
                log.error(f"Erro ao carregar {filepath}: {e}")

    def _compute_next_runs(self):
        now = datetime.now()
        for job in self.jobs:
            name = job["name"]
            if name not in self.next_runs:
                if croniter:
                    self.next_runs[name] = croniter(job["schedule"], now).get_next(datetime)
                else:
                    # fallback: roda imediatamente na primeira vez
                    self.next_runs[name] = now

    def tick(self):
        now = datetime.now()
        for job in self.jobs:
            name = job["name"]
            next_run = self.next_runs.get(name)
            if next_run and now >= next_run:
                log.info(f"Disparando job: {name}")
                self._run_job(job)
                # Agenda próxima execução
                if croniter:
                    self.next_runs[name] = croniter(job["schedule"], now).get_next(datetime)
                else:
                    # fallback: 4 horas
                    from datetime import timedelta
                    self.next_runs[name] = now + timedelta(hours=4)

    def _run_job(self, job: dict):
        task = job.get("task", "")
        model = os.environ.get("MODEL") or job.get("model", "gpt-4.1-mini")
        max_iter = job.get("max_iterations", 20)

        output_dir = Path(HERMES_HOME) / "cron" / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"{job['name']}_{ts}.txt"

        cmd = self._build_command(task, model, max_iter)
        if not cmd:
            log.error("Nenhum executável hermes encontrado em /opt/hermes ou PATH.")
            return

        try:
            log.info(f"Executando: {cmd[0]} {cmd[1] if len(cmd) > 1 else ''} ...")

            # Stream output to both stdout (Railway logs) AND file
            with open(output_file, "w") as f:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env={**os.environ},
                )
                output_lines = []
                for line in proc.stdout:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    f.write(line)
                    output_lines.append(line)
                proc.wait(timeout=3600)

            if proc.returncode == 0:
                log.info(f"Job '{job['name']}' concluído → {output_file}")
            else:
                log.error(f"Job '{job['name']}' falhou (code {proc.returncode})")
                tail = "".join(output_lines[-50:])
                log.error(tail[-2000:])

        except subprocess.TimeoutExpired:
            log.error(f"Job '{job['name']}' timeout após 1 hora")
        except Exception as e:
            log.exception(f"Erro ao executar job '{job['name']}': {e}")

    def _build_command(self, task: str, model: str, max_iter: int) -> list:
        """Detecta o executável do hermes e monta o comando."""
        # 1. hermes no PATH (pip install -e . cria o entry point)
        if shutil.which("hermes"):
            return ["hermes", "run", "--task", task, "--model", model,
                    "--max-iterations", str(max_iter)]

        # 2. python -m hermes (quando o entry point não está no PATH)
        hermes_src = Path("/opt/hermes")
        if (hermes_src / "hermes").is_dir() or (hermes_src / "hermes.py").exists():
            return [sys.executable, "-m", "hermes", "run",
                    "--task", task, "--model", model,
                    "--max-iterations", str(max_iter)]

        # 3. script direto
        for candidate in [hermes_src / "main.py", hermes_src / "cli.py"]:
            if candidate.exists():
                return [sys.executable, str(candidate),
                        "run", "--task", task, "--model", model,
                        "--max-iterations", str(max_iter)]

        return []

    def start(self):
        self._compute_next_runs()
        log.info(f"Scheduler iniciado com {len(self.jobs)} job(s).")
        for name, next_run in self.next_runs.items():
            log.info(f"  → {name}: próxima execução em {next_run.strftime('%Y-%m-%d %H:%M:%S')}")

    def stop(self):
        log.info("Scheduler encerrado.")


# ── Referência global ao scheduler (para trigger manual via HTTP) ────────────
_scheduler: CronScheduler | None = None

# ── Painel web + health check (Railway exige porta aberta) ───────────────────
_DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hermes Daemon</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0;
         display: flex; align-items: center; justify-content: center; min-height: 100vh; }
  .card { background: #1e293b; border-radius: 12px; padding: 2rem; max-width: 420px;
          width: 90%; text-align: center; box-shadow: 0 4px 24px rgba(0,0,0,.4); }
  h1 { font-size: 1.4rem; margin-bottom: .5rem; }
  .status { color: #94a3b8; font-size: .85rem; margin-bottom: 1.5rem; }
  #go-btn { background: #22c55e; color: #fff; border: none; border-radius: 8px;
            padding: 14px 48px; font-size: 1.1rem; font-weight: 600; cursor: pointer;
            transition: background .2s; }
  #go-btn:hover { background: #16a34a; }
  #go-btn:disabled { background: #475569; cursor: wait; }
  #result { margin-top: 1rem; font-size: .85rem; color: #94a3b8; min-height: 1.2em; }
</style>
</head>
<body>
<div class="card">
  <h1>Hermes Daemon</h1>
  <p class="status" id="status">Pronto</p>
  <button id="go-btn" onclick="triggerRun()">GO</button>
  <p id="result"></p>
</div>
<script>
async function triggerRun() {
  const btn = document.getElementById('go-btn');
  const res = document.getElementById('result');
  const st  = document.getElementById('status');
  btn.disabled = true; btn.textContent = 'Executando...';
  st.textContent = 'Job disparado — aguarde...';
  res.textContent = '';
  try {
    const r = await fetch('/trigger', { method: 'POST' });
    const j = await r.json();
    st.textContent = j.status === 'ok' ? 'Concluído' : 'Erro';
    res.textContent = j.message || '';
  } catch(e) {
    st.textContent = 'Erro de conexão';
    res.textContent = e.toString();
  }
  btn.disabled = false; btn.textContent = 'GO';
}
</script>
</body>
</html>
"""


class _DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
            return
        # Painel principal
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(_DASHBOARD_HTML.encode())

    def do_POST(self):
        if self.path != "/trigger":
            self.send_response(404)
            self.end_headers()
            return

        import json
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        if _scheduler and _scheduler.jobs:
            try:
                log.info("[MANUAL] Trigger recebido via painel web")
                for job in _scheduler.jobs:
                    log.info(f"[MANUAL] Executando job: {job['name']}")
                    _scheduler._run_job(job)
                body = json.dumps({"status": "ok",
                    "message": f"{len(_scheduler.jobs)} job(s) executado(s)"})
            except Exception as e:
                log.exception(f"[MANUAL] Erro: {e}")
                body = json.dumps({"status": "error", "message": str(e)})
        else:
            body = json.dumps({"status": "error",
                "message": "Nenhum job carregado no scheduler"})
        self.wfile.write(body.encode())

    def log_message(self, format, *args):
        pass  # silencia logs de cada request


def _start_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), _DashboardHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log.info(f"Painel web na porta {port} (GET / = dashboard, POST /trigger = go)")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    global _scheduler
    _start_health_server()
    log.info("Hermes daemon iniciado.")
    log.info(f"HERMES_HOME = {HERMES_HOME}")

    if not yaml:
        log.error("PyYAML não instalado. pip install pyyaml")
        sys.exit(1)

    if not croniter:
        log.warning("croniter não instalado — próximas execuções em intervalos fixos de 4h.")

    _scheduler = CronScheduler()
    _scheduler.start()
    log.info("CronScheduler ativo — verificando jobs a cada 60s.")

    while _running:
        _scheduler.tick()
        time.sleep(60)

    _scheduler.stop()
    log.info("Daemon encerrado.")


if __name__ == "__main__":
    main()
