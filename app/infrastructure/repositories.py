"""Repositórios SQL (SQLite). Convertem linhas em entidades de domínio; não contêm regras de negócio."""
import json
import sqlite3
from dataclasses import fields
from typing import Optional

from ..domain.entities import (ItemCardapio, ItemPedido, Pedido, Produto, Promocao, Unidade, Usuario)


def _build(cls, row):
    if row is None:
        return None
    nomes = {f.name for f in fields(cls)}
    dados = {k: row[k] for k in row.keys() if k in nomes}
    for campo in ("ativa", "ativo", "disponivel"):
        if campo in dados:
            dados[campo] = bool(dados[campo])
    return cls(**dados)


class UsuarioRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.c = conn

    def criar(self, nome, email, senha_hash, perfil, unidade_id, criado_em) -> Usuario:
        cur = self.c.execute(
            "INSERT INTO usuarios (nome,email,senha_hash,perfil,unidade_id,criado_em) VALUES (?,?,?,?,?,?)",
            (nome, email, senha_hash, perfil, unidade_id, criado_em))
        return self.por_id(cur.lastrowid)

    def por_id(self, uid: int) -> Optional[Usuario]:
        return _build(Usuario, self.c.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone())

    def por_email(self, email: str) -> Optional[Usuario]:
        return _build(Usuario, self.c.execute("SELECT * FROM usuarios WHERE email=?", (email,)).fetchone())

    def listar(self, limit: int, offset: int):
        total = self.c.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
        rows = self.c.execute("SELECT * FROM usuarios ORDER BY id LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [_build(Usuario, r) for r in rows], total

    def anonimizar(self, uid: int, email_anonimo: str, senha_hash: str):
        self.c.execute("UPDATE usuarios SET nome='Usuário anonimizado', email=?, senha_hash=?, ativo=0 WHERE id=?",
                       (email_anonimo, senha_hash, uid))


class ConsentimentoRepository:
    def __init__(self, conn):
        self.c = conn

    def registrar(self, usuario_id: int, concedido: bool, criado_em: str):
        self.c.execute("INSERT INTO consentimentos (usuario_id,finalidade,concedido,criado_em) VALUES (?,?,?,?)",
                       (usuario_id, "FIDELIDADE", int(concedido), criado_em))

    def vigente(self, usuario_id: int) -> bool:
        row = self.c.execute(
            "SELECT concedido FROM consentimentos WHERE usuario_id=? AND finalidade='FIDELIDADE' ORDER BY id DESC LIMIT 1",
            (usuario_id,)).fetchone()
        return bool(row["concedido"]) if row else False


class UnidadeRepository:
    def __init__(self, conn):
        self.c = conn

    def criar(self, nome, cidade, uf, criado_em) -> Unidade:
        cur = self.c.execute("INSERT INTO unidades (nome,cidade,uf,criado_em) VALUES (?,?,?,?)", (nome, cidade, uf, criado_em))
        return self.por_id(cur.lastrowid)

    def por_id(self, uid) -> Optional[Unidade]:
        return _build(Unidade, self.c.execute("SELECT * FROM unidades WHERE id=?", (uid,)).fetchone())

    def listar(self, limit, offset, somente_ativas=False):
        where = "WHERE ativa=1" if somente_ativas else ""
        total = self.c.execute(f"SELECT COUNT(*) FROM unidades {where}").fetchone()[0]
        rows = self.c.execute(f"SELECT * FROM unidades {where} ORDER BY id LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [_build(Unidade, r) for r in rows], total

    def atualizar(self, uid, nome, ativa):
        self.c.execute("UPDATE unidades SET nome=?, ativa=? WHERE id=?", (nome, int(ativa), uid))


class ProdutoRepository:
    def __init__(self, conn):
        self.c = conn

    def criar(self, nome, descricao, preco_base_centavos, criado_em) -> Produto:
        cur = self.c.execute("INSERT INTO produtos (nome,descricao,preco_base_centavos,criado_em) VALUES (?,?,?,?)",
                             (nome, descricao, preco_base_centavos, criado_em))
        return self.por_id(cur.lastrowid)

    def por_id(self, pid) -> Optional[Produto]:
        return _build(Produto, self.c.execute("SELECT * FROM produtos WHERE id=?", (pid,)).fetchone())

    def listar(self, limit, offset):
        total = self.c.execute("SELECT COUNT(*) FROM produtos WHERE ativo=1").fetchone()[0]
        rows = self.c.execute("SELECT * FROM produtos WHERE ativo=1 ORDER BY id LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [_build(Produto, r) for r in rows], total

    def definir_item_cardapio(self, unidade_id, produto_id, preco_centavos, disponivel):
        self.c.execute(
            "INSERT INTO cardapio_unidade (unidade_id,produto_id,preco_centavos,disponivel) VALUES (?,?,?,?) "
            "ON CONFLICT(unidade_id,produto_id) DO UPDATE SET preco_centavos=excluded.preco_centavos, disponivel=excluded.disponivel",
            (unidade_id, produto_id, preco_centavos, int(disponivel)))

    def item_cardapio(self, unidade_id, produto_id) -> Optional[ItemCardapio]:
        return _build(ItemCardapio, self.c.execute(
            "SELECT * FROM cardapio_unidade WHERE unidade_id=? AND produto_id=?", (unidade_id, produto_id)).fetchone())

    def cardapio(self, unidade_id, limit, offset):
        total = self.c.execute(
            "SELECT COUNT(*) FROM cardapio_unidade cu JOIN produtos p ON p.id=cu.produto_id WHERE cu.unidade_id=? AND p.ativo=1",
            (unidade_id,)).fetchone()[0]
        rows = self.c.execute(
            "SELECT p.id AS produto_id, p.nome, p.descricao, cu.preco_centavos, cu.disponivel, COALESCE(e.quantidade,0) AS saldo "
            "FROM cardapio_unidade cu JOIN produtos p ON p.id=cu.produto_id "
            "LEFT JOIN estoque e ON e.unidade_id=cu.unidade_id AND e.produto_id=cu.produto_id "
            "WHERE cu.unidade_id=? AND p.ativo=1 ORDER BY p.id LIMIT ? OFFSET ?", (unidade_id, limit, offset)).fetchall()
        return [dict(r) for r in rows], total


class EstoqueRepository:
    def __init__(self, conn):
        self.c = conn

    def saldo(self, unidade_id, produto_id) -> int:
        row = self.c.execute("SELECT quantidade FROM estoque WHERE unidade_id=? AND produto_id=?", (unidade_id, produto_id)).fetchone()
        return row["quantidade"] if row else 0

    def entrada(self, unidade_id, produto_id, quantidade):
        self.c.execute(
            "INSERT INTO estoque (unidade_id,produto_id,quantidade) VALUES (?,?,?) "
            "ON CONFLICT(unidade_id,produto_id) DO UPDATE SET quantidade=quantidade+excluded.quantidade",
            (unidade_id, produto_id, quantidade))

    def saida_condicional(self, unidade_id, produto_id, quantidade) -> bool:
        """Baixa atômica: só ocorre se houver saldo suficiente (evita saldo negativo)."""
        cur = self.c.execute(
            "UPDATE estoque SET quantidade=quantidade-? WHERE unidade_id=? AND produto_id=? AND quantidade>=?",
            (quantidade, unidade_id, produto_id, quantidade))
        return cur.rowcount == 1

    def registrar_movimento(self, unidade_id, produto_id, tipo, quantidade, motivo, pedido_id, usuario_id, criado_em):
        self.c.execute(
            "INSERT INTO estoque_movimentos (unidade_id,produto_id,tipo,quantidade,motivo,pedido_id,usuario_id,criado_em) VALUES (?,?,?,?,?,?,?,?)",
            (unidade_id, produto_id, tipo, quantidade, motivo, pedido_id, usuario_id, criado_em))

    def listar_saldos(self, unidade_id, limit, offset):
        total = self.c.execute("SELECT COUNT(*) FROM estoque WHERE unidade_id=?", (unidade_id,)).fetchone()[0]
        rows = self.c.execute(
            "SELECT e.unidade_id, e.produto_id, p.nome AS produto, e.quantidade FROM estoque e JOIN produtos p ON p.id=e.produto_id "
            "WHERE e.unidade_id=? ORDER BY e.produto_id LIMIT ? OFFSET ?", (unidade_id, limit, offset)).fetchall()
        return [dict(r) for r in rows], total

    def listar_movimentos(self, unidade_id, produto_id, limit, offset):
        where, params = "WHERE unidade_id=?", [unidade_id]
        if produto_id:
            where += " AND produto_id=?"
            params.append(produto_id)
        total = self.c.execute(f"SELECT COUNT(*) FROM estoque_movimentos {where}", params).fetchone()[0]
        rows = self.c.execute(f"SELECT * FROM estoque_movimentos {where} ORDER BY id DESC LIMIT ? OFFSET ?", params + [limit, offset]).fetchall()
        return [dict(r) for r in rows], total


class PromocaoRepository:
    def __init__(self, conn):
        self.c = conn

    def criar(self, codigo, descricao, percentual, minimo, valido_ate, criado_em) -> Promocao:
        cur = self.c.execute(
            "INSERT INTO promocoes (codigo,descricao,percentual,valor_minimo_centavos,valido_ate,criado_em) VALUES (?,?,?,?,?,?)",
            (codigo, descricao, percentual, minimo, valido_ate, criado_em))
        return self.por_id(cur.lastrowid)

    def por_id(self, pid):
        return _build(Promocao, self.c.execute("SELECT * FROM promocoes WHERE id=?", (pid,)).fetchone())

    def por_codigo(self, codigo):
        return _build(Promocao, self.c.execute("SELECT * FROM promocoes WHERE codigo=?", (codigo,)).fetchone())

    def listar(self, limit, offset, somente_ativas):
        where = "WHERE ativa=1" if somente_ativas else ""
        total = self.c.execute(f"SELECT COUNT(*) FROM promocoes {where}").fetchone()[0]
        rows = self.c.execute(f"SELECT * FROM promocoes {where} ORDER BY id LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [_build(Promocao, r) for r in rows], total

    def definir_ativa(self, pid, ativa):
        self.c.execute("UPDATE promocoes SET ativa=? WHERE id=?", (int(ativa), pid))


class PedidoRepository:
    def __init__(self, conn):
        self.c = conn

    def criar(self, p: Pedido) -> Pedido:
        cur = self.c.execute(
            "INSERT INTO pedidos (cliente_id,unidade_id,canal_pedido,status,subtotal_centavos,desconto_centavos,total_centavos,"
            "promocao_id,forma_pagamento,criado_em,atualizado_em) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (p.cliente_id, p.unidade_id, p.canal_pedido, p.status, p.subtotal_centavos, p.desconto_centavos,
             p.total_centavos, p.promocao_id, p.forma_pagamento, p.criado_em, p.atualizado_em))
        p.id = cur.lastrowid
        for item in p.itens:
            self.c.execute("INSERT INTO pedido_itens (pedido_id,produto_id,quantidade,preco_unitario_centavos) VALUES (?,?,?,?)",
                           (p.id, item.produto_id, item.quantidade, item.preco_unitario_centavos))
        return self.por_id(p.id)

    def por_id(self, pid) -> Optional[Pedido]:
        row = self.c.execute("SELECT * FROM pedidos WHERE id=?", (pid,)).fetchone()
        if row is None:
            return None
        pedido = _build(Pedido, row)
        itens = self.c.execute("SELECT * FROM pedido_itens WHERE pedido_id=? ORDER BY id", (pid,)).fetchall()
        pedido.itens = [_build(ItemPedido, i) for i in itens]
        return pedido

    def atualizar_status(self, pid, status, atualizado_em):
        self.c.execute("UPDATE pedidos SET status=?, atualizado_em=? WHERE id=?", (status, atualizado_em, pid))

    def listar(self, filtros: dict, limit: int, offset: int):
        where, params = [], []
        for coluna, chave in (("canal_pedido", "canal"), ("status", "status"), ("unidade_id", "unidade_id"), ("cliente_id", "cliente_id")):
            if filtros.get(chave) is not None:
                where.append(f"{coluna}=?")
                params.append(filtros[chave])
        clausula = ("WHERE " + " AND ".join(where)) if where else ""
        total = self.c.execute(f"SELECT COUNT(*) FROM pedidos {clausula}", params).fetchone()[0]
        ids = self.c.execute(f"SELECT id FROM pedidos {clausula} ORDER BY id DESC LIMIT ? OFFSET ?", params + [limit, offset]).fetchall()
        return [self.por_id(r["id"]) for r in ids], total


class PagamentoRepository:
    def __init__(self, conn):
        self.c = conn

    def criar(self, pedido_id, chave, metodo, status, valor, enviado, recebido, mensagem, criado_em) -> dict:
        cur = self.c.execute(
            "INSERT INTO pagamentos (pedido_id,idempotency_key,metodo,status,valor_centavos,payload_enviado,payload_recebido,mensagem,criado_em) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (pedido_id, chave, metodo, status, valor, json.dumps(enviado), json.dumps(recebido) if recebido else None, mensagem, criado_em))
        return self.por_id(cur.lastrowid)

    def _fmt(self, row):
        if row is None:
            return None
        d = dict(row)
        d["payload_enviado"] = json.loads(d["payload_enviado"])
        d["payload_recebido"] = json.loads(d["payload_recebido"]) if d["payload_recebido"] else None
        return d

    def por_id(self, pid):
        return self._fmt(self.c.execute("SELECT * FROM pagamentos WHERE id=?", (pid,)).fetchone())

    def por_chave(self, chave):
        return self._fmt(self.c.execute("SELECT * FROM pagamentos WHERE idempotency_key=?", (chave,)).fetchone())

    def do_pedido(self, pedido_id):
        rows = self.c.execute("SELECT * FROM pagamentos WHERE pedido_id=? ORDER BY id", (pedido_id,)).fetchall()
        return [self._fmt(r) for r in rows]


class FidelidadeRepository:
    def __init__(self, conn):
        self.c = conn

    def registrar(self, cliente_id, tipo, pontos, pedido_id, descricao, criado_em):
        self.c.execute("INSERT INTO fidelidade_movimentos (cliente_id,tipo,pontos,pedido_id,descricao,criado_em) VALUES (?,?,?,?,?,?)",
                       (cliente_id, tipo, pontos, pedido_id, descricao, criado_em))

    def saldo(self, cliente_id) -> int:
        row = self.c.execute(
            "SELECT COALESCE(SUM(CASE tipo WHEN 'ACUMULO' THEN pontos ELSE -pontos END),0) AS saldo FROM fidelidade_movimentos WHERE cliente_id=?",
            (cliente_id,)).fetchone()
        return row["saldo"]

    def historico(self, cliente_id, limit, offset):
        total = self.c.execute("SELECT COUNT(*) FROM fidelidade_movimentos WHERE cliente_id=?", (cliente_id,)).fetchone()[0]
        rows = self.c.execute("SELECT * FROM fidelidade_movimentos WHERE cliente_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
                              (cliente_id, limit, offset)).fetchall()
        return [dict(r) for r in rows], total


class AuditoriaRepository:
    def __init__(self, conn):
        self.c = conn

    def registrar(self, usuario_id, perfil, acao, entidade, entidade_id, detalhes, request_id, criado_em):
        self.c.execute(
            "INSERT INTO auditoria (usuario_id,perfil,acao,entidade,entidade_id,detalhes,request_id,criado_em) VALUES (?,?,?,?,?,?,?,?)",
            (usuario_id, perfil, acao, entidade, None if entidade_id is None else str(entidade_id),
             json.dumps(detalhes, ensure_ascii=False) if detalhes else None, request_id, criado_em))

    def listar(self, acao, entidade, entidade_id, limit, offset):
        where, params = [], []
        for coluna, valor in (("acao", acao), ("entidade", entidade), ("entidade_id", entidade_id)):
            if valor:
                where.append(f"{coluna}=?")
                params.append(str(valor))
        clausula = ("WHERE " + " AND ".join(where)) if where else ""
        total = self.c.execute(f"SELECT COUNT(*) FROM auditoria {clausula}", params).fetchone()[0]
        rows = self.c.execute(f"SELECT * FROM auditoria {clausula} ORDER BY id DESC LIMIT ? OFFSET ?", params + [limit, offset]).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["detalhes"] = json.loads(d["detalhes"]) if d["detalhes"] else None
            out.append(d)
        return out, total
