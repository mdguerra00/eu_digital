"""
Módulo Financeiro para o Agente "EU DE NEGÓCIOS"
Gerencia a carteira do agente, rastreando lucros, despesas e a divisão 80/20 com o Criador.

Backend: Supabase (primário) com fallback para JSON local.
Tabelas: agent_wallet_transactions, agent_wallet_balance
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional


# ─── Supabase client (opcional) ────────────────────────────────────────────────
try:
    from supabase import create_client, Client as SupabaseClient
    _SUPABASE_AVAILABLE = True
except ImportError:
    _SUPABASE_AVAILABLE = False

_AGENT_NAME = "EU_DE_NEGOCIOS"


def _get_supabase() -> Optional["SupabaseClient"]:
    """Retorna um cliente Supabase se as variáveis de ambiente estiverem configuradas."""
    if not _SUPABASE_AVAILABLE:
        return None
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception as e:
        print(f"[FinancialWallet] Aviso: falha ao criar cliente Supabase: {e}")
        return None


# ─── Classe Principal ───────────────────────────────────────────────────────────

class FinancialWallet:
    """
    Gerencia a carteira financeira do agente.
    - 80% do lucro líquido vai para o Criador
    - 20% do lucro líquido fica com o Agente para reinvestimento

    Persiste no Supabase (primário). Se indisponível, usa JSON local como fallback.
    """

    def __init__(self, wallet_file: str = "agent_wallet.json", agent_name: str = _AGENT_NAME):
        self.agent_name = agent_name
        self.wallet_file = Path(wallet_file)
        self._supabase = _get_supabase()

        if self._supabase:
            print("[FinancialWallet] ✅ Usando Supabase como backend financeiro.")
            self._ensure_balance_row()
        else:
            print("[FinancialWallet] ⚠️  Supabase indisponível — usando fallback JSON local.")
            self._local_data = self._load_local_wallet()

    # ── Supabase: saldo ──────────────────────────────────────────────────────────

    def _ensure_balance_row(self) -> None:
        """Garante que existe uma linha de saldo para este agente."""
        try:
            result = (
                self._supabase.table("agent_wallet_balance")
                .select("agent_name")
                .eq("agent_name", self.agent_name)
                .limit(1)
                .execute()
            )
            if not result.data:
                self._supabase.table("agent_wallet_balance").insert({
                    "agent_name": self.agent_name,
                    "agent_balance": 0.0,
                    "creator_balance": 0.0,
                    "total_revenue": 0.0,
                    "total_expenses": 0.0,
                    "minimum_reserve": 100.0,
                }).execute()
        except Exception as e:
            print(f"[FinancialWallet] Erro ao verificar linha de saldo: {e}")

    def _fetch_balance_row(self) -> Dict[str, float]:
        """Lê a linha de saldo atual do Supabase."""
        try:
            result = (
                self._supabase.table("agent_wallet_balance")
                .select("*")
                .eq("agent_name", self.agent_name)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0]
        except Exception as e:
            print(f"[FinancialWallet] Erro ao buscar saldo: {e}")
        return {
            "agent_balance": 0.0,
            "creator_balance": 0.0,
            "total_revenue": 0.0,
            "total_expenses": 0.0,
            "minimum_reserve": 100.0,
        }

    def _update_balance_row(self, updates: Dict[str, Any]) -> None:
        """Atualiza a linha de saldo no Supabase."""
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        try:
            self._supabase.table("agent_wallet_balance").update(updates).eq(
                "agent_name", self.agent_name
            ).execute()
        except Exception as e:
            print(f"[FinancialWallet] Erro ao atualizar saldo: {e}")

    def _insert_transaction(self, tx: Dict[str, Any]) -> Dict[str, Any]:
        """Insere uma transação no Supabase e retorna o registro criado."""
        tx["agent_name"] = self.agent_name
        try:
            result = (
                self._supabase.table("agent_wallet_transactions")
                .insert(tx)
                .execute()
            )
            if result.data:
                return result.data[0]
        except Exception as e:
            print(f"[FinancialWallet] Erro ao inserir transação: {e}")
        return tx

    # ── Fallback JSON ────────────────────────────────────────────────────────────

    def _load_local_wallet(self) -> Dict[str, Any]:
        if self.wallet_file.exists():
            try:
                with open(self.wallet_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[FinancialWallet] Aviso: falha ao carregar JSON local: {e}. Criando nova carteira.")
        return {
            "agent_name": self.agent_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "agent_balance": 0.0,
            "creator_balance": 0.0,
            "total_revenue": 0.0,
            "total_expenses": 0.0,
            "transactions": [],
            "minimum_reserve": 100.0,
        }

    def _save_local_wallet(self) -> None:
        try:
            with open(self.wallet_file, "w", encoding="utf-8") as f:
                json.dump(self._local_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[FinancialWallet] Erro ao salvar JSON local: {e}")

    # ── API pública ──────────────────────────────────────────────────────────────

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

        creator_share = round(amount * 0.80, 2)
        agent_share = round(amount * 0.20, 2)

        if self._supabase:
            balance = self._fetch_balance_row()
            new_agent_balance = round(float(balance["agent_balance"]) + agent_share, 2)
            new_creator_balance = round(float(balance["creator_balance"]) + creator_share, 2)
            new_total_revenue = round(float(balance["total_revenue"]) + amount, 2)

            tx_payload = {
                "type": "revenue",
                "amount": amount,
                "source": source,
                "description": description,
                "creator_share": creator_share,
                "agent_share": agent_share,
                "agent_balance_after": new_agent_balance,
                "creator_balance_after": new_creator_balance,
                "status": "confirmed",
            }
            transaction = self._insert_transaction(tx_payload)
            self._update_balance_row({
                "agent_balance": new_agent_balance,
                "creator_balance": new_creator_balance,
                "total_revenue": new_total_revenue,
            })
            return transaction

        # fallback JSON
        self._local_data["total_revenue"] += amount
        self._local_data["creator_balance"] += creator_share
        self._local_data["agent_balance"] += agent_share
        transaction = {
            "id": len(self._local_data["transactions"]) + 1,
            "type": "revenue",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "amount": amount,
            "source": source,
            "description": description,
            "creator_share": creator_share,
            "agent_share": agent_share,
            "agent_balance_after": self._local_data["agent_balance"],
            "creator_balance_after": self._local_data["creator_balance"],
        }
        self._local_data["transactions"].append(transaction)
        self._save_local_wallet()
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

        if self._supabase:
            balance = self._fetch_balance_row()
            if float(balance["agent_balance"]) < amount:
                raise ValueError(
                    f"Saldo insuficiente. Disponível: {balance['agent_balance']}, Solicitado: {amount}"
                )
            new_agent_balance = round(float(balance["agent_balance"]) - amount, 2)
            new_total_expenses = round(float(balance["total_expenses"]) + amount, 2)

            tx_payload = {
                "type": "expense",
                "amount": amount,
                "category": category,
                "description": description,
                "agent_balance_after": new_agent_balance,
                "status": "confirmed",
            }
            transaction = self._insert_transaction(tx_payload)
            self._update_balance_row({
                "agent_balance": new_agent_balance,
                "total_expenses": new_total_expenses,
            })
            return transaction

        # fallback JSON
        if self._local_data["agent_balance"] < amount:
            raise ValueError(
                f"Saldo insuficiente. Disponível: {self._local_data['agent_balance']}, Solicitado: {amount}"
            )
        self._local_data["total_expenses"] += amount
        self._local_data["agent_balance"] -= amount
        transaction = {
            "id": len(self._local_data["transactions"]) + 1,
            "type": "expense",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "amount": amount,
            "category": category,
            "description": description,
            "agent_balance_after": self._local_data["agent_balance"],
        }
        self._local_data["transactions"].append(transaction)
        self._save_local_wallet()
        return transaction

    def get_balance(self) -> Dict[str, float]:
        """Retorna o saldo atual da carteira."""
        if self._supabase:
            b = self._fetch_balance_row()
            return {
                "agent_balance": float(b["agent_balance"]),
                "creator_balance": float(b["creator_balance"]),
                "total_revenue": float(b["total_revenue"]),
                "total_expenses": float(b["total_expenses"]),
                "net_profit": round(float(b["total_revenue"]) - float(b["total_expenses"]), 2),
                "minimum_reserve": float(b.get("minimum_reserve", 100.0)),
            }
        return {
            "agent_balance": self._local_data["agent_balance"],
            "creator_balance": self._local_data["creator_balance"],
            "total_revenue": self._local_data["total_revenue"],
            "total_expenses": self._local_data["total_expenses"],
            "net_profit": self._local_data["total_revenue"] - self._local_data["total_expenses"],
            "minimum_reserve": self._local_data.get("minimum_reserve", 100.0),
        }

    def get_transactions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retorna as últimas transações."""
        if self._supabase:
            try:
                result = (
                    self._supabase.table("agent_wallet_transactions")
                    .select("*")
                    .eq("agent_name", self.agent_name)
                    .order("created_at", desc=True)
                    .limit(limit)
                    .execute()
                )
                return list(reversed(result.data)) if result.data else []
            except Exception as e:
                print(f"[FinancialWallet] Erro ao buscar transações: {e}")
                return []
        return self._local_data["transactions"][-limit:]

    def request_creator_withdrawal(self, amount: Optional[float] = None) -> Dict[str, Any]:
        """
        Prepara uma solicitação de saque para o Criador.

        Args:
            amount: Valor a sacar (None = sacar tudo disponível)

        Returns:
            Dicionário com informações da solicitação
        """
        balance = self.get_balance()

        if amount is None:
            amount = balance["creator_balance"]

        if amount <= 0:
            raise ValueError("Valor de saque deve ser positivo")

        if balance["creator_balance"] < amount:
            raise ValueError(
                f"Saldo insuficiente. Disponível: {balance['creator_balance']}, Solicitado: {amount}"
            )

        if self._supabase:
            tx_payload = {
                "type": "withdrawal_request",
                "amount": amount,
                "description": f"Solicitação de saque do Criador — saldo disponível: R$ {balance['creator_balance']:.2f}",
                "agent_balance_after": balance["agent_balance"],
                "creator_balance_after": balance["creator_balance"],
                "status": "pending",
                "metadata": {"creator_balance_at_request": balance["creator_balance"]},
            }
            return self._insert_transaction(tx_payload)

        # fallback JSON (não persiste o request, apenas retorna)
        return {
            "type": "withdrawal_request",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "amount": amount,
            "status": "pending",
            "creator_balance_at_request": balance["creator_balance"],
        }

    def get_financial_summary(self) -> str:
        """Retorna um resumo financeiro em formato legível."""
        b = self.get_balance()
        backend = "Supabase" if self._supabase else "JSON local (fallback)"
        return (
            f"\n=== RESUMO FINANCEIRO DO AGENTE ===\n"
            f"Backend: {backend}\n"
            f"Saldo do Agente (20%):  R$ {b['agent_balance']:.2f}\n"
            f"Saldo do Criador (80%): R$ {b['creator_balance']:.2f}\n"
            f"Receita Total:          R$ {b['total_revenue']:.2f}\n"
            f"Despesas Totais:        R$ {b['total_expenses']:.2f}\n"
            f"Lucro Líquido:          R$ {b['net_profit']:.2f}\n"
            f"Reserva Mínima:         R$ {b['minimum_reserve']:.2f}\n"
        )


# ─── Exemplo de uso ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    wallet = FinancialWallet()

    print("Registrando receita de afiliado...")
    tx1 = wallet.record_revenue(1000.0, "afiliado_hotmart", "Venda de curso de marketing")
    print(f"Transação: {tx1}")

    print("\nRegistrando despesa de ferramentas...")
    tx2 = wallet.record_expense(50.0, "ferramentas", "Assinatura de software")
    print(f"Transação: {tx2}")

    print(wallet.get_financial_summary())
    print("\nÚltimas transações:")
    for tx in wallet.get_transactions():
        print(f"  - {tx.get('type')}: R$ {tx.get('amount', 'N/A')} "
              f"({tx.get('source') or tx.get('category', 'N/A')})")
