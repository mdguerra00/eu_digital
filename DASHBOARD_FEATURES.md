# Dashboard Features - Visual Overview

## Three-Tier Interface Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CONTROL CENTER PRO                             │
│                     http://localhost:5000/pro                           │
│                                                                         │
│  ┌─ Financial │ Affiliate │ Performance │ Health │ Reports ────────┐  │
│  │                                                                  │  │
│  │  📊 Financial Dashboard      💰 Affiliate Manager               │  │
│  │  ├─ Revenue Tracking         ├─ CRUD Operations                │  │
│  │  ├─ Expense Management       ├─ Niche Filtering               │  │
│  │  ├─ 80/20 Split              ├─ Commission Tracking            │  │
│  │  ├─ Charts & Trends          ├─ Active/Inactive Toggle        │  │
│  │  └─ Export (CSV/PDF)         └─ Modal Editor                  │  │
│  │                                                                  │  │
│  │  📈 Performance Metrics      ❤️ Service Health                 │  │
│  │  ├─ Latency Trends           ├─ OpenAI Status                  │  │
│  │  ├─ Fallback Rates           ├─ Supabase Status                │  │
│  │  ├─ Revenue Analysis         ├─ Perplexity Status             │  │
│  │  └─ KPI Statistics           └─ Steel Browser Status           │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                       CONTROL DASHBOARD                                 │
│                     http://localhost:5000/                              │
│                                                                         │
│  ┌─ Dashboard │ Control │ Alerts │ Metrics │ Health │ Audit ──────┐   │
│  │                                                                  │   │
│  │  🎮 Agent Control              ⚙️ Configuration                  │   │
│  │  ├─ Pause/Resume Buttons       ├─ Current Config Display      │   │
│  │  ├─ Last Cycle Details         ├─ Model Selection              │   │
│  │  ├─ Quick Metrics              ├─ Temperature Control          │   │
│  │  └─ Status Indicator           └─ Interval Settings            │   │
│  │                                                                  │   │
│  │  🔔 Alert Management           📋 Audit Log                    │   │
│  │  ├─ Unresolved Alerts          ├─ Action History               │   │
│  │  ├─ Alert Severity Colors      ├─ Status Tracking              │   │
│  │  ├─ One-click Resolution       ├─ Sortable Table               │   │
│  │  └─ Alert History              └─ 100 Most Recent              │   │
│  │                                                                  │   │
│  │  📈 Metrics Dashboard           ❤️ Service Status               │   │
│  │  ├─ Tool Latency Charts         ├─ 4 External Services         │   │
│  │  ├─ Fallback Rates              ├─ Latency Indicators          │   │
│  │  ├─ Revenue Trends              ├─ Quota Usage Gauges          │   │
│  │  └─ Performance Stats           └─ Last Check Time             │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                     CLASSIC MONITORING DASHBOARD                        │
│                      http://localhost:5000/classic                      │
│                                                                         │
│  Original interface maintained for backward compatibility               │
│  ├─ Cycle History & Details                                            │
│  ├─ Creator Messaging Chat                                             │
│  ├─ Wallet Status Display                                              │
│  └─ Execution Receipts Audit Trail                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Feature Matrix

### Dashboard Comparison

| Feature | Classic | Standard | Pro |
|---------|---------|----------|-----|
| **View Cycles** | ✓ | ✓ | ✓ |
| **Chat Messages** | ✓ | ✓ | ✓ |
| **Pause/Resume Agent** | ✗ | ✓ | ✓ |
| **Edit Task Prompt** | ✗ | ✓ | ✓ |
| **System Alerts** | ✗ | ✓ | ✓ |
| **Performance Metrics** | ✗ | ✓ | ✓ |
| **Service Health** | ✗ | ✓ | ✓ |
| **Audit Log** | ✗ | ✓ | ✓ |
| **Financial Reports** | ✗ | ✗ | ✓ |
| **Affiliate Management** | ✗ | ✗ | ✓ |
| **Advanced Charts** | ✗ | ✗ | ✓ |
| **Export to PDF** | ✗ | ✗ | ✓ |

---

## Real-time Updates Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      CLIENT (Browser)                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ EventSource('/events')                                 │ │
│  │ .onmessage → JSON.parse() → Handle Event              │ │
│  └────────────────────────────────────────────────────────┘ │
│         ▲                                                    │
│         │                                                    │
│         │ SSE Stream                                        │
│         │ (application/event-stream)                       │
│         │                                                    │
└─────────┼────────────────────────────────────────────────────┘
          │
          │
┌─────────┼────────────────────────────────────────────────────┐
│         │      BACKEND (Flask)                               │
│         │                                                    │
│  ┌──────▼─────────────────────────────────────────────────┐ │
│  │ /events endpoint                                       │ │
│  │ ├─ Client Queue                                        │ │
│  │ ├─ Generator (yield data)                              │ │
│  │ └─ Heartbeat every 25s                                 │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Event Types:                                               │
│  ├─ new_cycle        → Cycle completed                     │
│  ├─ new_message      → Message from creator               │
│  ├─ alert_resolved   → Alert marked resolved              │
│  ├─ prompt_changed   → Task prompt updated                │
│  ├─ agent_paused     → Agent execution paused             │
│  ├─ agent_resumed    → Agent execution resumed            │
│  ├─ affiliate_added  → Affiliate link created             │
│  ├─ affiliate_updated→ Affiliate link modified            │
│  └─ affiliate_deleted→ Affiliate link removed             │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Broadcast System (_sse_clients list)                   │ │
│  │                                                         │ │
│  │ When event occurs:                                     │ │
│  │ for each client_queue in _sse_clients:                │ │
│  │   queue.put_nowait(event_data)                        │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Event Sources:                                         │ │
│  │ ├─ Database (via _poller_loop thread)                 │ │
│  │ ├─ User actions (pause, resume, messages)             │ │
│  │ ├─ System alerts (automatic)                          │ │
│  │ └─ Affiliate operations (CRUD)                        │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## Affiliate Management Flow

```
┌─────────────────────────────────────────────────────┐
│         Pro Dashboard - Affiliates Tab             │
│                                                     │
│  [+ Novo Link] [Todos] [Ativos] [Inativos]        │
│                                                     │
│  ┌─────────────────────────────────────────────┐  │
│  │ Affiliate Links Table                       │  │
│  ├──────────────────────────────────────────────┤  │
│  │ Produto │ Nicho │ Plat │ Com │ Preço │ ... │  │
│  ├──────────────────────────────────────────────┤  │
│  │ Python  │ Dev   │ HM   │ 30% │ R$197 │ ✎ ✕ │  │
│  │ React   │ Dev   │ HM   │ 25% │ R$247 │ ✎ ✕ │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  Click [✎] → Opens Modal Editor                   │
│                                                     │
│  ┌─────────────────────────────────────────────┐  │
│  │ Modal: Editar Link de Afiliado             │  │
│  ├─────────────────────────────────────────────┤  │
│  │ Nome do Produto ________                    │  │
│  │ Nicho ________                              │  │
│  │ Plataforma ________                         │  │
│  │ URL do Link ________                        │  │
│  │ Comissão % _____ ☐ Ativo                  │  │
│  │ Preço (R$) ___                             │  │
│  │ Rating (⭐) _._                            │  │
│  │ Notas ________________                      │  │
│  │                                              │  │
│  │ [Salvar] [Cancelar]                        │  │
│  └─────────────────────────────────────────────┘  │
│                                                     │
│  API Flow:                                         │
│  POST   /api/affiliates         → Create          │
│  PUT    /api/affiliates/<id>    → Update          │
│  DELETE /api/affiliates/<id>    → Delete          │
│  GET    /api/affiliates         → List            │
└─────────────────────────────────────────────────────┘
```

---

## Financial Management Flow

```
┌─────────────────────────────────────────────────────┐
│       Pro Dashboard - Financial Tab                │
│                                                     │
│  ┌─────────────┬─────────────┬─────────────┐       │
│  │ Receita     │ Despesas    │ Margem      │       │
│  │ R$ 5,432.10 │ R$ 1,200.50 │ R$ 4,231.60│       │
│  └─────────────┴─────────────┴─────────────┘       │
│                                                     │
│  ┌─────────────────────────────────────────┐       │
│  │ Divisão de Lucros (Estatuto)            │       │
│  │                                          │       │
│  │ Criador (80%) ████████░ R$ 3,385.28   │       │
│  │ Agente  (20%) ██░░░░░░░░ R$ 846.32    │       │
│  └─────────────────────────────────────────┘       │
│                                                     │
│  ┌─────────────────────────────────────────┐       │
│  │ Histórico de Receitas (últimos 7 dias)  │       │
│  │                                          │       │
│  │  1000│     ╱╲        ╱╲                  │       │
│  │   750│    ╱  ╲      ╱  ╲    ╱╲          │       │
│  │   500│___╱____╲____╱____╲__╱__╲___      │       │
│  │      │ Dom Seg Ter Qua Qui Sex Sab     │       │
│  │                                          │       │
│  │ → Click bar for details                │       │
│  └─────────────────────────────────────────┘       │
│                                                     │
│  ┌─────────────────────────────────────────┐       │
│  │ Transações Recentes                     │       │
│  ├────────────────────────────────────────┤       │
│  │ Data      │ Tipo    │ Descrição │ Valor│       │
│  ├────────────────────────────────────────┤       │
│  │ 11/03     │ Receita │ Hotmart   │+R$500│       │
│  │ 10/03     │ Despesa │ API Quota │-R$ 50│       │
│  │ 09/03     │ Receita │ Amazon    │+R$450│       │
│  └────────────────────────────────────────┘       │
│                                                     │
│  [📊 Exportar CSV] [📄 Exportar PDF]               │
└─────────────────────────────────────────────────────┘
```

---

## Alert System

```
┌─────────────────────────────────────────────┐
│        Alerts Tab / Notifications           │
│                                             │
│  🔴 Critical (Unresolved)                   │
│  ┌───────────────────────────────────────┐ │
│  │ ⚠️ Violação de Estatuto Detectada     │ │
│  │ Ação bloqueada: Manipulação de saldo  │ │
│  │ Ciclo #145 - Há 5 minutos             │ │
│  │                      [Resolver]        │ │
│  └───────────────────────────────────────┘ │
│                                             │
│  🟠 Warning (Unresolved)                    │
│  ┌───────────────────────────────────────┐ │
│  │ ⚠️ Saldo Abaixo do Mínimo             │ │
│  │ Saldo agente: R$ 45.50 (limite: R$...) │ │
│  │ Ciclo #144 - Há 15 minutos            │ │
│  │                      [Resolver]        │ │
│  └───────────────────────────────────────┘ │
│                                             │
│  Alert Types & Severity:                   │
│  ├─ statute_violation    → 🔴 Critical     │
│  ├─ low_balance          → 🟠 Warning      │
│  ├─ service_error        → 🟠 Warning      │
│  ├─ performance_warning  → 🟡 Info         │
│  └─ high_fallback_rate   → 🟡 Info         │
│                                             │
│  Resolved Alerts History (last 10):        │
│  ├─ Configuration changed       10 min ago  │
│  ├─ Affiliate link added        2 hours    │
│  └─ Service degraded resolved   1 day ago  │
└─────────────────────────────────────────────┘
```

---

## API Endpoints Summary

### Control Endpoints
```
GET    /api/config                    # Get system configuration
PUT    /api/config/prompt             # Update task prompt
POST   /api/control/pause             # Pause agent
POST   /api/control/resume            # Resume agent
```

### Monitoring Endpoints
```
GET    /api/alerts                    # List alerts
POST   /api/alerts/<id>/resolve       # Resolve alert
GET    /api/health                    # Service health
GET    /api/metrics?type=<metric>     # Performance metrics
GET    /api/audit-log                 # Audit trail
```

### Affiliate Endpoints
```
GET    /api/affiliates                # List all links
GET    /api/affiliates?active_only=true  # List active links
POST   /api/affiliates                # Create new link
PUT    /api/affiliates/<id>           # Update link
DELETE /api/affiliates/<id>           # Delete link
```

### Real-time Endpoint
```
GET    /events                        # Server-Sent Events stream
```

### Data Access Endpoints
```
GET    /api/status                    # Agent status
GET    /api/cycles                    # Cycle history
GET    /api/cycles/<id>               # Cycle details
GET    /api/wallet                    # Financial balance
GET    /api/transactions              # Transaction history
GET    /api/messages                  # Creator messages
POST   /api/messages                  # Send message
GET    /api/receipts                  # Execution receipts
```

---

## Database Schema Overview

```
┌─────────────────────────────────────┐
│      Existing Tables (from main)    │
├─────────────────────────────────────┤
│ • agent_cycles                      │
│ • agent_state                       │
│ • agent_wallet_balance              │
│ • agent_wallet_transactions         │
│ • creator_messages                  │
│ • execution_receipts                │
│ • affiliate_links                   │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│    NEW Tables (Control Interface)   │
├─────────────────────────────────────┤
│ system_alerts (RLS enabled)         │
│ ├─ id, agent_name                  │
│ ├─ alert_type, severity            │
│ ├─ title, description              │
│ └─ resolved, metadata              │
│                                     │
│ audit_log (RLS enabled)             │
│ ├─ id, agent_name, action          │
│ ├─ actor, resource_type, resource_id│
│ ├─ changes, status, error_message  │
│ └─ timestamp                        │
│                                     │
│ performance_metrics (RLS enabled)   │
│ ├─ id, agent_name, cycle_number    │
│ ├─ metric_type, metric_value       │
│ ├─ percentile, metadata            │
│ └─ created_at                       │
│                                     │
│ service_health (RLS enabled)        │
│ ├─ id, service_name, status        │
│ ├─ latency_ms, quota_used_percent  │
│ └─ last_check_at, updated_at       │
└─────────────────────────────────────┘
```

---

## Deployment Architecture

```
┌────────────────────────────────────────────────┐
│              Production Deployment             │
│                                                │
│  ┌──────────────────────────────────────────┐ │
│  │ Load Balancer / Reverse Proxy (Nginx)   │ │
│  │ ├─ HTTPS/SSL termination                │ │
│  │ ├─ CORS headers                         │ │
│  │ └─ Gzip compression                     │ │
│  └──┬───────────────────────────────────────┘ │
│     │                                         │
│  ┌──▼───────────────────────────────────────┐ │
│  │ Flask Application (interface/app.py)     │ │
│  │ ├─ Route handlers                        │ │
│  │ ├─ Database layer                        │ │
│  │ ├─ Broadcast system                      │ │
│  │ ├─ Audit logging                         │ │
│  │ └─ SSE streaming                         │ │
│  └──┬───────────────────────────────────────┘ │
│     │                                         │
│  ┌──▼───────────────────────────────────────┐ │
│  │ Supabase PostgreSQL                      │ │
│  │ ├─ agent_cycles                          │ │
│  │ ├─ system_alerts                         │ │
│  │ ├─ audit_log                             │ │
│  │ ├─ performance_metrics                   │ │
│  │ └─ service_health                        │ │
│  └──────────────────────────────────────────┘ │
│                                                │
│  External Services (monitored):               │
│  ├─ OpenAI API                               │
│  ├─ Perplexity API                           │
│  └─ Steel Browser                            │
└────────────────────────────────────────────────┘
```

---

## User Workflow Examples

### Example 1: Monitor & Control Agent

```
1. Open http://localhost:5000
2. View last cycle results
3. Check quick metrics (revenue, balance, alerts)
4. Click Pause if needed
5. Monitor real-time updates via SSE
6. Review alerts and resolve if needed
7. Continue monitoring or close dashboard
```

### Example 2: Manage Affiliate Links

```
1. Navigate to http://localhost:5000/pro
2. Click Affiliates tab
3. View current active links (filtered by status)
4. Click "+ Novo Link" to add product
5. Fill in affiliate details
6. Review commission % and rating
7. Save link
8. Monitor performance in financial tab
```

### Example 3: Generate Financial Report

```
1. Go to http://localhost:5000/pro
2. Click Finanças tab
3. Review revenue/expense summary
4. Check 80/20 profit split
5. Scroll through transaction history
6. Click "📊 Exportar CSV" or "📄 Exportar PDF"
7. Save report for records
8. Share with creator if needed
```

---

## Status Indicators & Colors

```
✓ Active/Running      → Green (#10b981)
⊗ Paused/Stopped      → Yellow (#f59e0b)
✕ Error/Failed        → Red (#ef4444)
◆ Info/Neutral        → Blue (#3b82f6)
○ Warning/Caution     → Orange (#f97316)
◌ Pending/Loading     → Gray (#6b7280)
```

---

This comprehensive control interface provides complete visibility and management of the autonomous agent system!

