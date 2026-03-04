import os
import uuid
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from supabase import create_client, Client
from openai import OpenAI


# -----------------------------
# Config
# -----------------------------
SUPABASE_URL = os.environ["SUPABASE_URL"]

# Preferir SERVICE_ROLE no backend (Railway). Se não tiver, cai no ANON.
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_ANON_KEY"]

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

TABLE = os.environ.get("AGENT_CYCLES_TABLE", "agent_cycles")
AGENT_NAME = os.environ.get("AGENT_NAME", "EU_DE_NEGOCIOS")
FOCUS = os.environ.get("FOCUS", "Auto-aprimoramento interno")
TASK_PROMPT = os.environ.get("TASK_PROMPT", "").strip()

MEMORY_WINDOW = int(os.environ.get("MEMORY_WINDOW", "10"))  # quantos ciclos anteriores ler
MODEL = os.environ.get("MODEL", "gpt-4.1-mini")  # ajuste se quiser

TEMPERATURE = float(os.environ.get("TEMPERATURE", "0.4"))
REQUEST_TIMEOUT_S = float(os.environ.get("REQUEST_TIMEOUT_S", "60"))


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
    Busca os últimos ciclos para o agent_name.
    Ajuste o select conforme suas colunas reais.
    """
    res = (
        sb.table(TABLE)
        .select("id, created_at, agent_name, run_id, cycle_number, focus, task_prompt, output, reflection, next_actions")
        .eq("agent_name", agent_name)
        .order("cycle_number", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def summarize_memory(cycles: List[Dict[str, Any]]) -> str:
    """
    Gera um "resumo de memória" compacto sem LLM (confiável).
    """
    if not cycles:
        return "Nenhum ciclo anterior encontrado."

    # ciclos vêm em ordem decrescente; inverter p/ ler do mais antigo -> mais novo
    cycles_sorted = list(reversed(cycles))

    lines: List[str] = []
    for c in cycles_sorted:
        cn = c.get("cycle_number")
        created = c.get("created_at", "")
        focus = (c.get("focus") or "").strip()
        tp = (c.get("task_prompt") or "").strip()
        out = (c.get("output") or "").strip()
        refl = (c.get("reflection") or "").strip()
        nxt = (c.get("next_actions") or "").strip()

        # truncar para não virar bíblia
        out = (out[:350] + "…") if len(out) > 350 else out
        refl = (refl[:250] + "…") if len(refl) > 250 else refl
        nxt = (nxt[:250] + "…") if len(nxt) > 250 else nxt
        tp = (tp[:140] + "…") if len(tp) > 140 else tp
        focus = (focus[:120] + "…") if len(focus) > 120 else focus

        lines.append(
            f"- Ciclo {cn} ({created}):\n"
            f"  Focus: {focus or '[vazio]'}\n"
            f"  Task: {tp or '[vazio]'}\n"
            f"  Output: {out or '[vazio]'}\n"
            f"  Reflection: {refl or '[vazio]'}\n"
            f"  Next: {nxt or '[vazio]'}"
        )

    return "\n".join(lines)


def get_next_cycle_number(agent_name: str) -> int:
    """
    Pega o último cycle_number do agente e soma 1.
    """
    res = (
        sb.table(TABLE)
        .select("cycle_number")
        .eq("agent_name", agent_name)
        .order("cycle_number", desc=True)
        .limit(1)
        .execute()
    )
    if res.data and res.data[0].get("cycle_number") is not None:
        return int(res.data[0]["cycle_number"]) + 1
    return 1


def write_cycle(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Insere uma linha no Supabase. Levanta erro se insert falhar.
    """
    res = sb.table(TABLE).insert(row).execute()
    if not res.data:
        raise RuntimeError(f"Insert falhou (sem data retornada). Response: {res}")
    return res.data[0]


def _extract_json(text: str) -> Dict[str, Any]:
    """
    Extrai JSON de uma resposta que às vezes vem com texto extra.
    """
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise RuntimeError(f"Resposta não-JSON do modelo:\n{text}")
        return json.loads(text[start : end + 1])


def llm_reflect_and_act(
    memory_summary: str,
    focus: str,
    task_prompt: str,
    cycle_number: int,
) -> Dict[str, str]:
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

    # Importante: task_prompt agora é obrigatório e sempre preenchido
    user = f"""
AGENTE: {AGENT_NAME}
FOCO DO AGENTE: {focus}
CICLO ATUAL: {cycle_number}

TASK_PROMPT (instrução do ciclo):
{task_prompt}

MEMÓRIA (últimos ciclos, resumida):
{memory_summary}

TAREFA DO CICLO:
1) OUTPUT: entregue algo útil e incremental ligado ao FOCO e ao TASK_PROMPT.
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
        temperature=TEMPERATURE,
        timeout=REQUEST_TIMEOUT_S,
    )

    text = (resp.choices[0].message.content or "").strip()
    data = _extract_json(text)

    output = (data.get("output") or "").strip()
    reflection = (data.get("reflection") or "").strip()
    next_actions = (data.get("next_actions") or "").strip()

    # garantias mínimas para evitar inserir NULL/strings vazias demais
    if not output:
        output = "Sem output (fallback): o modelo não retornou conteúdo."
    if not reflection:
        reflection = "Sem reflection (fallback): o modelo não retornou conteúdo."
    if not next_actions:
        next_actions = "Sem next_actions (fallback): o modelo não retornou conteúdo."

    return {"output": output, "reflection": reflection, "next_actions": next_actions}


def run_once(run_id: str) -> Dict[str, Any]:
    # TASK_PROMPT é NOT NULL na tabela — então aqui NUNCA pode ser vazio
    task_prompt = TASK_PROMPT
    if not task_prompt:
        # fallback seguro (você pode trocar por raise, se preferir travar)
        task_prompt = "Rodar um ciclo de reflexão e auto-aprimoramento do agente (default)"

    # 1) memória
    recent = fetch_recent_cycles(AGENT_NAME, limit=MEMORY_WINDOW)
    memory_summary = summarize_memory(recent)

    # 2) próximo ciclo
    cycle_number = get_next_cycle_number(AGENT_NAME)

    # 3) LLM
    llm_out = llm_reflect_and_act(
        memory_summary=memory_summary,
        focus=FOCUS,
        task_prompt=task_prompt,
        cycle_number=cycle_number,
    )
    output = llm_out["output"]
    reflection = llm_out["reflection"]
    next_actions = llm_out["next_actions"]

    # 4) montar row (evita NULL em task_prompt)
    row: Dict[str, Any] = {
        "created_at": utc_now_iso(),  # opcional (se sua tabela já seta default, pode remover)
        "agent_name": AGENT_NAME,
        "run_id": run_id,
        "cycle_number": cycle_number,
        "focus": FOCUS,
        "task_prompt": task_prompt,
        "output": output,
        "reflection": reflection,
        "next_actions": next_actions,
    }

    # 5) write
    return write_cycle(row)


# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    run_id = os.environ.get("RUN_ID") or str(uuid.uuid4())

    saved = run_once(run_id)
    print("Saved cycle:", saved.get("id"), "cycle_number:", saved.get("cycle_number"))
