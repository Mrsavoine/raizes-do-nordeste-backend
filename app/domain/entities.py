"""Entidades e regras puras do domínio (sem dependência de Flask, SQLite ou JWT)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .errors import ConflictError


class Perfil(str, Enum):
    CLIENTE = "CLIENTE"
    ATENDENTE = "ATENDENTE"
    COZINHA = "COZINHA"
    GERENTE = "GERENTE"
    ADMIN = "ADMIN"


class CanalPedido(str, Enum):
    APP = "APP"
    TOTEM = "TOTEM"
    BALCAO = "BALCAO"
    PICKUP = "PICKUP"
    WEB = "WEB"


class StatusPedido(str, Enum):
    AGUARDANDO_PAGAMENTO = "AGUARDANDO_PAGAMENTO"
    PAGO = "PAGO"
    EM_PREPARO = "EM_PREPARO"
    PRONTO = "PRONTO"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"
    PAGAMENTO_RECUSADO = "PAGAMENTO_RECUSADO"


class StatusPagamento(str, Enum):
    APROVADO = "APROVADO"
    RECUSADO = "RECUSADO"
    FALHA = "FALHA"


class TipoMovimento(str, Enum):
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"


# Máquina de estados do pedido. PAGO e PAGAMENTO_RECUSADO só são alcançados pelo fluxo de pagamento.
TRANSICOES: dict[StatusPedido, set[StatusPedido]] = {
    StatusPedido.AGUARDANDO_PAGAMENTO: {StatusPedido.PAGO, StatusPedido.PAGAMENTO_RECUSADO, StatusPedido.CANCELADO},
    StatusPedido.PAGO: {StatusPedido.EM_PREPARO, StatusPedido.CANCELADO},
    StatusPedido.EM_PREPARO: {StatusPedido.PRONTO, StatusPedido.CANCELADO},
    StatusPedido.PRONTO: {StatusPedido.ENTREGUE},
    StatusPedido.ENTREGUE: set(),
    StatusPedido.CANCELADO: set(),
    StatusPedido.PAGAMENTO_RECUSADO: set(),
}

# Quais status cada perfil pode definir manualmente via PATCH /pedidos/{id}/status.
STATUS_PERMITIDOS_POR_PERFIL: dict[Perfil, set[StatusPedido]] = {
    Perfil.COZINHA: {StatusPedido.EM_PREPARO, StatusPedido.PRONTO},
    Perfil.ATENDENTE: {StatusPedido.EM_PREPARO, StatusPedido.PRONTO, StatusPedido.ENTREGUE, StatusPedido.CANCELADO},
    Perfil.GERENTE: {StatusPedido.EM_PREPARO, StatusPedido.PRONTO, StatusPedido.ENTREGUE, StatusPedido.CANCELADO},
    Perfil.ADMIN: {StatusPedido.EM_PREPARO, StatusPedido.PRONTO, StatusPedido.ENTREGUE, StatusPedido.CANCELADO},
    Perfil.CLIENTE: {StatusPedido.CANCELADO},
}

PONTOS_MINIMOS_RESGATE = 10


@dataclass
class Unidade:
    id: int
    nome: str
    cidade: str
    uf: str
    ativa: bool
    criado_em: str


@dataclass
class Usuario:
    id: int
    nome: str
    email: str
    senha_hash: str
    perfil: str
    unidade_id: Optional[int]
    ativo: bool
    criado_em: str

    def eh_equipe(self) -> bool:
        return self.perfil != Perfil.CLIENTE.value


@dataclass
class Produto:
    id: int
    nome: str
    descricao: Optional[str]
    preco_base_centavos: int
    ativo: bool
    criado_em: str


@dataclass
class ItemCardapio:
    unidade_id: int
    produto_id: int
    preco_centavos: int
    disponivel: bool


@dataclass
class Promocao:
    id: int
    codigo: str
    descricao: str
    percentual: int
    valor_minimo_centavos: int
    ativa: bool
    valido_ate: Optional[str]
    criado_em: str

    def calcular_desconto(self, subtotal_centavos: int, agora_iso: str) -> int:
        """Valida a elegibilidade e devolve o desconto em centavos (arredondado para baixo)."""
        if not self.ativa:
            raise ConflictError("A promoção informada não está ativa.", code="PROMOCAO_INATIVA")
        if self.valido_ate and agora_iso > self.valido_ate:
            raise ConflictError("A promoção informada está expirada.", code="PROMOCAO_EXPIRADA")
        if subtotal_centavos < self.valor_minimo_centavos:
            raise ConflictError(
                "O pedido não atinge o valor mínimo da promoção.",
                details=[{"field": "codigoPromocao", "issue": f"Mínimo de {self.valor_minimo_centavos / 100:.2f}"}],
                code="PROMOCAO_NAO_ELEGIVEL",
            )
        return subtotal_centavos * self.percentual // 100


@dataclass
class ItemPedido:
    produto_id: int
    quantidade: int
    preco_unitario_centavos: int
    id: Optional[int] = None
    pedido_id: Optional[int] = None

    @property
    def subtotal_centavos(self) -> int:
        return self.quantidade * self.preco_unitario_centavos


@dataclass
class Pedido:
    id: Optional[int]
    cliente_id: int
    unidade_id: int
    canal_pedido: str
    status: str
    subtotal_centavos: int
    desconto_centavos: int
    total_centavos: int
    promocao_id: Optional[int]
    forma_pagamento: str
    criado_em: str
    atualizado_em: str
    itens: list[ItemPedido] = field(default_factory=list)

    def pode_transitar_para(self, novo: StatusPedido) -> bool:
        return novo in TRANSICOES[StatusPedido(self.status)]

    def validar_transicao(self, novo: StatusPedido) -> None:
        if not self.pode_transitar_para(novo):
            raise ConflictError(
                f"Transição de {self.status} para {novo.value} não é permitida.",
                details=[{"field": "status", "issue": f"Atual: {self.status}"}],
                code="TRANSICAO_DE_STATUS_INVALIDA",
            )


def calcular_pontos(total_centavos: int) -> int:
    """Regra de fidelidade: 1 ponto por real inteiro pago."""
    return total_centavos // 100
