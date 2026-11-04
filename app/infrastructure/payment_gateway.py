"""Gateway de pagamento SIMULADO. Nenhuma chamada de rede e nenhum dado de cartão são tratados."""
import uuid

from ..domain.errors import GatewayUnavailableError


class PaymentGatewayMock:
    """Comportamento determinístico controlado por `simulacao`: APROVADO (padrão), RECUSADO ou FALHA."""

    def processar(self, pedido_id: int, valor_centavos: int, metodo: str, simulacao: str | None) -> dict:
        resultado = (simulacao or "APROVADO").upper()
        transacao = str(uuid.uuid4())
        if resultado == "FALHA":
            raise GatewayUnavailableError(
                "O gateway de pagamento não respondeu a tempo. Tente novamente com a mesma Idempotency-Key.",
                details=[{"field": "gateway", "issue": "timeout simulado"}],
            )
        if resultado == "RECUSADO":
            return {"transactionId": transacao, "status": "RECUSADO", "motivo": "SALDO_OU_LIMITE_INSUFICIENTE",
                    "mensagem": "Pagamento recusado pelo emissor (simulação)."}
        return {"transactionId": transacao, "status": "APROVADO", "motivo": None,
                "mensagem": "Pagamento aprovado (simulação)."}
