import os
import uuid
import json
import time
import traceback
from datetime import datetime, timezone, timedelta
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

TASK_PROMPT_ENV = os.environ.get("TASK_PROMPT", "").strip()

MEMORY_WINDOW = int(os.environ.get("MEMORY_WINDOW", "10"))
MODEL = os.environ.get("MODEL", "gpt-4.1-mini")

TEMPERATURE = float(os.environ.get("TEMPERATURE", "0.4"))
REQUEST_TIMEOUT_S = float(os.environ.get("REQUEST_TIMEOUT_S", "60"))

# Intervalo entre ciclos
LOOP_INTERVAL_MINUTES = float(os.environ.get("LOOP_INTERVAL_MINUTES", "20"))
LOOP_INTERVAL_SECONDS = max(60, int(LOOP_INTERVAL_MINUTES * 60))

# Em caso de erro, espera um pouco antes de tentar de novo
ERROR_RETRY_SECONDS = int(os.environ.get("ERROR_RETRY_SECONDS", "120"))

# --- Mapeamento de colunas (compatível com seu schema) ---
RESULT_COL = os.environ.get("RESULT_COL", "result_text")
TASK_PROMPT_COL = os.environ.get("TASK_PROMPT_COL", "task_prompt")
REFLECTION_COL = os.environ.get("REFLECTION_COL", "reflection")
NEXT_ACTIONS_COL = os.environ.get("NEXT_ACTIONS_COL", "next_actions")

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
# Logging helpers
# -----------------------------
def log(*parts: Any) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}]", *parts, flush=True)


# -----------------------------
# Datetime helpers
# -----------------------------
def utc_now_dt() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso(dt: Optional[datetime] = None) -> str:
    if dt is None:
        dt = utc_now_dt()
    # Gera formato mais limpo e compatível, ex.: 2026-03-04T18:20:00.123456Z
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip()
        if not s:
            return None
        # Suporte a ISO com Z
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
        except Exception:
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


# -----------------------------
# Supabase helpers
# -----------------------------
def fetch_recent_cycles(agent_name: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Busca os ciclos mais recentes para memória do agente.
    Ordena por created_at DESC para refletir a ordem temporal real.
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

    res = (
        sb.table(TABLE)
        .select(", ".join(select_cols))
        .eq(AGENT_NAME_COL, agent_name)
        .order(CREATED_AT_COL, desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def fetch_last_cycle(agent_name: str) -> Optional[Dict[str, Any]]:
    """
    Busca o último ciclo salvo.
    Usamos created_at DESC, porque é a referência temporal correta
    para segurar a cadência de 20 minutos mesmo após restart.
    """
    select_cols = [
        "id",
        CREATED_AT_COL,
        CYCLE_NUMBER_COL,
        RUN_ID_COL,
        AGENT_NAME_COL,
    ]

    res = (
        sb.table(TABLE)
        .select(", ".join(select_cols))
        .eq(AGENT_NAME_COL, agent_name)
        .order(CREATED_AT_COL, desc=True)
        .limit(1)
        .execute()
    )

    if res.data:
        return res.data[0]
    return None


def summarize_memory(cycles: List[Dict[str, Any]]) -> str:
    if not cycles:
        return "Nenhum ciclo anterior encontrado."

    # cycles veio DESC; para resumir, mostramos do mais antigo para o mais novo
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
    """
    Busca o maior cycle_number já existente e soma 1.
    """
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
    """
    Faz insert do ciclo e retorna a linha salva.
    """
    log("Insert payload keys:", sorted(list(row.keys())))

    res = sb.table(TABLE).insert(row).execute()
    if not res.data:
        raise RuntimeError(f"Insert falhou (sem data retornada). Response: {res}")

    return res.data[0]


def seconds_until_next_cycle(agent_name: str, interval_seconds: int) -> int:
    """
    Calcula quantos segundos faltam até a próxima janela permitida.

    Isso resolve dois problemas:
    1) garante a cadência de ~20 min entre ciclos;
    2) evita duplicação se o processo/container reiniciar.
    """
    last_cycle = fetch_last_cycle(agent_name)
    if not last_cycle:
        return 0

    last_created_raw = last_cycle.get(CREATED_AT_COL)
    last_created_dt = parse_datetime(last_created_raw)
    if last_created_dt is None:
        # Se não conseguiu interpretar, melhor não bloquear
        log(
            "Aviso: não foi possível interpretar",
            f"{CREATED_AT_COL}={last_created_raw!r}.",
            "Permitindo execução imediata."
        )
        return 0

    next_allowed_dt = last_created_dt + timedelta(seconds=interval_seconds)
    remaining = int((next_allowed_dt - utc_now_dt()).total_seconds())

    if remaining > 0:
        log(
            f"Último ciclo encontrado em {utc_now_iso(last_created_dt)} | "
            f"próximo permitido em {utc_now_iso(next_allowed_dt)} | "
            f"faltam {remaining}s"
        )
        return remaining

    return 0


# -----------------------------
# LLM helpers
# -----------------------------
def _extract_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()

    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise RuntimeError(f"Resposta não-JSON do modelo:\n{text}")
        return json.loads(text[start:end + 1])


def llm_cycle(memory_summary: str, focus: str, task_prompt: str, cycle_number: int) -> Dict[str, str]:
    system = (
        "Você é um agente autônomo que evolui por ciclos. "
        "A cada ciclo, você deve: "
        "(1) produzir um RESULT útil, "
        "(2) refletir sobre melhorias e "
        "(3) definir próximos passos. "
        "Seja específico, conciso e incremental. "
        "Não reescreva tudo do zero."
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

    # Nunca deixar campos principais vazios
    if not result_text:
        result_text = "Sem result_text (fallback): o modelo não retornou conteúdo."
    if not reflection:
        reflection = "Sem reflection (fallback): o modelo não retornou conteúdo."
    if not next_actions:
        next_actions = "Sem next_actions (fallback): o modelo não retornou conteúdo."

    return {
        "result_text": result_text,
        "reflection": reflection,
        "next_actions": next_actions,
    }


# -----------------------------
# Core cycle
# -----------------------------
def run_once(run_id: str) -> Dict[str, Any]:
    """
    Executa exatamente 1 ciclo completo.
    """
    cycle_started_at = utc_now_dt()

    task_prompt = TASK_PROMPT_ENV or "Rodar um ciclo de reflexão e auto-aprimoramento do agente (default)"

    recent = fetch_recent_cycles(AGENT_NAME, limit=MEMORY_WINDOW)
    memory_summary = summarize_memory(recent)

    cycle_number = get_next_cycle_number(AGENT_NAME)

    log(
        f"Iniciando ciclo {cycle_number} | "
        f"run_id={run_id} | "
        f"started_at={utc_now_iso(cycle_started_at)}"
    )

    llm_out = llm_cycle(
        memory_summary=memory_summary,
        focus=FOCUS,
        task_prompt=task_prompt,
        cycle_number=cycle_number,
    )

    row: Dict[str, Any] = {
        CREATED_AT_COL: utc_now_iso(cycle_started_at),
        AGENT_NAME_COL: AGENT_NAME,
        RUN_ID_COL: run_id,
        CYCLE_NUMBER_COL: cycle_number,
        FOCUS_COL: FOCUS,
        TASK_PROMPT_COL: task_prompt,
        RESULT_COL: llm_out["result_text"],
        REFLECTION_COL: llm_out["reflection"],
        NEXT_ACTIONS_COL: llm_out["next_actions"],
    }

    saved = write_cycle(row)

    log(
        f"Ciclo salvo com sucesso | "
        f"id={saved.get('id')} | "
        f"cycle_number={saved.get(CYCLE_NUMBER_COL)} | "
        f"created_at={saved.get(CREATED_AT_COL)}"
    )

    return saved


def sleep_in_chunks(total_seconds: int) -> None:
    """
    Dorme em blocos curtos para manter logs previsíveis e evitar sleeps longos cegos.
    """
    total_seconds = max(0, int(total_seconds))
    if total_seconds == 0:
        return

    end = time.monotonic() + total_seconds

    while True:
        remaining = int(end - time.monotonic())
        if remaining <= 0:
            break

        chunk = min(remaining, 30)
        time.sleep(chunk)


def main_loop() -> None:
    """
    Loop principal do worker.

    Regras:
    - se ainda não passaram 20 min do último ciclo salvo, espera;
    - quando a janela abre, executa 1 ciclo;
    - depois volta a checar novamente;
    - se o container reiniciar, a checagem do último created_at evita duplicação.
    """
    process_run_id = os.environ.get("RUN_ID") or str(uuid.uuid4())

    log("Worker iniciado.")
    log(f"AGENT_NAME={AGENT_NAME}")
    log(f"TABLE={TABLE}")
    log(f"MODEL={MODEL}")
    log(f"LOOP_INTERVAL_MINUTES={LOOP_INTERVAL_MINUTES}")
    log(f"MEMORY_WINDOW={MEMORY_WINDOW}")
    log(f"Process RUN_ID={process_run_id}")

    while True:
        try:
            wait_seconds = seconds_until_next_cycle(AGENT_NAME, LOOP_INTERVAL_SECONDS)

            if wait_seconds > 0:
                log(f"Aguardando {wait_seconds}s até a próxima janela de execução.")
                sleep_in_chunks(wait_seconds)
                continue

            run_once(process_run_id)

            # Não dormimos fixo 20 min aqui.
            # Voltamos ao topo e recalculamos com base no último created_at salvo.
            # Isso mantém a cadência correta mesmo se a execução demorar.
            continue

        except KeyboardInterrupt:
            log("Encerrado manualmente.")
            break

        except Exception as e:
            log("Erro no loop principal:", repr(e))
            traceback.print_exc()
            log(f"Nova tentativa em {ERROR_RETRY_SECONDS}s.")
            sleep_in_chunks(ERROR_RETRY_SECONDS)


# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    main_loop()
