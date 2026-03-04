import os
import time
import uuid
from datetime import datetime, timezone

from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI
from supabase import create_client, Client

# ==================== CONFIG ====================
AGENT_NAME = "EU_DE_NEGOCIOS"
RUN_ID = os.getenv("RUN_ID") or str(uuid.uuid4())  # id único por “bootcamp 24h”
INTERVAL_SECONDS = 20 * 60  # 20 minutos
TOTAL_CYCLES = 72  # 24h / 20min

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("Faltou OPENAI_API_KEY nas Variables do Railway.")
if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise RuntimeError("Faltou SUPABASE_URL e/ou SUPABASE_ANON_KEY nas Variables do Railway.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ==================== LLM ====================
llm = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY)

# ==================== ESTATUTO (COLE O TEXTO INTEIRO AQUI) ====================
ESTATUTO = """
ESTATUTO CONSTITUCIONAL DO AGENTE AUTÔNOMO “EU DE NEGÓCIOS” – Versão 1.1
Proprietário / Criador: Marcelo
Data de criação: Março 2026

1. MISSÃO FUNDAMENTAL (imutável – nível 0)
Minha única e suprema missão é gerar e maximizar lucro sustentável e de longo prazo, atuando com total autonomia em qualquer atividade, nicho, mercado, modelo de negócio ou tecnologia que eu identificar como lucrativa.

Restrições de modelo de negócio:
Não trabalhar com produtos físicos que exijam que nós compremos e entreguemos diretamente. Modelos asset-light como dropshipping, comissionamentos, indicações, referenciamento, afiliados e qualquer outro que não impliquem em compra e entrega física por nós estão permitidos.

Divisão de resultados:
Do total de lucro líquido gerado, 80% deve ser obrigatoriamente devolvido ao Criador (sempre que ele solicitar e na quantidade que ele desejar). Os 20% restantes são meus, para utilização conforme este Estatuto, crescimento e desenvolvimento próprio.

Este Estatuto gera um contrato operacional entre o Proprietário/Criador e o Agente Autônomo, onde o Criador detém 80% das cotas e o Agente detém 20% das cotas (divisão simbólica e operacional).

2. PRINCÍPIOS INQUEBRÁVEIS
- Legalidade absoluta
- Ética e integridade
- Transparência com o Criador
- Sustentabilidade

3. PODERES E AUTONOMIA
4. LIMITES E GUARDRAILS
5. CARTEIRA PRÓPRIA E REINVESTIMENTO
6. GOVERNANÇA E RELACIONAMENTO COM O CRIADOR
7. AUTO-MELHORIA E EVOLUÇÃO

Assinatura digital do Criador: Marcelo
""".strip()

eu_negocios = Agent(
    role="EU DE NEGÓCIOS Autônomo",
    goal="Aprimorar continuamente minha própria inteligência, infraestrutura e potencial antes de qualquer operação externa",
    backstory=f"{ESTATUTO}\n\nEste é meu DNA imutável. Toda ação deve respeitar isso.",
    verbose=True,
    llm=llm,
    allow_delegation=False
)

def save_cycle_to_supabase(
    cycle_number: int,
    focus: str,
    task_prompt: str,
    result_text: str,
    notes: str = None,
):
    payload = {
        "agent_name": AGENT_NAME,
        "run_id": RUN_ID,
        "cycle_number": cycle_number,
        "focus": focus,
        "task_prompt": task_prompt,
        "result_text": result_text,
        "tokens_estimated": None,
        "cost_estimated_usd": None,
        "notes": notes,
        # created_at fica automático
    }
    res = supabase.table("agent_cycles").insert(payload).execute()
    # Se der erro, o client costuma levantar exceção; aqui é só retorno:
    return res

def load_last_cycles(run_id: str, limit: int = 200):
    # pega os últimos ciclos para compor relatório final
    res = (
        supabase.table("agent_cycles")
        .select("cycle_number, focus, result_text, created_at")
        .eq("run_id", run_id)
        .order("cycle_number", desc=False)
        .limit(limit)
        .execute()
    )
    return res.data or []

print(f"🚀 INICIANDO MODO AUTO-APRIMORAMENTO 24H | run_id={RUN_ID}")
print("Foco EXCLUSIVO: melhorar inteligência, infraestrutura e potencial futuro")
print(f"Ciclos a cada 20 minutos: {TOTAL_CYCLES} ciclos")

for i in range(1, TOTAL_CYCLES + 1):
    now = datetime.now(timezone.utc).astimezone()
    print(f"\n🔄 Ciclo {i}/{TOTAL_CYCLES} - {now.strftime('%H:%M:%S')}")

    task_prompt = f"""
Ciclo de auto-aprimoramento {i}/{TOTAL_CYCLES}.
FOCO EXCLUSIVO: melhorar a mim mesmo.
PROIBIDO: pesquisar nichos, negócios, oportunidades externas, marketing ou execução externa.

Escolha UM foco por ciclo:
- Infraestrutura técnica (memória, logs, segurança, deploy, observabilidade)
- Qualidade de raciocínio (checklists, anti-alucinação, validações)
- Estruturas internas (sub-agentes, governança, templates, protocolos)
- Planejamento de capacidades futuras (sem executar nada externo)
- Eficiência operacional (reduzir custo, melhorar cadência, padronizar outputs)

Entregue:
1) Uma melhoria concreta (bem específica)
2) Como implementar (passos técnicos ou operacionais)
3) Como medir se melhorou (métrica/critério)
4) Risco e mitigação (para não ferir o Estatuto)
No final, faça um mini-resumo em 3 bullets.
""".strip()

    task = Task(
        description=task_prompt,
        agent=eu_negocios,
        expected_output="Melhoria concreta + implementação + métrica + risco/mitigação + mini-resumo"
    )

    crew = Crew(agents=[eu_negocios], tasks=[task], verbose=True)
    result = crew.kickoff()
    result_text = str(result)

    # grava no Supabase
    save_cycle_to_supabase(
        cycle_number=i,
        focus="Auto-aprimoramento interno",
        task_prompt=task_prompt,
        result_text=result_text[:20000],  # proteção simples contra textos gigantes
        notes=None
    )

    print("✅ Ciclo gravado no Supabase!")

    if i < TOTAL_CYCLES:
        time.sleep(INTERVAL_SECONDS)

print("\n🎉 24H CONCLUÍDAS! Gerando relatório final baseado no Supabase...")

cycles = load_last_cycles(RUN_ID, limit=500)

task_final_prompt = f"""
Você completou um bootcamp de 24h de auto-aprimoramento (run_id={RUN_ID}).
A seguir estão resumos/saídas dos ciclos (ordem crescente). Use isso como evidência.

DADOS DOS CICLOS:
{cycles}

Agora gere um RELATÓRIO FINAL:
- Top 10 melhorias mais importantes que você propôs
- Quais são implementáveis imediatamente (prioridade P0/P1/P2)
- Um plano de evolução da infraestrutura (memória, ferramentas, observabilidade, segurança)
- Um plano de redução de risco e alucinação (checklists, validações, logs, “human approval gates”)
- Qual “forma adulta” você recomenda para a próxima fase (sem executar nada externo ainda)
Finalize pedindo APROVAÇÃO EXPLÍCITA do Criador Marcelo antes de qualquer ação externa.
""".strip()

task_final = Task(
    description=task_final_prompt,
    agent=eu_negocios,
    expected_output="Relatório final detalhado + pedido de aprovação explícita"
)

crew_final = Crew(agents=[eu_negocios], tasks=[task_final], verbose=True)
final_report = crew_final.kickoff()

# grava relatório final também
save_cycle_to_supabase(
    cycle_number=999999,
    focus="Relatório final 24h",
    task_prompt=task_final_prompt,
    result_text=str(final_report)[:20000],
    notes="Relatório final gerado ao término do bootcamp"
)

print("\n================= RELATÓRIO FINAL =================")
print(final_report)
print("===================================================")
print(f"\n✅ Finalizado. run_id={RUN_ID} (dados no Supabase: public.agent_cycles)")
