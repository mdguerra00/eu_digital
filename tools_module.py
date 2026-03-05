"""
Módulo de Ferramentas para o Agente "EU DE NEGÓCIOS"
Fornece capacidades de busca web, navegação e análise de conteúdo.
"""

import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup


class WebSearchTool:
    """
    Ferramenta de busca web usando a API do Brave Search (gratuita).
    Permite que o agente pesquise nichos, produtos e tendências de mercado.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa a ferramenta de busca.
        
        Args:
            api_key: Chave da API Brave Search (opcional, pode usar fallback)
        """
        self.api_key = api_key
        self.base_url = "https://api.search.brave.com/res/v1/web/search"
        self.search_history = []
    
    def search(self, query: str, count: int = 10) -> Dict[str, Any]:
        """
        Realiza uma busca na web.
        
        Args:
            query: Termo de busca
            count: Número de resultados (máximo 20)
        
        Returns:
            Dicionário com resultados da busca
        """
        if not query or len(query.strip()) == 0:
            return {"error": "Query vazia", "results": []}
        
        try:
            # Se não houver API key, usar fallback com busca simulada
            if not self.api_key:
                return self._search_fallback(query)
            
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key,
            }
            
            params = {
                "q": query,
                "count": min(count, 20),
            }
            
            response = requests.get(self.base_url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Processar resultados
            results = []
            for item in data.get("web", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "description": item.get("description", ""),
                    "source": item.get("source", ""),
                })
            
            search_record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "query": query,
                "result_count": len(results),
                "results": results,
            }
            self.search_history.append(search_record)
            
            return {
                "success": True,
                "query": query,
                "result_count": len(results),
                "results": results,
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "results": [],
            }
    
    def _search_fallback(self, query: str) -> Dict[str, Any]:
        """
        Fallback de busca quando não há API key disponível.
        Retorna resultados simulados para fins de demonstração.
        """
        fallback_results = {
            "nicho de mercado": [
                {
                    "title": "10 Nichos de Mercado Mais Lucrativos em 2026",
                    "url": "https://example.com/nichos-lucrativos",
                    "description": "Análise dos nichos com maior potencial de lucro para afiliados.",
                    "source": "Blog de Marketing",
                },
                {
                    "title": "Marketing de Afiliados: Nichos em Alta Demanda",
                    "url": "https://example.com/afiliados-nichos",
                    "description": "Descubra os nichos que estão gerando mais comissões.",
                    "source": "Plataforma de Afiliados",
                },
            ],
            "produto digital": [
                {
                    "title": "Produtos Digitais Mais Vendidos - Análise 2026",
                    "url": "https://example.com/produtos-digitais",
                    "description": "Ranking de produtos digitais com maior taxa de conversão.",
                    "source": "Análise de Mercado",
                },
            ],
            "dropshipping": [
                {
                    "title": "Dropshipping: Guia Completo para Iniciantes",
                    "url": "https://example.com/dropshipping-guia",
                    "description": "Como começar um negócio de dropshipping com baixo investimento.",
                    "source": "E-commerce Blog",
                },
            ],
        }
        
        # Buscar resultados relevantes
        results = []
        query_lower = query.lower()
        
        for key, items in fallback_results.items():
            if key in query_lower:
                results.extend(items)
        
        # Se não encontrar correspondência exata, retornar alguns resultados genéricos
        if not results:
            results = [
                {
                    "title": f"Resultados para: {query}",
                    "url": "https://example.com/search",
                    "description": "Busca simulada - conecte uma API real para resultados autênticos.",
                    "source": "Fallback",
                },
            ]
        
        return {
            "success": True,
            "query": query,
            "result_count": len(results),
            "results": results[:10],
        }
    
    def get_search_history(self) -> List[Dict[str, Any]]:
        """Retorna o histórico de buscas realizadas."""
        return self.search_history


class WebScraperTool:
    """
    Ferramenta de raspagem web para extrair conteúdo de páginas.
    Permite análise de concorrentes, extração de preços e tendências.
    """
    
    def __init__(self):
        self.scrape_history = []
    
    def scrape_page(self, url: str, extract_text: bool = True, extract_links: bool = False) -> Dict[str, Any]:
        """
        Raspa o conteúdo de uma página web.
        
        Args:
            url: URL da página
            extract_text: Se deve extrair texto
            extract_links: Se deve extrair links
        
        Returns:
            Dicionário com conteúdo extraído
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            result = {
                "url": url,
                "status_code": response.status_code,
                "title": soup.title.string if soup.title else "N/A",
            }
            
            # Extrair texto
            if extract_text:
                # Remover scripts e styles
                for script in soup(["script", "style"]):
                    script.decompose()
                
                text = soup.get_text(separator="\n", strip=True)
                # Limitar a 2000 caracteres
                result["text"] = text[:2000]
            
            # Extrair links
            if extract_links:
                links = []
                for link in soup.find_all('a', href=True):
                    links.append({
                        "text": link.get_text(strip=True),
                        "href": link['href'],
                    })
                result["links"] = links[:20]  # Limitar a 20 links
            
            scrape_record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "url": url,
                "success": True,
            }
            self.scrape_history.append(scrape_record)
            
            return result
        
        except Exception as e:
            return {
                "url": url,
                "success": False,
                "error": str(e),
            }
    
    def extract_prices(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Extrai preços de conteúdo HTML.
        
        Args:
            html_content: Conteúdo HTML
        
        Returns:
            Lista de preços encontrados
        """
        prices = []
        
        # Padrões comuns de preço
        patterns = [
            r'R\$\s*(\d+[.,]\d{2})',  # R$ 99.90
            r'\$\s*(\d+[.,]\d{2})',   # $ 99.90
            r'(\d+[.,]\d{2})\s*reais',  # 99.90 reais
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html_content)
            for match in matches:
                prices.append({
                    "value": match,
                    "pattern": pattern,
                })
        
        return prices
    
    def get_scrape_history(self) -> List[Dict[str, Any]]:
        """Retorna o histórico de raspagens realizadas."""
        return self.scrape_history


class MarketAnalyzerTool:
    """
    Ferramenta de análise de mercado que combina busca e raspagem
    para gerar insights sobre nichos e oportunidades.
    """
    
    def __init__(self, search_tool: WebSearchTool, scraper_tool: WebScraperTool):
        self.search_tool = search_tool
        self.scraper_tool = scraper_tool
    
    def analyze_niche(self, niche_name: str) -> Dict[str, Any]:
        """
        Analisa um nicho de mercado.
        
        Args:
            niche_name: Nome do nicho (ex: "marketing digital", "cursos online")
        
        Returns:
            Dicionário com análise do nicho
        """
        analysis = {
            "niche": niche_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "search_results": None,
            "competitor_analysis": [],
            "opportunities": [],
        }
        
        # Buscar informações sobre o nicho
        search_query = f"{niche_name} mercado oportunidades 2026"
        search_results = self.search_tool.search(search_query, count=5)
        analysis["search_results"] = search_results
        
        # Analisar alguns dos top resultados
        if search_results.get("success"):
            for result in search_results.get("results", [])[:3]:
                url = result.get("url")
                if url:
                    scrape_result = self.scraper_tool.scrape_page(url, extract_text=True)
                    if scrape_result.get("success"):
                        analysis["competitor_analysis"].append({
                            "url": url,
                            "title": result.get("title"),
                            "text_preview": scrape_result.get("text", "")[:500],
                        })
        
        # Gerar oportunidades (baseado em padrões simples)
        analysis["opportunities"] = [
            f"Criar conteúdo em português focado em '{niche_name}'",
            f"Buscar produtos de afiliados relacionados a '{niche_name}'",
            f"Analisar concorrência em plataformas de cursos para '{niche_name}'",
            f"Investigar demanda por '{niche_name}' em redes sociais",
        ]
        
        return analysis


# Exemplo de uso
if __name__ == "__main__":
    print("=== Testando Ferramentas de Web ===\n")
    
    # Teste 1: Web Search
    print("1. Testando Web Search...")
    search_tool = WebSearchTool()
    results = search_tool.search("marketing de afiliados 2026")
    print(f"   Resultados encontrados: {results['result_count']}")
    for i, result in enumerate(results['results'][:3], 1):
        print(f"   {i}. {result['title']}")
    
    # Teste 2: Web Scraper
    print("\n2. Testando Web Scraper...")
    scraper_tool = WebScraperTool()
    scrape_result = scraper_tool.scrape_page("https://example.com", extract_text=True)
    print(f"   Status: {scrape_result.get('status_code', 'N/A')}")
    print(f"   Título: {scrape_result.get('title', 'N/A')}")
    
    # Teste 3: Market Analyzer
    print("\n3. Testando Market Analyzer...")
    analyzer = MarketAnalyzerTool(search_tool, scraper_tool)
    analysis = analyzer.analyze_niche("cursos online")
    print(f"   Nicho: {analysis['niche']}")
    print(f"   Oportunidades identificadas: {len(analysis['opportunities'])}")
    for opp in analysis['opportunities']:
        print(f"   - {opp}")
