"""
autenticar_blogger.py
Script para gerar o BLOGGER_TOKEN_JSON que vai na variável de ambiente do Railway.

COMO USAR:
1. Acesse console.cloud.google.com
2. Crie um projeto (ou use um existente)
3. Ative a Blogger API v3
4. Crie credenciais OAuth 2.0 (tipo: Aplicativo para computador)
5. Baixe o client_secret_*.json
6. Execute: python autenticar_blogger.py --client-secret client_secret_xxx.json
7. Faça login com a conta Google que ADMINISTRA o blog
8. Copie o token impresso e cole na variável BLOGGER_TOKEN_JSON no Railway

REQUISITOS:
    pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
"""

import argparse
import json
import sys
import webbrowser
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/blogger"]
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"   # modo instalado (sem servidor local)


def autenticar(client_secret_path: str) -> dict:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("\n[ERRO] Instale as dependências primeiro:")
        print("  pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        sys.exit(1)

    secret_file = Path(client_secret_path)
    if not secret_file.exists():
        print(f"\n[ERRO] Arquivo não encontrado: {client_secret_path}")
        print("Baixe em: console.cloud.google.com → Credenciais → Baixar JSON")
        sys.exit(1)

    print("\n" + "="*60)
    print("AUTENTICAÇÃO DO BLOGGER")
    print("="*60)
    print(f"\nUsando: {client_secret_path}")
    print(f"Escopos: {SCOPES}")
    print("\nATENÇÃO: faça login com a conta Google que ADMINISTRA")
    print(f"o blog ID: {_get_blog_id_hint()}")
    print("="*60 + "\n")

    flow = InstalledAppFlow.from_client_secrets_file(secret_file, SCOPES)

    # Tenta abrir no browser automaticamente
    try:
        creds = flow.run_local_server(port=0)
        print("\n✅ Autenticação concluída pelo browser.")
    except Exception:
        # Fallback: modo manual (para ambientes sem browser)
        auth_url, _ = flow.authorization_url(prompt="consent")
        print(f"Abra esta URL no browser:\n\n{auth_url}\n")
        code = input("Cole o código de autorização aqui: ").strip()
        flow.fetch_token(code=code)
        creds = flow.credentials

    return json.loads(creds.to_json())


def _get_blog_id_hint() -> str:
    import os
    return os.environ.get("BLOGGER_BLOG_ID", "4662900378644975091 (padrão detectado)")


def verificar_permissao(token_json: dict) -> None:
    """Verifica se o token consegue listar posts no blog (confirma permissão)."""
    import os
    try:
        import requests
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        creds = Credentials.from_authorized_user_info(token_json, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        blog_id = os.environ.get("BLOGGER_BLOG_ID", "4662900378644975091")
        url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}"
        resp = requests.get(url, headers={"Authorization": f"Bearer {creds.token}"}, timeout=10)

        if resp.status_code == 200:
            blog = resp.json()
            print(f"\n✅ Permissão confirmada!")
            print(f"   Blog: {blog.get('name')}")
            print(f"   URL:  {blog.get('url')}")
        elif resp.status_code == 403:
            print(f"\n⚠️  403 — A conta autenticada não tem permissão neste blog.")
            print("   Certifique-se de que o email usado é admin/autor do blog.")
        else:
            print(f"\n⚠️  Resposta inesperada: {resp.status_code} — {resp.text[:200]}")
    except Exception as e:
        print(f"\n[AVISO] Não foi possível verificar permissão: {e}")


def main():
    parser = argparse.ArgumentParser(description="Gera BLOGGER_TOKEN_JSON para o Railway")
    parser.add_argument(
        "--client-secret",
        required=True,
        help="Caminho para o client_secret_*.json baixado do Google Cloud Console",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Salvar token em arquivo (opcional). Ex: --output token.json",
    )
    args = parser.parse_args()

    token_json = autenticar(args.client_secret)

    # Verificar permissão no blog
    verificar_permissao(token_json)

    token_str = json.dumps(token_json)

    print("\n" + "="*60)
    print("TOKEN GERADO — copie abaixo e cole no Railway:")
    print("Variável: BLOGGER_TOKEN_JSON")
    print("="*60)
    print(f"\n{token_str}\n")
    print("="*60)
    print("\nPassos no Railway:")
    print("1. Acesse seu serviço → Variables")
    print("2. Adicione/atualize: BLOGGER_TOKEN_JSON = <token acima>")
    print("3. Redeploy (o Railway reinicia automaticamente)")
    print("="*60)

    if args.output:
        Path(args.output).write_text(json.dumps(token_json, indent=2))
        print(f"\nToken salvo em: {args.output}")


if __name__ == "__main__":
    main()
