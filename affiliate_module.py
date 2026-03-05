"""
Módulo de Afiliados para o Agente "EU DE NEGÓCIOS"
Lê links de afiliado do Supabase e gera conteúdo de divulgação.
"""

import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class AffiliateModule:
    """
    Gerencia os links de afiliado cadastrados no Supabase.
    O agente usa este módulo para:
    - Listar produtos disponíveis para promover
    - Obter hotlinks para incluir em conteúdo
    - Gerar textos de divulgação por nicho
    """

    TABLE = "affiliate_links"

    def __init__(self, supabase_client=None, agent_name: str = "EU_DE_NEGOCIOS"):
        self.sb = supabase_client
        self.agent_name = agent_name

    def get_active_links(self, niche: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retorna links de afiliado ativos.
        Se niche informado, filtra por nicho específico.
        """
        if self.sb is None:
            print("[AffiliateModule] Supabase não configurado.", flush=True)
            return []

        try:
            query = (
                self.sb.table(self.TABLE)
                .select("id, product_name, platform, niche, hotlink, commission_pct, price_brl, rating, notes")
                .eq("agent_name", self.agent_name)
                .eq("active", True)
            )
            if niche:
                query = query.eq("niche", niche)

            res = query.order("commission_pct", desc=True).limit(limit).execute()
            links = res.data or []
            print(f"[AffiliateModule] {len(links)} link(s) ativo(s) encontrado(s).", flush=True)
            return links

        except Exception as e:
            print(f"[AffiliateModule] Erro ao buscar links: {repr(e)}", flush=True)
            return []

    def get_best_link(self, niche: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retorna o melhor link (maior comissão) para um nicho."""
        links = self.get_active_links(niche=niche, limit=1)
        return links[0] if links else None

    def format_links_summary(self, links: List[Dict[str, Any]]) -> str:
        """Formata lista de links para incluir no contexto do agente."""
        if not links:
            return "Nenhum link de afiliado cadastrado ainda."

        lines = ["=== LINKS DE AFILIADO DISPONÍVEIS ==="]
        for lk in links:
            lines.append(
                f"- {lk['product_name']} ({lk['niche']}) | "
                f"Comissão: {lk.get('commission_pct', '?')}% | "
                f"Preço: R${lk.get('price_brl', '?')} | "
                f"Avaliação: {lk.get('rating', '?')}/5 | "
                f"Link: {lk['hotlink']}"
            )
        return "\n".join(lines)

    def generate_promo_text(self, link: Dict[str, Any], format: str = "instagram") -> str:
        """
        Gera texto de divulgação para um produto.
        format: 'instagram' | 'twitter' | 'email' | 'whatsapp'
        """
        name = link.get("product_name", "Produto")
        hotlink = link.get("hotlink", "")
        niche = link.get("niche", "")
        price = link.get("price_brl")
        rating = link.get("rating")

        price_str = f"R${price:.0f}" if price else ""
        rating_str = f"⭐ {rating}/5" if rating else ""

        if format == "twitter":
            return (
                f"🔥 {name} — um dos mais vendidos no nicho de {niche.replace('_', ' ')}! "
                f"{rating_str} {price_str} "
                f"👉 {hotlink} "
                f"#afiliados #hotmart #{niche.replace('_', '')}"
            )
        elif format == "instagram":
            return (
                f"✨ Conhece o {name}?\n\n"
                f"Um dos produtos mais recomendados no nicho de {niche.replace('_', ' ')} "
                f"com avaliação {rating_str}.\n\n"
                f"{'Valor acessível: ' + price_str if price_str else ''}\n\n"
                f"🔗 Link na bio ou acesse: {hotlink}\n\n"
                f"#afiliados #hotmart #{niche.replace('_', '')} #produtodigital"
            )
        elif format == "whatsapp":
            return (
                f"Oi! Vi que você se interessa por {niche.replace('_', ' ')}.\n\n"
                f"Quero te indicar o *{name}* — {rating_str}\n"
                f"{'Está por apenas ' + price_str + '!' if price_str else ''}\n\n"
                f"Acessa aqui: {hotlink}"
            )
        elif format == "email":
            return (
                f"Assunto: Recomendação especial: {name}\n\n"
                f"Olá!\n\n"
                f"Quero compartilhar uma oportunidade no nicho de {niche.replace('_', ' ')}:\n\n"
                f"**{name}**\n"
                f"Avaliação: {rating_str}\n"
                f"{'Investimento: ' + price_str if price_str else ''}\n\n"
                f"Acesse agora: {hotlink}\n\n"
                f"Abraços!"
            )
        else:
            return f"{name} — {hotlink}"


# Tool para integrar ao tool_executor
def execute_affiliate_action(
    affiliate_module: "AffiliateModule",
    action: str,
    args: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Ponto de entrada para o tool_executor chamar este módulo.
    
    Actions disponíveis:
    - list_links: lista todos os links ativos
    - get_best: retorna melhor link por nicho
    - generate_promo: gera texto de divulgação
    """
    try:
        if action == "list_links":
            niche = args.get("niche")
            links = affiliate_module.get_active_links(niche=niche)
            summary = affiliate_module.format_links_summary(links)
            return {
                "tool": "affiliate.list_links",
                "success": True,
                "count": len(links),
                "links": links,
                "summary": summary,
            }

        elif action == "get_best":
            niche = args.get("niche")
            link = affiliate_module.get_best_link(niche=niche)
            if not link:
                return {
                    "tool": "affiliate.get_best",
                    "success": False,
                    "error": "Nenhum link encontrado. Cadastre links na tabela affiliate_links no Supabase.",
                }
            return {
                "tool": "affiliate.get_best",
                "success": True,
                "link": link,
                "summary": affiliate_module.format_links_summary([link]),
            }

        elif action == "generate_promo":
            niche = args.get("niche")
            format_ = args.get("format", "instagram")
            link = affiliate_module.get_best_link(niche=niche)
            if not link:
                return {
                    "tool": "affiliate.generate_promo",
                    "success": False,
                    "error": "Nenhum link cadastrado. Adicione links na tabela affiliate_links.",
                }
            promo_text = affiliate_module.generate_promo_text(link, format=format_)
            return {
                "tool": "affiliate.generate_promo",
                "success": True,
                "product": link["product_name"],
                "format": format_,
                "promo_text": promo_text,
                "hotlink": link["hotlink"],
            }

        else:
            return {
                "tool": f"affiliate.{action}",
                "success": False,
                "error": f"Action '{action}' não reconhecida. Use: list_links, get_best, generate_promo",
            }

    except Exception as e:
        return {
            "tool": f"affiliate.{action}",
            "success": False,
            "error": repr(e),
        }
