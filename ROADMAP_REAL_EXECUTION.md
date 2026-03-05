# Roadmap: sair da simulação e operar em ambiente real

## Diagnóstico objetivo do estado atual

1. **O ciclo principal ainda é orientado a texto do LLM**, não a um plano executável validado.
   - O `llm_cycle` retorna apenas `result_text`, `reflection` e `next_actions` em JSON livre.
   - Depois disso, o executor tenta inferir ações por palavras-chave em `next_actions`.

2. **Existem caminhos explícitos de fallback/simulação**, que podem gerar sensação de "execução real" sem garantia de impacto externo.
   - Sem Supabase, os ciclos são salvos em arquivo local (`agent_cycles.json`).
   - Sem chave da Perplexity, a busca usa resultados simulados (`example.com`, etc.).

3. **Ferramentas executadas não fecham o loop de decisão**.
   - O resultado de `tool_executor.execute_tools(...)` é logado, mas não alimenta o estado persistido do ciclo (nem como artefato estruturado obrigatório).

4. **Não existe camada de prova operacional (receipts)**.
   - Não há um ledger imutável de: qual tool rodou, com qual input, qual output bruto, hash/evidência e status final.

---

## Próximo passo (o mais importante): criar o "Plano Executável + Comprovante"

Se você fizer **apenas uma mudança de arquitetura agora**, faça esta:

### 1) Trocar `next_actions` textual por um plano estruturado obrigatório

Formato mínimo sugerido:

```json
{
  "plan": [
    {
      "id": "step_1",
      "tool": "web_search",
      "args": {"query": "...", "count": 5},
      "success_criteria": "...",
      "on_failure": "retry_once|skip|halt"
    }
  ]
}
```

Sem esse plano válido, o ciclo deve falhar (`fail fast`), em vez de "seguir com texto".

### 2) Criar tabela (ou arquivo append-only) de `execution_receipts`

Para cada step:
- `run_id`, `cycle_number`, `step_id`
- `tool`, `args`
- `started_at`, `finished_at`, `status`
- `raw_output` (ou ponteiro para blob)
- `evidence_hash` (sha256 do output relevante)
- `used_fallback` (boolean obrigatório)

Isso transforma "o agente disse que fez" em **"a execução está comprovada"**.

### 3) Bloquear fallback em modo real

Introduzir `AGENT_MODE=real|simulation`.
- `simulation`: permite fallback atual.
- `real`: proíbe fallback silencioso (ex.: Perplexity sem chave deve retornar erro explícito e marcar cycle como failed).

---

## Sequência prática de implementação (curta)

1. **Semana 1 — Verdade operacional**
   - Implementar `AGENT_MODE`.
   - Implementar `execution_receipts`.
   - Exigir plano estruturado do LLM.

2. **Semana 2 — Ações reais pequenas e reversíveis**
   - Criar 1 ação de escrita real e segura (ex.: publicar relatório em um destino real controlado por você: tabela específica, bucket, ou endpoint interno).
   - Toda ação com idempotência (`idempotency_key`) e dry-run opcional.

3. **Semana 3 — Governança de risco**
   - Política de aprovação por nível de risco (`low`, `medium`, `high`).
   - `high` só executa com aprovação explícita.

---

## Definição objetiva de “não é mentira”

Uma execução só conta como real se cumprir **todos**:
1. Tem `receipt` persistido.
2. Tem `used_fallback=false` em modo `real`.
3. Tem evidência verificável (`hash`, output bruto, timestamps).
4. O próximo ciclo consome essa evidência como memória factual.

Se faltar qualquer item, deve aparecer no relatório como **simulação**.

---

## KPI de transição (simulação -> real)

- `% de steps com receipt` (meta: 100%)
- `% de steps com used_fallback=false em AGENT_MODE=real` (meta: 100%)
- `% de ciclos com pelo menos 1 ação externa comprovada` (meta crescente)
- `taxa de erro por ferramenta` (para decidir onde endurecer/reduzir escopo)

---

## Resumo executivo

O próximo passo não é "mais prompt" nem "mais reflexão".
É **infra de execução verificável**:
1) plano estruturado,
2) receipts imutáveis,
3) modo real sem fallback silencioso.

Sem isso, o sistema continua um gerador de narrativas operacionais.
Com isso, vira um agente auditável.
