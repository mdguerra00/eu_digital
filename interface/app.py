#!/usr/bin/env python3
"""
Dashboard da interface para monitorar e interagir com o agente EU_DE_NEGOCIOS.

Uso local:
    OPENAI_API_KEY=... SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... \\
    python interface/app.py

Porta padrão: 5000 (configurável via DASHBOARD_PORT)
"""
from __future__ import annotations

import json
import os
import queue
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

# ──────────────────────────────────────────────────────────────────────────────
# Supabase (opcional — fallback local se ausente)
# ──────────────────────────────────────────────────────────────────────────────
_sb: Optional[Any] = None
try:
    from supabase import create_client  # type: ignore
    _url = os.environ.get("SUPABASE_URL", "")
    _key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY", "")
    )
    if _url and _key:
        _sb = create_client(_url, _key)
        print(f"[DASHBOARD] Supabase conectado: {_url}")
    else:
        print("[DASHBOARD] Supabase não configurado. Usando fallback JSON local.")
except Exception as _e:
    print(f"[DASHBOARD] Supabase indisponível: {_e}")

sb = _sb

# ──────────────────────────────────────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────────────────────────────────────
AGENT_NAME = os.environ.get("AGENT_NAME", "EU_DE_NEGOCIOS")
TABLE = os.environ.get("AGENT_CYCLES_TABLE", "agent_cycles")
STATE_TABLE = os.environ.get("AGENT_STATE_TABLE", "agent_state")
RECEIPTS_TABLE = os.environ.get("EXECUTION_RECEIPTS_TABLE", "execution_receipts")
CREATOR_MESSAGES_TABLE = os.environ.get("CREATOR_MESSAGES_TABLE", "creator_messages")
WALLET_BALANCE_TABLE = "agent_wallet_balance"
WALLET_TX_TABLE = "agent_wallet_transactions"
ALERTS_TABLE = "system_alerts"
AUDIT_LOG_TABLE = "audit_log"
PERFORMANCE_METRICS_TABLE = "performance_metrics"
SERVICE_HEALTH_TABLE = "service_health"
AFFILIATE_LINKS_TABLE = "affiliate_links"

# Diretório raiz do projeto (parent de interface/)
BASE_DIR = Path(__file__).resolve().parent.parent

app = Flask(__name__, template_folder="templates")
app.config["JSON_ENSURE_ASCII"] = False
app.config["JSON_SORT_KEYS"] = False


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path, default: Any = None) -> Any:
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def _write_json(path: Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ──────────────────────────────────────────────────────────────────────────────
# Data access — Ciclos
# ──────────────────────────────────────────────────────────────────────────────
def get_cycles(limit: int = 20) -> List[Dict]:
    if sb is not None:
        try:
            res = (
                sb.table(TABLE)
                .select(
                    "id, created_at, cycle_number, run_id, focus, task_prompt, "
                    "result_text, reflection, next_actions, notes"
                )
                .eq("agent_name", AGENT_NAME)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return res.data or []
        except Exception as e:
            print(f"[WARN] get_cycles Supabase: {e}")

    # Fallback local
    cycles = _read_json(BASE_DIR / "agent_cycles.json", [])
    filtered = [c for c in cycles if c.get("agent_name") == AGENT_NAME]
    return sorted(filtered, key=lambda x: x.get("created_at", ""), reverse=True)[:limit]


def get_cycle_by_id(cycle_id: Any) -> Optional[Dict]:
    if sb is not None:
        try:
            res = (
                sb.table(TABLE)
                .select("*")
                .eq("id", cycle_id)
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]
        except Exception as e:
            print(f"[WARN] get_cycle_by_id Supabase: {e}")

    cycles = _read_json(BASE_DIR / "agent_cycles.json", [])
    for c in cycles:
        if str(c.get("id")) == str(cycle_id):
            return c
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Data access — Status do agente
# ──────────────────────────────────────────────────────────────────────────────
def get_status() -> Dict:
    cycles = get_cycles(limit=1)
    last_cycle = cycles[0] if cycles else None

    current_prompt = ""
    if sb is not None:
        try:
            res = (
                sb.table(STATE_TABLE)
                .select("current_task_prompt, updated_at")
                .eq("agent_name", AGENT_NAME)
                .limit(1)
                .execute()
            )
            if res.data:
                current_prompt = res.data[0].get("current_task_prompt", "")
        except Exception:
            pass

    if not current_prompt:
        state = _read_json(BASE_DIR / "agent_state.json", {})
        current_prompt = state.get("current_task_prompt", "")

    # Feedback atual do criador
    feedback = _read_json(BASE_DIR / "creator_feedback.json", {})
    creator_feedback = feedback.get("feedback", "") if feedback else ""

    return {
        "agent_name": AGENT_NAME,
        "last_cycle": last_cycle,
        "current_task_prompt": current_prompt,
        "creator_feedback": creator_feedback,
        "supabase_connected": sb is not None,
        "timestamp": utc_now_iso(),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Data access — Carteira
# ──────────────────────────────────────────────────────────────────────────────
def get_wallet() -> Dict:
    if sb is not None:
        try:
            res = (
                sb.table(WALLET_BALANCE_TABLE)
                .select("*")
                .eq("agent_name", AGENT_NAME)
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]
        except Exception as e:
            print(f"[WARN] get_wallet Supabase: {e}")

    wallet = _read_json(BASE_DIR / "agent_wallet.json", {})
    return {
        "agent_balance": wallet.get("agent_balance", 0.0),
        "creator_balance": wallet.get("creator_balance", 0.0),
        "total_revenue": wallet.get("total_revenue", 0.0),
        "total_expenses": wallet.get("total_expenses", 0.0),
        "minimum_reserve": wallet.get("minimum_reserve", 0.0),
    }


def get_transactions(limit: int = 20) -> List[Dict]:
    if sb is not None:
        try:
            res = (
                sb.table(WALLET_TX_TABLE)
                .select("*")
                .eq("agent_name", AGENT_NAME)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return res.data or []
        except Exception as e:
            print(f"[WARN] get_transactions Supabase: {e}")
    return []


# ──────────────────────────────────────────────────────────────────────────────
# Data access — Mensagens do Criador
# ──────────────────────────────────────────────────────────────────────────────
def get_messages(limit: int = 100) -> List[Dict]:
    if sb is not None:
        try:
            res = (
                sb.table(CREATOR_MESSAGES_TABLE)
                .select("id, message, priority, status, created_at, author, processed_at, cycle_number")
                .eq("agent_name", AGENT_NAME)
                .order("created_at", desc=False)
                .limit(limit)
                .execute()
            )
            return res.data or []
        except Exception as e:
            print(f"[WARN] get_messages Supabase: {e}")

    msgs = _read_json(BASE_DIR / "creator_messages.json", [])
    return sorted(msgs, key=lambda x: x.get("created_at", ""))[-limit:]


def send_message(message: str, priority: str = "normal") -> Dict:
    payload = {
        "agent_name": AGENT_NAME,
        "message": message,
        "priority": priority,
        "status": "pending",
        "author": "Criador",
        "created_at": utc_now_iso(),
    }

    if sb is not None:
        try:
            res = sb.table(CREATOR_MESSAGES_TABLE).insert(payload).execute()
            if res.data:
                saved = res.data[0]
                _broadcast({"type": "new_message", "data": saved})
                return {"success": True, "data": saved}
        except Exception as e:
            print(f"[WARN] send_message Supabase: {e}")

    # Fallback local
    msgs_path = BASE_DIR / "creator_messages.json"
    msgs = _read_json(msgs_path, [])
    payload["id"] = len(msgs) + 1
    msgs.append(payload)
    try:
        _write_json(msgs_path, msgs)
    except Exception as e:
        return {"success": False, "error": str(e)}

    # Compatibilidade: atualiza creator_feedback.json (lido pelo main.py como fallback)
    try:
        _write_json(BASE_DIR / "creator_feedback.json", {
            "feedback": message,
            "author": "Criador",
            "timestamp": utc_now_iso(),
        })
    except Exception:
        pass

    _broadcast({"type": "new_message", "data": payload})
    return {"success": True, "data": payload}


# ──────────────────────────────────────────────────────────────────────────────
# Data access — Recibos de execução
# ──────────────────────────────────────────────────────────────────────────────
def get_receipts(limit: int = 30) -> List[Dict]:
    if sb is not None:
        try:
            res = (
                sb.table(RECEIPTS_TABLE)
                .select(
                    "id, cycle_number, step_id, tool, status, "
                    "started_at, finished_at, latency_ms, used_fallback, evidence_hash"
                )
                .order("started_at", desc=True)
                .limit(limit)
                .execute()
            )
            return res.data or []
        except Exception as e:
            print(f"[WARN] get_receipts Supabase: {e}")

    receipts_path = BASE_DIR / "execution_receipts.jsonl"
    if receipts_path.exists():
        try:
            receipts = []
            with open(receipts_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            receipts.append(json.loads(line))
                        except Exception:
                            continue
            return list(reversed(receipts[-limit:]))
        except Exception:
            pass
    return []


# ──────────────────────────────────────────────────────────────────────────────
# SSE — Server-Sent Events (broadcast em tempo real)
# ──────────────────────────────────────────────────────────────────────────────
_sse_clients: List[queue.Queue] = []
_sse_lock = threading.Lock()


def _broadcast(data: Dict) -> None:
    with _sse_lock:
        dead = []
        for q in _sse_clients:
            try:
                q.put_nowait(data)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_clients.remove(q)


def _poller_loop() -> None:
    """Thread de background: detecta novos ciclos a cada 30s e faz broadcast."""
    time.sleep(5)
    last_id: Optional[Any] = None

    while True:
        try:
            cycles = get_cycles(limit=1)
            if cycles:
                cid = cycles[0].get("id")
                if cid is not None and cid != last_id:
                    if last_id is not None:
                        _broadcast({"type": "new_cycle", "data": cycles[0]})
                    last_id = cid
        except Exception as e:
            print(f"[SSE poller] {e}")
        time.sleep(30)


threading.Thread(target=_poller_loop, daemon=True, name="sse-poller").start()


# ──────────────────────────────────────────────────────────────────────────────
# Rotas Flask
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("dashboard.html", agent_name=AGENT_NAME)


@app.route("/pro")
def pro():
    return render_template("enhanced.html", agent_name=AGENT_NAME)


@app.route("/classic")
def classic():
    return render_template("index.html", agent_name=AGENT_NAME)


@app.route("/api/status")
def api_status():
    return jsonify(get_status())


@app.route("/api/cycles")
def api_cycles():
    limit = min(int(request.args.get("limit", 20)), 100)
    return jsonify(get_cycles(limit=limit))


@app.route("/api/cycles/<cycle_id>")
def api_cycle_detail(cycle_id: str):
    cycle = get_cycle_by_id(cycle_id)
    if cycle is None:
        return jsonify({"error": "Ciclo não encontrado"}), 404
    return jsonify(cycle)


@app.route("/api/wallet")
def api_wallet():
    return jsonify(get_wallet())


@app.route("/api/transactions")
def api_transactions():
    limit = min(int(request.args.get("limit", 20)), 100)
    return jsonify(get_transactions(limit=limit))


@app.route("/api/messages", methods=["GET"])
def api_get_messages():
    limit = min(int(request.args.get("limit", 100)), 500)
    return jsonify(get_messages(limit=limit))


@app.route("/api/messages", methods=["POST"])
def api_send_message():
    body = request.get_json(force=True) or {}
    msg = (body.get("message") or "").strip()
    priority = body.get("priority", "normal")
    if not msg:
        return jsonify({"success": False, "error": "Mensagem vazia"}), 400
    if priority not in ("normal", "high", "urgent"):
        priority = "normal"
    return jsonify(send_message(msg, priority))


@app.route("/api/receipts")
def api_receipts():
    limit = min(int(request.args.get("limit", 30)), 100)
    return jsonify(get_receipts(limit=limit))


@app.route("/events")
def sse():
    client_q: queue.Queue = queue.Queue(maxsize=50)
    with _sse_lock:
        _sse_clients.append(client_q)

    def generate():
        # Sinal inicial de conexão
        yield f"data: {json.dumps({'type': 'connected', 'agent': AGENT_NAME})}\n\n"
        try:
            while True:
                try:
                    event = client_q.get(timeout=25)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    # Heartbeat para manter a conexão viva
                    yield 'data: {"type":"heartbeat"}\n\n'
        finally:
            with _sse_lock:
                if client_q in _sse_clients:
                    _sse_clients.remove(client_q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# Alerts and Health Monitoring
# ──────────────────────────────────────────────────────────────────────────────
def get_alerts(limit: int = 50) -> List[Dict]:
    if sb is not None:
        try:
            res = (
                sb.table(ALERTS_TABLE)
                .select("*")
                .eq("agent_name", AGENT_NAME)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return res.data or []
        except Exception as e:
            print(f"[WARN] get_alerts: {e}")
    return []


def get_service_health() -> List[Dict]:
    if sb is not None:
        try:
            res = (
                sb.table(SERVICE_HEALTH_TABLE)
                .select("*")
                .order("updated_at", desc=True)
                .execute()
            )
            return res.data or []
        except Exception as e:
            print(f"[WARN] get_service_health: {e}")
    return []


def get_audit_log(limit: int = 100) -> List[Dict]:
    if sb is not None:
        try:
            res = (
                sb.table(AUDIT_LOG_TABLE)
                .select("*")
                .eq("agent_name", AGENT_NAME)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return res.data or []
        except Exception as e:
            print(f"[WARN] get_audit_log: {e}")
    return []


def get_performance_metrics(metric_type: Optional[str] = None, limit: int = 100) -> List[Dict]:
    if sb is not None:
        try:
            query = (
                sb.table(PERFORMANCE_METRICS_TABLE)
                .select("*")
                .eq("agent_name", AGENT_NAME)
            )
            if metric_type:
                query = query.eq("metric_type", metric_type)
            res = query.order("created_at", desc=True).limit(limit).execute()
            return res.data or []
        except Exception as e:
            print(f"[WARN] get_performance_metrics: {e}")
    return []


def log_audit_action(action: str, resource_type: str = "", resource_id: str = "", changes: Dict = None) -> bool:
    if sb is None:
        return False
    try:
        sb.table(AUDIT_LOG_TABLE).insert({
            "agent_name": AGENT_NAME,
            "action": action,
            "actor": "user",
            "resource_type": resource_type,
            "resource_id": resource_id,
            "changes": changes or {},
            "created_at": utc_now_iso(),
        }).execute()
        return True
    except Exception as e:
        print(f"[WARN] log_audit_action: {e}")
        return False


# ──────────────────────────────────────────────────────────────────────────────
# API Routes — Control & Configuration
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/alerts", methods=["GET"])
def api_alerts():
    limit = min(int(request.args.get("limit", 50)), 200)
    return jsonify(get_alerts(limit=limit))


@app.route("/api/alerts/<alert_id>/resolve", methods=["POST"])
def api_resolve_alert(alert_id: str):
    if sb is None:
        return jsonify({"success": False, "error": "Supabase não configurado"}), 503
    try:
        sb.table(ALERTS_TABLE).update({
            "resolved": True,
            "resolved_at": utc_now_iso(),
        }).eq("id", alert_id).execute()
        log_audit_action("alert_resolved", "alert", alert_id)
        _broadcast({"type": "alert_resolved", "alert_id": alert_id})
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify(get_service_health())


@app.route("/api/audit-log", methods=["GET"])
def api_audit_log():
    limit = min(int(request.args.get("limit", 100)), 500)
    return jsonify(get_audit_log(limit=limit))


@app.route("/api/metrics", methods=["GET"])
def api_metrics():
    metric_type = request.args.get("type")
    limit = min(int(request.args.get("limit", 100)), 500)
    return jsonify(get_performance_metrics(metric_type=metric_type, limit=limit))


@app.route("/api/config", methods=["GET"])
def api_get_config():
    return jsonify({
        "agent_name": AGENT_NAME,
        "model": os.environ.get("MODEL", "gpt-4.1-mini"),
        "temperature": float(os.environ.get("TEMPERATURE", "0.7")),
        "loop_interval_minutes": int(os.environ.get("LOOP_INTERVAL_MINUTES", "20")),
        "memory_window": int(os.environ.get("MEMORY_WINDOW", "10")),
        "agent_mode": os.environ.get("AGENT_MODE", "real"),
        "supabase_connected": sb is not None,
    })


@app.route("/api/config/prompt", methods=["PUT"])
def api_update_prompt():
    body = request.get_json(force=True) or {}
    new_prompt = (body.get("prompt") or "").strip()
    if not new_prompt:
        return jsonify({"success": False, "error": "Prompt vazio"}), 400

    if sb is None:
        return jsonify({"success": False, "error": "Supabase não configurado"}), 503

    try:
        sb.table(STATE_TABLE).upsert({
            "agent_name": AGENT_NAME,
            "current_task_prompt": new_prompt,
            "updated_at": utc_now_iso(),
        }).execute()
        log_audit_action("prompt_updated", "agent_state", AGENT_NAME, {"new_prompt": new_prompt[:100]})
        _broadcast({"type": "prompt_changed", "prompt": new_prompt})
        return jsonify({"success": True, "prompt": new_prompt})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/control/pause", methods=["POST"])
def api_pause_agent():
    if sb is None:
        return jsonify({"success": False, "error": "Supabase não configurado"}), 503
    try:
        sb.table(STATE_TABLE).upsert({
            "agent_name": AGENT_NAME,
            "agent_paused": True,
            "updated_at": utc_now_iso(),
        }).execute()
        log_audit_action("agent_paused", "agent_state", AGENT_NAME)
        _broadcast({"type": "agent_paused"})
        return jsonify({"success": True, "status": "paused"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/control/resume", methods=["POST"])
def api_resume_agent():
    if sb is None:
        return jsonify({"success": False, "error": "Supabase não configurado"}), 503
    try:
        sb.table(STATE_TABLE).upsert({
            "agent_name": AGENT_NAME,
            "agent_paused": False,
            "updated_at": utc_now_iso(),
        }).execute()
        log_audit_action("agent_resumed", "agent_state", AGENT_NAME)
        _broadcast({"type": "agent_resumed"})
        return jsonify({"success": True, "status": "running"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# API Routes — Affiliate Management
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/api/affiliates", methods=["GET"])
def api_get_affiliates():
    if sb is None:
        return jsonify([]), 200
    try:
        active_only = request.args.get("active_only", "false").lower() == "true"
        query = sb.table(AFFILIATE_LINKS_TABLE).select("*")
        if active_only:
            query = query.eq("active", True)
        res = query.order("commission_pct", desc=True).execute()
        return jsonify(res.data or [])
    except Exception as e:
        print(f"[WARN] get_affiliates: {e}")
        return jsonify([]), 200


@app.route("/api/affiliates", methods=["POST"])
def api_create_affiliate():
    if sb is None:
        return jsonify({"success": False, "error": "Supabase não configurado"}), 503
    body = request.get_json(force=True) or {}
    try:
        link_data = {
            "agent_name": AGENT_NAME,
            "product_name": body.get("product_name", "").strip(),
            "platform": body.get("platform", "").strip(),
            "niche": body.get("niche", "").strip(),
            "hotlink": body.get("hotlink", "").strip(),
            "commission_pct": float(body.get("commission_pct", 0)),
            "price_brl": float(body.get("price_brl", 0)),
            "rating": float(body.get("rating", 0)),
            "active": body.get("active", True),
            "notes": body.get("notes", "").strip(),
            "created_at": utc_now_iso(),
        }

        res = sb.table(AFFILIATE_LINKS_TABLE).insert(link_data).execute()
        if res.data:
            log_audit_action("affiliate_added", "affiliate_links", res.data[0].get("id"), link_data)
            _broadcast({"type": "affiliate_added", "data": res.data[0]})
            return jsonify({"success": True, "data": res.data[0]}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/affiliates/<link_id>", methods=["PUT"])
def api_update_affiliate(link_id: str):
    if sb is None:
        return jsonify({"success": False, "error": "Supabase não configurado"}), 503
    body = request.get_json(force=True) or {}
    try:
        update_data = {}
        if "product_name" in body:
            update_data["product_name"] = body["product_name"].strip()
        if "niche" in body:
            update_data["niche"] = body["niche"].strip()
        if "commission_pct" in body:
            update_data["commission_pct"] = float(body["commission_pct"])
        if "active" in body:
            update_data["active"] = bool(body["active"])
        if "notes" in body:
            update_data["notes"] = body["notes"].strip()

        update_data["updated_at"] = utc_now_iso()

        res = sb.table(AFFILIATE_LINKS_TABLE).update(update_data).eq("id", link_id).execute()
        if res.data:
            log_audit_action("affiliate_updated", "affiliate_links", link_id, update_data)
            _broadcast({"type": "affiliate_updated", "id": link_id})
            return jsonify({"success": True, "data": res.data[0]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/affiliates/<link_id>", methods=["DELETE"])
def api_delete_affiliate(link_id: str):
    if sb is None:
        return jsonify({"success": False, "error": "Supabase não configurado"}), 503
    try:
        sb.table(AFFILIATE_LINKS_TABLE).delete().eq("id", link_id).execute()
        log_audit_action("affiliate_deleted", "affiliate_links", link_id)
        _broadcast({"type": "affiliate_deleted", "id": link_id})
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", os.environ.get("DASHBOARD_PORT", "5000")))
    debug = os.environ.get("DASHBOARD_DEBUG", "").lower() in ("1", "true")
    print(f"[DASHBOARD] Iniciando em http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
