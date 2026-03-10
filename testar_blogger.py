"""
testar_blogger.py — Diagnóstico manual da API do Blogger
Execute localmente com o token gerado pelo autenticar_blogger.py

Uso:
  python testar_blogger.py
"""

import json
import os
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# ── Lê o token da variável de ambiente BLOGGER_TOKEN_JSON ──
# Para rodar localmente: set BLOGGER_TOKEN_JSON=<valor gerado pelo autenticar_blogger.py>
TOKEN_JSON = os.environ.get("BLOGGER_TOKEN_JSON", "")
if not TOKEN_JSON:
    print("❌ Variável BLOGGER_TOKEN_JSON não encontrada.")
    print("   Execute: set BLOGGER_TOKEN_JSON=<valor do autenticar_blogger.py>")
    exit(1)

BLOG_ID = "4662900378644975091"
SCOPES = ["https://www.googleapis.com/auth/blogger"]

def get_token():
    creds = Credentials.from_authorized_user_info(json.loads(TOKEN_JSON.strip()), SCOPES)
    if creds.expired and creds.refresh_token:
        print("⟳ Token expirado, renovando...")
        creds.refresh(Request())
        print("✅ Token renovado!")
    return creds.token

def sep(titulo):
    print(f"\n{'─'*55}")
    print(f"  {titulo}")
    print('─'*55)

token = get_token()
headers = {"Authorization": f"Bearer {token}"}

# ── TESTE 1: Quais blogs este usuário tem acesso? ──
sep("TESTE 1 — Blogs acessíveis por este usuário")
r = requests.get("https://www.googleapis.com/blogger/v3/users/self/blogs", headers=headers)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    blogs = r.json().get("items", [])
    if blogs:
        for b in blogs:
            print(f"  • [{b['id']}] {b['name']} — {b.get('url','')}")
    else:
        print("  ⚠️  Nenhum blog encontrado para este usuário!")
else:
    print(f"  ERRO: {r.text[:300]}")

# ── TESTE 2: Leitura do blog pelo ID ──
sep(f"TESTE 2 — Leitura do blog {BLOG_ID}")
r = requests.get(f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}", headers=headers)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    d = r.json()
    print(f"  Nome:  {d.get('name')}")
    print(f"  URL:   {d.get('url')}")
    print(f"  Posts: {d.get('posts', {}).get('totalItems', '?')}")
else:
    print(f"  ERRO: {r.text[:300]}")

# ── TESTE 3: Buscar blog pelo URL do blog ──
sep("TESTE 3 — Buscar blog pelo URL")
r = requests.get(
    "https://www.googleapis.com/blogger/v3/blogs/byurl",
    headers=headers,
    params={"url": "https://equilibriobemviver.blogspot.com"}
)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    d = r.json()
    print(f"  ID encontrado: {d.get('id')}")
    print(f"  Nome:          {d.get('name')}")
else:
    print(f"  ERRO: {r.text[:300]}")

# ── TESTE 4: Tentar publicar post de TESTE ──
sep("TESTE 4 — Publicar post de teste (isDraft=true)")
url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts/?isDraft=true"
payload = {
    "title": "[TESTE DIAGNÓSTICO] Post de teste — pode apagar",
    "content": "<p>Teste de publicação via API. Pode apagar este post.</p>",
}
r = requests.post(url, headers={**headers, "Content-Type": "application/json"}, json=payload)
print(f"Status: {r.status_code}")
if r.status_code in (200, 201):
    d = r.json()
    print(f"  ✅ SUCESSO! Post criado como rascunho.")
    print(f"  ID:  {d.get('id')}")
    print(f"  URL: {d.get('url')}")
else:
    print(f"  ❌ ERRO: {r.text[:400]}")

print(f"\n{'═'*55}")
print("  Diagnóstico concluído.")
print('═'*55)
