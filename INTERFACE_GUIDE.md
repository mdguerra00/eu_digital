# Control Interface Complete Guide

## Overview

The `eu_digital` agent now includes a **complete control center** interface for monitoring, managing, and optimizing the autonomous agent system. The interface provides three levels of access:

1. **Classic Dashboard** (`/classic`) - Original monitoring interface
2. **Standard Dashboard** (`/`) - Enhanced control panel with alerts and configuration
3. **Pro Dashboard** (`/pro`) - Advanced analytics with financial management and affiliate control

---

## Architecture

### Backend (Flask)

Located in `interface/app.py`, the backend provides RESTful APIs organized into sections:

#### Core Data Access
- `GET /api/status` - Agent status and configuration
- `GET /api/cycles` - Execution cycle history
- `GET /api/cycle/<id>` - Specific cycle details
- `GET /api/wallet` - Financial balance
- `GET /api/transactions` - Transaction history
- `GET /api/messages` - Creator messages
- `GET /api/receipts` - Execution audit trail

#### Control & Configuration
- `GET /api/config` - System configuration (model, temperature, intervals)
- `PUT /api/config/prompt` - Update agent's current task
- `POST /api/control/pause` - Pause agent execution
- `POST /api/control/resume` - Resume agent execution

#### Monitoring & Alerts
- `GET /api/alerts` - System alerts and notifications
- `POST /api/alerts/<id>/resolve` - Mark alert as resolved
- `GET /api/health` - External service health status
- `GET /api/metrics` - Performance metrics aggregation
- `GET /api/audit-log` - Complete audit trail

#### Affiliate Management
- `GET /api/affiliates` - List all affiliate links
- `POST /api/affiliates` - Create new affiliate link
- `PUT /api/affiliates/<id>` - Update affiliate link
- `DELETE /api/affiliates/<id>` - Delete affiliate link

#### Real-time Events
- `GET /events` - Server-Sent Events for live updates
  - `new_cycle` - New execution cycle completed
  - `new_message` - New creator message
  - `alert_resolved` - Alert resolved
  - `prompt_changed` - Task prompt updated
  - `agent_paused` / `agent_resumed` - Control state changes

### Database Schema

New tables created in Supabase:

#### `system_alerts`
- `id` (uuid, PK)
- `agent_name` (text)
- `alert_type` (text): 'statute_violation' | 'low_balance' | 'service_error' | 'performance_warning' | 'high_fallback_rate'
- `severity` (text): 'info' | 'warning' | 'critical'
- `title`, `description` (text)
- `metadata` (jsonb)
- `resolved` (boolean), `resolved_at` (timestamptz)
- `created_at`, `updated_at` (timestamptz)

#### `audit_log`
- `id` (uuid, PK)
- `agent_name`, `action` (text)
- `actor` (text): 'user' or 'system'
- `resource_type`, `resource_id` (text)
- `changes` (jsonb)
- `status` (text): 'success' | 'failed'
- `created_at` (timestamptz)

#### `performance_metrics`
- `id` (uuid, PK)
- `agent_name`, `cycle_number` (integer)
- `metric_type` (text): 'tool_latency' | 'fallback_rate' | 'cycle_duration' | 'revenue_per_cycle'
- `metric_value` (numeric)
- `percentile` (integer): 50, 95, 99
- `metadata` (jsonb)
- `created_at` (timestamptz)

#### `service_health`
- `id` (uuid, PK)
- `service_name` (text): 'openai' | 'supabase' | 'perplexity' | 'steel_browser'
- `status` (text): 'healthy' | 'degraded' | 'down'
- `latency_ms` (integer)
- `quota_used_percent` (numeric)
- `updated_at` (timestamptz)

---

## Interface Features

### 1. Dashboard (/)

**Control Panel**
- Pause/Resume agent execution in real-time
- View last execution cycle details
- Quick access to all major functions

**Quick Metrics**
- Total cycles executed
- Total revenue
- Agent balance
- Active alerts count

**Last Cycle Display**
- Cycle number and timestamp
- Result text (truncated)
- Reflection and next actions preview

### 2. Advanced Dashboard (/pro)

**Financial Management Tab**
- Revenue, expenses, net margin overview
- Profit split visualization (80/20)
- Historical revenue chart
- Transaction history with filters
- Export capabilities (CSV, PDF)

**Affiliate Management Tab**
- CRUD interface for affiliate links
- Filter by status (active/inactive)
- Batch operations support
- Modal editor for link details
- Fields:
  - Product name
  - Niche (market segment)
  - Platform (where link is used)
  - Commission percentage
  - Product price (BRL)
  - Rating (0-5 stars)
  - Status (active/inactive)
  - Notes

**Performance Metrics Tab**
- Tool latency visualization
- Fallback rate trends
- Revenue per cycle analysis
- Key statistics (success rate, avg latency)

**Health Monitoring Tab**
- External service status (OpenAI, Supabase, Perplexity, Steel Browser)
- Latency measurements
- Quota usage percentages
- Last check timestamps

**Audit Log Tab**
- Complete action history
- Sortable by action type
- Timestamp and status tracking

### 3. Alerts & Notifications

**Alert Types**
- `statute_violation` - Constitutional guardrail breach
- `low_balance` - Agent balance below minimum reserve
- `service_error` - External API failures
- `performance_warning` - Metrics above SLO thresholds
- `high_fallback_rate` - Using fallbacks too frequently

**Alert Management**
- Real-time notification push
- Mark as resolved
- Severity levels (info, warning, critical)
- Persistent audit trail

### 4. System Health

**Service Monitoring**
- **OpenAI**: Model availability and latency
- **Supabase**: Database connection and quota status
- **Perplexity**: Search API availability and rate limits
- **Steel Browser**: Web scraping service status

**Metrics Tracked**
- Response latency (ms)
- Error rates
- Quota usage percentage
- Last successful check

### 5. Audit & Compliance

**Tracked Actions**
- Prompt updates
- Control commands (pause/resume)
- Affiliate link changes
- Configuration modifications
- Message processing
- Alert resolution

**Audit Fields**
- Actor (user/system)
- Action type
- Resource affected
- Changes made
- Status (success/failed)
- Timestamp

---

## Usage Examples

### Starting the Interface

```bash
# Standard dashboard on port 5000
OPENAI_API_KEY=... SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... \
python interface/app.py

# Custom port
PORT=8080 python interface/app.py

# Debug mode
DASHBOARD_DEBUG=true python interface/app.py
```

### Programmatic Control

```javascript
// Pause agent
await fetch('/api/control/pause', { method: 'POST' });

// Update task prompt
await fetch('/api/config/prompt', {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ prompt: 'New task here...' }),
});

// Get current config
const config = await fetch('/api/config').then(r => r.json());
console.log(config);
// {
//   agent_name: 'EU_DE_NEGOCIOS',
//   model: 'gpt-4.1-mini',
//   temperature: 0.7,
//   loop_interval_minutes: 20,
//   memory_window: 10,
//   agent_mode: 'real',
//   supabase_connected: true
// }

// Create affiliate link
await fetch('/api/affiliates', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    product_name: 'Curso Python Avançado',
    platform: 'Hotmart',
    niche: 'Programação',
    hotlink: 'https://...',
    commission_pct: 30,
    price_brl: 197,
    rating: 4.8,
    active: true,
    notes: 'Alta conversão em LinkedIn'
  }),
});
```

---

## Real-time Updates (SSE)

The interface uses Server-Sent Events for live updates:

```javascript
const es = new EventSource('/events');

es.onmessage = (event) => {
  const data = JSON.parse(event.data);

  switch(data.type) {
    case 'new_cycle':
      console.log('Novo ciclo:', data.data.cycle_number);
      break;
    case 'alert_resolved':
      console.log('Alerta resolvido:', data.alert_id);
      break;
    case 'prompt_changed':
      console.log('Prompt atualizado');
      break;
    case 'new_message':
      console.log('Nova mensagem do criador');
      break;
  }
};
```

---

## Security Considerations

### Row Level Security (RLS)

All tables have RLS enabled:
- `system_alerts`: Public read, agent-only write
- `audit_log`: Public read, system-only write
- `performance_metrics`: Public read, system-only write
- `service_health`: Public read, system-only update

### Environment Variables

**Required**
- `OPENAI_API_KEY` - LLM backend

**Highly Recommended**
- `SUPABASE_URL` - Database connection
- `SUPABASE_SERVICE_ROLE_KEY` - Full database access
- `SUPABASE_ANON_KEY` - User-level access (fallback)

**Optional**
- `DASHBOARD_PORT` - Custom port (default: 5000)
- `DASHBOARD_DEBUG` - Enable debug mode (default: false)
- `AGENT_NAME` - Agent identifier (default: EU_DE_NEGOCIOS)

### Best Practices

1. **Never expose service role key** in client-side code
2. **Use HTTPS** in production environments
3. **Implement authentication** layer for access control
4. **Monitor audit logs** regularly for suspicious activity
5. **Set up alerting** for critical events
6. **Review RLS policies** quarterly for compliance

---

## Integration Examples

### Slack Notifications

```python
# Add to main.py alert handler
import requests

def notify_slack(alert):
    webhook = os.getenv('SLACK_WEBHOOK_URL')
    if not webhook:
        return

    color = {
        'critical': 'danger',
        'warning': 'warning',
        'info': 'good'
    }.get(alert['severity'], 'good')

    requests.post(webhook, json={
        'attachments': [{
            'color': color,
            'title': alert['title'],
            'text': alert['description'],
            'ts': int(datetime.now().timestamp())
        }]
    })
```

### Discord Webhooks

```python
async def notify_discord(alert):
    webhook = os.getenv('DISCORD_WEBHOOK_URL')
    if not webhook:
        return

    embed = {
        'title': alert['title'],
        'description': alert['description'],
        'color': {
            'critical': 0xff0000,
            'warning': 0xffff00,
            'info': 0x00ff00
        }.get(alert['severity'], 0x0000ff)
    }

    async with aiohttp.ClientSession() as session:
        await session.post(webhook, json={'embeds': [embed]})
```

---

## Troubleshooting

### Dashboard Won't Connect
1. Verify Supabase credentials
2. Check firewall/network access
3. Review Flask logs for errors
4. Ensure tables exist (`system_alerts`, `audit_log`, etc.)

### Real-time Updates Not Working
1. Check SSE connection in browser DevTools
2. Verify CORS headers are present
3. Ensure `/events` endpoint is responsive
4. Check for proxy/load balancer issues

### Affiliate Links Not Showing
1. Verify `affiliate_links` table exists in Supabase
2. Check table has data for current agent
3. Ensure RLS policies allow reads
4. Review browser console for API errors

### Performance Issues
1. Reduce `limit` parameter in API calls
2. Add database indexes on frequently queried columns
3. Implement caching for static data
4. Monitor database query performance

---

## Future Enhancements

- Multi-user support with role-based access control
- Advanced charting library (Chart.js integration)
- Export functionality (PDF, XLSX reports)
- Automated SLO alerting
- Predictive revenue analytics
- A/B testing interface for affiliate strategies
- Custom metric definitions
- Webhook integrations for external systems
- Mobile-responsive dashboard
- Dark/light theme toggle

---

## Support

For issues or questions:
1. Check logs: `tail -f interface/app.py` output
2. Review database: `SELECT * FROM system_alerts WHERE resolved = false;`
3. Test connectivity: `curl http://localhost:5000/api/config`
4. Verify Supabase: Check `Statistics` tab in Supabase dashboard

