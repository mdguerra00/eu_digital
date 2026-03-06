-- Migração idempotente para garantir a tabela public.execution_receipts
-- compatível com o worker (main.py), inclusive em ambiente parcialmente criado.

create table if not exists public.execution_receipts (
  id bigint generated always as identity primary key
);

alter table public.execution_receipts
  add column if not exists run_id text,
  add column if not exists cycle_number integer,
  add column if not exists step_id text,
  add column if not exists tool text,
  add column if not exists args jsonb,
  add column if not exists started_at timestamptz,
  add column if not exists finished_at timestamptz,
  add column if not exists status text,
  add column if not exists raw_output jsonb,
  add column if not exists evidence_hash text,
  add column if not exists used_fallback boolean,
  add column if not exists fallback_reason text,
  add column if not exists fallback_reason_code text,
  add column if not exists latency_ms integer,
  add column if not exists chars_captured integer,
  add column if not exists final_url text,
  add column if not exists idempotency_key text,
  add column if not exists created_at timestamptz;

-- Defaults / NOT NULL para alinhar com o payload do worker.
alter table public.execution_receipts
  alter column args set default '{}'::jsonb,
  alter column raw_output set default '{}'::jsonb,
  alter column used_fallback set default false,
  alter column latency_ms set default 0,
  alter column chars_captured set default 0,
  alter column created_at set default now();

update public.execution_receipts
set
  args = coalesce(args, '{}'::jsonb),
  raw_output = coalesce(raw_output, '{}'::jsonb),
  used_fallback = coalesce(used_fallback, false),
  latency_ms = coalesce(latency_ms, 0),
  chars_captured = coalesce(chars_captured, 0),
  created_at = coalesce(created_at, now())
where
  args is null
  or raw_output is null
  or used_fallback is null
  or latency_ms is null
  or chars_captured is null
  or created_at is null;

alter table public.execution_receipts
  alter column run_id set not null,
  alter column cycle_number set not null,
  alter column step_id set not null,
  alter column tool set not null,
  alter column args set not null,
  alter column started_at set not null,
  alter column finished_at set not null,
  alter column status set not null,
  alter column raw_output set not null,
  alter column evidence_hash set not null,
  alter column used_fallback set not null,
  alter column latency_ms set not null,
  alter column chars_captured set not null,
  alter column idempotency_key set not null,
  alter column created_at set not null;

-- Constraints (adiciona só se ainda não existirem)
do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'execution_receipts_status_chk'
      and conrelid = 'public.execution_receipts'::regclass
  ) then
    alter table public.execution_receipts
      add constraint execution_receipts_status_chk
      check (status in ('success', 'failed'));
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'execution_receipts_latency_chk'
      and conrelid = 'public.execution_receipts'::regclass
  ) then
    alter table public.execution_receipts
      add constraint execution_receipts_latency_chk
      check (latency_ms >= 0);
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'execution_receipts_chars_chk'
      and conrelid = 'public.execution_receipts'::regclass
  ) then
    alter table public.execution_receipts
      add constraint execution_receipts_chars_chk
      check (chars_captured >= 0);
  end if;
end
$$;

create unique index if not exists execution_receipts_idempotency_key_uidx
  on public.execution_receipts (idempotency_key);

create index if not exists execution_receipts_run_cycle_idx
  on public.execution_receipts (run_id, cycle_number);

create index if not exists execution_receipts_started_at_idx
  on public.execution_receipts (started_at desc);

-- Permissões para o fluxo atual (service role)
grant select, insert on table public.execution_receipts to service_role;

-- Segurança (RLS)
alter table public.execution_receipts enable row level security;

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
