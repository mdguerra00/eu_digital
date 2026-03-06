# CLAUDE.md — AI Assistant Guide for `eu_digital`

## Project Overview

`eu_digital` is an autonomous business-optimization agent system designed to generate sustainable profit through digital channels. It operates in a continuous reasoning loop (LLM → tool use → persist → repeat) governed by a constitutional statute (`ESTATUTO.md`).

**Key facts:**
- Language: Python 3
- LLM backend: OpenAI (`gpt-4.1-mini` by default, configurable via `MODEL` env var)
- Persistence: Supabase PostgreSQL (local JSON/JSONL fallback)
- Deployment target: Railway.app (containerized)
- Operational cadence: 20-minute cycles (configurable via `LOOP_INTERVAL_MINUTES`)

---

## Repository Structure

```
eu_digital/
├── main.py                          # Core agent orchestrator (1,293 lines)
├── tools_module.py                  # Tool implementations (663 lines)
├── tool_executor.py                 # Tool orchestration/dispatch (457 lines)
├── financial_module.py              # Wallet & revenue tracking (401 lines)
├── affiliate_module.py              # Affiliate link management (246 lines)
├── test_flight.py                   # Local test harness with mock Supabase (232 lines)
├── avaliar_receipts_kpis.py         # KPI analysis & traffic-light SLO reports (284 lines)
├── create_execution_receipts.sql    # Idempotent schema migration for receipts table
├── requirements.txt                 # Python dependencies
├── creator_feedback.json            # Creator messages injected into agent context
├── ESTATUTO.md                      # Constitutional constraints (MUST READ)
├── ROADMAP_REAL_EXECUTION.md        # Architecture transition plan
├── DEPLOY_SUPABASE_AUDIT_*.md       # Deployment audit reports
├── MONITORAMENTO_EXECUTION_RECEIPTS_SUPABASE.md  # SLO specifications
└── RUNBOOK_EXECUTION_RECEIPTS_SUPABASE.md        # Operational runbook
```

---

## Architecture

### Agent Loop (`main.py`)

```
main_loop()
  └─ run_once()
       ├─ fetch_recent_cycles()         # Pull memory window from Supabase
       ├─ fetch_creator_message()       # Load creator_feedback.json
       ├─ llm_cycle()                   # OpenAI reasoning → result + next_actions
       ├─ validate_against_statute()    # Constitutional guardrail check
       ├─ ToolExecutor.execute_tools()  # Keyword-based tool dispatch
       ├─ write_cycle()                 # Persist to Supabase (fallback: JSON)
       ├─ _write_execution_receipt()    # Telemetry audit trail
       └─ update_task_prompt_from_cycle() # Dynamic prompt evolution
```

### Module Responsibilities

| Module | Responsibility |
|---|---|
| `main.py` | Orchestration, LLM calls, memory, statute validation, persistence |
| `tools_module.py` | Web search (Perplexity/DuckDuckGo), web scraping (Steel Browser), market analysis |
| `tool_executor.py` | Text-based keyword dispatch to tools; generates tool-enriched insights |
| `financial_module.py` | Wallet balance, revenue/expense recording, 80/20 profit split |
| `affiliate_module.py` | Read affiliate links from Supabase; filter by niche/commission |

### Fallback Strategy (Critical Design Pattern)

Every external dependency has a local fallback:

| Service | Primary | Fallback |
|---|---|---|
| Persistence | Supabase tables | `agent_cycles.json`, `agent_state.json` |
| Search | Perplexity API | DuckDuckGo HTML scraping |
| Web scraping | Steel Browser endpoint | `requests` + BeautifulSoup |
| Receipts | `execution_receipts` table | `execution_receipts.jsonl` |
| Wallet | `agent_wallet_*` tables | `agent_wallet.json` |

`AGENT_MODE=real` disables silent fallbacks (recommended for production auditing). `AGENT_MODE=simulation` allows permissive fallbacks (for development).

---

## Environment Variables

### Mandatory
```
OPENAI_API_KEY          # App exits immediately without this
```

### Highly Recommended (production)
```
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY   # Preferred over anon key (bypasses RLS)
SUPABASE_ANON_KEY           # Alternative if service role unavailable
```

### Optional with Fallbacks
```
PERPLEXITY_API_KEY          # Search (falls back to DuckDuckGo)
STEEL_BROWSER_ENDPOINT      # Scraping (falls back to public URL)
STEEL_BROWSER_API_KEY       # Scraper auth token
```

### Operational Tuning
```
AGENT_MODE              # "real" | "simulation" (default: "real")
LOOP_INTERVAL_MINUTES   # Cycle frequency in minutes (default: 20)
MEMORY_WINDOW           # Recent cycles used for LLM context (default: 10)
MODEL                   # OpenAI model ID (default: "gpt-4.1-mini")
TEMPERATURE             # LLM temperature (optional)
AGENT_NAME              # Agent identifier (default: "EU_DE_NEGOCIOS")
FOCUS                   # Current strategic focus (default: "Auto-aprimoramento interno")
TASK_PROMPT             # Override current task (default: empty)
AGENT_CYCLES_TABLE      # Supabase table name (default: "agent_cycles")
AGENT_STATE_TABLE       # Supabase table name (default: "agent_state")
```

---

## Database Schema

### Supabase Tables

**`agent_cycles`** — Core execution record per reasoning cycle
```sql
id, agent_name, run_id, cycle_number, created_at,
focus, task_prompt, result_text, reflection,
next_actions, execution_plan, notes
```

**`agent_state`** — Dynamic prompt state (upserted each cycle)
```sql
agent_name, current_task_prompt, updated_at
```

**`execution_receipts`** — Immutable telemetry/audit trail
```sql
id, run_id, cycle_number, step_id, tool,
args (JSONB), started_at, finished_at,
status (success|failed), raw_output (JSONB),
evidence_hash (SHA256), used_fallback,
fallback_reason, fallback_reason_code,
latency_ms, chars_captured, final_url,
idempotency_key (UNIQUE), created_at
```

**`agent_wallet_balance`** — Financial state
```sql
agent_name, agent_balance, creator_balance,
total_revenue, total_expenses, minimum_reserve
```

**`agent_wallet_transactions`** — Transaction ledger
```sql
agent_name, transaction_type (revenue|expense),
amount, description, created_at
```

**`affiliate_links`** — Pre-seeded commission opportunities (read-only from agent)
```sql
id, agent_name, product_name, platform, niche,
hotlink, commission_pct, price_brl, rating, active, notes, created_at
```

### Schema Migration
```bash
# Apply idempotent migration to Supabase
psql $DATABASE_URL -f create_execution_receipts.sql
```

---

## Running the Agent

### Local Development
```bash
pip install -r requirements.txt

# Minimum setup (simulation mode with local fallbacks)
OPENAI_API_KEY=sk-... AGENT_MODE=simulation python main.py

# Full production setup
OPENAI_API_KEY=sk-... \
SUPABASE_URL=https://xxx.supabase.co \
SUPABASE_SERVICE_ROLE_KEY=... \
PERPLEXITY_API_KEY=... \
python main.py
```

### Running Tests
```bash
OPENAI_API_KEY=sk-... python test_flight.py
```

`test_flight.py` uses in-memory mock Supabase tables. No real database connection needed for local testing.

### KPI Analysis
```bash
python avaliar_receipts_kpis.py
```

Outputs traffic-light (green/yellow/red) SLO report for the last 24h, 7d, and last N cycles.

---

## Constitutional Constraints (ESTATUTO.md)

**All agent behavior is governed by the statute. Read `ESTATUTO.md` before modifying agent logic.**

Key constraints enforced via `validate_against_statute()` in `main.py`:
1. **Strict legality** — No illegal or unethical actions
2. **No physical products** — Digital-only business models
3. **No creator money manipulation** — Cannot access or move creator funds
4. **Transparent reporting** — All significant actions must be logged
5. **Profit split** — 80% to creator, 20% retained by agent
6. **Operational modes** — Test → Semi-autonomous → Advanced (graduated autonomy)

When modifying `main.py`, ensure `validate_against_statute()` is called before any consequential action.

---

## Key Conventions and Patterns

### Error Handling
- All Supabase operations are wrapped in try/except with fallback to local storage
- Errors are logged with `[ERROR]` prefix; warnings with `[WARN]`; info with `[INFO]`
- `AGENT_MODE=real` raises exceptions instead of silently falling back

### Idempotency
- `execution_receipts` uses `idempotency_key` (unique constraint) to prevent duplicate inserts on retry
- `agent_state` uses upsert semantics (not insert)

### Evidence Hashing
```python
# SHA256 hash of raw tool output for immutable audit trail
evidence_hash = hashlib.sha256(raw_output_str.encode()).hexdigest()
```

### Tool Dispatch (tool_executor.py)
Tool selection is currently **keyword-based** (text matching on action descriptions). The roadmap plans migration to **structured execution plans** (JSON). When adding new tools, register their trigger keywords in `ToolExecutor.execute_tools()`.

### Loop Detection (main.py)
`update_task_prompt_from_cycle()` detects repeated/generic patterns in next_actions and forces prompt variation to prevent the agent from getting stuck. When editing prompt-evolution logic, preserve this anti-loop mechanism.

### Proxy Fallback (tools_module.py)
Network requests use a proxy fallback mechanism. Do not remove timeout enforcement (12–30s depending on service).

---

## Known Issues and Active Work

| Priority | Issue | Status |
|---|---|---|
| P0 | `execution_receipts` table fallback to JSONL (breaks audit trail) | Open |
| P1 | Low tool diversity (mostly `web_search`; `market_analyzer` rarely triggered) | Open |
| P2 | `affiliate_links` table always empty (requires manual pre-seeding) | Open |
| P3 | No automated CI/CD or test suite beyond `test_flight.py` | Open |
| P3 | No `.gitignore` (credentials could be accidentally committed) | Open |

See `DEPLOY_SUPABASE_REAVALIACAO_2026-03-06.md` for the latest audit status.

---

## Development Workflow

### Branch Strategy
- Active development branch: as specified in task instructions (typically `claude/...`)
- Target merge: `master`
- Always push with: `git push -u origin <branch-name>`

### Making Changes
1. Read the relevant module before editing
2. Check if the change touches agent reasoning → validate statute compliance
3. If touching Supabase schema → update `create_execution_receipts.sql`
4. Run `test_flight.py` to verify no regressions
5. Commit with descriptive message, push to feature branch

### Adding a New Tool
1. Implement tool class in `tools_module.py` (follow `WebSearchTool` pattern)
2. Register trigger keywords in `tool_executor.py` → `execute_tools()`
3. Add `_write_execution_receipt()` call with appropriate `step_id` and `tool` name
4. Test locally with `test_flight.py`

### Modifying the LLM Prompt
- The prompt is assembled in `llm_cycle()` in `main.py`
- Memory context (`fetch_recent_cycles()`), focus, and task_prompt are combined
- Preserve the statute validation step after every LLM call

---

## External Services Summary

| Service | Purpose | Endpoint |
|---|---|---|
| OpenAI | LLM reasoning | `https://api.openai.com/v1/chat/completions` |
| Supabase | PostgreSQL persistence | `$SUPABASE_URL` |
| Perplexity | Real-time web search | `https://api.perplexity.ai/chat/completions` |
| DuckDuckGo | Fallback search | `https://html.duckduckgo.com/html/` |
| Steel Browser | JS-capable web scraping | `$STEEL_BROWSER_ENDPOINT` (Railway internal) |

---

## Files NOT to Modify Without Understanding

- `ESTATUTO.md` — Constitutional document; changes affect all guardrails
- `validate_against_statute()` in `main.py` — Core safety mechanism
- `idempotency_key` logic in `_write_execution_receipt()` — Audit integrity
- `create_execution_receipts.sql` — Production schema; changes require migration plan

---

## Roadmap (from ROADMAP_REAL_EXECUTION.md)

**Current Phase (Phase 1):** Text-based action interpretation, partial telemetry
**Target Phase (Phase 2):**
- Structured JSON execution plans (replacing keyword-based dispatch)
- 100% receipts coverage in Supabase (no JSONL fallback in real mode)
- Automated SLO alerting dashboard
- Expanded tool repertoire (financial APIs, content generation, affiliate tracking)
