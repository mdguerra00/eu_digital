"""
Módulo Financeiro para o Agente "EU DE NEGÓCIOS"
Gerencia a carteira do agente, rastreando lucros, despesas e a divisão 80/20 com o Criador.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional


class FinancialWallet:
    """
    Gerencia a carteira financeira do agente.
    - 80% do lucro líquido vai para o Criador
    - 20% do lucro líquido fica com o Agente para reinvestimento
    """
    
    def __init__(self, wallet_file: str = "agent_wallet.json"):
        self.wallet_file = Path(wallet_file)
        self.data = self._load_wallet()
    
    def _load_wallet(self) -> Dict[str, Any]:
        """Carrega a carteira do arquivo JSON ou cria uma nova se não existir."""
        if self.wallet_file.exists():
            try:
                with open(self.wallet_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Aviso: falha ao carregar carteira: {e}. Criando nova carteira.")
        
        # Estrutura padrão da carteira
        return {
            "agent_name": "EU_DE_NEGOCIOS",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "agent_balance": 0.0,  # 20% do lucro
            "creator_balance": 0.0,  # 80% do lucro (pendente de saque)
            "total_revenue": 0.0,  # Receita total
            "total_expenses": 0.0,  # Despesas totais
            "transactions": [],  # Histórico de transações
            "minimum_reserve": 100.0,  # Reserva mínima de segurança (em unidades)
        }
    
    def _save_wallet(self) -> None:
        """Salva a carteira no arquivo JSON."""
        try:
            with open(self.wallet_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar carteira: {e}")
    
    def record_revenue(self, amount: float, source: str, description: str = "") -> Dict[str, Any]:
        """
        Registra uma receita e aplica a divisão 80/20.
        
        Args:
            amount: Valor da receita
            source: Fonte da receita (ex: "afiliado_hotmart", "comissao_clickbank")
            description: Descrição adicional
        
        Returns:
            Dicionário com a transação registrada
        """
        if amount <= 0:
            raise ValueError("Valor de receita deve ser positivo")
        
        # Calcular divisão
        creator_share = amount * 0.80
        agent_share = amount * 0.20
        
        # Atualizar saldos
        self.data["total_revenue"] += amount
        self.data["creator_balance"] += creator_share
        self.data["agent_balance"] += agent_share
        
        # Registrar transação
        transaction = {
            "id": len(self.data["transactions"]) + 1,
            "type": "revenue",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "amount": amount,
            "source": source,
            "description": description,
            "creator_share": creator_share,
            "agent_share": agent_share,
            "agent_balance_after": self.data["agent_balance"],
            "creator_balance_after": self.data["creator_balance"],
        }
        self.data["transactions"].append(transaction)
        self._save_wallet()
        
        return transaction
    
    def record_expense(self, amount: float, category: str, description: str = "") -> Dict[str, Any]:
        """
        Registra uma despesa (deduzida do saldo do agente).
        
        Args:
            amount: Valor da despesa
            category: Categoria (ex: "infraestrutura", "ferramentas", "marketing")
            description: Descrição adicional
        
        Returns:
            Dicionário com a transação registrada
        """
        if amount <= 0:
            raise ValueError("Valor de despesa deve ser positivo")
        
        if self.data["agent_balance"] < amount:
            raise ValueError(f"Saldo insuficiente. Disponível: {self.data['agent_balance']}, Solicitado: {amount}")
        
        # Atualizar saldos
        self.data["total_expenses"] += amount
        self.data["agent_balance"] -= amount
        
        # Registrar transação
        transaction = {
            "id": len(self.data["transactions"]) + 1,
            "type": "expense",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "amount": amount,
            "category": category,
            "description": description,
            "agent_balance_after": self.data["agent_balance"],
        }
        self.data["transactions"].append(transaction)
        self._save_wallet()
        
        return transaction
    
    def get_balance(self) -> Dict[str, float]:
        """Retorna o saldo atual da carteira."""
        return {
            "agent_balance": self.data["agent_balance"],
            "creator_balance": self.data["creator_balance"],
            "total_revenue": self.data["total_revenue"],
            "total_expenses": self.data["total_expenses"],
            "net_profit": self.data["total_revenue"] - self.data["total_expenses"],
        }
    
    def get_transactions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retorna as últimas transações."""
        return self.data["transactions"][-limit:]
    
    def request_creator_withdrawal(self, amount: Optional[float] = None) -> Dict[str, Any]:
        """
        Prepara uma solicitação de saque para o Criador.
        
        Args:
            amount: Valor a sacar (None = sacar tudo)
        
        Returns:
            Dicionário com informações da solicitação
        """
        if amount is None:
            amount = self.data["creator_balance"]
        
        if amount <= 0:
            raise ValueError("Valor de saque deve ser positivo")
        
        if self.data["creator_balance"] < amount:
            raise ValueError(f"Saldo insuficiente. Disponível: {self.data['creator_balance']}, Solicitado: {amount}")
        
        # Criar solicitação (não deduz automaticamente, aguarda aprovação do Criador)
        request = {
            "id": len(self.data["transactions"]) + 1,
            "type": "withdrawal_request",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "amount": amount,
            "status": "pending",
            "creator_balance_at_request": self.data["creator_balance"],
        }
        
        return request
    
    def get_financial_summary(self) -> str:
        """Retorna um resumo financeiro em formato legível."""
        balance = self.get_balance()
        summary = f"""
=== RESUMO FINANCEIRO DO AGENTE ===
Saldo do Agente (20%): R$ {balance['agent_balance']:.2f}
Saldo do Criador (80%): R$ {balance['creator_balance']:.2f}
Receita Total: R$ {balance['total_revenue']:.2f}
Despesas Totais: R$ {balance['total_expenses']:.2f}
Lucro Líquido: R$ {balance['net_profit']:.2f}
Reserva Mínima: R$ {self.data['minimum_reserve']:.2f}
"""
        return summary


# Exemplo de uso
if __name__ == "__main__":
    wallet = FinancialWallet()
    
    # Simular receitas
    print("Registrando receita de afiliado...")
    tx1 = wallet.record_revenue(1000.0, "afiliado_hotmart", "Venda de curso de marketing")
    print(f"Transação: {tx1}")
    
    print("\nRegistrando despesa de ferramentas...")
    tx2 = wallet.record_expense(50.0, "ferramentas", "Assinatura de software")
    print(f"Transação: {tx2}")
    
    print(wallet.get_financial_summary())
    print("\nÚltimas transações:")
    for tx in wallet.get_transactions():
        print(f"  - {tx['type']}: R$ {tx.get('amount', 'N/A')} ({tx.get('source', tx.get('category', 'N/A'))})")
