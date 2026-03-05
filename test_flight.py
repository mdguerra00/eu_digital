#!/usr/bin/env python3
"""
Test Flight Script para o Agente EU DE NEGÓCIOS
Este script simula um ambiente local com Supabase e Perplexity Search para testar o agente.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# Configurar variáveis de ambiente para o teste
os.environ["SUPABASE_URL"] = "http://localhost:8000"
os.environ["SUPABASE_ANON_KEY"] = "test-key-12345"
os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "sk-test")
os.environ["AGENT_CYCLES_TABLE"] = "agent_cycles"
os.environ["AGENT_STATE_TABLE"] = "agent_state"
os.environ["AGENT_NAME"] = "EU_DE_NEGOCIOS"
os.environ["FOCUS"] = "Encontrar nichos lucrativos de marketing de afiliados"
os.environ["TASK_PROMPT"] = "Pesquise os 5 nichos mais lucrativos para marketing de afiliados em 2026 e defina uma estratégia de entrada."
os.environ["MEMORY_WINDOW"] = "5"
os.environ["MODEL"] = "gpt-4.1-mini"
os.environ["TEMPERATURE"] = "0.4"
os.environ["LOOP_INTERVAL_MINUTES"] = "20"

# Simular Supabase localmente
class MockSupabaseClient:
    def __init__(self):
        self.data = {
            "agent_cycles": [],
            "agent_state": []
        }
    
    def table(self, table_name):
        return MockTable(self.data, table_name)

class MockTable:
    def __init__(self, data, table_name):
        self.data = data
        self.table_name = table_name
        self._filters = {}
        self._order_by = None
        self._limit_val = None
        self._select_cols = None
    
    def select(self, cols):
        self._select_cols = cols
        return self
    
    def eq(self, col, val):
        self._filters[col] = val
        return self
    
    def order(self, col, desc=False):
        self._order_by = (col, desc)
        return self
    
    def limit(self, n):
        self._limit_val = n
        return self
    
    def insert(self, row):
        row["id"] = len(self.data[self.table_name]) + 1
        row["created_at"] = datetime.now(timezone.utc).isoformat()
        self.data[self.table_name].append(row)
        self._insert_row = row
        return self
    
    def update(self, row):
        # Para o teste, apenas simulamos uma atualização bem-sucedida
        self._update_row = row
        return self

    def upsert(self, row):
        existing_idx = None
        agent_name = row.get("agent_name")
        for i, current in enumerate(self.data[self.table_name]):
            if current.get("agent_name") == agent_name:
                existing_idx = i
                break

        if existing_idx is not None:
            updated = dict(self.data[self.table_name][existing_idx])
            updated.update(row)
            self.data[self.table_name][existing_idx] = updated
            self._upsert_row = updated
        else:
            row = dict(row)
            row["id"] = len(self.data[self.table_name]) + 1
            row.setdefault("created_at", datetime.now(timezone.utc).isoformat())
            self.data[self.table_name].append(row)
            self._upsert_row = row

        return self
    
    def execute(self):
        # Filtrar dados
        results = self.data[self.table_name]
        for col, val in self._filters.items():
            results = [r for r in results if r.get(col) == val]
        
        # Ordenar
        if self._order_by:
            col, desc = self._order_by
            results = sorted(results, key=lambda x: x.get(col, ""), reverse=desc)
        
        # Limitar
        if self._limit_val:
            results = results[:self._limit_val]
        
        return MockResponse(results)

class MockResponse:
    def __init__(self, data):
        self.data = data

def mock_create_client(url, key):
    return MockSupabaseClient()

# Simular Perplexity Search API
class MockPerplexitySearchTool:
    def __init__(self, api_key=None):
        self.api_key = api_key
    
    def search(self, query):
        # Resultados simulados para nichos lucrativos
        mock_results = {
            "marketing de afiliados": [
                {"title": "Top 10 Affiliate Programs 2026", "url": "https://example.com/affiliate-programs", "snippet": "Best affiliate programs with high commissions..."},
                {"title": "Hotmart: Plataforma de Afiliados", "url": "https://hotmart.com", "snippet": "Plataforma brasileira líder em produtos digitais..."},
                {"title": "ClickBank: Ganhe Comissões", "url": "https://clickbank.com", "snippet": "Marketplace de produtos digitais com até 75% de comissão..."}
            ],
            "produtos digitais": [
                {"title": "Mercado de Cursos Online 2026", "url": "https://example.com/cursos", "snippet": "Crescimento de 45% no mercado de cursos online..."},
                {"title": "Eduzz: Plataforma de Vendas", "url": "https://eduzz.com", "snippet": "Plataforma para vender cursos e produtos digitais..."}
            ],
            "nicho de saúde": [
                {"title": "Suplementos e Fitness: Mercado em Expansão", "url": "https://example.com/fitness", "snippet": "Mercado de suplementos cresce 30% ao ano..."},
            ]
        }
        
        # Retornar resultados baseados na query
        for key, results in mock_results.items():
            if key.lower() in query.lower():
                return results
        
        return []

# Patch do Supabase e Perplexity Search
def run_test_flight():
    print("\n" + "="*70)
    print("VÔOO DE TESTE - AGENTE EU DE NEGÓCIOS")
    print("="*70)
    
    # Importar após patches
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    
    # Patch do Supabase e Perplexity Search
    with patch('supabase.create_client', mock_create_client):
        with patch('tools_module.WebSearchTool', MockPerplexitySearchTool):
            import main
            
            print("\n[✓] Ambiente de teste configurado")
            print(f"[✓] Agente: {main.AGENT_NAME}")
            print(f"[✓] Focus: {main.FOCUS}")
            print(f"[✓] Task Prompt: {main.TASK_PROMPT_ENV[:80]}...")
            
            # Executar um ciclo
            print("\n" + "-"*70)
            print("Iniciando Ciclo 1...")
            print("-"*70)
            
            try:
                run_id = "test-flight-001"
                result = main.run_once(run_id)
                
                print("\n[✓] Ciclo executado com sucesso!")
                print(f"[✓] ID do Ciclo: {result.get('id')}")
                print(f"[✓] Número do Ciclo: {result.get('cycle_number')}")
                print(f"[✓] Timestamp: {result.get('created_at')}")
                
                # Exibir resultado
                print("\n" + "-"*70)
                print("RESULTADO DO CICLO:")
                print("-"*70)
                result_text = result.get('result_text', '')
                print(result_text[:500] + "..." if len(result_text) > 500 else result_text)
                
                # Exibir reflexão
                print("\n" + "-"*70)
                print("REFLEXÃO:")
                print("-"*70)
                reflection = result.get('reflection', '')
                print(reflection[:500] + "..." if len(reflection) > 500 else reflection)
                
                # Exibir próximas ações
                print("\n" + "-"*70)
                print("PRÓXIMAS AÇÕES:")
                print("-"*70)
                next_actions = result.get('next_actions', '')
                print(next_actions[:500] + "..." if len(next_actions) > 500 else next_actions)
                
                # Verificar saldo da carteira
                print("\n" + "-"*70)
                print("ESTADO DA CARTEIRA:")
                print("-"*70)
                balance = main.wallet.get_balance()
                print(f"Receita Total: R$ {balance['total_revenue']:.2f}")
                print(f"Despesas Totais: R$ {balance['total_expenses']:.2f}")
                print(f"Lucro Liquido: R$ {balance['net_profit']:.2f}")
                print(f"Saldo do Agente (20%): R$ {balance['agent_balance']:.2f}")
                print(f"Saldo do Criador (80%): R$ {balance['creator_balance']:.2f}")
                print(f"\nNota: Os saldos comecam em 0, pois nenhuma receita foi registrada neste teste.")
                print(f"Quando o agente gerar receita, sera automaticamente dividida em 80% Criador / 20% Agente.")
                
                print("\n" + "="*70)
                print("VÔOO DE TESTE CONCLUÍDO COM SUCESSO!")
                print("="*70)
                
                return True
            
            except Exception as e:
                print(f"\n[✗] ERRO DURANTE A EXECUÇÃO: {repr(e)}")
                import traceback
                traceback.print_exc()
                return False

if __name__ == "__main__":
    success = run_test_flight()
    sys.exit(0 if success else 1)
