"""
blogger_module.py
Módulo para publicar artigos no Blogger via API do Google.
O agente EU_DE_NEGOCIOS usa este módulo para publicar conteúdo real.
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional

import requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

# Escopos necessários para ler e escrever no Blogger
SCOPES = ["https://www.googleapis.com/auth/blogger"]

# ID do blog (preenchido após autenticação inicial)
BLOG_ID = os.environ.get("BLOGGER_BLOG_ID", "")

# Caminho para o token salvo (Railway persiste variáveis de ambiente)
TOKEN_PATH = "blogger_token.json"
CREDENTIALS_PATH = "blogger_credentials.json"


def _get_credentials() -> Optional[Credentials]:
    """Obtém credenciais OAuth válidas, renovando se necessário."""
    creds = None

    # Tenta carregar token salvo
    token_json = os.environ.get("BLOGGER_TOKEN_JSON")
    if token_json:
        try:
            creds = Credentials.from_authorized_user_info(
                json.loads(token_json), SCOPES
            )
        except Exception as e:
            logger.warning(f"Token salvo inválido: {e}")

    # Fallback: arquivo local
    if not creds and os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # Renova token expirado automaticamente
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
            logger.info("Token renovado com sucesso.")
        except Exception as e:
            logger.error(f"Falha ao renovar token: {e}")
            creds = None

    return creds


def _save_token(creds: Credentials):
    """Salva token em arquivo local para reutilização."""
    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())
    logger.info(f"Token salvo em {TOKEN_PATH}")


def authenticate() -> bool:
    """
    Realiza autenticação OAuth interativa (rode localmente uma vez).
    Gera o blogger_token.json que deve ser adicionado ao Railway.
    """
    if not os.path.exists(CREDENTIALS_PATH):
        logger.error(
            f"Arquivo {CREDENTIALS_PATH} não encontrado. "
            "Baixe o JSON do Google Cloud Console e salve como blogger_credentials.json"
        )
        return False

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(creds)

    print("\n✅ Autenticação concluída!")
    print(f"Token salvo em: {TOKEN_PATH}")
    print("\nAdicione o conteúdo do token como variável de ambiente no Railway:")
    print("  Nome: BLOGGER_TOKEN_JSON")
    print(f"  Valor: {creds.to_json()}")
    return True


def get_blog_id() -> Optional[str]:
    """Descobre o ID do blog automaticamente pelo URL."""
    creds = _get_credentials()
    if not creds:
        logger.error("Sem credenciais válidas.")
        return None

    url = "https://www.googleapis.com/blogger/v3/blogs/byurl"
    params = {"url": "https://viverbemsaudavel.blogspot.com"}
    headers = {"Authorization": f"Bearer {creds.token}"}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        blog_id = data.get("id")
        print(f"✅ Blog ID encontrado: {blog_id}")
        print("Adicione no Railway como variável: BLOGGER_BLOG_ID=" + blog_id)
        return blog_id
    except Exception as e:
        logger.error(f"Erro ao buscar blog ID: {e}")
        return None


def publish_post(
    title: str,
    content: str,
    labels: list[str] = None,
    affiliate_link: str = None,
    affiliate_product: str = None,
) -> dict:
    """
    Publica um artigo no Blogger.

    Args:
        title: Título do artigo
        content: Conteúdo HTML do artigo
        labels: Lista de categorias/tags (ex: ["emagrecimento", "saúde"])
        affiliate_link: Link de afiliado para incluir no artigo
        affiliate_product: Nome do produto afiliado

    Returns:
        dict com status, url e id do post publicado
    """
    creds = _get_credentials()
    if not creds:
        return {"success": False, "error": "Sem credenciais válidas. Execute authenticate() primeiro."}

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


if __name__ == "__main__":
    # Rode este arquivo diretamente para autenticar:
    # python blogger_module.py
    print("=== Autenticação do Blogger ===")
    print("Este script abre o navegador para você autorizar o acesso ao Blogger.")
    print()
    if authenticate():
        print()
        print("=== Buscando ID do blog ===")
        get_blog_id()
