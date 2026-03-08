"""
blogger_module.py
Módulo para publicar artigos no Blogger via API do Google.
O agente EU_DE_NEGOCIOS usa este módulo para publicar conteúdo real.

CORREÇÃO: Token renovado é salvo no Supabase (agent_state) para persistir
entre restarts do Railway. Sem isso, o token expirava a cada ciclo.
"""

import os
import json
import logging
from typing import Optional

import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/blogger"]
BLOG_ID = os.environ.get("BLOGGER_BLOG_ID", "")


def _supabase_headers() -> dict:
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _load_token_from_supabase() -> Optional[str]:
    """Lê o token salvo na tabela agent_state do Supabase."""
    url = os.environ.get("SUPABASE_URL", "")
    if not url:
        return None
    try:
        resp = requests.get(
            f"{url}/rest/v1/agent_state",
            headers=_supabase_headers(),
            params={"select": "current_task_prompt", "agent_name": "eq.BLOGGER_TOKEN"},
            timeout=10,
        )
        data = resp.json()
        if data and isinstance(data, list) and len(data) > 0:
            return data[0].get("current_task_prompt")
    except Exception as e:
        logger.warning(f"[BloggerToken] Erro ao ler token do Supabase: {e}")
    return None


def _save_token_to_supabase(token_json: str):
    """Salva o token renovado no Supabase para persistir entre restarts."""
    url = os.environ.get("SUPABASE_URL", "")
    if not url:
        return
    try:
        resp = requests.post(
            f"{url}/rest/v1/agent_state",
            headers={**_supabase_headers(), "Prefer": "resolution=merge-duplicates"},
            json={
                "agent_name": "BLOGGER_TOKEN",
                "current_task_prompt": token_json,
            },
            timeout=10,
        )
        if resp.status_code in (200, 201):
            logger.info("[BloggerToken] Token salvo no Supabase com sucesso.")
        else:
            logger.warning(f"[BloggerToken] Supabase retornou {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"[BloggerToken] Erro ao salvar token no Supabase: {e}")


def _get_credentials() -> Optional[Credentials]:
    """
    Obtém credenciais OAuth válidas, renovando se necessário.
    Ordem de prioridade:
      1. Supabase (token mais recente, persiste entre restarts)
      2. Variável de ambiente BLOGGER_TOKEN_JSON (fallback)
    Após renovar, salva no Supabase para o próximo ciclo.
    """
    creds = None

    # 1. Tenta carregar do Supabase (mais atualizado)
    token_from_supabase = _load_token_from_supabase()
    if token_from_supabase:
        try:
            creds = Credentials.from_authorized_user_info(
                json.loads(token_from_supabase), SCOPES
            )
            logger.info("[BloggerToken] Token carregado do Supabase.")
        except Exception as e:
            logger.warning(f"[BloggerToken] Token do Supabase inválido: {e}")
            creds = None

    # 2. Fallback: variável de ambiente
    if not creds:
        token_json = os.environ.get("BLOGGER_TOKEN_JSON")
        if token_json:
            try:
                creds = Credentials.from_authorized_user_info(
                    json.loads(token_json), SCOPES
                )
                logger.info("[BloggerToken] Token carregado da variável de ambiente.")
            except Exception as e:
                logger.warning(f"[BloggerToken] Token da env inválido: {e}")

    if not creds:
        logger.error("[BloggerToken] Nenhuma credencial encontrada.")
        return None

    # Renova se expirado
    if creds.expired and creds.refresh_token:
        try:
            logger.info("[BloggerToken] Token expirado, renovando...")
            creds.refresh(Request())
            _save_token_to_supabase(creds.to_json())
            logger.info("[BloggerToken] Token renovado e salvo no Supabase.")
        except Exception as e:
            logger.error(f"[BloggerToken] Falha ao renovar token: {e}")
            return None

    return creds


def get_blog_id() -> Optional[str]:
    """Descobre o ID do blog automaticamente pelo URL."""
    creds = _get_credentials()
    if not creds:
        return None

    url = "https://www.googleapis.com/blogger/v3/blogs/byurl"
    params = {"url": "https://equilibriobemviver.blogspot.com"}
    headers = {"Authorization": f"Bearer {creds.token}"}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        blog_id = data.get("id")
        logger.info(f"Blog ID encontrado: {blog_id}")
        return blog_id
    except Exception as e:
        logger.error(f"Erro ao buscar blog ID: {e}")
        return None


def publish_post(
    title: str,
    content: str,
    labels: list = None,
    affiliate_link: str = None,
    affiliate_product: str = None,
) -> dict:
    """
    Publica um artigo no Blogger.

    Args:
        title: Título do artigo
        content: Conteúdo HTML do artigo
        labels: Lista de categorias/tags
        affiliate_link: Link de afiliado para incluir no artigo
        affiliate_product: Nome do produto afiliado

    Returns:
        dict com status, url e id do post publicado
    """
    creds = _get_credentials()
    if not creds:
        return {"success": False, "error": "Sem credenciais válidas. Execute autenticar_blogger.py primeiro."}

    blog_id = BLOG_ID or get_blog_id()
    if not blog_id:
        return {"success": False, "error": "BLOGGER_BLOG_ID não configurado."}

    # Adiciona CTA de afiliado no final do artigo se fornecido
    if affiliate_link and affiliate_product:
        cta_html = f"""
<hr>
<div style="background:#f0f7f0;border-left:4px solid #2e7d32;padding:16px;margin:24px 0;border-radius:4px;">
  <p><strong>🌿 Produto recomendado:</strong> {affiliate_product}</p>
  <p>
    <a href="{affiliate_link}"
       style="background:#2e7d32;color:white;padding:10px 20px;text-decoration:none;border-radius:4px;display:inline-block;">
      👉 Saiba mais e garanta o seu
    </a>
  </p>
  <p><small><em>Link de afiliado — ao comprar através deste link você apoia este blog sem custo adicional.</em></small></p>
</div>
"""
        content = content + cta_html

    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts/"
    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
    }
    payload = {
        "title": title,
        "content": content,
        "labels": labels or ["saúde", "emagrecimento"],
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        result = {
            "success": True,
            "post_id": data.get("id"),
            "url": data.get("url"),
            "title": data.get("title"),
            "published_at": data.get("published"),
        }
        logger.info(f"Artigo publicado: {result['url']}")
        return result

    except requests.exceptions.HTTPError as e:
        error_detail = ""
        try:
            error_detail = e.response.json().get("error", {}).get("message", "")
        except Exception:
            pass
        logger.error(f"Erro HTTP ao publicar: {e} — {error_detail}")
        return {"success": False, "error": str(e), "detail": error_detail}
    except Exception as e:
        logger.error(f"Erro ao publicar no Blogger: {e}")
        return {"success": False, "error": str(e)}


def list_recent_posts(max_results: int = 5) -> list:
    """Lista os posts mais recentes do blog."""
    creds = _get_credentials()
    if not creds:
        return []

    blog_id = BLOG_ID or get_blog_id()
    if not blog_id:
        return []

    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts"
    headers = {"Authorization": f"Bearer {creds.token}"}
    params = {"maxResults": max_results, "orderBy": "published"}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        posts = resp.json().get("items", [])
        return [
            {
                "id": p.get("id"),
                "title": p.get("title"),
                "url": p.get("url"),
                "published": p.get("published"),
                "labels": p.get("labels", []),
            }
            for p in posts
        ]
    except Exception as e:
        logger.error(f"Erro ao listar posts: {e}")
        return []
