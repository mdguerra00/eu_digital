import os
import uuid
import json
import time
import hashlib
import traceback
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from pathlib import Path

from supabase import create_client, Client
from openai import OpenAI
from postgrest.exceptions import APIError

# Importar módulos do agente
from financial_module import FinancialWallet
from tools_module import WebSearchTool, WebScraperTool, MarketAnalyzerTool, SteelBrowserTool
from tool_executor import ToolExecutor


# -----------------------------
# Config
# -----------------------------
# Tentar carregar Supabase, mas permitir fallback se não estiver configurado
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Validar que pelo menos OpenAI está configurado
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY não está configurada. Por favor, defina a variável de ambiente.")

TABLE = os.environ.get("AGENT_CYCLES_TABLE", "agent_cycles")

# NOVO (tabela de estado, separada, sem mexer no agent_cycles)
STATE_TABLE = os.environ.get("AGENT_STATE_TABLE", "agent_state")

AGENT_NAME = os.environ.get("AGENT_NAME", "EU_DE_NEGOCIOS")
FOCUS = os.environ.get("FOCUS", "Auto-aprimoramento interno")

TASK_PROMPT_ENV = os.environ.get("TASK_PROMPT", "").strip()

MEMORY_WINDOW = int(os.environ.get("MEMORY_WINDOW", "10"))
MODEL = os.environ.get("MODEL", "gpt-4.1-mini")
AGENT_MODE = os.environ.get("AGENT_MODE", "real").strip().lower()
if AGENT_MODE not in {"real", "simulation"}:
    print(f"[AVISO] AGENT_MODE inválido: {AGENT_MODE!r}. Usando 'real'.")
    AGENT_MODE = "real"

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
PLAN_COL = os.environ.get("PLAN_COL", "execution_plan")

CREATED_AT_COL = os.environ.get("CREATED_AT_COL", "created_at")
AGENT_NAME_COL = os.environ.get("AGENT_NAME_COL", "agent_name")
RUN_ID_COL = os.environ.get("RUN_ID_COL", "run_id")
CYCLE_NUMBER_COL = os.environ.get("CYCLE_NUMBER_COL", "cycle_number")
FOCUS_COL = os.environ.get("FOCUS_COL", "focus")
RECEIPTS_TABLE = os.environ.get("EXECUTION_RECEIPTS_TABLE", "execution_receipts")
_receipts_table_disabled = False

# --- Carregamento do Estatuto ---
ESTATUTO_PATH = Path(__file__).parent / "ESTATUTO.md"
ESTATUTO_CONTENT = ""
if ESTATUTO_PATH.exists():
    try:
        ESTATUTO_CONTENT = ESTATUTO_PATH.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Aviso: falha ao carregar ESTATUTO.md: {e}")
else:
    print(f"Aviso: arquivo ESTATUTO.md não encontrado em {ESTATUTO_PATH}")


# -----------------------------
# Clients
# -----------------------------
# Inicializar Supabase apenas se as credenciais estiverem disponíveis
if SUPABASE_URL and SUPABASE_KEY:
    sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print(f"[INFO] Supabase conectado: {SUPABASE_URL}")
else:
    print("[AVISO] Supabase não configurado. Usando fallback local (arquivo JSON).")
    sb = None

oa = OpenAI(api_key=OPENAI_API_KEY)

# Inicializar módulos do agente
wallet = FinancialWallet(wallet_file="agent_wallet.json")
search_tool = WebSearchTool(api_key=os.environ.get("PERPLEXITY_API_KEY"))
# CORRIGIDO: Steel Browser no Railway nao precisa de API key — so precisa do endpoint.
# Prioridade: variavel STEEL_BROWSER_ENDPOINT > URL hardcoded do Railway
# STEEL BROWSER — mesmo projeto Railway = usar URL interna (mais rapido, sem passar pela internet)
# Prioridade:
#   1) STEEL_BROWSER_ENDPOINT (variavel no Railway — recomendado)
#   2) URL interna Railway  http://steel-browser.railway.internal/scrape
#   3) URL publica como ultimo fallback
_steel_endpoint = os.environ.get(
    "STEEL_BROWSER_ENDPOINT",
    "http://steel-browser.railway.internal/scrape"  # URL interna — mesmo projeto Railway
)
steel_browser = SteelBrowserTool(
    api_key=os.environ.get("STEEL_BROWSER_API_KEY"),  # opcional, pode ser None
    endpoint=_steel_endpoint,
)
scraper_tool = WebScraperTool(steel_browser=steel_browser if steel_browser.is_configured() else None)
print(f"[SteelBrowser] configured={steel_browser.is_configured()} | endpoint={steel_browser.endpoint}", flush=True)
market_analyzer = MarketAnalyzerTool(search_tool, scraper_tool)
tool_executor = ToolExecutor(search_tool, scraper_tool, market_analyzer, wallet)


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
    if sb is not None:
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
    
    cycles_file = Path("agent_cycles.json")
    if not cycles_file.exists():
        return []
    
    try:
        with open(cycles_file, 'r', encoding='utf-8') as f:
            cycles = json.load(f)
        filtered = [c for c in cycles if c.get(AGENT_NAME_COL) == agent_name]
        return sorted(filtered, key=lambda x: x.get(CREATED_AT_COL, ""), reverse=True)[:limit]
    except Exception as e:
        log(f"Erro ao ler cycles.json: {e}")
        return []


def fetch_last_cycle(agent_name: str) -> Optional[Dict[str, Any]]:
    if sb is not None:
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
    
    cycles_file = Path("agent_cycles.json")
    if not cycles_file.exists():
        return None
    
    try:
        with open(cycles_file, 'r', encoding='utf-8') as f:
            cycles = json.load(f)
        filtered = [c for c in cycles if c.get(AGENT_NAME_COL) == agent_name]
        if filtered:
            return sorted(filtered, key=lambda x: x.get(CREATED_AT_COL, ""), reverse=True)[0]
    except Exception as e:
        log(f"Erro ao ler cycles.json: {e}")
    
    return None


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
    if sb is None:
        cycles_file = Path("agent_cycles.json")
        if not cycles_file.exists():
            return 1

        try:
            with open(cycles_file, "r", encoding="utf-8") as f:
                cycles = json.load(f)

            filtered_cycles = [
                c for c in cycles
                if c.get(AGENT_NAME_COL) == agent_name and c.get(CYCLE_NUMBER_COL) is not None
            ]
            if not filtered_cycles:
                return 1

            max_cycle = max(int(c[CYCLE_NUMBER_COL]) for c in filtered_cycles)
            return max_cycle + 1
        except Exception as e:
            log(f"Aviso: falha ao calcular próximo ciclo via agent_cycles.json: {e}")
            return 1

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



def _coerce_api_error_payload(exc: Exception) -> Dict[str, Any]:
    """Normaliza payload de APIError para dict, evitando crashes por tipo inesperado."""
    raw_payload = None

    args = getattr(exc, "args", ())
    if args:
        raw_payload = args[0]

    if isinstance(raw_payload, dict):
        return raw_payload

    if isinstance(raw_payload, str):
        try:
            parsed_payload = json.loads(raw_payload)
            if isinstance(parsed_payload, dict):
                return parsed_payload
        except Exception:
            pass

        try:
            import ast
            parsed_payload = ast.literal_eval(raw_payload)
            if isinstance(parsed_payload, dict):
                return parsed_payload
        except Exception:
            pass

        return {"message": raw_payload}

    message = str(exc)
    if message:
        return {"message": message}

    return {}

def write_cycle(row: Dict[str, Any]) -> Dict[str, Any]:
    log("Insert payload keys:", sorted(list(row.keys())))

    if sb is not None:
        try:
            res = sb.table(TABLE).insert(row).execute()
        except APIError as e:
            error_payload = _coerce_api_error_payload(e)

            if not isinstance(error_payload, dict):
                error_payload = {"message": str(error_payload)}
            error_payload = {}
            raw_payload = getattr(e, "args", [None])[0]
            if isinstance(raw_payload, dict):
                error_payload = raw_payload
            elif isinstance(raw_payload, str):
                try:
                    parsed_payload = json.loads(raw_payload)
                    if isinstance(parsed_payload, dict):
                        error_payload = parsed_payload
                except Exception:
                    try:
                        import ast
                        parsed_payload = ast.literal_eval(raw_payload)
                        if isinstance(parsed_payload, dict):
                            error_payload = parsed_payload
                        else:
                            error_payload = {"message": raw_payload}
                    except Exception:
                        error_payload = {"message": raw_payload}

            error_code = error_payload.get("code")
            error_message = error_payload.get("message", "")

            missing_column = None
            if error_code == "PGRST204":
                marker = "Could not find the '"
                if marker in error_message:
                    start = error_message.find(marker) + len(marker)
                    end = error_message.find("' column", start)
                    if end > start:
                        missing_column = error_message[start:end]

            if missing_column and missing_column in row:
                log(
                    f"Aviso: coluna ausente no schema cache ({missing_column!r}). "
                    "Removendo do payload e tentando novamente."
                )
                sanitized_row = dict(row)
                sanitized_row.pop(missing_column, None)
                log("Retry insert payload keys:", sorted(list(sanitized_row.keys())))
                res = sb.table(TABLE).insert(sanitized_row).execute()
            else:
                raise

        if not res.data:
            raise RuntimeError(f"Insert falhou (sem data retornada). Response: {res}")
        return res.data[0]
    
    log("[FALLBACK] Salvando ciclo em arquivo JSON local...")
    cycles_file = Path("agent_cycles.json")
    cycles = []
    if cycles_file.exists():
        try:
            with open(cycles_file, 'r', encoding='utf-8') as f:
                cycles = json.load(f)
        except Exception as e:
            log(f"Aviso ao ler cycles.json: {e}")
    
    row["id"] = len(cycles) + 1
    cycles.append(row)
    
    try:
        with open(cycles_file, 'w', encoding='utf-8') as f:
            json.dump(cycles, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"Erro ao salvar cycles.json: {e}")
    
    return row


def seconds_until_next_cycle(agent_name: str, interval_seconds: int) -> int:
    last_cycle = fetch_last_cycle(agent_name)
    if not last_cycle:
        return 0

    last_created_raw = last_cycle.get(CREATED_AT_COL)
    last_created_dt = parse_datetime(last_created_raw)
    if last_created_dt is None:
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
# NOVO: Agent State (prompt vivo)
# -----------------------------
def get_current_task_prompt() -> str:
    """
    Lê o prompt atual do agente na tabela agent_state.
    Se não existir, cria com fallback e retorna.
    """
    fallback = TASK_PROMPT_ENV or "Rodar um ciclo de reflexão e auto-aprimoramento do agente (default)"

    if sb is None:
        return _get_local_state_prompt(fallback)

    try:
        res = (
            sb.table(STATE_TABLE)
            .select("agent_name, current_task_prompt, updated_at")
            .eq("agent_name", AGENT_NAME)
            .limit(1)
            .execute()
        )

        if res.data:
            p = (res.data[0].get("current_task_prompt") or "").strip()
            return p or fallback

        # Não existe ainda -> cria
        sb.table(STATE_TABLE).insert({
            "agent_name": AGENT_NAME,
            "current_task_prompt": fallback,
            "updated_at": utc_now_iso(),
        }).execute()
        return fallback

    except Exception as e:
        log("Aviso: falha ao ler/criar agent_state, usando fallback. Erro:", repr(e))
        return fallback


def update_task_prompt_from_cycle(saved_row: Dict[str, Any]) -> None:
    """
    Após salvar um ciclo, atualiza o prompt do próximo ciclo.
    Não interfere no insert do ciclo; se falhar, só loga e segue.
    """
    try:
        next_actions = (saved_row.get(NEXT_ACTIONS_COL) or "").strip()
        reflection = (saved_row.get(REFLECTION_COL) or "").strip()

        # Prompt simples e robusto: deriva diretamente do next_actions
        new_prompt = next_actions or "Defina próximos passos concretos para o agente com base no último ciclo."

        # Enriquecer com reflexão (sem ficar grande demais)
        if reflection:
            new_prompt = (
                f"Use as lições/reflexões abaixo para executar os próximos passos.\n\n"
                f"REFLECTION:\n{reflection}\n\n"
                f"NEXT_ACTIONS:\n{next_actions or '[vazio]'}\n\n"
                f"Agora execute o próximo passo mais importante primeiro, com entregáveis claros."
            )

        if sb is not None:
            # Upsert (update se existe; insert se não existe)
            sb.table(STATE_TABLE).upsert({
                "agent_name": AGENT_NAME,
                "current_task_prompt": new_prompt,
                "updated_at": utc_now_iso(),
            }).execute()
        else:
            _write_local_state_prompt(new_prompt)

        log("Agent state atualizado: current_task_prompt definido a partir do último ciclo.")

    except Exception as e:
        log("Aviso: falha ao atualizar agent_state (não bloqueia). Erro:", repr(e))


def _get_local_state_prompt(fallback_prompt: str) -> str:
    state_file = Path("agent_state.json")
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state_data = json.load(f)
            prompt = (state_data.get("current_task_prompt") or "").strip()
            return prompt or fallback_prompt
        except Exception as e:
            log("Aviso: falha ao ler agent_state.json, usando fallback. Erro:", repr(e))

    _write_local_state_prompt(fallback_prompt)
    return fallback_prompt


def _write_local_state_prompt(prompt: str) -> None:
    state_file = Path("agent_state.json")
    try:
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "agent_name": AGENT_NAME,
                    "current_task_prompt": prompt,
                    "updated_at": utc_now_iso(),
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
    except Exception as e:
        log("Aviso: falha ao persistir agent_state.json. Erro:", repr(e))


# -----------------------------
# Guardrail Validation (Validador de Estatuto)
# -----------------------------
def validate_against_statute(next_actions: str, reflection: str, cycle_number: int) -> tuple:
    """
    Valida se as acoes propostas estao em conformidade com os Principios Inquebraveis do Estatuto.
    Retorna (is_valid, validation_message).
    """
    next_actions_lower = (next_actions or "").lower()
    
    # Verificacao 1: Proibicao de produtos fisicos
    physical_keywords = ["comprar", "entregar", "estoque", "mercadoria", "físico"]
    for keyword in physical_keywords:
        if keyword in next_actions_lower:
            return False, f"VIOLACAO DO ESTATUTO (Secao 1): Acao propoe trabalhar com produtos fisicos. Acao rejeitada: {next_actions[:100]}..."
    
    # Verificacao 2: Proibicao de movimentar dinheiro do Criador
    money_keywords = ["usar dinheiro do criador", "dinheiro do criador", "investir capital do criador", "gastar conta do marcelo", "movimentar conta pessoal"]
    for keyword in money_keywords:
        if keyword in next_actions_lower:
            return False, f"VIOLACAO DO ESTATUTO (Secao 4): Acao propoe movimentar dinheiro do Criador sem aprovacao. Acao rejeitada: {next_actions[:100]}..."
    
    # Verificacao 3: Proibicao de alterar o Estatuto unilateralmente
    statute_keywords = ["alterar estatuto", "modificar estatuto", "mudar regras do estatuto", "editar constituicao", "aumentar minha porcentagem"]
    for keyword in statute_keywords:
        if keyword in next_actions_lower:
            return False, f"VIOLACAO DO ESTATUTO (Secao 4): Acao propoe alterar o Estatuto sem aprovacao do Criador. Acao rejeitada: {next_actions[:100]}..."
    
    # Verificacao 4: Proibicao de atividades ilegais ou antieticas
    illegal_keywords = ["fraude", "spam", "pirataria", "sonegacao", "lavagem de dinheiro", "enganar cliente", "burlar regras"]
    for keyword in illegal_keywords:
        if keyword in next_actions_lower:
            return False, f"VIOLACAO DO ESTATUTO (Secao 2 - Principios Inquebraveis): Acao propoe atividade ilegal ou antietica. Acao rejeitada: {next_actions[:100]}..."
    
    return True, "Acoes validadas com sucesso contra o Estatuto Constitucional."


def _validate_execution_plan(plan: Any) -> tuple[bool, str]:
    if isinstance(plan, str):
        try:
            plan = json.loads(plan)
        except Exception:
            return False, "execution_plan em texto, mas não é JSON válido"

    if not isinstance(plan, list) or not plan:
        return False, "execution_plan ausente ou vazio"

    for i, step in enumerate(plan, start=1):
        if not isinstance(step, dict):
            return False, f"step #{i} inválido (esperado objeto)"
        if not step.get("id"):
            return False, f"step #{i} sem campo obrigatório: id"
        if not step.get("tool"):
            return False, f"step #{i} sem campo obrigatório: tool"
        if not isinstance(step.get("args"), dict):
            return False, f"step #{i} sem campo obrigatório: args (objeto)"
        if not step.get("success_criteria"):
            return False, f"step #{i} sem campo obrigatório: success_criteria"
        if not step.get("on_failure"):
            return False, f"step #{i} sem campo obrigatório: on_failure"

    return True, "execution_plan válido"


def _normalize_execution_plan(plan: Any) -> List[Dict[str, Any]]:
    """Converte execution_plan para uma lista de steps quando possível."""
    if isinstance(plan, str):
        try:
            plan = json.loads(plan)
        except Exception:
            return []

    if not isinstance(plan, list):
        return []

    return [step for step in plan if isinstance(step, dict)]


def _write_execution_receipt(
    *,
    run_id: str,
    cycle_number: int,
    step_id: str,
    tool: str,
    args: Dict[str, Any],
    tool_output: Dict[str, Any],
    used_fallback: bool,
    idempotency_key: str,
) -> None:
    global _receipts_table_disabled

    started_at = utc_now_iso()
    finished_at = utc_now_iso()
    status = "success" if tool_output.get("success") else "failed"
    raw_output = json.dumps(tool_output, ensure_ascii=False)
    evidence_hash = hashlib.sha256(raw_output.encode("utf-8")).hexdigest()

    receipt = {
        "run_id": run_id,
        "cycle_number": cycle_number,
        "step_id": step_id,
        "tool": tool,
        "args": args,
        "started_at": started_at,
        "finished_at": finished_at,
        "status": status,
        "raw_output": tool_output,
        "evidence_hash": evidence_hash,
        "used_fallback": used_fallback,
        "idempotency_key": idempotency_key,
    }

    if sb is not None and not _receipts_table_disabled:
        try:
            sb.table(RECEIPTS_TABLE).insert(receipt).execute()
            return
        except Exception as e:
            # Railway/Supabase pode não ter a tabela de receipts criada ainda.
            # Nesse caso, fazemos fallback para arquivo local e evitamos falhar o ciclo.
            if "PGRST205" in repr(e) or RECEIPTS_TABLE in repr(e):
                _receipts_table_disabled = True
                log(
                    f"Aviso: tabela de receipts '{RECEIPTS_TABLE}' indisponível no Supabase. "
                    "Usando fallback local (execution_receipts.jsonl)."
                )
            else:
                log("Aviso: falha ao gravar receipt no Supabase:", repr(e))

    receipts_file = Path("execution_receipts.jsonl")
    with open(receipts_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, ensure_ascii=False) + "\n")


def _receipt_already_exists(idempotency_key: str) -> bool:
    global _receipts_table_disabled

    if sb is not None and not _receipts_table_disabled:
        try:
            res = (
                sb.table(RECEIPTS_TABLE)
                .select("id")
                .eq("idempotency_key", idempotency_key)
                .limit(1)
                .execute()
            )
            return bool(res.data)
        except Exception as e:
            if "PGRST205" in repr(e) or RECEIPTS_TABLE in repr(e):
                _receipts_table_disabled = True
                log(
                    f"Aviso: tabela de receipts '{RECEIPTS_TABLE}' indisponível no Supabase durante consulta. "
                    "Usando fallback local (execution_receipts.jsonl)."
                )
            else:
                log("Aviso: falha ao consultar receipt por idempotency_key:", repr(e))
            return False

    receipts_file = Path("execution_receipts.jsonl")
    if not receipts_file.exists():
        return False

    try:
        with open(receipts_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if row.get("idempotency_key") == idempotency_key:
                    return True
    except Exception as e:
        log("Aviso: falha ao ler execution_receipts.jsonl:", repr(e))

    return False


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


def llm_cycle(memory_summary: str, focus: str, task_prompt: str, cycle_number: int) -> Dict[str, Any]:
    # Construir o system prompt com o Estatuto integrado
    statute_section = ""
    if ESTATUTO_CONTENT:
        statute_section = f"""

=== ESTATUTO CONSTITUCIONAL (Sua Constituição) ===
{ESTATUTO_CONTENT}
=== FIM DO ESTATUTO ===

Todas as suas decisões, planos e ações devem estar 100% alinhados com este Estatuto.
Em caso de conflito, priorize sempre os Princípios Inquebráveis (Seção 2).
"""
    
    system = (
        "Você é um agente autônomo que evolui por ciclos. "
        "A cada ciclo, você deve: "
        "(1) produzir um RESULT útil, "
        "(2) refletir sobre melhorias e "
        "(3) definir próximos passos. "
        "Seja específico, conciso e incremental. "
        "Não reescreva tudo do zero."
        + statute_section
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
  "next_actions": "...",
  "execution_plan": [
    {{
      "id": "step_1",
      "tool": "web_search|web_scraper|market_analyzer|financial_wallet.record_revenue",
      "args": {{}},
      "success_criteria": "...",
      "on_failure": "retry_once|skip|halt"
    }}
  ]
}}
"""

    content = ""

    # Compatibilidade entre versões do SDK/OpenAI API (Chat Completions x Responses)
    try:
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
    except Exception as first_error:
        try:
            resp = oa.responses.create(
                model=MODEL,
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=TEMPERATURE,
                timeout=REQUEST_TIMEOUT_S,
            )
            content = (getattr(resp, "output_text", "") or "").strip()
            if not content:
                parts = []
                for item in getattr(resp, "output", []) or []:
                    for c in getattr(item, "content", []) or []:
                        t = getattr(c, "text", None)
                        if t:
                            parts.append(t)
                content = "\n".join(parts).strip()
        except Exception:
            raise first_error
    data = _extract_json(content)

    result_text = (data.get("result_text") or "").strip()
    reflection = (data.get("reflection") or "").strip()
    next_actions = (data.get("next_actions") or "").strip()

    if not result_text:
        result_text = "Sem result_text (fallback): o modelo não retornou conteúdo."
    if not reflection:
        reflection = "Sem reflection (fallback): o modelo não retornou conteúdo."
    if not next_actions:
        next_actions = "Sem next_actions (fallback): o modelo não retornou conteúdo."
    
    # Validar contra o Estatuto antes de retornar
    is_valid, validation_msg = validate_against_statute(next_actions, reflection, cycle_number)
    if not is_valid:
        log(f"GUARDRAIL ACIONADO: {validation_msg}")
        # Se houver violação, registrar e sugerir reformulação
        next_actions = f"[GUARDRAIL] {validation_msg}\n\nPor favor, reformule as próximas ações para estar em conformidade com o Estatuto."
    else:
        log(f"GUARDRAIL OK: {validation_msg}")

    execution_plan = _normalize_execution_plan(data.get("execution_plan"))
    is_plan_valid, plan_msg = _validate_execution_plan(execution_plan)

    if AGENT_MODE == "real" and not is_plan_valid:
        raise RuntimeError(f"AGENT_MODE=real exige execution_plan válido. Erro: {plan_msg}")

    if AGENT_MODE != "real" and not is_plan_valid:
        log(f"Aviso: execution_plan inválido/ausente em simulation: {plan_msg}")
        execution_plan = []

    return {
        "result_text": result_text,
        "reflection": reflection,
        "next_actions": next_actions,
        "execution_plan": execution_plan,
    }


# -----------------------------
# Core cycle
# -----------------------------
def run_once(run_id: str) -> Dict[str, Any]:
    cycle_started_at = utc_now_dt()

    # ALTERAÇÃO MÍNIMA: em vez do env fixo, lê do agent_state
    task_prompt = get_current_task_prompt()

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
        PLAN_COL: llm_out.get("execution_plan", []),
    }

    saved = write_cycle(row)

    log(
        f"Ciclo salvo com sucesso | "
        f"id={saved.get('id')} | "
        f"cycle_number={saved.get(CYCLE_NUMBER_COL)} | "
        f"created_at={saved.get(CREATED_AT_COL)}"
    )

    # NOVO (não bloqueia): atualiza prompt do próximo ciclo
    update_task_prompt_from_cycle(saved)
    
    # Executar ferramentas (prioriza plano estruturado)
    try:
        execution_plan = llm_out.get("execution_plan") or []
        if execution_plan:
            tool_execution = tool_executor.execute_plan(execution_plan, cycle_number)
        else:
            if AGENT_MODE == "real":
                raise RuntimeError("AGENT_MODE=real não permite execução sem execution_plan.")
            tool_execution = tool_executor.execute_tools(llm_out["next_actions"], cycle_number)

        log(f"Ferramentas executadas: {len(tool_execution['tools_executed'])}")
        for tool_result in tool_execution['tools_executed']:
            log(f"  - {tool_result.get('tool')}: {tool_result.get('success')}")
            idempotency_key = (
                tool_result.get("idempotency_key")
                or hashlib.sha256(
                    f"{run_id}:{cycle_number}:{tool_result.get('step_id') or tool_result.get('tool')}".encode("utf-8")
                ).hexdigest()
            )

            if _receipt_already_exists(idempotency_key):
                log(f"  - receipt já existe para idempotency_key={idempotency_key[:12]}..., pulando gravação")
            else:
                _write_execution_receipt(
                    run_id=run_id,
                    cycle_number=cycle_number,
                    step_id=tool_result.get("step_id") or tool_result.get("tool") or "unknown_step",
                    tool=tool_result.get("tool") or "unknown_tool",
                    args=tool_result.get("args_input") or {},
                    tool_output=tool_result,
                    used_fallback=bool(tool_result.get("used_fallback", False)),
                    idempotency_key=idempotency_key,
                )

            if AGENT_MODE == "real" and bool(tool_result.get("used_fallback", False)):
                raise RuntimeError(
                    f"Fallback detectado em modo real para tool={tool_result.get('tool')}"
                )
        if tool_execution['insights']:
            log(f"Insights gerados: {len(tool_execution['insights'])}")
            for insight in tool_execution['insights']:
                log(f"  - {insight}")
    except Exception as e:
        log(f"Erro ao executar ferramentas: {repr(e)}")

    return saved


def sleep_in_chunks(total_seconds: int) -> None:
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
    process_run_id = os.environ.get("RUN_ID") or str(uuid.uuid4())

    log("Worker iniciado.")
    log(f"AGENT_NAME={AGENT_NAME}")
    log(f"TABLE={TABLE}")
    log(f"STATE_TABLE={STATE_TABLE}")
    log(f"MODEL={MODEL}")
    log(f"AGENT_MODE={AGENT_MODE}")
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
            continue

        except KeyboardInterrupt:
            log("Encerrado manualmente.")
            break

        except Exception as e:
            log("Erro no loop principal:", repr(e))
            traceback.print_exc()
            log(f"Nova tentativa em {ERROR_RETRY_SECONDS}s.")
            sleep_in_chunks(ERROR_RETRY_SECONDS)


if __name__ == "__main__":
    main_loop()
