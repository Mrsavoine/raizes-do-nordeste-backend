"""Conversão de entidades em contratos JSON. Dados sensíveis (senha_hash) nunca são serializados."""
from ..domain.entities import Pedido, Produto, Promocao, Unidade, Usuario


def reais(centavos):
    return None if centavos is None else round(centavos / 100, 2)


def usuario(u: Usuario) -> dict:
    return {"id": u.id, "nome": u.nome, "email": u.email, "perfil": u.perfil, "unidadeId": u.unidade_id,
            "ativo": u.ativo, "criadoEm": u.criado_em}


def unidade(u: Unidade) -> dict:
    return {"id": u.id, "nome": u.nome, "cidade": u.cidade, "uf": u.uf, "ativa": u.ativa}


def produto(p: Produto) -> dict:
    return {"id": p.id, "nome": p.nome, "descricao": p.descricao, "precoBase": reais(p.preco_base_centavos)}


def promocao(p: Promocao) -> dict:
    return {"id": p.id, "codigo": p.codigo, "descricao": p.descricao, "percentual": p.percentual,
            "valorMinimo": reais(p.valor_minimo_centavos), "ativa": p.ativa, "validoAte": p.valido_ate}


def pedido(p: Pedido) -> dict:
    return {
        "pedidoId": p.id, "clienteId": p.cliente_id, "unidadeId": p.unidade_id, "canalPedido": p.canal_pedido,
        "status": p.status, "subtotal": reais(p.subtotal_centavos), "desconto": reais(p.desconto_centavos),
        "total": reais(p.total_centavos), "formaPagamento": p.forma_pagamento, "promocaoId": p.promocao_id,
        "itens": [{"produtoId": i.produto_id, "quantidade": i.quantidade, "precoUnitario": reais(i.preco_unitario_centavos)}
                  for i in p.itens],
        "createdAt": p.criado_em, "updatedAt": p.atualizado_em,
    }


def pagamento(p: dict) -> dict:
    return {"pagamentoId": p["id"], "pedidoId": p["pedido_id"], "metodo": p["metodo"], "status": p["status"],
            "valor": reais(p["valor_centavos"]), "mensagem": p["mensagem"], "payloadEnviado": p["payload_enviado"],
            "payloadRecebido": p["payload_recebido"], "createdAt": p["criado_em"]}


def movimento_estoque(m: dict) -> dict:
    return {"id": m["id"], "unidadeId": m["unidade_id"], "produtoId": m["produto_id"], "tipo": m["tipo"],
            "quantidade": m["quantidade"], "motivo": m["motivo"], "pedidoId": m["pedido_id"],
            "usuarioId": m["usuario_id"], "createdAt": m["criado_em"]}


def auditoria(a: dict) -> dict:
    return {"id": a["id"], "usuarioId": a["usuario_id"], "perfil": a["perfil"], "acao": a["acao"],
            "entidade": a["entidade"], "entidadeId": a["entidade_id"], "detalhes": a["detalhes"],
            "requestId": a["request_id"], "createdAt": a["criado_em"]}
