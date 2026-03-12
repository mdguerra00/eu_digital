"""
Hermes Demo — Aplicação web que demonstra o potencial do agente autônomo Hermes.

Roda sem dependências externas (sem OpenAI, sem Supabase).
Usa Flask para servir um painel interativo com:
  - Dashboard com status do agente
  - Visualização de skills
  - Simulação de ciclos de negócios
  - Log de atividades em tempo real
"""

import json
import os
import random
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# ── Estado em memória (simulado) ─────────────────────────────────────────────

AGENT_STATE = {
    "name": "EU_DE_NEGOCIOS",
    "status": "online",
    "mode": "simulation",
    "model": "gpt-4.1-mini",
    "uptime_start": datetime.now().isoformat(),
    "total_cycles": 0,
    "wallet": {
        "agent_balance": 0.0,
        "creator_balance": 0.0,
        "total_revenue": 0.0,
    },
    "memory": [],
    "activity_log": [],
}

# Skills carregadas do diretório hermes_deploy/skills (ou skills/ no container)
SKILLS = {}
_base = Path(__file__).parent
SKILLS_DIR = _base / "skills" if (_base / "skills").exists() else _base.parent / "hermes_deploy" / "skills"


def _load_skills():
    """Carrega skills .md do diretório hermes_deploy/skills."""
    if not SKILLS_DIR.exists():
        return
    for md_file in SKILLS_DIR.glob("*.md"):
        name = md_file.stem
        SKILLS[name] = {
            "name": name,
            "content": md_file.read_text(encoding="utf-8"),
            "loaded_at": datetime.now().isoformat(),
        }


_load_skills()

# ── Dados de simulação ───────────────────────────────────────────────────────

NICHES = [
    {"name": "Saúde & Bem-estar", "emoji": "💊", "potential": "alto"},
    {"name": "Finanças Pessoais", "emoji": "💰", "potential": "alto"},
    {"name": "Desenvolvimento Pessoal", "emoji": "🧠", "potential": "médio"},
    {"name": "Tecnologia & Cursos", "emoji": "💻", "potential": "alto"},
    {"name": "Relacionamentos", "emoji": "❤️", "potential": "médio"},
]

PLATFORMS = ["Hotmart", "Monetizze", "Eduzz", "Braip"]

SAMPLE_PRODUCTS = [
    {"name": "Curso de Investimentos 2026", "platform": "Hotmart", "commission": 45, "price": 297.0, "rating": 4.7, "niche": "Finanças Pessoais"},
    {"name": "Método Emagrecimento Natural", "platform": "Monetizze", "commission": 50, "price": 197.0, "rating": 4.5, "niche": "Saúde & Bem-estar"},
    {"name": "Masterclass Produtividade", "platform": "Eduzz", "commission": 40, "price": 147.0, "rating": 4.3, "niche": "Desenvolvimento Pessoal"},
    {"name": "Full Stack Python Pro", "platform": "Hotmart", "commission": 35, "price": 497.0, "rating": 4.8, "niche": "Tecnologia & Cursos"},
    {"name": "Inglês em 6 Meses", "platform": "Braip", "commission": 55, "price": 397.0, "rating": 4.6, "niche": "Desenvolvimento Pessoal"},
    {"name": "Renda Extra Digital", "platform": "Hotmart", "commission": 60, "price": 97.0, "rating": 4.2, "niche": "Finanças Pessoais"},
    {"name": "Fitplan Premium", "platform": "Monetizze", "commission": 42, "price": 247.0, "rating": 4.4, "niche": "Saúde & Bem-estar"},
    {"name": "Dev Mobile React Native", "platform": "Eduzz", "commission": 38, "price": 597.0, "rating": 4.9, "niche": "Tecnologia & Cursos"},
]

CYCLE_STEPS = [
    {"step": "memory_read", "label": "Lendo MEMORY.md", "tool": "file_read", "duration_ms": 200},
    {"step": "web_search", "label": "Pesquisando oportunidades", "tool": "web_search", "duration_ms": 1500},
    {"step": "analyze", "label": "Analisando produtos", "tool": "market_analyzer", "duration_ms": 800},
    {"step": "select", "label": "Selecionando melhor produto", "tool": "reasoning", "duration_ms": 600},
    {"step": "action", "label": "Executando ação concreta", "tool": "content_gen", "duration_ms": 1200},
    {"step": "memory_write", "label": "Atualizando MEMORY.md", "tool": "file_write", "duration_ms": 300},
    {"step": "receipt", "label": "Registrando receipt", "tool": "execution_receipt", "duration_ms": 150},
]


def _log(message: str, level: str = "INFO"):
    entry = {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "level": level,
        "message": message,
    }
    AGENT_STATE["activity_log"].append(entry)
    # Manter últimas 100 entradas
    if len(AGENT_STATE["activity_log"]) > 100:
        AGENT_STATE["activity_log"] = AGENT_STATE["activity_log"][-100:]


def _simulate_revenue():
    """Simula uma receita de comissão."""
    product = random.choice(SAMPLE_PRODUCTS)
    commission_value = round(product["price"] * product["commission"] / 100, 2)
    creator_share = round(commission_value * 0.80, 2)
    agent_share = round(commission_value * 0.20, 2)

    AGENT_STATE["wallet"]["total_revenue"] += commission_value
    AGENT_STATE["wallet"]["creator_balance"] += creator_share
    AGENT_STATE["wallet"]["agent_balance"] += agent_share

    return {
        "product": product["name"],
        "platform": product["platform"],
        "commission_value": commission_value,
        "creator_share": creator_share,
        "agent_share": agent_share,
    }


# ── Rotas ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    """Retorna estado atual do agente."""
    return jsonify({
        "agent": {
            "name": AGENT_STATE["name"],
            "status": AGENT_STATE["status"],
            "mode": AGENT_STATE["mode"],
            "model": AGENT_STATE["model"],
            "total_cycles": AGENT_STATE["total_cycles"],
            "uptime_start": AGENT_STATE["uptime_start"],
        },
        "wallet": AGENT_STATE["wallet"],
        "skills_count": len(SKILLS),
        "memory_entries": len(AGENT_STATE["memory"]),
        "log_entries": len(AGENT_STATE["activity_log"]),
    })


@app.route("/api/skills")
def api_skills():
    """Retorna skills carregadas."""
    return jsonify(list(SKILLS.values()))


@app.route("/api/niches")
def api_niches():
    """Retorna nichos disponíveis para pesquisa."""
    return jsonify(NICHES)


@app.route("/api/products")
def api_products():
    """Retorna produtos de afiliado simulados."""
    niche = request.args.get("niche")
    if niche:
        filtered = [p for p in SAMPLE_PRODUCTS if p["niche"] == niche]
        return jsonify(filtered)
    return jsonify(SAMPLE_PRODUCTS)


@app.route("/api/cycle/run", methods=["POST"])
def api_run_cycle():
    """Simula execução de um ciclo completo do Hermes."""
    run_id = str(uuid.uuid4())[:8]
    AGENT_STATE["total_cycles"] += 1
    cycle_num = AGENT_STATE["total_cycles"]

    _log(f"Ciclo #{cycle_num} iniciado (run_id: {run_id})")

    steps_result = []
    for step in CYCLE_STEPS:
        started = datetime.now()
        # Simula latência
        time.sleep(step["duration_ms"] / 5000)  # Acelerado 5x para demo
        finished = datetime.now()

        result = {
            "step": step["step"],
            "label": step["label"],
            "tool": step["tool"],
            "status": "success",
            "latency_ms": step["duration_ms"] + random.randint(-50, 100),
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
        }

        # Adicionar detalhes específicos por step
        if step["step"] == "web_search":
            niche = random.choice(NICHES)
            result["detail"] = f"Pesquisou '{niche['name']}' em {random.choice(PLATFORMS)}"
        elif step["step"] == "select":
            product = random.choice(SAMPLE_PRODUCTS)
            result["detail"] = f"Selecionou: {product['name']} ({product['commission']}% comissão)"
        elif step["step"] == "action":
            actions = [
                "Gerou artigo de review para blog",
                "Criou post para redes sociais",
                "Montou comparativo de produtos",
                "Redigiu email marketing",
            ]
            result["detail"] = random.choice(actions)

        steps_result.append(result)
        _log(f"  [{step['tool']}] {step['label']} — OK ({result['latency_ms']}ms)")

    # Chance de gerar receita (30%)
    revenue = None
    if random.random() < 0.3:
        revenue = _simulate_revenue()
        _log(f"  💰 Comissão gerada: R${revenue['commission_value']:.2f} ({revenue['product']})", "SUCCESS")

    # Salvar na memória
    memory_entry = {
        "cycle": cycle_num,
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "steps": len(steps_result),
        "revenue": revenue,
        "summary": f"Ciclo #{cycle_num} executado com {len(steps_result)} etapas",
    }
    AGENT_STATE["memory"].append(memory_entry)
    if len(AGENT_STATE["memory"]) > 50:
        AGENT_STATE["memory"] = AGENT_STATE["memory"][-50:]

    _log(f"Ciclo #{cycle_num} finalizado com sucesso")

    return jsonify({
        "run_id": run_id,
        "cycle_number": cycle_num,
        "steps": steps_result,
        "revenue": revenue,
        "wallet": AGENT_STATE["wallet"],
    })


@app.route("/api/log")
def api_log():
    """Retorna log de atividades."""
    limit = request.args.get("limit", 50, type=int)
    return jsonify(AGENT_STATE["activity_log"][-limit:])


@app.route("/api/memory")
def api_memory():
    """Retorna entradas de memória do agente."""
    return jsonify(AGENT_STATE["memory"])


@app.route("/api/architecture")
def api_architecture():
    """Retorna diagrama da arquitetura do Hermes."""
    return jsonify({
        "components": [
            {"id": "daemon", "label": "Hermes Daemon", "type": "core", "desc": "Scheduler autônomo com cron jobs"},
            {"id": "llm", "label": "GPT-4.1-mini", "type": "external", "desc": "Motor de raciocínio (OpenAI)"},
            {"id": "skills", "label": "Skills Engine", "type": "core", "desc": "Conhecimento persistente em .md"},
            {"id": "memory", "label": "MEMORY.md", "type": "storage", "desc": "Memória de longo prazo"},
            {"id": "web", "label": "Web Search", "type": "tool", "desc": "Perplexity / DuckDuckGo"},
            {"id": "supabase", "label": "Supabase", "type": "external", "desc": "PostgreSQL + audit trail"},
            {"id": "receipts", "label": "Execution Receipts", "type": "storage", "desc": "Telemetria imutável"},
            {"id": "wallet", "label": "Wallet", "type": "core", "desc": "Controle financeiro 80/20"},
        ],
        "connections": [
            {"from": "daemon", "to": "llm", "label": "reasoning"},
            {"from": "llm", "to": "skills", "label": "load/create"},
            {"from": "llm", "to": "web", "label": "search"},
            {"from": "llm", "to": "memory", "label": "read/write"},
            {"from": "daemon", "to": "supabase", "label": "persist"},
            {"from": "daemon", "to": "receipts", "label": "audit"},
            {"from": "daemon", "to": "wallet", "label": "track"},
        ],
    })


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _log("Hermes Demo iniciado")
    _log(f"{len(SKILLS)} skills carregadas: {', '.join(SKILLS.keys())}")
    port = int(os.environ.get("PORT", 5050))
    print(f"\n  🔱 Hermes Demo — http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=(port == 5050))
