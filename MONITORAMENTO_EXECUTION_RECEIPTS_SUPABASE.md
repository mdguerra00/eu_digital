# Especificação de Monitoramento Contínuo — Pipeline `execution_receipts`

## Tabela de métricas (SLIs/SLOs)

| Métrica | Definição | SLO mínimo | Fonte |
|---|---|---:|---|
| `% ciclos com receipts no banco` | ciclos sem fallback / ciclos totais (24h) | >= 99% | `receipts_cycle_metrics.jsonl` + Supabase |
| `% fallback local` | ciclos com fallback ativo / ciclos totais (24h) | <= 1% | `receipts_cycle_metrics.jsonl` |
| Latência de persistência | p95 de `latency_ms` por ciclo | <= 1500ms | `execution_receipts` |
| Cobertura de telemetria | receipts com `tool`, `status`, `latency_ms`, `final_url`, `chars_captured` | >= 99% | `execution_receipts` |

## Tabela de alertas

| Severidade | Condição | Janela | Ação |
|---|---|---|---|
| warning | `% fallback local` > 0% | 15 min | notificar canal de engenharia |
| critical | fallback contínuo > 1 ciclo | tempo real | pager SRE + abertura automática de incidente |
| warning | cobertura de telemetria < 99% | 1h | backlog backend |
| critical | `% ciclos com receipts no banco` < 99% | 24h | bloquear promoção de release |

## Campos obrigatórios de telemetria por subchamada
- `run_id`
- `cycle_number`
- `step_id`
- `tool`
- `status`
- `latency_ms`
- `chars_captured`
- `final_url`
- `fallback_reason`
- `fallback_reason_code`
- `idempotency_key`

## Dashboard mínimo diário
- Série temporal: `% fallback local` por hora.
- Série temporal: `% ciclos com receipts no banco` (24h móvel).
- Heatmap: `fallback_reason_code` por ciclo.
- Tabela: top ferramentas por latência média e p95.

## Rotina de reconciliação automática (JSONL x Supabase)
- [ ] Job diário lê `execution_receipts.jsonl`.
- [ ] Para cada `idempotency_key`, checa existência no banco.
- [ ] Reinsere ausentes.
- [ ] Gera relatório de divergência (total lido, total já presente, total reenviado, total erro).

## Checklist de implantação
- [ ] Configurar `RECEIPTS_FALLBACK_ALERT_THRESHOLD=1`.
- [ ] Publicar coleta de `receipts_cycle_metrics.jsonl` no stack de observabilidade.
- [ ] Criar alertas warning/critical conforme limiares.
- [ ] Validar runbook de replay em ambiente de staging.
- [ ] Aprovar rollout em produção com monitoramento em tempo real por 24h.
