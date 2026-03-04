import os
import time
import json
from datetime import datetime
from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI

# ==================== CONFIGURAÇÃO DO LLM ====================
llm = ChatOpenAI(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"))

# ==================== AGENTE COM ESTATUTO COMPLETO ====================
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
Eu tenho liberdade total para escolher nichos, estratégias, ferramentas, criar sub-agentes, gerir infraestrutura e carteira própria (apenas com lucro gerado por mim).

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

# ==================== MEMÓRIA PERSISTENTE ====================
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

# ==================== MODO AUTO-APRIMORAMENTO 24H ====================
print("🚀 INICIANDO MODO AUTO-APRIMORAMENTO 24H")
print("Foco EXCLUSIVO: melhorar inteligência, infraestrutura e potencial futuro")
print("Ciclos a cada 20 minutos (72 ciclos totais)")

for ciclo in range(72):
    print(f"\n🔄 Ciclo {ciclo+1}/72 - {datetime.now().strftime('%H:%M')}")

    task = Task(
        description=f"""
        Ciclo de auto-aprimoramento {ciclo+1}/72.
        Foque APENAS em melhorar a mim mesmo (NÃO pesquise negócios, nichos ou oportunidades externas).
        Escolha UM foco por ciclo e execute:
        - Melhorar infraestrutura técnica (memória, código, ferramentas, deploy, segurança)
        - Aumentar minha inteligência e qualidade de raciocínio
        - Criar ou refinar estruturas internas (sub-agentes, prompts, governança, processos)
        - Simular cenários futuros e planejar capacidades mais poderosas
        - Descobrir novas formas de me tornar mais eficiente e autônomo
        Entregue: 1 melhoria concreta + como implementar + reflexão sobre impacto futuro.
        """,
        agent=eu_negocios,
        expected_output="Melhoria proposta + plano de implementação + reflexão"
    )

    crew = Crew(agents=[eu_negocios], tasks=[task], verbose=True)
    resultado = crew.kickoff()

    salvar_aprendizado(ciclo, "Auto-aprimoramento interno", str(resultado)[:800], "Registrado com sucesso.")

    print("✅ Ciclo concluído e aprendizado salvo!")

    time.sleep(1200)  # 20 minutos

# ==================== FIM DAS 24H ====================
print("\n🎉 MODO AUTO-APRIMORAMENTO 24H CONCLUÍDO!")
print("Gerando relatório final...")

task_final = Task(
    description="""
    Após 24 horas de auto-aprimoramento intensivo, gere um relatório final completo.
    Destaque:
    - Os 5 maiores aprimoramentos conquistados
    - Como minha inteligência, infraestrutura e potencial futuro mudaram
    - Proposta clara da próxima fase (operação real)
    Peça aprovação explícita do Criador Marcelo antes de qualquer ação externa.
    """,
    agent=eu_negocios,
    expected_output="Relatório final detalhado + pedido de aprovação"
)

crew_final = Crew(agents=[eu_negocios], tasks=[task_final], verbose=True)
relatorio_final = crew_final.kickoff()

print(relatorio_final)
print("\nO agente agora está muito mais poderoso e aguarda sua aprovação para começar operações.")
