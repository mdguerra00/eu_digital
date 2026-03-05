"""
Módulo de Ferramentas para o Agente "EU DE NEGÓCIOS"
Fornece capacidades de busca web, navegação e análise de conteúdo.

Alteração: Brave Search API -> Perplexity Search API
- Lê a chave do Railway via env var: PERPLEXITY_API_KEY
Docs: POST https://api.perplexity.ai/search  (Authorization: Bearer <token>)
"""

import os
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup


class WebSearchTool:
    """
    Ferramenta de busca web usando a Perplexity Search API.
    Permite que o agente pesquise nichos, produtos e tendências de mercado.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa a ferramenta de busca.

        Args:
            api_key: Perplexity API key (Bearer token). Opcional (usa fallback se ausente).
        """
        self.api_key = api_key
        self.base_url = "https://api.perplexity.ai/search"
        self.search_history: List[Dict[str, Any]] = []

    def search(
        self,
        query: str,
        count: int = 10,
        *,
        country: Optional[str] = None,
        search_language_filter: Optional[List[str]] = None,
        search_domain_filter: Optional[List[str]] = None,
        search_recency_filter: Optional[str] = None,  # hour/day/week/month/year
        max_tokens: Optional[int] = None,
        max_tokens_per_page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Realiza uma busca na web via Perplexity Search API.

        Args:
            query: Termo de busca
            count: Número de resultados (1..20)
            country: ISO 3166-1 alpha-2 (ex: "BR", "US")
            search_language_filter: lista ISO 639-1 (ex: ["pt", "en"])
            search_domain_filter: lista de domínios (ex: ["g1.globo.com", "reuters.com"])
            search_recency_filter: "hour" | "day" | "week" | "month" | "year"
            max_tokens: máximo de tokens de contexto agregados (opcional)
            max_tokens_per_page: máximo de tokens por página (opcional)

        Returns:
            Dicionário com resultados da busca
        """
        if not query or len(query.strip()) == 0:
            return {"success": False, "error": "Query vazia", "results": []}

        try:
            # Se não houver API key, usar fallback com busca simulada
            if not self.api_key:
                return self._search_fallback(query)

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            payload: Dict[str, Any] = {
                "query": query,
                "max_results": max(1, min(int(count), 20)),
            }

            # Parâmetros opcionais conforme docs do /search
            if country:
                payload["country"] = country
            if search_language_filter:
                payload["search_language_filter"] = search_language_filter[:20]
            if search_domain_filter:
                payload["search_domain_filter"] = search_domain_filter[:20]
            if search_recency_filter:
                payload["search_recency_filter"] = search_recency_filter
            if max_tokens is not None:
                payload["max_tokens"] = int(max_tokens)
            if max_tokens_per_page is not None:
                payload["max_tokens_per_page"] = int(max_tokens_per_page)

            response = requests.post(self.base_url, headers=headers, json=payload, timeout=15)
            response.raise_for_status()

            data = response.json()

            # Perplexity /search retorna:
            # { "results": [ {title,url,snippet,date,last_updated}, ... ], "id": "...", "server_time": "..." }
            raw_results = data.get("results", []) or []
            results: List[Dict[str, Any]] = []

            for item in raw_results:
                title = (item.get("title") or "").strip()
                url = (item.get("url") or "").strip()
                snippet = (item.get("snippet") or "").strip()
                date = (item.get("date") or "").strip()
                last_updated = (item.get("last_updated") or "").strip()

                results.append(
                    {
                        "title": title,
                        "url": url,
                        "description": snippet,        # mantém compatibilidade com seu formato antigo
                        "source": "Perplexity Search", # pode trocar por domínio se quiser
                        "date": date,
                        "last_updated": last_updated,
                    }
                )

            search_record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "query": query,
                "result_count": len(results),
                "results": results,
                "provider_meta": {
                    "provider": "perplexity",
                    "id": data.get("id"),
                    "server_time": data.get("server_time"),
                },
            }
            self.search_history.append(search_record)

            return {
                "success": True,
                "query": query,
                "result_count": len(results),
                "results": results,
                "provider_meta": search_record["provider_meta"],
                "used_fallback": False,
            }

        except requests.HTTPError as e:
            # Ajuda na depuração: tenta retornar body (JSON ou texto)
            try:
                err_payload = response.json()  # type: ignore[name-defined]
            except Exception:
                err_payload = getattr(response, "text", "")  # type: ignore[name-defined]
            return {
                "success": False,
                "error": f"HTTPError: {str(e)}",
                "details": err_payload,
                "query": query,
                "results": [],
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

        results: List[Dict[str, Any]] = []
        query_lower = query.lower()

        for key, items in fallback_results.items():
            if key in query_lower:
                results.extend(items)

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
            "used_fallback": True,
            "provider_meta": {
                "provider": "fallback",
                "reason": "PERPLEXITY_API_KEY ausente",
            },
        }

    def get_search_history(self) -> List[Dict[str, Any]]:
        """Retorna o histórico de buscas realizadas."""
        return self.search_history


class WebScraperTool:
    """
    Ferramenta de raspagem web para extrair conteúdo de páginas.
    Permite análise de concorrentes, extração de preços e tendências.
    """

    def __init__(self, steel_browser: Optional["SteelBrowserTool"] = None):
        self.steel_browser = steel_browser
        self.scrape_history: List[Dict[str, Any]] = []

    def scrape_page(
        self, url: str, extract_text: bool = True, extract_links: bool = False
    ) -> Dict[str, Any]:
        """
        Raspa o conteúdo de uma página web.
        """
        steel_error: Optional[str] = None

        if self.steel_browser is not None:
            steel_result = self.steel_browser.scrape(
                url=url,
                extract_text=extract_text,
                extract_links=extract_links,
            )
            if steel_result.get("success"):
                self.scrape_history.append(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "url": url,
                        "success": True,
                        "provider": "steel_browser",
                    }
                )
                return steel_result

            steel_error = steel_result.get("error", "Falha desconhecida no Steel Browser")

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            result: Dict[str, Any] = {
                "url": url,
                "success": True,
                "status_code": response.status_code,
                "title": soup.title.string if soup.title else "N/A",
                "provider": "requests_bs4",
            }

            if steel_error:
                result["steel_error"] = steel_error

            if extract_text:
                for script in soup(["script", "style"]):
                    script.decompose()

                text = soup.get_text(separator="\n", strip=True)
                result["text"] = text[:2000]

            if extract_links:
                links = []
                for link in soup.find_all("a", href=True):
                    links.append(
                        {
                            "text": link.get_text(strip=True),
                            "href": link["href"],
                        }
                    )
                result["links"] = links[:20]

            self.scrape_history.append(
                {"timestamp": datetime.now(timezone.utc).isoformat(), "url": url, "success": True}
            )

            return result

        except Exception as e:
            error_result: Dict[str, Any] = {"url": url, "success": False, "error": str(e)}
            if steel_error:
                error_result["steel_error"] = steel_error
            return error_result

    def extract_prices(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Extrai preços de conteúdo HTML.
        """
        prices: List[Dict[str, Any]] = []
        patterns = [
            r"R\$\s*(\d+[.,]\d{2})",
            r"\$\s*(\d+[.,]\d{2})",
            r"(\d+[.,]\d{2})\s*reais",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, html_content)
            for match in matches:
                prices.append({"value": match, "pattern": pattern})

        return prices

    def get_scrape_history(self) -> List[Dict[str, Any]]:
        """Retorna o histórico de raspagens realizadas."""
        return self.scrape_history


class SteelBrowserTool:
    """
    Cliente HTTP para serviços de browser remoto (ex.: Steel Browser no Railway).
    Usa endpoint configurável para permitir variações de rota/provedor.
    """

    def __init__(self, api_key: Optional[str], endpoint: Optional[str] = None, timeout_s: int = 25):
        self.api_key = api_key
        self.endpoint = endpoint or os.getenv("STEEL_BROWSER_ENDPOINT", "https://api.steel.dev/v1/scrape")
        self.timeout_s = timeout_s

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def scrape(self, url: str, extract_text: bool = True, extract_links: bool = False) -> Dict[str, Any]:
        if not self.is_configured():
            return {"success": False, "url": url, "error": "STEEL_BROWSER_API_KEY ausente"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload: Dict[str, Any] = {
            "url": url,
            "options": {
                "extract_text": extract_text,
                "extract_links": extract_links,
            },
        }

        try:
            response = requests.post(self.endpoint, headers=headers, json=payload, timeout=self.timeout_s)
            response.raise_for_status()
            data = response.json()

            text = data.get("text") or data.get("content") or data.get("markdown") or ""
            title = data.get("title") or data.get("page", {}).get("title") or "N/A"
            links = data.get("links") or []

            result: Dict[str, Any] = {
                "url": url,
                "success": True,
                "status_code": data.get("status_code") or response.status_code,
                "title": title,
                "provider": "steel_browser",
            }

            if extract_text:
                result["text"] = text[:2000]

            if extract_links:
                result["links"] = links[:20] if isinstance(links, list) else []

            return result
        except Exception as e:
            return {
                "url": url,
                "success": False,
                "provider": "steel_browser",
                "error": str(e),
            }

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
        """
        analysis: Dict[str, Any] = {
            "niche": niche_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "search_results": None,
            "competitor_analysis": [],
            "opportunities": [],
        }

        search_query = f"{niche_name} mercado oportunidades 2026"
        search_results = self.search_tool.search(
            search_query,
            count=5,
            country="BR",
            search_recency_filter="year",
            search_language_filter=["pt"],
        )
        analysis["search_results"] = search_results

        if search_results.get("success"):
            for result in search_results.get("results", [])[:3]:
                url = result.get("url")
                if url:
                    scrape_result = self.scraper_tool.scrape_page(url, extract_text=True)
                    if scrape_result.get("success"):
                        analysis["competitor_analysis"].append(
                            {
                                "url": url,
                                "title": result.get("title"),
                                "text_preview": (scrape_result.get("text", "") or "")[:500],
                            }
                        )

        analysis["opportunities"] = [
            f"Criar conteúdo em português focado em '{niche_name}'",
            f"Buscar produtos de afiliados relacionados a '{niche_name}'",
            f"Analisar concorrência em plataformas de cursos para '{niche_name}'",
            f"Investigar demanda por '{niche_name}' em redes sociais",
        ]

        return analysis


if __name__ == "__main__":
    print("=== Testando Ferramentas de Web (Perplexity) ===\n")

    # Railway: a chave deve estar em Variables como PERPLEXITY_API_KEY
    api_key = os.getenv("PERPLEXITY_API_KEY")

    # 1) Web Search
    print("1. Testando Web Search...")
    search_tool = WebSearchTool(api_key=api_key)
    results = search_tool.search("marketing de afiliados 2026", count=5)
    print(f"   Resultados encontrados: {results.get('result_count', 0)}")
    for i, result in enumerate(results.get("results", [])[:3], 1):
        print(f"   {i}. {result.get('title')}")

    # 2) Web Scraper
    print("\n2. Testando Web Scraper...")
    scraper_tool = WebScraperTool()
    scrape_result = scraper_tool.scrape_page("https://example.com", extract_text=True)
    print(f"   Status: {scrape_result.get('status_code', 'N/A')}")
    print(f"   Título: {scrape_result.get('title', 'N/A')}")

    # 3) Market Analyzer
    print("\n3. Testando Market Analyzer...")
    analyzer = MarketAnalyzerTool(search_tool, scraper_tool)
    analysis = analyzer.analyze_niche("cursos online")
    print(f"   Nicho: {analysis['niche']}")
    print(f"   Oportunidades identificadas: {len(analysis['opportunities'])}")
    for opp in analysis["opportunities"]:
        print(f"   - {opp}")
