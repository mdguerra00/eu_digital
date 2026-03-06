# Runbook Operacional — Correção definitiva de `execution_receipts` no Supabase

## Objetivo
Eliminar fallback local contínuo (`execution_receipts.jsonl`) e restaurar persistência primária em banco para >=99% dos ciclos.

## 1) Pré-checagens
- [ ] Confirmar `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` e `EXECUTION_RECEIPTS_TABLE` no worker.
- [ ] Confirmar projeto/ambiente correto (produção vs homologação).
- [ ] Confirmar se há arquivo local pendente: `execution_receipts.jsonl`.

## 2) Diagnóstico diferencial

### A) Tabela ausente / schema incorreto
```sql
select table_schema, table_name
from information_schema.tables
where table_name = 'execution_receipts';
```

### B) Grants insuficientes
```sql
grant select, insert on table public.execution_receipts to service_role;
```

### C) RLS bloqueando
```sql
alter table public.execution_receipts enable row level security;
-- policy exemplo para role técnica
create policy if not exists execution_receipts_service_role_insert
on public.execution_receipts
for insert
to service_role
with check (true);
```

### D) Endpoint/projeto errado
- [ ] Validar `SUPABASE_URL` em runtime.
- [ ] Comparar `project_ref` esperado vs ativo no log de inicialização.

## 3) Validação técnica passo a passo
- [ ] Rodar ciclo do agente e observar ausência de aviso `fallback local`.
- [ ] Confirmar insert real no banco por `run_id` + `cycle_number`.
- [ ] Confirmar latência e campos de telemetria (`latency_ms`, `chars_captured`, `final_url`, `fallback_reason_code`).

## 4) Teste de insert com mesma role do worker
Pseudocódigo:
```python
sb.table("execution_receipts").insert({
  "run_id": "smoke-test",
  "cycle_number": 0,
  "step_id": "healthcheck",
  "tool": "healthcheck",
  "status": "success",
  "idempotency_key": "healthcheck-<timestamp>"
}).execute()
```

## 5) Replay/backfill do `execution_receipts.jsonl`
- [ ] Garantir tabela operante.
- [ ] Reiniciar worker (função de replay roda no início do ciclo).
- [ ] Confirmar log: `[ReceiptsReplay] replay concluído: X receipt(s) reenviados.`
- [ ] Se necessário, repetir até drenar backlog.

## 6) Verificação pós-correção (24h)
- [ ] `% ciclos com receipts no banco` >= 99%.
- [ ] `% fallback local` <= 1%.
- [ ] 0 alertas contínuos de fallback acima do limiar.

## 7) Rollback
- [ ] Se persistência falhar após deploy, manter ciclo ativo com fallback local.
- [ ] Reverter migração/policy alterada.
- [ ] Reprocessar backlog do JSONL após restauração.

## 8) Critérios de sucesso
- [ ] `execution_receipts` persistido no Supabase em >=99% dos ciclos (24h).
- [ ] Alertas de fallback estabilizados em zero contínuo.
- [ ] Reconciliação JSONL x tabela sem lacunas.
