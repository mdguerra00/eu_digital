import os
import uuid
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from supabase import create_client, Client
from openai import OpenAI


# -----------------------------
# Config
# -----------------------------
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_ANON_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

TABLE = os.environ.get("AGENT_CYCLES_TABLE", "agent_cycles")

AGENT_NAME = os.environ.get("AGENT_NAME", "EU_DE_NEGOCIOS")
FOCUS = os.environ.get("FOCUS", "Auto-aprimoramento interno")

# ESTA env var era o que faltou no Railway; mas mesmo sem ela, o código não deixa NULL
TASK_PROMPT_ENV = os.environ.get("TASK_PROMPT", "").strip()

MEMORY_WINDOW = int(os.environ.get("MEMORY_WINDOW", "10"))
MODEL = os.environ.get("MODEL", "gpt-4.1-mini")

TEMPERATURE = float(os.environ.get("TEMPERATURE", "0.4"))
REQUEST_TIMEOUT_S = float(os.environ.get("REQUEST_TIMEOUT_S", "60"))

# --- Mapeamento de colunas (para bater com seu schema) ---
# Seu erro atual prova que esta coluna existe e é NOT NULL:
RESULT_COL = os.environ.get("RESULT_COL", "result_text")
TASK_PROMPT_COL = os.environ.get("TASK_PROMPT_COL", "task_prompt")

# Se seu schema usar outros nomes, ajuste via env:
REFLECTION_COL = os.environ.get("REFLECTION_COL", "reflection")      # ex: "reflection_text"
NEXT_ACTIONS_COL = os.environ.get("NEXT_ACTIONS_COL", "next_actions") # ex: "next_actions_text"

# Campos básicos comuns
CREATED_AT_COL = os.environ.get("CREATED_AT_COL", "created_at")
AGENT_NAME_COL = os.environ.get("AGENT_NAME_COL", "agent_name")
RUN_ID_COL = os.environ.get("RUN_ID_COL", "run_id")
CYCLE_NUMBER_COL = os.environ.get("CYCLE_NUMBER_COL", "cycle_number")
FOCUS_COL = os.environ.get("FOCUS_COL", "focus")


# -----------------------------
# Clients
# -----------------------------
sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
oa = OpenAI(api_key=OPENAI_API_KEY)


# -----------------------------
# Helpers
# -----------------------------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_recent_cycles(agent_name: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Busca ciclos anteriores. Faz select só de colunas prováveis/parametrizáveis.
    Se alguma coluna não existir no seu schema, ajuste pelas env vars acima.
    """
    select_cols = [
        "id",
        CREATED_AT_COL,
        AGENT_NAME_COL,
        RUN_ID_COL,
        CYCLE_NUMBER_COL,
        FOCUS_COL,
        TASK_PROMPT_COL,
        RESULT_COL,
        REFLECTION_COL,
        NEXT_ACTIONS_COL,
    ]
    # PostgREST aceita string "a,b,c"
    res = (
        sb.table(TABLE)
        .select(", ".join(select_cols))
        .eq(AGENT_NAME_COL, agent_name)
        .order(CYCLE_NUMBER_COL, desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def summarize_memory(cycles: List[Dict[str, Any]]) -> str:
    if not cycles:
        return "Nenhum ciclo anterior encontrado."

    cycles_sorted = list(reversed(cycles))
    lines: List[str] = []

    for c in cycles_sorted:
        cn = c.get(CYCLE_NUMBER_COL)
        created = c.get(CREATED_AT_COL, "")
        focus = (c.get(FOCUS_COL) or "").strip()
        tp = (c.get(TASK_PROMPT_COL) or "").strip()
        result = (c.get(RESULT_COL) or "").strip()
        refl = (c.get(REFLECTION_COL) or "").strip()
        nxt = (c.get(NEXT_ACTIONS_COL) or "").strip()

        def trunc(s: str, n: int) -> str:
            return (s[:n] + "…") if len(s) > n else s

        lines.append(
            f"- Ciclo {cn} ({created}):\n"
            f"  Focus: {trunc(focus, 140) or '[vazio]'}\n"
            f"  Task: {trunc(tp, 180) or '[vazio]'}\n"
            f"  Result: {trunc(result, 380) or '[vazio]'}\n"
            f"  Reflection: {trunc(refl, 280) or '[vazio]'}\n"
            f"  Next: {trunc(nxt, 280) or '[vazio]'}"
        )

    return "\n".join(lines)


def get_next_cycle_number(agent_name: str) -> int:
    res = (
        sb.table(TABLE)
        .select(CYCLE_NUMBER_COL)
        .eq(AGENT_NAME_COL, agent_name)
        .order(CYCLE_NUMBER_COL, desc=True)
        .limit(1)
        .execute()
    )
    if res.data and res.data[0].get(CYCLE_NUMBER_COL) is not None:
        return int(res.data[0][CYCLE_NUMBER_COL]) + 1
    return 1


def write_cycle(row: Dict[str, Any]) -> Dict[str, Any]:
    res = sb.table(TABLE).insert(row).execute()
    if not res.data:
        raise RuntimeError(f"Insert falhou (sem data retornada). Response: {res}")
    return res.data[0]


def _extract_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise RuntimeError(f"Resposta não-JSON do modelo:\n{text}")
        return json.loads(text[start : end + 1])


def llm_cycle(memory_summary: str, focus: str, task_prompt: str, cycle_number: int) -> Dict[str, str]:
    system = (
        "Você é um agente autônomo que evolui por ciclos. "
        "A cada ciclo, você deve: (1) produzir um RESULT útil, "
        "(2) refletir sobre melhorias e (3) definir próximos passos. "
        "Seja específico, conciso e incremental. Não reescreva tudo do zero."
    )

    user = f"""
AGENTE: {AGENT_NAME}
FOCO: {focus}
CICLO: {cycle_number}

TASK_PROMPT:
{task_prompt}

MEMÓRIA (resumo dos últimos ciclos):
{memory_summary}

Entregue JSON puro no formato:
{{
  "result_text": "...",
  "reflection": "...",
  "next_actions": "..."
}}
"""

    resp = oa.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=TEMPERATURE,
        timeout=REQUEST_TIMEOUT_S,
    )

    content = (resp.choices[0].message.content or "").strip()
    data = _extract_json(content)

    result_text = (data.get("result_text") or "").strip()
    reflection = (data.get("reflection") or "").strip()
    next_actions = (data.get("next_actions") or "").strip()

    # Fallbacks (NUNCA deixar NULL/vazio demais)
    if not result_text:
        result_text = "Sem result_text (fallback): o modelo não retornou conteúdo."
    if not reflection:
        reflection = "Sem reflection (fallback): o modelo não retornou conteúdo."
    if not next_actions:
        next_actions = "Sem next_actions (fallback): o modelo não retornou conteúdo."

    return {"result_text": result_text, "reflection": reflection, "next_actions": next_actions}


def run_once(run_id: str) -> Dict[str, Any]:
    # TASK_PROMPT é NOT NULL no seu schema anterior; agora garantimos sempre preenchido
    task_prompt = TASK_PROMPT_ENV or "Rodar um ciclo de reflexão e auto-aprimoramento do agente (default)"

    recent = fetch_recent_cycles(AGENT_NAME, limit=MEMORY_WINDOW)
    memory_summary = summarize_memory(recent)

    cycle_number = get_next_cycle_number(AGENT_NAME)

    llm_out = llm_cycle(
        memory_summary=memory_summary,
        focus=FOCUS,
        task_prompt=task_prompt,
        cycle_number=cycle_number,
    )

    # Monta row usando NOMES DE COLUNA DO SEU SCHEMA
    row: Dict[str, Any] = {
        CREATED_AT_COL: utc_now_iso(),   # se sua tabela já tem default, pode remover
        AGENT_NAME_COL: AGENT_NAME,
        RUN_ID_COL: run_id,
        CYCLE_NUMBER_COL: cycle_number,
        FOCUS_COL: FOCUS,
        TASK_PROMPT_COL: task_prompt,
        RESULT_COL: llm_out["result_text"],          # <<< resolve seu erro atual
        REFLECTION_COL: llm_out["reflection"],
        NEXT_ACTIONS_COL: llm_out["next_actions"],
    }

    return write_cycle(row)


# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    run_id = os.environ.get("RUN_ID") or str(uuid.uuid4())
    saved = run_once(run_id)
    print("Saved cycle:", saved.get("id"), "cycle_number:", saved.get(CYCLE_NUMBER_COL))
