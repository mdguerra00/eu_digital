import os
import time
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
MEMORY_WINDOW = int(os.environ.get("MEMORY_WINDOW", "10"))  # quantos ciclos anteriores ler
MODEL = os.environ.get("MODEL", "gpt-4.1-mini")  # ajuste se quiser

# -----------------------------
# Clients
# -----------------------------
sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
oa = OpenAI(api_key=OPENAI_API_KEY)

# -----------------------------
# Helpers
# -----------------------------
def fetch_recent_cycles(agent_name: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Busca os últimos ciclos para o agent_name.
    Ajuste o select conforme suas colunas reais.
    """
    res = (
        sb.table(TABLE)
        .select("id, created_at, agent_name, run_id, cycle_number, focus, output, reflection, next_actions")
        .eq("agent_name", agent_name)
        .order("cycle_number", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []

def summarize_memory(cycles: List[Dict[str, Any]]) -> str:
    """
    Gera um "resumo de memória" compacto.
    (Sem LLM aqui — simples e confiável. Se quiser, depois a gente troca por LLM.)
    """
    if not cycles:
        return "Nenhum ciclo anterior encontrado."

    # ciclos vêm em ordem decrescente; vamos inverter para ler do mais antigo -> mais novo
    cycles_sorted = list(reversed(cycles))

    lines = []
    for c in cycles_sorted:
        cn = c.get("cycle_number")
        created = c.get("created_at", "")
        out = (c.get("output") or "").strip()
        refl = (c.get("reflection") or "").strip()
        nxt = (c.get("next_actions") or "").strip()

        # truncar para não virar bíblia
        out = (out[:350] + "…") if len(out) > 350 else out
        refl = (refl[:250] + "…") if len(refl) > 250 else refl
        nxt = (nxt[:250] + "…") if len(nxt) > 250 else nxt

        lines.append(
            f"- Ciclo {cn} ({created}):\n"
            f"  Output: {out or '[vazio]'}\n"
            f"  Reflection: {refl or '[vazio]'}\n"
            f"  Next: {nxt or '[vazio]'}"
        )

    return "\n".join(lines)

def get_next_cycle_number(agent_name: str) -> int:
    res = (
        sb.table(TABLE)
        .select("cycle_number")
        .eq("agent_name", agent_name)
        .order("cycle_number", desc=True)
        .limit(1)
        .execute()
    )
    if res.data:
        return int(res.data[0]["cycle_number"]) + 1
    return 1

def write_cycle(row: Dict[str, Any]) -> Dict[str, Any]:
    res = sb.table(TABLE).insert(row).execute()
    if not res.data:
        raise RuntimeError(f"Insert falhou: {res}")
    return res.data[0]

def llm_reflect_and_act(memory_summary: str, focus: str, cycle_number: int) -> Dict[str, str]:
    """
    Faz o LLM produzir:
    - output (ação/resultado do ciclo)
    - reflection (o que aprendeu / o que melhorar)
    - next_actions (próximos passos curtos)
    """
    system = (
        "Você é um agente autônomo que evolui por ciclos. "
        "A cada ciclo, você deve: (1) produzir um output útil, "
        "(2) refletir sobre melhorias e (3) definir próximos passos. "
        "Seja específico, conciso e incremental. Não reescreva tudo do zero."
    )

    user = f"""
FOCO DO AGENTE: {focus}
CICLO ATUAL: {cycle_number}

MEMÓRIA (últimos ciclos, resumida):
{memory_summary}

TAREFA DO CICLO:
1) OUTPUT: entregue algo útil e incremental ligado ao FOCO.
2) REFLECTION: identifique 2-4 pontos de melhoria (processo, qualidade, riscos, estrutura).
3) NEXT_ACTIONS: liste 3-6 próximos passos curtos e objetivos.

Formato de saída OBRIGATÓRIO (JSON puro):
{{
  "output": "...",
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
        temperature=0.4,
    )

    text = resp.choices[0].message.content.strip()

    # parse simples/robusto sem libs extras:
    # tenta extrair JSON do texto
    import json
    try:
        data = json.loads(text)
    except Exception:
        # fallback: tenta encontrar o primeiro { ... } e parsear
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise RuntimeError(f"Resposta não-JSON do modelo:\n{text}")
        data = json.loads(text[start : end + 1])

    return {
        "output": (data.get("output") or "").strip(),
        "reflection": (data.get("reflection") or "").strip(),
        "next_actions": (data.get("next_actions") or "").strip(),
    }

def run_once(run_id: str) -> Dict[str, Any]:
    cycle_number = get_next_cycle_number(AGENT_NAME)
    recent = fetch_recent_cycles(AGENT_NAME, limit=MEMORY_WINDOW)
    memory_summary = summarize_memory(recent)

    ai = llm_reflect_and_act(memory_summary, FOCUS, cycle_number)

    row = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "agent_name": AGENT_NAME,
        "run_id": run_id,
        "cycle_number": cycle_number,
        "focus": FOCUS,
        "output": ai["output"],
        "reflection": ai["reflection"],
        "next_actions": ai["next_actions"],
    }

    saved = write_cycle(row)
    return saved

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    # Um run_id por execução do processo (ou injete via env se preferir)
    import uuid
    run_id = os.environ.get("RUN_ID") or str(uuid.uuid4())

    saved = run_once(run_id)
    print("Saved cycle:", saved.get("id"), "cycle_number:", saved.get("cycle_number"))
