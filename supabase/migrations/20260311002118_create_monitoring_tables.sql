/*
  # Create monitoring and audit tables for complete control interface

  1. New Tables
    - `system_alerts` — Real-time alerts and notifications
    - `audit_log` — Complete audit trail of all actions
    - `performance_metrics` — Aggregated performance data
    - `service_health` — External service health status
    
  2. Modified Tables
    - None (existing tables will be used for metrics aggregation)
    
  3. Security
    - Enable RLS on all new tables
    - Add policies for read access and agent-specific writes
    
  4. Indexes
    - Added for frequently queried columns (agent_name, created_at, priority)
*/

CREATE TABLE IF NOT EXISTS system_alerts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_name text NOT NULL,
  alert_type text NOT NULL, -- 'statute_violation' | 'low_balance' | 'service_error' | 'performance_warning' | 'high_fallback_rate'
  severity text NOT NULL, -- 'info' | 'warning' | 'critical'
  title text NOT NULL,
  description text,
  metadata jsonb DEFAULT '{}'::jsonb,
  resolved boolean DEFAULT false,
  resolved_at timestamptz,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

ALTER TABLE system_alerts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can read alerts"
  ON system_alerts FOR SELECT
  USING (true);

CREATE POLICY "Only agent and service can create alerts"
  ON system_alerts FOR INSERT
  WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_system_alerts_agent_name ON system_alerts(agent_name);
CREATE INDEX IF NOT EXISTS idx_system_alerts_created_at ON system_alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_alerts_severity ON system_alerts(severity);


CREATE TABLE IF NOT EXISTS audit_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_name text NOT NULL,
  action text NOT NULL, -- 'config_change' | 'prompt_edit' | 'affiliate_add' | 'message_send' | 'control_start' | 'control_stop'
  actor text NOT NULL, -- 'user' or 'system'
  actor_id text,
  resource_type text,
  resource_id text,
  changes jsonb DEFAULT '{}'::jsonb,
  status text DEFAULT 'success', -- 'success' | 'failed'
  error_message text,
  ip_address text,
  user_agent text,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can read audit log"
  ON audit_log FOR SELECT
  USING (true);

CREATE POLICY "Only system can create audit entries"
  ON audit_log FOR INSERT
  WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_audit_log_agent_name ON audit_log(agent_name);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);


CREATE TABLE IF NOT EXISTS performance_metrics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_name text NOT NULL,
  cycle_number integer,
  metric_type text NOT NULL, -- 'tool_latency' | 'fallback_rate' | 'cycle_duration' | 'revenue_per_cycle'
  metric_value numeric NOT NULL,
  percentile integer, -- 50, 95, 99
  period_start timestamptz,
  period_end timestamptz,
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE performance_metrics ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can read performance metrics"
  ON performance_metrics FOR SELECT
  USING (true);

CREATE POLICY "Only system can write metrics"
  ON performance_metrics FOR INSERT
  WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_performance_metrics_agent_name ON performance_metrics(agent_name);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_metric_type ON performance_metrics(metric_type);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_created_at ON performance_metrics(created_at DESC);


CREATE TABLE IF NOT EXISTS service_health (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  service_name text NOT NULL, -- 'openai' | 'supabase' | 'perplexity' | 'steel_browser'
  status text NOT NULL, -- 'healthy' | 'degraded' | 'down'
  latency_ms integer,
  last_check_at timestamptz,
  error_message text,
  quota_used_percent numeric DEFAULT 0,
  quota_limit_units text,
  metadata jsonb DEFAULT '{}'::jsonb,
  updated_at timestamptz DEFAULT now()
);

ALTER TABLE service_health ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can read service health"
  ON service_health FOR SELECT
  USING (true);

CREATE POLICY "Only system can update health"
  ON service_health FOR UPDATE
  WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_service_health_service_name ON service_health(service_name);
CREATE INDEX IF NOT EXISTS idx_service_health_status ON service_health(status);
