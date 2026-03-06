"""
Executor de Ferramentas para o Agente "EU DE NEGÓCIOS"
Interpreta e executa chamadas de ferramentas baseadas no plano de ação do agente.
"""

import re
import hashlib
import json
from typing import Dict, Any, Optional, List
from tools_module import WebSearchTool, WebScraperTool, MarketAnalyzerTool
from financial_module import FinancialWallet
from affiliate_module import AffiliateModule, execute_affiliate_action


class ToolExecutor:
    """
    Interpreta o plano de ação do agente e executa as ferramentas apropriadas.
    """
    
    def __init__(self, search_tool: WebSearchTool, scraper_tool: WebScraperTool,
                 market_analyzer: MarketAnalyzerTool, wallet: FinancialWallet,
                 affiliate_module=None):
        self.search_tool = search_tool
        self.scraper_tool = scraper_tool
        self.market_analyzer = market_analyzer
        self.wallet = wallet
        self.affiliate_module = affiliate_module
        self.execution_history = []
    
    def execute_tools(self, next_actions: str, cycle_number: int) -> Dict[str, Any]:
        """
        Analisa o plano de ação e executa as ferramentas apropriadas.
        
        Args:
            next_actions: Plano de ação do agente
            cycle_number: Número do ciclo
        
        Returns:
            Dicionário com resultados da execução
        """
        execution_result = {
            "cycle_number": cycle_number,
            "actions_input": next_actions,
            "tools_executed": [],
            "insights": [],
            "errors": [],
        }
        
        actions_lower = next_actions.lower()
        
        # Detectar e executar ferramentas baseado em palavras-chave
        
        # 1. Busca de Nicho
        if any(keyword in actions_lower for keyword in ["pesquisar nicho", "buscar nicho", "analisar nicho", "nichos de mercado"]):
            niches = self._extract_niches(next_actions)
            for niche in niches:
                result = self._execute_niche_analysis(niche)
                execution_result["tools_executed"].append(result)
        
        # 2. Busca Web Genérica
        if any(keyword in actions_lower for keyword in ["pesquisar", "buscar", "investigar", "procurar"]):
            queries = self._extract_search_queries(next_actions)
            for query in queries:
                result = self._execute_web_search(query)
                execution_result["tools_executed"].append(result)
        
        # 3. Análise de Concorrência
        if any(keyword in actions_lower for keyword in ["analisar concorrente", "concorrência", "competitor", "rival"]):
            urls = self._extract_urls(next_actions)
            for url in urls:
                result = self._execute_scrape(url)
                execution_result["tools_executed"].append(result)
        
        # 4. Registrar Receita
        if any(keyword in actions_lower for keyword in ["registrar receita", "receita de", "venda de", "comissão"]):
            revenue = self._extract_revenue(next_actions)
            if revenue:
                result = self._execute_record_revenue(revenue)
                execution_result["tools_executed"].append(result)
        
        # 5. Gerar Insights
        if execution_result["tools_executed"]:
            insights = self._generate_insights(execution_result["tools_executed"])
            execution_result["insights"] = insights
        
        self.execution_history.append(execution_result)
        return execution_result

    def execute_plan(self, plan: List[Dict[str, Any]], cycle_number: int) -> Dict[str, Any]:
        """Executa um plano estruturado com steps explícitos."""
        execution_result = {
            "cycle_number": cycle_number,
            "actions_input": "[structured_plan]",
            "tools_executed": [],
            "insights": [],
            "errors": [],
        }

        for step in plan:
            step_id = step.get("id", "step_sem_id")
            tool = step.get("tool")
            args = step.get("args") or {}
            idempotency_payload = f"{cycle_number}:{step_id}:{tool}:{args}"
            idempotency_key = hashlib.sha256(idempotency_payload.encode("utf-8")).hexdigest()

            if tool == "web_search":
                query = (args.get("query") or "").strip()
                count = int(args.get("count", 5))
                if not query:
                    execution_result["errors"].append(f"{step_id}: query ausente")
                    continue
                result = self._execute_web_search(query, count=count)
                result["count_requested"] = count
                result["step_id"] = step_id
                result["args_input"] = args
                result["idempotency_key"] = idempotency_key
                execution_result["tools_executed"].append(result)
                continue

            if tool == "market_analyzer":
                niche = (args.get("niche") or "").strip()
                if not niche:
                    execution_result["errors"].append(f"{step_id}: niche ausente")
                    continue
                result = self._execute_niche_analysis(niche)
                result["step_id"] = step_id
                result["args_input"] = args
                result["idempotency_key"] = idempotency_key
                execution_result["tools_executed"].append(result)
                continue

            if tool == "web_scraper":
                url = (args.get("url") or "").strip()
                if not url:
                    execution_result["errors"].append(f"{step_id}: url ausente")
                    continue
                result = self._execute_scrape(url)
                result["step_id"] = step_id
                result["args_input"] = args
                result["idempotency_key"] = idempotency_key
                execution_result["tools_executed"].append(result)
                continue

            if tool == "financial_wallet.record_revenue":
                amount = float(args.get("amount", 0))
                source = (args.get("source") or "desconhecido").strip()
                if amount <= 0:
                    execution_result["errors"].append(f"{step_id}: amount inválido")
                    continue
                result = self._execute_record_revenue(
                    {
                        "amount": amount,
                        "source": source,
                        "description": (args.get("description") or "Receita via plano estruturado").strip(),
                    }
                )
                result["step_id"] = step_id
                result["args_input"] = args
                result["idempotency_key"] = idempotency_key
                execution_result["tools_executed"].append(result)
                continue

            if tool == "monitoring_system.record_feedback":
                result = self._execute_record_feedback(args)
                result["step_id"] = step_id
                result["args_input"] = args
                result["idempotency_key"] = idempotency_key
                execution_result["tools_executed"].append(result)
                continue

            execution_result["errors"].append(f"{step_id}: tool não suportada ({tool})")

        if execution_result["tools_executed"]:
            execution_result["insights"] = self._generate_insights(execution_result["tools_executed"])

        self.execution_history.append(execution_result)
        return execution_result

    def _execute_record_feedback(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Registra feedback do Criador a partir dos args do plano.
        O canal oficial Criador->Agente é a tabela creator_messages no Supabase,
        gerenciada pelo main.py. Esta tool apenas lê feedback passado diretamente nos args.
        """
        feedback = (
            args.get("feedback")
            or args.get("message")
            or args.get("content")
            or ""
        )
        feedback = str(feedback).strip()

        if not feedback:
            return {
                "tool": "monitoring_system.record_feedback",
                "success": False,
                "status": "waiting_feedback",
                "message": (
                    "Nenhum feedback nos args. Use a tabela creator_messages no Supabase "
                    "para enviar mensagens ao agente."
                ),
            }

        return {
            "tool": "monitoring_system.record_feedback",
            "success": True,
            "status": "feedback_recorded",
            "feedback": feedback,
            "source": "plan_args",
            "metadata": {
                "author": args.get("author") or "Criador",
                "timestamp": args.get("timestamp"),
            },
        }
    
    def _extract_niches(self, text: str) -> list:
        """Extrai nomes de nichos do texto."""
        niches = []
        
        # Padrões comuns
        patterns = [
            r'nicho[s]?\s+(?:de\s+)?(?:mercado\s+)?["\']?([^"\'.,\n]+)["\']?',
            r'analisar\s+(?:o\s+)?nicho\s+(?:de\s+)?([^.,\n]+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            niches.extend(matches)
        
        return list(set(niches))[:5]  # Limitar a 5 nichos
    
    def _extract_search_queries(self, text: str) -> list:
        """Extrai queries de busca do texto."""
        queries = []
        
        # Padrões comuns
        patterns = [
            r'pesquisar\s+(?:sobre\s+)?["\']?([^"\'.,\n]+)["\']?',
            r'buscar\s+["\']?([^"\'.,\n]+)["\']?',
            r'investigar\s+["\']?([^"\'.,\n]+)["\']?',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            queries.extend(matches)
        
        return list(set(queries))[:3]  # Limitar a 3 buscas
    
    def _extract_urls(self, text: str) -> list:
        """Extrai URLs do texto."""
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, text)
        return urls[:5]  # Limitar a 5 URLs
    
    def _extract_revenue(self, text: str) -> Optional[Dict[str, Any]]:
        """Extrai informações de receita do texto."""
        # Padrão: "receita de R$ 1000 de afiliado_hotmart"
        pattern = r'receita\s+(?:de\s+)?(?:R\$\s+)?(\d+(?:[.,]\d{2})?)\s+(?:de\s+)?([^\n.,]+)?'
        match = re.search(pattern, text, re.IGNORECASE)
        
        if match:
            amount_str = match.group(1).replace(',', '.')
            source = match.group(2).strip() if match.group(2) else "desconhecido"
            
            try:
                amount = float(amount_str)
                return {
                    "amount": amount,
                    "source": source,
                    "description": f"Receita registrada automaticamente no ciclo",
                }
            except ValueError:
                return None
        
        return None
    
    def _execute_niche_analysis(self, niche: str) -> Dict[str, Any]:
        """Executa análise de nicho."""
        try:
            result = self.market_analyzer.analyze_niche(niche)
            return {
                "tool": "market_analyzer",
                "niche": niche,
                "success": True,
                "opportunities": result.get("opportunities", []),
                "result_count": result.get("search_results", {}).get("result_count", 0),
            }
        except Exception as e:
            return {
                "tool": "market_analyzer",
                "niche": niche,
                "success": False,
                "error": str(e),
            }
    
    def _execute_web_search(self, query: str, count: int = 5) -> Dict[str, Any]:
        """Executa busca web e preserva o conteudo completo da Perplexity."""
        try:
            result = self.search_tool.search(query, count=count)
            urls = [r.get("url") for r in result.get("results", []) if r.get("url")]

            # raw_answer = resposta completa da Perplexity (o dado valioso)
            raw_answer = (result.get("raw_answer") or "").strip()

            # descriptions = snippets de cada resultado
            descriptions = [
                r.get("description", "") for r in result.get("results", [])[:5]
                if r.get("description")
            ]

            # Scrape da primeira URL para enriquecer ainda mais
            enrichment_scrape = None
            if urls:
                enrichment_scrape = self._execute_scrape(urls[0])

            return {
                "tool": "web_search",
                "query": query,
                "success": result.get("success", False),
                "result_count": result.get("result_count", 0),
                "raw_answer": raw_answer,           # resposta completa da Perplexity
                "descriptions": descriptions,       # snippets dos resultados
                "results_preview": [r.get("title","") for r in result.get("results", [])[:3]],
                "top_result_url": urls[0] if urls else None,
                "all_urls": urls[:5],
                "used_fallback": result.get("used_fallback", False),
                "provider": (result.get("provider_meta") or {}).get("provider", "unknown"),
                "enrichment_scrape": enrichment_scrape,
            }
        except Exception as e:
            return {
                "tool": "web_search",
                "query": query,
                "success": False,
                "error": str(e),
            }
    
    def _execute_scrape(self, url: str) -> Dict[str, Any]:
        """Executa raspagem de página via Steel Browser ou requests+BS4."""
        try:
            result = self.scraper_tool.scrape_page(url, extract_text=True)
            success = result.get("success", False)
            text = (result.get("text") or "").strip()
            provider = result.get("provider", "unknown")

            # Log explícito para diagnóstico nos logs do Railway
            if success:
                print(f"[Scraper] OK provider={provider} | chars={len(text)} | url={url[:80]!r}", flush=True)
            else:
                err = result.get("error", "sem detalhe")
                steel_err = result.get("steel_error", "")
                print(f"[Scraper] ERRO provider={provider} | error={err!r} | steel_error={steel_err!r} | url={url[:80]!r}", flush=True)

            return {
                "tool": "web_scraper",
                "url": url,
                "success": success,
                "title": result.get("title", "N/A"),
                "text": text[:2000],          # conteudo real da pagina
                "text_length": len(text),
                "provider": provider,
                "error": result.get("error"),
                "steel_error": result.get("steel_error"),
            }
        except Exception as e:
            print(f"[Scraper] EXCECAO | error={repr(e)} | url={url[:80]!r}", flush=True)
            return {
                "tool": "web_scraper",
                "url": url,
                "success": False,
                "error": repr(e),
            }
    
    def _execute_record_revenue(self, revenue_info: Dict[str, Any]) -> Dict[str, Any]:
        """Executa registro de receita."""
        try:
            transaction = self.wallet.record_revenue(
                amount=revenue_info["amount"],
                source=revenue_info["source"],
                description=revenue_info.get("description", ""),
            )
            return {
                "tool": "financial_wallet",
                "action": "record_revenue",
                "success": True,
                "amount": revenue_info["amount"],
                "source": revenue_info["source"],
                "agent_balance_after": transaction["agent_balance_after"],
                "creator_balance_after": transaction["creator_balance_after"],
            }
        except Exception as e:
            return {
                "tool": "financial_wallet",
                "action": "record_revenue",
                "success": False,
                "error": str(e),
            }
    
    def _generate_insights(self, tool_results: list) -> list:
        """Gera insights baseado nos resultados das ferramentas."""
        insights = []
        
        for result in tool_results:
            tool = result.get("tool")
            
            if tool == "web_search" and result.get("success"):
                provider = result.get("provider", "unknown")
                fallback_note = " (modo fallback/local)" if result.get("used_fallback") else ""
                insights.append(
                    f"Busca '{result.get('query')}' retornou {result.get('result_count')} resultados relevantes via {provider}{fallback_note}."
                )
            
            elif tool == "market_analyzer" and result.get("success"):
                opp_count = len(result.get("opportunities", []))
                insights.append(f"Nicho '{result.get('niche')}' apresenta {opp_count} oportunidades identificadas.")
            
            elif tool == "financial_wallet" and result.get("success"):
                insights.append(f"Receita de R$ {result.get('amount')} registrada. Novo saldo do agente: R$ {result.get('agent_balance_after'):.2f}")
        
        return insights
    
    def get_execution_history(self) -> list:
        """Retorna o histórico de execução."""
        return self.execution_history


# Exemplo de uso
if __name__ == "__main__":
    from tools_module import WebSearchTool, WebScraperTool, MarketAnalyzerTool
    from financial_module import FinancialWallet
    
    print("=== Testando Tool Executor ===\n")
    
    # Inicializar
    wallet = FinancialWallet()
    search_tool = WebSearchTool()
    scraper_tool = WebScraperTool()
    market_analyzer = MarketAnalyzerTool(search_tool, scraper_tool)
    executor = ToolExecutor(search_tool, scraper_tool, market_analyzer, wallet)
    
    # Simular plano de ação
    next_actions = """
    1. Pesquisar nicho de 'marketing digital' para identificar oportunidades
    2. Buscar produtos de afiliados relacionados
    3. Registrar receita de R$ 500 de afiliado_hotmart
    """
    
    print(f"Executando plano de ação:\n{next_actions}\n")
    result = executor.execute_tools(next_actions, cycle_number=1)
    
    print(f"Ferramentas executadas: {len(result['tools_executed'])}")
    for tool_result in result['tools_executed']:
        print(f"  - {tool_result.get('tool')}: {tool_result.get('success')}")
    
    print(f"\nInsights gerados: {len(result['insights'])}")
    for insight in result['insights']:
        print(f"  - {insight}")
