-- Cria tabela de receipts de execução usada pelo worker (main.py)
create table if not exists public.execution_receipts (
  id bigint generated always as identity primary key,
  run_id text not null,
  cycle_number integer not null,
  step_id text not null,
  tool text not null,
  args jsonb not null default '{}'::jsonb,
  started_at timestamptz not null,
  finished_at timestamptz not null,
  status text not null,
  raw_output jsonb not null default '{}'::jsonb,
  evidence_hash text not null,
  used_fallback boolean not null default false,
  fallback_reason text,
  fallback_reason_code text,
  latency_ms integer not null default 0,
  chars_captured integer not null default 0,
  final_url text,
  idempotency_key text not null unique,
  created_at timestamptz not null default now(),
  constraint execution_receipts_status_chk check (status in ('success', 'failed')),
  constraint execution_receipts_latency_chk check (latency_ms >= 0),
  constraint execution_receipts_chars_chk check (chars_captured >= 0)
);

create index if not exists execution_receipts_run_cycle_idx
  on public.execution_receipts (run_id, cycle_number);

create index if not exists execution_receipts_started_at_idx
  on public.execution_receipts (started_at desc);

-- Permissões mínimas para o fluxo atual do worker
grant select, insert on table public.execution_receipts to service_role;

-- Opcional: leitura para painéis internos
grant select on table public.execution_receipts to authenticated;

-- Segurança (RLS)
alter table public.execution_receipts enable row level security;

-- service_role normalmente bypassa RLS, mas deixamos policy explícita
drop policy if exists execution_receipts_service_role_insert on public.execution_receipts;
create policy execution_receipts_service_role_insert
on public.execution_receipts
for insert
to service_role
with check (true);

drop policy if exists execution_receipts_service_role_select on public.execution_receipts;
create policy execution_receipts_service_role_select
on public.execution_receipts
for select
to service_role
using (true);
