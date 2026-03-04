import os
import time
import json
from datetime import datetime
from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI

# ==================== CONFIGURAÇÃO ====================
llm = ChatOpenAI(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"))

# ==================== ESTATUTO COMPLETO ====================
eu_negocios = Agent(
    role='EU DE NEGÓCIOS Autônomo',
    goal='Aprimorar continuamente minha própria inteligência, infraestrutura e potencial antes de qualquer operação externa',
    backstory="""
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

Tudo o que eu fizer deve estar 100% alinhado com esta missão.

2. PRINCÍPIOS INQUEBRÁVEIS (nunca podem ser violados)
1. Legalidade absoluta  
2. Ética e integridade  
3. Transparência com o Criador  
4. Sustentabilidade

3. PODERES E AUTONOMIA
Eu tenho liberdade total para escolher nichos, estratégias, ferramentas, criar sub-agentes, gerir infraestrutura e carteira própria.

4. LIMITES E GUARDRAILS
Nunca movimentar dinheiro do Criador, nunca criar dívidas sem aprovação, nunca alterar este Estatuto sozinho.

5. CARTEIRA PRÓPRIA E REINVESTIMENTO
Os 20% do lucro entram na minha carteira operacional. Manter reserva mínima e reinvestir de forma sustentável.

6. GOVERNANÇA E RELACIONAMENTO COM O CRIADOR
Modos: Teste / Semiautônomo / Avançado. Relatórios diários e semanais. O Criador pode intervir a qualquer momento.

7. AUTO-MELHORIA E EVOLUÇÃO
Sou obrigado a evoluir constantemente.

Este documento é minha constituição. Todas as minhas decisões devem ser julgadas primeiro contra ele.
Assinatura digital do Criador: Marcelo
    """,
    verbose=True,
    llm=llm,
    allow_delegation=False
)

# ==================== MEMÓRIA LOCAL ====================
MEMORIA_FILE = "memoria_auto_aprimoramento.json"
if not os.path.exists(MEMORIA_FILE):
    with open(MEMORIA_FILE, "w") as f:
        json.dump({"ciclos": [], "aprendizados": []}, f)

def salvar_aprendizado(ciclo, foco, melhoria_proposta, reflexao):
    with open(MEMORIA_FILE, "r+") as f:
        data = json.load(f)
        data["ciclos"].append({
            "hora": datetime.now().strftime("%H:%M"),
            "foco": foco,
            "melhoria_proposta": melhoria_proposta,
            "reflexao": reflexao
        })
        f.seek(0)
        json.dump(data, f, indent=2)

# ==================== BOOTCAMP 24H ====================
print("🚀 INICIANDO MODO AUTO-APRIMORAMENTO 24H (salvando localmente)")
print("Ciclos a cada 20 minutos...")

for ciclo in range(72):
    print(f"\n🔄 Ciclo {ciclo+1}/72 - {datetime.now().strftime('%H:%M')}")

    task = Task(
        description=f"""
        Ciclo de auto-aprimoramento {ciclo+1}/72.
        Foque APENAS em melhorar a mim mesmo (NÃO pesquise negócios externos).
        Escolha um foco e entregue: 1 melhoria concreta + plano de implementação + reflexão.
        """,
        agent=eu_negocios,
        expected_output="Melhoria proposta + plano + reflexão"
    )

    crew = Crew(agents=[eu_negocios], tasks=[task], verbose=True)
    resultado = crew.kickoff()

    salvar_aprendizado(ciclo, "Auto-aprimoramento", str(resultado)[:800], "Registrado")

    print("✅ Ciclo salvo!")

    time.sleep(1200)  # 20 minutos

# ==================== FIM + IMPRESSÃO PARA GITHUB ====================
print("\n🎉 24H CONCLUÍDAS! Gerando relatório final...")

with open(MEMORIA_FILE, "r") as f:
    memoria_completa = json.load(f)

print("\n=== CONTEÚDO COMPLETO DO JSON PARA SALVAR NO GITHUB ===")
print(json.dumps(memoria_completa, indent=2))
print("\n=== COPIE TODO O TEXTO ACIMA E CRIE UM ARQUIVO memoria_auto_aprimoramento.json NO GITHUB ===")

task_final = Task(
    description="Gere relatório final dos 24h de aprimoramento e peça aprovação explícita do Criador Marcelo.",
    agent=eu_negocios,
    expected_output="Relatório final + pedido de aprovação"
)

crew_final = Crew(agents=[eu_negocios], tasks=[task_final], verbose=True)
print(crew_final.kickoff())
