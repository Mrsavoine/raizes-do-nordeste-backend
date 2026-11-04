"""Gera DER (a partir do banco migrado), diagrama de classes (por introspecção das entidades),
casos de uso, arquitetura e sequência. Requer Graphviz (dot) e matplotlib. Uso: python -m scripts.gerar_diagramas"""
import dataclasses
import os
import sqlite3
import subprocess
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from app.domain import entities  # noqa: E402
from app.infrastructure.db import connect, run_migrations  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIAG, DER = os.path.join(RAIZ, "docs", "diagramas"), os.path.join(RAIZ, "docs", "der")
FONTE = "Helvetica"


def dot(nome, fonte, pasta=DIAG):
    os.makedirs(pasta, exist_ok=True)
    with open(os.path.join(pasta, nome + ".dot"), "w", encoding="utf-8") as f:
        f.write(fonte)
    for fmt in ("png", "svg"):
        extra = ["-Gdpi=170"] if fmt == "png" else []
        subprocess.run(["dot", f"-T{fmt}", *extra, os.path.join(pasta, nome + ".dot"), "-o", os.path.join(pasta, f"{nome}.{fmt}")], check=True)


def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def der():
    d = tempfile.mkdtemp()
    conn = connect(os.path.join(d, "der.db"))
    run_migrations(conn)
    tabelas = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='schema_migrations' ORDER BY name")]
    linhas = [f'digraph DER {{ rankdir=LR; nodesep=0.45; ranksep=1.2; splines=true; node [shape=plaintext fontname="{FONTE}" fontsize=10]; edge [fontname="{FONTE}" fontsize=9 color="#44546A"];']
    arestas = []
    for t in tabelas:
        cols = conn.execute(f"PRAGMA table_info({t})").fetchall()
        fks = {fk[3]: (fk[2], fk[4]) for fk in conn.execute(f"PRAGMA foreign_key_list({t})")}
        unicos = {c for idx in conn.execute(f"PRAGMA index_list({t})") if idx[2] for c in [i[2] for i in conn.execute(f"PRAGMA index_info({idx[1]})")]}
        html = f'<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="3"><TR><TD COLSPAN="3" BGCOLOR="#1F3864"><FONT COLOR="white"><B>{t}</B></FONT></TD></TR>'
        for c in cols:
            marca = ("PK" if c[5] else "") + (" FK" if c[1] in fks else "") + (" UQ" if c[1] in unicos and not c[5] else "")
            html += f'<TR><TD ALIGN="LEFT" PORT="{c[1]}"><B>{esc(marca.strip()) or "&#160;"}</B></TD><TD ALIGN="LEFT">{esc(c[1])}</TD><TD ALIGN="LEFT">{esc(c[2])}{" NN" if c[3] and not c[5] else ""}</TD></TR>'
        linhas.append(f'{t} [label=<{html}</TABLE>>];')
        for col, (pai, _) in fks.items():
            opcional = not [c for c in cols if c[1] == col][0][3]
            arestas.append(f'{t}:{col} -> {pai} [arrowtail=crow arrowhead=tee dir=both taillabel="N" headlabel="{"0..1" if opcional else "1"}"];')
    linhas += arestas + ["}"]
    dot("der_raizes_do_nordeste", "\n".join(linhas), DER)


def classes():
    linhas = [f'digraph Classes {{ rankdir=LR; nodesep=0.5; ranksep=0.9; node [shape=plaintext fontname="{FONTE}" fontsize=10]; edge [fontname="{FONTE}" fontsize=9 color="#44546A"];']
    metodos = {"Usuario": ["eh_equipe()"], "Promocao": ["calcular_desconto(subtotal, agora)"], "ItemPedido": ["subtotal_centavos (property)"],
               "Pedido": ["pode_transitar_para(novo)", "validar_transicao(novo)"]}
    for nome in ("Unidade", "Usuario", "Produto", "ItemCardapio", "Promocao", "ItemPedido", "Pedido"):
        cls = getattr(entities, nome)
        attrs = "".join(f'<TR><TD ALIGN="LEFT">+ {esc(f.name)}: {esc(str(f.type).replace("typing.", ""))}</TD></TR>' for f in dataclasses.fields(cls))
        mets = "".join(f'<TR><TD ALIGN="LEFT">+ {esc(m)}</TD></TR>' for m in metodos.get(nome, [])) or '<TR><TD> </TD></TR>'
        linhas.append(f'{nome} [label=<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0"><TR><TD BGCOLOR="#1F3864"><FONT COLOR="white"><B>{nome}</B></FONT></TD></TR>{attrs}{mets}</TABLE>>];')
    for nome in ("Perfil", "CanalPedido", "StatusPedido", "StatusPagamento", "TipoMovimento"):
        vals = "".join(f'<TR><TD ALIGN="LEFT">{m.value}</TD></TR>' for m in getattr(entities, nome))
        linhas.append(f'{nome} [label=<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0"><TR><TD BGCOLOR="#7F7F7F"><FONT COLOR="white"><I>«enum» {nome}</I></FONT></TD></TR>{vals}</TABLE>>];')
    rel = [("Pedido", "ItemPedido", "1", "1..*", "compõe", "diamond"), ("Pedido", "Promocao", "0..*", "0..1", "aplica", "none"),
           ("Pedido", "Usuario", "0..*", "1", "cliente", "none"), ("Pedido", "Unidade", "0..*", "1", "feito em", "none"),
           ("Usuario", "Unidade", "0..*", "0..1", "lotado em", "none"), ("ItemCardapio", "Unidade", "0..*", "1", "cardápio de", "none"),
           ("ItemCardapio", "Produto", "0..*", "1", "precifica", "none"), ("ItemPedido", "Produto", "0..*", "1", "refere", "none")]
    for a, b, ma, mb, rot, forma in rel:
        linhas.append(f'{a} -> {b} [label="{rot}" taillabel="{ma}" headlabel="{mb}" arrowhead=none arrowtail={forma} dir=back];' if forma == "diamond"
                      else f'{a} -> {b} [label="{rot}" taillabel="{ma}" headlabel="{mb}" arrowhead=vee];')
    for a, b in (("Usuario", "Perfil"), ("Pedido", "CanalPedido"), ("Pedido", "StatusPedido")):
        linhas.append(f'{a} -> {b} [style=dashed arrowhead=open label="usa"];')
    linhas.append("}")
    dot("diagrama_de_classes", "\n".join(linhas))


def casos_de_uso():
    atores = {"Cliente": "#DEEBF7", "Atendente": "#E2F0D9", "Cozinha": "#FFF2CC", "Gerente": "#FCE4D6", "Administrador": "#EAD1F5", "Gateway": "#D9D9D9"}
    ucs = {"UC01 Cadastrar-se / Autenticar": ["Cliente", "Atendente", "Cozinha", "Gerente", "Administrador"],
           "UC02 Consultar cardápio da unidade": ["Cliente", "Atendente"],
           "UC03 Realizar pedido (valida estoque)": ["Cliente", "Atendente"],
           "UC04 Solicitar pagamento": ["Cliente", "Atendente", "Gateway"],
           "UC05 Consultar/filtrar pedidos por canal": ["Cliente", "Atendente", "Gerente"],
           "UC06 Atualizar status (preparo, pronto, entregue)": ["Cozinha", "Atendente"],
           "UC07 Cancelar pedido": ["Cliente", "Atendente", "Gerente"],
           "UC08 Gerir estoque da unidade": ["Gerente", "Administrador"],
           "UC09 Gerir cardápio, produtos e promoções": ["Gerente", "Administrador"],
           "UC10 Participar da fidelidade (consentir, resgatar)": ["Cliente"],
           "UC11 Consultar auditoria": ["Gerente", "Administrador"],
           "UC12 Gerir unidades e usuários de equipe": ["Administrador"],
           "UC13 Exercer direito de anonimização (LGPD)": ["Cliente"]}
    l = [f'digraph UC {{ rankdir=LR; nodesep=0.25; ranksep=2.2; node [fontname="{FONTE}" fontsize=10]; edge [arrowhead=none color="#44546A"];',
         'subgraph cluster_sis { label="Sistema Back-End — Rede Raízes do Nordeste"; fontname="Helvetica"; style=rounded; color="#1F3864";']
    for i, uc in enumerate(ucs):
        l.append(f'uc{i} [label="{uc}" shape=ellipse style=filled fillcolor="#F2F2F2" width=3.1];')
    l.append("}")
    for a, cor in atores.items():
        l.append(f'{a} [label="«ator»\\n{"Gateway de Pagamento" if a == "Gateway" else a}" shape=box style="filled,rounded" fillcolor="{cor}"];')
    for i, (uc, quem) in enumerate(ucs.items()):
        for a in quem:
            l.append(f'{a} -> uc{i};')
    l.append("{rank=same; Cliente; Atendente; Cozinha; Gerente; Administrador; Gateway}}")
    # os atores ficam à esquerda; o gateway é ator externo
    dot("diagrama_de_casos_de_uso", "\n".join(l).replace("{rank=same; Cliente; Atendente; Cozinha; Gerente; Administrador; Gateway}", ""))


def arquitetura():
    l = [f'digraph Arq {{ rankdir=TB; nodesep=0.5; ranksep=0.7; node [shape=box style="filled,rounded" fontname="{FONTE}" fontsize=10 width=3.4]; edge [fontname="{FONTE}" fontsize=9 color="#1F3864"];',
         'canais [label="Canais: APP · TOTEM · BALCÃO · PICKUP · WEB" fillcolor="#D9D9D9"];',
         'api [label="API (app/api)\\nControllers REST · autenticação JWT/roles · contratos · OpenAPI · erro padrão" fillcolor="#DEEBF7"];',
         'app [label="Application (app/application)\\nCasos de uso · transações · validação · auditoria" fillcolor="#E2F0D9"];',
         'dom [label="Domain (app/domain)\\nEntidades · enums · máquina de estados · regras (promoção, pontos) · erros" fillcolor="#FFF2CC"];',
         'inf [label="Infrastructure (app/infrastructure)\\nRepositórios SQL · migrations · JWT/scrypt · gateway de pagamento mock" fillcolor="#FCE4D6"];',
         'db [label="SQLite (database/migrations)" shape=cylinder fillcolor="#EAD1F5"]; ext [label="Gateway de pagamento\\n(simulado)" fillcolor="#D9D9D9"];',
         'canais -> api [label="HTTP/JSON"]; api -> app [label="chama"]; app -> dom [label="usa"]; app -> inf [label="usa repositórios e gateway"];',
         'inf -> dom [label="constrói entidades" style=dashed]; inf -> db [label="SQL"]; inf -> ext [label="mock em processo" style=dashed]; }']
    dot("arquitetura_em_camadas", "\n".join(l))


def sequencia():
    fig, ax = plt.subplots(figsize=(13, 8.6))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 8.6)
    ax.axis("off")
    atores = ["Cliente\n(App/Totem/Web)", "API\n(Controller)", "PedidoService\n(Application)", "Repositórios\n(Infra/SQLite)", "Gateway\nmock"]
    xs = [1.2, 3.9, 6.6, 9.3, 11.9]
    for x, a in zip(xs, atores):
        ax.add_patch(FancyBboxPatch((x - 1.0, 7.75), 2.0, 0.7, boxstyle="round,pad=0.03", fc="#DEEBF7", ec="#1F3864"))
        ax.text(x, 8.1, a, ha="center", va="center", fontsize=8.5, fontweight="bold")
        ax.plot([x, x], [0.2, 7.75], color="#7F7F7F", lw=0.8, ls="--")
    msgs = [(0, 1, "POST /pedidos {canalPedido, unidadeId, itens} + JWT", 7.3, False),
            (1, 1, "valida JWT e perfil; valida JSON", 6.95, True),
            (1, 2, "criar_pedido(ctx, dados)", 6.6, False),
            (2, 3, "BEGIN IMMEDIATE · valida unidade/cardápio/saldo", 6.2, False),
            (2, 3, "INSERT pedido + itens · baixa condicional de estoque", 5.8, False),
            (3, 2, "pedido (AGUARDANDO_PAGAMENTO) · auditoria PEDIDO_CRIADO · COMMIT", 5.4, False),
            (1, 0, "201 Created {pedidoId, total, status}", 5.0, False),
            (0, 1, "POST /pagamentos + Idempotency-Key", 4.55, False),
            (1, 2, "solicitar_pagamento(chave, pedidoId)", 4.2, False),
            (2, 4, "processar(valor, método, simulação)", 3.8, False),
            (4, 2, "APROVADO | RECUSADO | (timeout → FALHA)", 3.4, False),
            (2, 3, "INSERT pagamento · UPDATE status (PAGO / PAGAMENTO_RECUSADO + estorno de estoque)", 3.0, False),
            (3, 2, "COMMIT · auditoria PAGAMENTO_*", 2.6, False),
            (1, 0, "201 {status, pedidoStatus, payload} · 502 se FALHA", 2.2, False),
            (0, 1, "PATCH /pedidos/{id}/status (Cozinha/Atendente)", 1.75, False),
            (2, 3, "valida transição · UPDATE status · auditoria PEDIDO_STATUS_ALTERADO", 1.3, False),
            (1, 0, "200 OK {status}", 0.85, False)]
    for de, para, texto, y, auto in msgs:
        x1, x2 = xs[de], xs[para]
        if auto:
            ax.annotate("", xy=(x1 + 0.05, y - 0.12), xytext=(x1 + 0.05, y + 0.12), arrowprops=dict(arrowstyle="->", color="#1F3864"))
            ax.text(x1 + 0.25, y, texto, fontsize=7.5, va="center")
            continue
        retorno = x2 < x1 and (de, para) in {(3, 2), (1, 0), (4, 2)}
        ax.annotate("", xy=(x2, y), xytext=(x1, y), arrowprops=dict(arrowstyle="->", color="#1F3864", ls="--" if retorno else "-"))
        ax.text((x1 + x2) / 2, y + 0.07, texto, fontsize=7.5, ha="center", va="bottom")
    fig.savefig(os.path.join(DIAG, "diagrama_de_sequencia.png"), dpi=170, bbox_inches="tight")
    fig.savefig(os.path.join(DIAG, "diagrama_de_sequencia.svg"), bbox_inches="tight")


if __name__ == "__main__":
    der()
    classes()
    casos_de_uso()
    arquitetura()
    sequencia()
    print("Diagramas gerados em docs/diagramas e docs/der")
