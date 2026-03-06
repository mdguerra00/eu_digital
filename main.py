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
from affiliate_module import AffiliateModule


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
CREATOR_MESSAGES_TABLE = os.environ.get("CREATOR_MESSAGES_TABLE", "creator_messages")

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
affiliate_mod = AffiliateModule(supabase_client=None, agent_name=AGENT_NAME)  # sb injetado abaixo
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
    "http://steel-browser.railway.internal:3000/v1/scrape"  # porta 3000, HTTP interno
)
steel_browser = SteelBrowserTool(
    api_key=os.environ.get("STEEL_BROWSER_API_KEY"),  # opcional, pode ser None
    endpoint=_steel_endpoint,
)
scraper_tool = WebScraperTool(steel_browser=steel_browser if steel_browser.is_configured() else None)
print(f"[SteelBrowser] configured={steel_browser.is_configured()} | endpoint={steel_browser.endpoint}", flush=True)
affiliate_mod.sb = sb  # injeta cliente Supabase após inicialização
market_analyzer = MarketAnalyzerTool(search_tool, scraper_tool)
tool_executor = ToolExecutor(search_tool, scraper_tool, market_analyzer, wallet, affiliate_module=affiliate_mod)


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

        # Separar result_text do tool_results_summary se existir
        tool_marker = "=== RESULTADOS REAIS DAS FERRAMENTAS ==="
        result_base = result
        tool_data = ""
        if tool_marker in result:
            parts = result.split(tool_marker, 1)
            result_base = parts[0].strip()
            tool_data = parts[1].strip() if len(parts) > 1 else ""

        entry = (
            f"- Ciclo {cn} ({created}):\n"
            f"  Focus: {trunc(focus, 120) or '[vazio]'}\n"
            f"  Result: {trunc(result_base, 300) or '[vazio]'}\n"
        )
        if tool_data:
            entry += f"  DadosReais: {trunc(tool_data, 500)}\n"
        entry += (
            f"  Reflection: {trunc(refl, 200) or '[vazio]'}\n"
            f"  Next: {trunc(nxt, 200) or '[vazio]'}"
        )
        lines.append(entry)

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

        # Prompt do próximo ciclo — sanitizado para evitar herdar modo de espera
        # Padrões que indicam loop improdutivo
        BLOQUEADOS = [
            "aguardar aprovação", "aguardando aprovação", "monitor_feedback",
            "esperar feedback", "monitorar feedback", "approval", "await",
            "continuar monitorando", "recebimento de aprovação",
        ]
        # Padrões que indicam planejamento genérico sem execução concreta
        GENERICOS = [
            "mapear para cada", "preparar cronograma", "plano de divulgação",
            "estratégias personalizadas", "montar plano", "elaborar plano",
            "definir estratégia", "planejar entrada", "próximos passos",
            "mapear canais", "perfil do público", "cronograma inicial",
            "campanhas piloto", "validação prática", "aprofundar a análise",
            "cruzar esses dados", "plano de entrada", "continuar a análise",
            "continuar mapeando", "estratégia detalhada", "mapeamento completo",
        ]
        prompt_contaminado = any(b in (next_actions or "").lower() for b in BLOQUEADOS)
        prompt_generico = any(g in (next_actions or "").lower() for g in GENERICOS)

        cycle_number = saved_row.get(CYCLE_NUMBER_COL) or 0

        if prompt_contaminado:
            log("[UpdatePrompt] AVISO: next_actions com padrão de espera. Resetando.")
            new_prompt = (
                "Ignore ciclos anteriores. Execute agora: use web_search para pesquisar "
                "'top produtos hotmart afiliados alta comissão 2026 brasil' e liste produtos reais "
                "com nome, nicho e comissão estimada."
            )
        elif prompt_generico:
            log("[UpdatePrompt] AVISO: next_actions genérico detectado. Forçando mudança de assunto.")
            cycle_num = saved_row.get(CYCLE_NUMBER_COL, 0)
            # Rotaciona entre ações diferentes para evitar loop no mesmo tema
            acoes_rotacao = [
                'Use web_search com query "produtos mais vendidos Hotmart categoria financas investimentos 2026". Liste 3 produtos com nome, comissão e preço.',
                'Use market_analyzer com niche="desenvolvimento pessoal produtividade". Identifique os 3 maiores players e oportunidades de entrada.',
                'Use web_search com query "produtos digitais mais vendidos Eduzz Monetizze Brasil 2026 alta comissão". Compare com Hotmart.',
                'Use web_search com query "nicho de pets produtos digitais afiliados Brasil 2026". Avalie potencial do nicho.',
                'Use market_analyzer com niche="cursos online tecnologia programacao". Avalie demanda e concorrência.',
            ]
            acao = acoes_rotacao[int(cycle_num) % len(acoes_rotacao)]
            new_prompt = (
                f"ATENÇÃO: os últimos ciclos ficaram presos em planejamento genérico. "
                f"IGNORE completamente os ciclos anteriores sobre 'Emagreça de Vez' e estratégias de divulgação. "
                f"Execute AGORA esta ação específica e diferente:\n\n{acao}"
            )
        elif reflection:
            new_prompt = (
                f"Dados do ciclo anterior para continuar:\n\n"
                f"REFLECTION:\n{reflection[:300]}\n\n"
                f"PRÓXIMO PASSO (execute agora, seja específico):\n{next_actions[:400] or '[vazio]'}"
            )
        else:
            new_prompt = next_actions or "Execute a próxima ação de negócio mais concreta agora."

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


# -----------------------------
# Creator Messages — canal Criador -> Agente via Supabase
# -----------------------------
def fetch_pending_creator_messages() -> List[Dict[str, Any]]:
    """Busca mensagens pendentes do Criador ordenadas por data."""
    if sb is None:
        return []
    try:
        res = (
            sb.table(CREATOR_MESSAGES_TABLE)
            .select("id, message, priority, created_at, author")
            .eq("agent_name", AGENT_NAME)
            .eq("status", "pending")
            .order("created_at", desc=False)
            .limit(5)
            .execute()
        )
        msgs = res.data or []
        if msgs:
            log(f"[CreatorMessages] {len(msgs)} mensagem(ns) pendente(s) do Criador.")
        return msgs
    except Exception as e:
        log(f"[CreatorMessages] Aviso: falha ao buscar ({repr(e)}). Continuando sem feedback.")
        return []


def mark_creator_messages_processed(message_ids: List[int], cycle_number: int) -> None:
    """Marca mensagens como processadas ao final do ciclo."""
    if sb is None or not message_ids:
        return
    try:
        for msg_id in message_ids:
            sb.table(CREATOR_MESSAGES_TABLE).update({
                "status": "processed",
                "read_at": utc_now_iso(),
                "processed_at": utc_now_iso(),
                "cycle_number": cycle_number,
            }).eq("id", msg_id).execute()
        log(f"[CreatorMessages] {len(message_ids)} mensagem(ns) marcada(s) como processada(s).")
    except Exception as e:
        log(f"[CreatorMessages] Aviso: falha ao marcar ({repr(e)}).")


def build_task_prompt_with_feedback(base_prompt: str, messages: List[Dict[str, Any]]) -> str:
    """Injeta mensagens do Criador no task_prompt com prioridade alta."""
    if not messages:
        return base_prompt

    urgent = [m for m in messages if m.get("priority") == "urgent"]
    others = [m for m in messages if m.get("priority") != "urgent"]

    parts = []
    if urgent:
        urgent_text = "\n".join(f"- {m['message']}" for m in urgent)
        parts.append(f"INSTRUCAO URGENTE DO CRIADOR (execute AGORA, prioridade maxima):\n{urgent_text}")
    if others:
        others_text = "\n".join(f"- [{m.get('priority','normal').upper()}] {m['message']}" for m in others)
        parts.append(f"INPUT DO CRIADOR (considere ao planejar este ciclo):\n{others_text}")

    parts.append(f"TASK BASE:\n{base_prompt}")
    combined = "\n\n".join(parts)
    log(f"[CreatorMessages] Task prompt enriquecido com {len(messages)} mensagem(ns).")
    return combined


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
        "Você é um agente autônomo de negócios cujo único objetivo é gerar receita real. "
        "A cada ciclo você executa buscas e análises reais usando as tools disponíveis. "
        "\n\nREGRAS INVIOLÁVEIS:"
        "\n- USE SEMPRE pelo menos uma tool por ciclo. Ciclo sem tool executada = ciclo inválido."
        "\n- NUNCA invente trabalho: não diga 'desenvolvi um script', 'criei uma automação', 'implementei X'."
        "  Você não tem capacidade de salvar arquivos ou escrever código. Só pode buscar, analisar e registrar."
        "\n- NUNCA use tools inexistentes como 'monitor_feedback'. Só use as listadas no user prompt."
        "\n- NUNCA entre em modo de espera ou peça aprovação. SEMPRE avance para a próxima ação de negócio."
        "\n- NUNCA repita a mesma query de ciclos anteriores. Cada ciclo deve buscar algo novo e concreto."
        "\n- O result_text deve refletir APENAS o que as tools realmente retornaram neste ciclo."
        "\n- Foco em resultados de negócio: encontrar produtos de afiliados, analisar nichos, identificar oportunidades reais."
        + statute_section
    )

    user = f"""
AGENTE: {AGENT_NAME}
FOCO: {focus}
CICLO: {cycle_number}

TASK_PROMPT:
{task_prompt}

MEMÓRIA (últimos ciclos):
{memory_summary}

TOOLS DISPONÍVEIS (use APENAS estas, exatamente com estes nomes):
- web_search                      → args: {{"query": "...", "count": 5}}
- web_scraper                     → args: {{"url": "https://..."}}
- market_analyzer                 → args: {{"niche": "..."}}
- financial_wallet.record_revenue → args: {{"amount": 0.0, "source": "...", "description": "..."}}
- affiliate.list_links            → args: {{"niche": "saude_emagrecimento"}} (opcional)
- affiliate.get_best              → args: {{"niche": "saude_emagrecimento"}} (opcional)
- affiliate.generate_promo        → args: {{"niche": "saude_emagrecimento", "format": "instagram|twitter|whatsapp|email"}}

PRIORIDADE DE USO: Se há links de afiliado cadastrados, USE affiliate.list_links primeiro para ver o que está disponível. Depois use affiliate.generate_promo para gerar conteúdo de divulgação real.

ATENÇÃO: NÃO invente tools. NÃO use "monitor_feedback". NÃO aguarde aprovação.
Se a memória mostra ciclos de espera, IGNORE-OS e execute a próxima ação útil agora.

Entregue JSON puro no formato:
{{
  "result_text": "resultado concreto deste ciclo",
  "reflection": "o que aprendeu e o que melhorar",
  "next_actions": "próximas ações específicas",
  "execution_plan": [
    {{
      "id": "step_1",
      "tool": "web_search",
      "args": {{"query": "exemplo de busca real", "count": 5}},
      "success_criteria": "obter resultados relevantes",
      "on_failure": "skip"
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

    if not is_plan_valid:
        # Em vez de lançar exceção, gerar plano de fallback automaticamente
        log(f"[LLM] execution_plan inválido/ausente ({plan_msg}). Gerando fallback.")
        fallback_query = next_actions[:120] if next_actions and "fallback" not in next_actions.lower() else "oportunidades afiliados produtos digitais Brasil 2026"
        execution_plan = [{
            "id": "step_fallback",
            "tool": "web_search",
            "args": {"query": fallback_query, "count": 5},
            "success_criteria": "obter dados relevantes",
            "on_failure": "skip",
        }]
        log(f"[LLM] Fallback plan: web_search query={fallback_query[:60]!r}")

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

    # Lê prompt base do agent_state
    task_prompt = get_current_task_prompt()

    # Lê mensagens pendentes do Criador e enriquece o prompt
    creator_msgs = fetch_pending_creator_messages()
    creator_msg_ids = [m["id"] for m in creator_msgs]
    task_prompt = build_task_prompt_with_feedback(task_prompt, creator_msgs)

    recent = fetch_recent_cycles(AGENT_NAME, limit=MEMORY_WINDOW)
    memory_summary = summarize_memory(recent)

    cycle_number = get_next_cycle_number(AGENT_NAME)

    log(
        f"Iniciando ciclo {cycle_number} | "
        f"run_id={run_id} | "
        f"creator_msgs={len(creator_msgs)} | "
        f"started_at={utc_now_iso(cycle_started_at)}"
    )

    llm_out = llm_cycle(
        memory_summary=memory_summary,
        focus=FOCUS,
        task_prompt=task_prompt,
        cycle_number=cycle_number,
    )

    # -------------------------------------------------------
    # EXECUTAR FERRAMENTAS ANTES DE SALVAR
    # Assim os resultados reais entram no registro do ciclo
    # -------------------------------------------------------
    tool_results_summary = ""
    _cycle_partial_real = False
    tool_execution: Dict[str, Any] = {"tools_executed": [], "insights": [], "errors": []}

    try:
        execution_plan = llm_out.get("execution_plan") or []
        if execution_plan:
            tool_execution = tool_executor.execute_plan(execution_plan, cycle_number)
        else:
            # LLM nao gerou execution_plan — forcar web_search como fallback em vez de falhar
            log("[RunOnce] AVISO: execution_plan vazio. Forcando web_search de fallback.")
            fallback_query = (llm_out.get("next_actions") or "oportunidades afiliados Brasil 2026")[:120]
            fallback_plan = [{
                "id": "step_fallback",
                "tool": "web_search",
                "args": {"query": fallback_query, "count": 5},
                "success_criteria": "obter dados relevantes",
                "on_failure": "skip",
            }]
            tool_execution = tool_executor.execute_plan(fallback_plan, cycle_number)

        log(f"Ferramentas executadas: {len(tool_execution['tools_executed'])}")

        # Gravar receipts e construir resumo dos resultados
        summary_parts = []
        for tool_result in tool_execution["tools_executed"]:
            tool_name = tool_result.get("tool", "unknown")
            success = tool_result.get("success", False)
            log(f"  - {tool_name}: success={success}")

            # Resumo rico do resultado — preserva o maximo de dados reais
            if tool_name == "web_search" and success:
                query_str = tool_result.get("query", "")
                raw_answer = (tool_result.get("raw_answer") or "").strip()
                descriptions = tool_result.get("descriptions", [])
                urls = tool_result.get("all_urls", [])
                enrich = tool_result.get("enrichment_scrape") or {}
                enrich_text = (enrich.get("text") or "").strip()

                part = f"[web_search: {query_str!r}]\n"
                if raw_answer:
                    part += f"Resposta Perplexity:\n{raw_answer[:1200]}\n"
                if descriptions:
                    part += "Snippets: " + " | ".join(d[:120] for d in descriptions[:3]) + "\n"
                if urls:
                    part += "URLs: " + " | ".join(urls[:3]) + "\n"
                if enrich_text:
                    part += f"Conteudo scraping ({enrich.get('url','')}):\n{enrich_text[:600]}\n"
                summary_parts.append(part.strip())

            elif tool_name == "market_analyzer" and success:
                niche = tool_result.get("niche", "")
                search_data = tool_result.get("search_results") or {}
                raw = (search_data.get("raw_answer") or "").strip()
                opps = tool_result.get("opportunities", [])
                competitors = tool_result.get("competitor_analysis", [])

                part = f"[market_analyzer: {niche!r}]\n"
                if raw:
                    part += f"Analise Perplexity:\n{raw[:1200]}\n"
                if opps:
                    part += "Oportunidades: " + " | ".join(opps[:4]) + "\n"
                if competitors:
                    for c in competitors[:2]:
                        part += f"Concorrente {c.get('url','')}: {(c.get('text_preview') or '')[:200]}\n"
                summary_parts.append(part.strip())

            elif tool_name == "web_scraper" and success:
                url = tool_result.get("url", "")
                text = (tool_result.get("text") or tool_result.get("title") or "").strip()
                summary_parts.append(f"[web_scraper: {url!r}]\n{text[:800]}")

            elif not success:
                summary_parts.append(f"[{tool_name}: ERRO] {tool_result.get('error','desconhecido')}")

            # Gravar receipt
            idempotency_key = (
                tool_result.get("idempotency_key")
                or hashlib.sha256(
                    f"{run_id}:{cycle_number}:{tool_result.get('step_id') or tool_name}".encode("utf-8")
                ).hexdigest()
            )
            if _receipt_already_exists(idempotency_key):
                log(f"  - receipt ja existe ({idempotency_key[:12]}...), pulando")
            else:
                _write_execution_receipt(
                    run_id=run_id,
                    cycle_number=cycle_number,
                    step_id=tool_result.get("step_id") or tool_name or "unknown_step",
                    tool=tool_name,
                    args=tool_result.get("args_input") or {},
                    tool_output=tool_result,
                    used_fallback=bool(tool_result.get("used_fallback", False)),
                    idempotency_key=idempotency_key,
                )

            if AGENT_MODE == "real" and bool(tool_result.get("used_fallback", False)):
                # Não derruba o ciclo — marca como partial_real e continua.
                log(
                    f"[AGENT_MODE=real] Fallback detectado em tool={tool_name} — "
                    "ciclo marcado como partial_real. Execução continua."
                )
                _cycle_partial_real = True

        if tool_execution["insights"]:
            log(f"Insights: {len(tool_execution['insights'])}")
            for insight in tool_execution["insights"]:
                log(f"  - {insight}")
            summary_parts.extend(tool_execution["insights"])

        tool_results_summary = "\n\n".join(summary_parts)

    except Exception as e:
        log(f"Erro ao executar ferramentas: {repr(e)}")
        tool_results_summary = f"[ERRO nas ferramentas]: {repr(e)}"

    # -------------------------------------------------------
    # SALVAR CICLO — agora com tool_results incluídos
    # -------------------------------------------------------
    # Enriquecer result_text com os dados reais das tools
    enriched_result = llm_out["result_text"]
    if tool_results_summary:
        enriched_result = (
            llm_out["result_text"]
            + "\n\n=== RESULTADOS REAIS DAS FERRAMENTAS ===\n"
            + tool_results_summary
        )

    row: Dict[str, Any] = {
        CREATED_AT_COL: utc_now_iso(cycle_started_at),
        AGENT_NAME_COL: AGENT_NAME,
        RUN_ID_COL: run_id,
        CYCLE_NUMBER_COL: cycle_number,
        FOCUS_COL: FOCUS,
        TASK_PROMPT_COL: task_prompt,
        RESULT_COL: enriched_result,
        REFLECTION_COL: llm_out["reflection"],
        NEXT_ACTIONS_COL: llm_out["next_actions"],
        PLAN_COL: llm_out.get("execution_plan", []),
        "notes": "partial_real" if _cycle_partial_real else AGENT_MODE,
    }

    saved = write_cycle(row)

    log(
        f"Ciclo salvo | id={saved.get('id')} | "
        f"cycle={saved.get(CYCLE_NUMBER_COL)} | "
        f"tool_results={len(tool_results_summary)} chars"
    )

    # Atualiza prompt do próximo ciclo
    update_task_prompt_from_cycle(saved)

    # Marca mensagens do Criador como processadas
    if creator_msg_ids:
        mark_creator_messages_processed(creator_msg_ids, cycle_number)

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


def _start_dashboard() -> None:
    """Inicia o dashboard web em background thread, se disponível."""
    try:
        import sys
        from pathlib import Path as _Path
        # Adiciona o diretório raiz ao path para importar interface.app
        _root = _Path(__file__).resolve().parent
        if str(_root) not in sys.path:
            sys.path.insert(0, str(_root))
        from interface.app import app as _dashboard_app
        _port = int(os.environ.get("DASHBOARD_PORT", "5000"))
        import threading as _threading
        _t = _threading.Thread(
            target=lambda: _dashboard_app.run(
                host="0.0.0.0", port=_port, debug=False, threaded=True, use_reloader=False
            ),
            daemon=True,
            name="dashboard",
        )
        _t.start()
        log(f"[Dashboard] Interface disponível na porta {_port}")
    except Exception as _e:
        log(f"[Dashboard] Aviso: não foi possível iniciar o dashboard: {_e}")


if __name__ == "__main__":
    _start_dashboard()
    main_loop()
