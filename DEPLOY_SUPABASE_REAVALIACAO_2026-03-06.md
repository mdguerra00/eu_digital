# Reavaliação de Deploys pós-correções (2026-03-06)

## 1) Contexto desta reavaliação
- Base de comparação: `DEPLOY_SUPABASE_AUDIT_2026-03-06.md`.
- Evidências novas analisadas: logs dos ciclos **112, 113 e início do 114** (janela aproximada **14:44:28 UTC → 14:46:35 UTC**).
- Objetivo: validar o que melhorou, o que permaneceu igual e o que ainda diverge do planejado.

---

## 2) Resultado executivo

### Status geral
- **Parcialmente conforme ao planejado**.
- Houve melhoria em **qualidade de aquisição de conteúdo** (fontes textuais com ~2000 chars em múltiplas chamadas).
- Persistem gaps críticos em **confiabilidade de `execution_receipts`** (fallback local continuado) e em **diversidade/observabilidade de ferramentas**.

### Semáforo por frente
- **Confiabilidade de dados (P0)**: 🔴 **Não atendido**
- **Qualidade por ciclo (P1)**: 🟡 **Parcialmente atendido**
- **Observabilidade (P2)**: 🔴 **Não atendido**
- **Eficiência/custo (P3)**: ⚪ **Sem evidência suficiente nesta janela**

---

## 3) Evidências objetivas (logs novos)
1. Worker inicializa normalmente, com conexão Supabase ativa e SteelBrowser configurado.
2. Cadência de ciclo estável (~1 minuto), com guardrail em todos os ciclos observados.
3. Ferramentas executadas por ciclo: **2 chamadas de `web_search`**, ambas com sucesso.
4. Persistência de ciclo mantida (`Ciclo salvo | id=289`, `id=290`) e `agent_state` atualizado.
5. **Persistência de receipts ainda falha em banco**:
   - Mensagem de fallback para `execution_receipts.jsonl`.
   - Alertas de fallback acumulado por múltiplos ciclos (`3 ciclo(s)`, `4 ciclo(s)`).
6. Aquisição de conteúdo melhor: scrapes com ~1999/2000 chars em fontes textuais.

---

## 4) Comparação direta: Planejado x Realizado

## 4.1 P0 — Restaurar `execution_receipts` no Supabase
**Planejado no audit anterior**
- Corrigir tabela/policies/grants e eliminar fallback local.
- Implementar replay de JSONL para banco.

**Realizado agora**
- ❌ **Não atendido**: fallback local continua ativo e com alerta recorrente.
- ❓ Sem evidência de replay/backfill executado.

**Impacto**
- Rastreabilidade ponta-a-ponta ainda incompleta.
- Auditoria e reconciliação continuam dependentes de arquivo local.

## 4.2 P1 — Política anti-fonte fraca e qualidade de conteúdo
**Planejado no audit anterior**
- Evitar síntese com fonte rasa; forçar nova fonte textual quando chars baixos.

**Realizado agora**
- ✅ **Melhoria observada**: múltiplas fontes textuais com ~2000 chars.
- ⚠️ Ainda sem evidência explícita de política automatizada por limiar de chars.

**Impacto**
- Qualidade de insumo para síntese melhorou na janela observada.

## 4.3 P1/P2 — Diversidade de toolkit + telemetria detalhada
**Planejado no audit anterior**
- Maior variedade de ferramentas por objetivo.
- Telemetria granular (latência, URL final, chars, status por etapa).

**Realizado agora**
- ❌ **Não atendido**: execução segue concentrada em `web_search` (2x/ciclo).
- ⚠️ Há detalhes de scraper, mas resumo de ferramentas permanece agregado, sem evidência de receipts no banco.

**Impacto**
- Menor profundidade analítica por ciclo.
- Menor capacidade de auditoria operacional estruturada.

## 4.4 P3 — Ajuste dinâmico de intervalo e cache de buscas
**Planejado no audit anterior**
- Adaptar intervalo por novidade e usar cache de consultas.

**Realizado agora**
- ⚪ Sem evidência suficiente na janela para confirmar implementação.
- Cadência segue fixa em 1 minuto.

---

## 5) Diagnóstico consolidado pós-correção

## O que evoluiu
- Estabilidade operacional preservada.
- Melhor densidade textual das fontes coletadas.
- Execução com duas buscas relevantes por ciclo, em vez de uma única busca simples.

## O que continua crítico
- `execution_receipts` indisponível no Supabase (persistência local como contingência contínua).
- Ausência de confirmação de replay/backfill de receipts.
- Observabilidade ainda não fechada para auditoria de ponta a ponta.

---

## 6) Plano de ação recomendado (revisado)

### Ação imediata (0–2h)
1. Validar existência física da tabela `execution_receipts` no projeto Supabase correto.
2. Revisar grants/policies da role do worker para `INSERT`/`SELECT`.
3. Rodar teste de insert mínimo da própria aplicação (mesma conexão/role do worker).
4. Se sucesso: executar replay de `execution_receipts.jsonl` pendente.

### Curto prazo (hoje)
5. Criar alerta hard para fallback > 1 ciclo contínuo.
6. Publicar métrica diária: `% ciclos com receipts no banco` e `% fallback local`.
7. Adicionar campo de causa padronizada do fallback (`table_missing`, `rls_denied`, `network`, etc.).

### Próxima iteração (24–48h)
8. Explicitar política anti-fonte fraca no executor (threshold de chars + retry em nova fonte textual).
9. Enriquecer telemetria por etapa (ferramenta, subchamada, latência, URL, chars, status).

---

## 7) Critérios de aceite desta reavaliação
- `execution_receipts` em banco em **>= 99%** dos ciclos por 24h.
- **0 alertas** de fallback contínuo acima do limite definido.
- Registro auditável de ferramentas/subchamadas por ciclo sem lacunas de persistência.

---

## 8) Prompts exatos para uma I.A. executar esta auditoria com precisão

> Use os prompts abaixo **literalmente** (copiar e colar), na ordem.

### Prompt 1 — Coleta e extração de evidências
```text
Você é um auditor técnico de runtime de agentes com foco em Supabase.

Tarefa:
1) Ler o arquivo DEPLOY_SUPABASE_AUDIT_2026-03-06.md e extrair:
   - Diagnóstico anterior
   - Plano recomendado por prioridade (P0/P1/P2/P3)
   - Critérios de sucesso definidos
2) Ler os logs mais recentes fornecidos no prompt atual.
3) Produzir uma tabela "Evidências" contendo, para cada item:
   - timestamp
   - ciclo
   - evento
   - status (ok/alerta/erro)
   - impacto operacional

Regras:
- Não invente dados ausentes.
- Se faltar prova para um item, marcar como "sem evidência".
- Responder em português.
- Priorizar sinais relacionados a: agent_cycles, agent_state, execution_receipts, fallback local, ferramentas, qualidade de scraping.
```

### Prompt 2 — Comparação planejado x realizado
```text
Com base nas evidências extraídas, compare o estado atual com o planejado no DEPLOY_SUPABASE_AUDIT_2026-03-06.md.

Formato obrigatório:
- Seções por prioridade: P0, P1, P2, P3
- Em cada seção, incluir:
  1) Planejado
  2) Realizado
  3) Status (Atendido / Parcial / Não atendido / Sem evidência)
  4) Risco residual
  5) Próxima ação objetiva

Regras:
- Use linguagem direta e verificável.
- Não generalizar sem evidência de log.
- Se houver melhoria parcial, explicitar exatamente qual métrica/sinal melhorou.
- Responder em português.
```

### Prompt 3 — Geração de relatório executivo final
```text
Gere um relatório final chamado "Reavaliação de Deploys pós-correções" com:
1) Resumo executivo (semáforo por frente)
2) Evidências objetivas
3) Comparação Planejado x Realizado
4) Diagnóstico consolidado
5) Plano de ação revisado (0-2h, hoje, 24-48h)
6) Critérios de aceite mensuráveis

Requisitos de qualidade:
- Não incluir recomendações vagas.
- Toda recomendação deve ter dono técnico sugerido (ex.: backend, data, SRE) e saída verificável.
- Destacar explicitamente se execution_receipts ainda está em fallback local.
- Manter foco em auditabilidade e confiabilidade de dados.
- Responder em português.
```

### Prompt 4 — Prompt de execução operacional (runbook para correção)
```text
Atue como engenheiro de confiabilidade e escreva um runbook operacional para corrigir definitivamente o problema de execution_receipts em fallback local.

O runbook deve conter:
- Pré-checagens
- Diagnóstico diferencial (tabela ausente vs RLS vs grants vs endpoint/projeto errado)
- Passo a passo técnico de validação
- Teste de insert com mesma role do worker
- Procedimento de replay/backfill do execution_receipts.jsonl
- Verificação pós-correção por 24h
- Plano de rollback
- Critérios de sucesso

Saída em checklist markdown com comandos/pseudocódigo quando aplicável.
Responder em português.
```

### Prompt 5 — Prompt de verificação automática contínua
```text
Crie uma especificação de monitoramento contínuo para o pipeline do agente no Supabase.

Incluir:
- SLIs/SLOs mínimos:
  - % ciclos com receipts gravados no banco
  - taxa de fallback local
  - latência de persistência por ciclo
- Alertas (warning/critical) com limiares objetivos
- Campos obrigatórios de telemetria por ferramenta/subchamada
- Dashboard mínimo para operação diária
- Rotina automática de reconciliação entre execution_receipts.jsonl e tabela execution_receipts

Formato:
- Tabela de métricas
- Tabela de alertas
- Checklist de implantação

Responder em português.
```
