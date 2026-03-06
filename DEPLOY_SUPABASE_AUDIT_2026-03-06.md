# Avaliação de Deploy Logs e Geração no Supabase (2026-03-06)

## Escopo analisado
- Janela dos logs: **14:27:01 UTC → 14:29:21 UTC**.
- Agente: `EU_DE_NEGOCIOS`.
- Tabelas esperadas: `agent_cycles`, `agent_state`, `execution_receipts`.

## Diagnóstico dos deploy logs

### O que está funcionando
1. **Inicialização e configuração do worker**
   - Container inicia normalmente.
   - Conexão com Supabase reportada como ativa.
   - `SteelBrowser` configurado e respondendo.

2. **Execução cíclica estável**
   - Ciclos 95, 96 e 97 executados em cadência de ~1 minuto (`LOOP_INTERVAL_MINUTES=1.0`).
   - Guardrail validando ações em todos os ciclos.
   - `web_search` executada com sucesso em todos os ciclos.

3. **Persistência principal funcionando**
   - Inserts em `agent_cycles` ocorreram com IDs incrementais (`271`, `272`, `273`).
   - Atualização de `agent_state` confirmada ao final de cada ciclo.

### Alertas e desalinhamentos
1. **Tabela de receipts indisponível**
   - Log explícito: `execution_receipts` indisponível; fallback para `execution_receipts.jsonl`.
   - Risco: perda de rastreabilidade centralizada, dificuldades de auditoria e reconciliação de execução.

2. **Baixa diversidade de ferramentas por ciclo**
   - Apenas 1 ferramenta (`web_search`) por ciclo.
   - O `SteelBrowser` aparece como scraper de uma URL por ciclo, mas o resumo de ferramentas mostra somente `web_search`, sugerindo granularidade parcial de telemetria.

3. **Qualidade da aquisição de conteúdo variável**
   - Ciclo 95: scraping de YouTube com apenas `451` caracteres úteis.
   - Ciclos 96/97: ~`2000` caracteres em páginas textuais (melhor qualidade para síntese).

4. **Possível truncamento de query nos logs**
   - Exemplo: `Google Analytic` sem “s” em trecho logado.
   - Pode ser apenas truncamento visual, mas vale validar construção final de prompt de busca.

## Avaliação do que está sendo gerado no Supabase

### Resultado observado (via logs)
- **`agent_cycles`**: aparentemente em linha com o esperado (persistência por ciclo, payload completo com `execution_plan`, `focus`, `next_actions`, `reflection`, `result_text`).
- **`agent_state`**: em linha com o esperado (atualização de `current_task_prompt` por ciclo).
- **`execution_receipts`**: **fora do esperado** (indisponível no banco; gravação apenas local em JSONL).

### Limitação desta auditoria
- Não foi possível consultar diretamente o Supabase neste ambiente por ausência de credenciais de acesso (`SUPABASE_SERVICE_ROLE_KEY`/`SUPABASE_ANON_KEY`).
- Portanto, a validação de “todas as planilhas/tabelas” foi inferida a partir dos logs fornecidos e não por inspeção SQL direta.

## Comparação com o esperado

### Em linha com o esperado
- Ciclo contínuo sem falhas fatais.
- Persistência de ciclos e estado.
- Guardrail ativo e sem bloqueios.

### Abaixo do esperado
- Receipts centralizados indisponíveis.
- Baixa profundidade por ciclo (muito foco em busca + scraping único).
- Telemetria funcional, porém incompleta para auditoria ponta-a-ponta (ferramentas x chamadas internas).

## Melhorias recomendadas (prioridade)

### P0 — Confiabilidade de dados
1. **Restaurar `execution_receipts` no Supabase imediatamente**
   - Verificar existência da tabela, permissões RLS/policies e grant do role usado no worker.
   - Enquanto indisponível, implementar rotina de replay do `execution_receipts.jsonl` para a tabela quando conexão voltar.

2. **Alerta automático para fallback de receipts**
   - Disparar alerta (Slack/Discord/email) quando houver fallback para arquivo local por mais de N ciclos.

### P1 — Qualidade de execução por ciclo
3. **Política anti-fonte fraca (ex.: YouTube sem transcrição)**
   - Se scraping retornar `< X chars` (ex.: 1200), forçar segunda fonte textual antes de sintetizar insight.

4. **Diversificar toolkit por objetivo**
   - Incluir passo opcional de `market_analyzer`/validação cruzada quando tema exigir decisão estratégica.

### P2 — Observabilidade e governança
5. **Expandir telemetria de ferramentas**
   - Registrar em `execution_receipts`: ferramenta, latência, chars capturados, URL final, status e motivo de fallback.

6. **Métricas operacionais mínimas**
   - Taxa de sucesso por ferramenta.
   - Tempo médio por ciclo.
   - Cobertura de receipts no banco (vs local).

### P3 — Eficiência e custo
7. **Ajuste dinâmico de intervalo**
   - Em ciclos com baixa novidade, ampliar intervalo para 2–5 min.
   - Em picos de eventos (mensagens do criador, erros, campanhas), reduzir para 1 min.

8. **Cache de pesquisas por janela curta (10–30 min)**
   - Evita repetir consultas quase idênticas sem ganho informacional.

## Checklist operacional sugerido (Supabase)
1. Confirmar schema e grants:
   - `agent_cycles`, `agent_state`, `execution_receipts`, `creator_messages`.
2. Testar insert manual com mesma role do worker.
3. Revisar políticas RLS para inserção/leitura do agente.
4. Rodar backfill de `execution_receipts.jsonl`.
5. Confirmar dashboards/queries de monitoramento pós-correção.

## Critérios de sucesso após melhorias
- `execution_receipts` gravando em banco em **>99%** dos ciclos.
- Queda de ciclos com fontes de baixa densidade textual.
- Aumento de qualidade dos insights (menos redundância e mais acionáveis).
- Visibilidade completa da execução por ciclo em dashboard único.
