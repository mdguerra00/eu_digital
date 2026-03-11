# Control Interface - Quick Start Guide

## Installation

### 1. Prerequisites

Make sure you have Python 3.8+ and Flask installed:

```bash
pip install -r requirements.txt
```

Additional dependencies for the control interface are already included:
- Flask (web framework)
- supabase-py (database client)
- requests (HTTP library)

### 2. Database Setup

The control interface requires new tables in Supabase. Run the migration:

```bash
# Via Supabase CLI (if installed)
supabase migration up

# OR manually execute SQL in Supabase console:
# Navigate to SQL Editor and run create_monitoring_tables migration
```

The following tables will be created:
- `system_alerts` - Alert management
- `audit_log` - Action audit trail
- `performance_metrics` - KPI aggregation
- `service_health` - External service status

### 3. Environment Setup

Set up your environment variables. Add to your `.env`:

```bash
# Required
OPENAI_API_KEY=sk-...

# Supabase (highly recommended)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# Optional
DASHBOARD_PORT=5000
DASHBOARD_DEBUG=false
AGENT_NAME=EU_DE_NEGOCIOS
AGENT_MODE=real

# Notifications (optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
```

### 4. Start the Interface

```bash
# Load environment and start
python interface/app.py

# Or with custom port
PORT=8080 python interface/app.py

# Or with debug mode for development
DASHBOARD_DEBUG=true python interface/app.py
```

The interface will be available at:
- Classic Dashboard: `http://localhost:5000/classic`
- Standard Dashboard: `http://localhost:5000/`
- Pro Dashboard: `http://localhost:5000/pro`

---

## First Steps

### 1. Access the Dashboard

Open your browser to `http://localhost:5000`

You should see:
- Agent status indicator (green = connected)
- Last execution cycle details
- Quick metrics (cycles, revenue, balance)
- Control buttons (Pause/Resume)

### 2. Configure Agent Task

1. Click **"Painel de Controle"** (Control Panel) in the sidebar
2. Edit the "Editar Tarefa Atual" (Edit Current Task) text area
3. Click **"Salvar Tarefa"** (Save Task)
4. Wait for confirmation

The new task will be injected into the agent's next execution cycle.

### 3. Monitor Execution

1. Click **"Dashboard"** to return to overview
2. Watch for **"Novo ciclo"** notifications at bottom right
3. Click on a cycle to view full details (results, reflection, next actions)

### 4. Add Affiliate Links (Pro Dashboard)

1. Navigate to `http://localhost:5000/pro`
2. Click **"Afiliados"** tab
3. Click **"+ Novo Link"** button
4. Fill in the form:
   - **Produto**: e.g., "Curso Python Avançado"
   - **Nicho**: e.g., "Programação"
   - **Plataforma**: e.g., "Hotmart"
   - **URL**: Affiliate link
   - **Comissão**: e.g., 30 (%)
   - **Preço**: e.g., 197.00 (R$)
   - **Rating**: e.g., 4.8 (stars)
5. Toggle **"Ativo"** to enable
6. Click **"Salvar"**

### 5. View Financial Reports

1. In Pro Dashboard, click **"Finanças"** tab
2. Review:
   - **Receita Total** - Total income
   - **Despesas Totais** - Total expenses
   - **Margem Líquida** - Net margin
   - **Divisão 80/20** - Creator/Agent split visualization
3. Scroll down for transaction history

---

## Common Tasks

### Pause the Agent

```bash
curl -X POST http://localhost:5000/api/control/pause
# Response: {"success": true, "status": "paused"}
```

Or click the **"Pausar"** button in the dashboard.

### Resume Agent

```bash
curl -X POST http://localhost:5000/api/control/resume
# Response: {"success": true, "status": "running"}
```

Or click the **"Retomar"** button.

### Update Task Prompt

```bash
curl -X PUT http://localhost:5000/api/config/prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Pesquise nichos de programação e gere leads"}'
```

### Get Configuration

```bash
curl http://localhost:5000/api/config
# Response:
# {
#   "agent_name": "EU_DE_NEGOCIOS",
#   "model": "gpt-4.1-mini",
#   "temperature": 0.7,
#   "loop_interval_minutes": 20,
#   "memory_window": 10,
#   "agent_mode": "real",
#   "supabase_connected": true
# }
```

### Create Affiliate Link

```bash
curl -X POST http://localhost:5000/api/affiliates \
  -H "Content-Type: application/json" \
  -d '{
    "product_name": "Curso Python",
    "platform": "Hotmart",
    "niche": "Programação",
    "hotlink": "https://...",
    "commission_pct": 30,
    "price_brl": 197,
    "rating": 4.8,
    "active": true
  }'
```

### List Affiliates

```bash
curl http://localhost:5000/api/affiliates
# Response: [{ ... }, { ... }]
```

### Get Active Alerts

```bash
curl http://localhost:5000/api/alerts
# Response: [{ id, title, severity, ... }]
```

### Resolve Alert

```bash
curl -X POST http://localhost:5000/api/alerts/{alert_id}/resolve
# Response: {"success": true}
```

---

## Understanding Metrics

### Dashboard Quick Metrics

| Metric | Meaning |
|--------|---------|
| **Ciclos Executados** | Total autonomous cycles completed |
| **Receita Total** | Sum of all commissions earned |
| **Saldo Agente** | Agent's 20% retained balance |
| **Alertas Ativos** | Unresolved system notifications |

### Financial Metrics (Pro)

| Metric | Formula |
|--------|---------|
| **Receita Total** | Sum of all transactions (revenue) |
| **Despesas Totais** | Sum of all transactions (expenses) |
| **Margem Líquida** | Receita - Despesas |
| **Criador (80%)** | (Receita - Despesas) × 0.80 |
| **Agente (20%)** | (Receita - Despesas) × 0.20 |

### Performance Metrics

| Metric | Normal Range |
|--------|--------------|
| **Latência Média** | 800-1500ms |
| **Taxa de Fallback** | < 5% |
| **Taxa de Sucesso** | > 95% |

---

## Troubleshooting

### Dashboard Won't Load

**Problem**: Blank page or 500 error

**Solution**:
1. Check Flask is running: `curl http://localhost:5000/`
2. Check Supabase connection: `curl http://localhost:5000/api/config`
3. Review Flask logs for errors
4. Verify all tables exist in Supabase

### Supabase Offline Error

**Problem**: Interface says "Modo local" (Local mode)

**Solution**:
1. Verify `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are set
2. Check internet connection
3. Test Supabase directly: `curl -H "Authorization: Bearer $KEY" $URL`
4. Check Supabase dashboard for service status

### Real-time Updates Not Working

**Problem**: SSE connection fails or updates are delayed

**Solution**:
1. Check browser console for connection errors
2. Verify firewall allows SSE connections
3. Check `nginx` / load balancer configuration (may block SSE)
4. Increase SSE timeout: Set `SSE_CLIENT_TIMEOUT=60` in config

### Affiliate Links Don't Appear

**Problem**: `GET /api/affiliates` returns empty array

**Solution**:
1. Verify `affiliate_links` table exists in Supabase
2. Add test link via API or Supabase console
3. Check RLS policies allow reads
4. Verify `agent_name` filter matches `AGENT_NAME` env var

### High Latency / Performance Issues

**Optimization**:
1. Reduce API `limit` parameter (default 20, max 500)
2. Add database indexes:
   ```sql
   CREATE INDEX idx_cycles_agent ON agent_cycles(agent_name, created_at DESC);
   CREATE INDEX idx_alerts_agent ON system_alerts(agent_name, resolved);
   ```
3. Enable caching: Set `CACHE_TIMEOUT=120` in config
4. Monitor slow queries in Supabase dashboard

---

## Security Best Practices

1. **Never commit** `.env` files with secrets
2. **Use HTTPS** in production (reverse proxy with SSL)
3. **Limit access** to `/` and `/pro` endpoints
4. **Rotate keys** regularly
5. **Monitor audit logs** for suspicious activity:
   ```bash
   curl http://localhost:5000/api/audit-log | jq '.[] | select(.status == "failed")'
   ```
6. **Set up alerts** for critical events
7. **Review RLS policies** quarterly

---

## Next Steps

1. **Read** `INTERFACE_GUIDE.md` for comprehensive documentation
2. **Explore** Pro Dashboard for advanced features
3. **Set up** notifications (Slack/Discord)
4. **Monitor** system health and alerts
5. **Optimize** affiliate portfolio in real-time
6. **Generate** financial reports weekly

---

## API Reference

Full API documentation: See `INTERFACE_GUIDE.md`

Key endpoints:
- `GET /api/config` - System configuration
- `PUT /api/config/prompt` - Update task
- `POST /api/control/pause` - Pause agent
- `POST /api/control/resume` - Resume agent
- `GET /api/affiliates` - List links
- `POST /api/affiliates` - Create link
- `GET /api/alerts` - List alerts
- `GET /api/health` - Service status
- `GET /events` - Real-time updates (SSE)

---

## Support

For issues:
1. Check logs: `tail -100 interface/app.py output`
2. Review Supabase dashboard
3. Test connectivity: `curl -v http://localhost:5000/`
4. Check environment variables: `env | grep -i dashboard`

