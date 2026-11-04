-- Raízes do Nordeste — esquema inicial (SQLite 3). Valores monetários em centavos (INTEGER).
CREATE TABLE unidades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT    NOT NULL UNIQUE,
    cidade      TEXT    NOT NULL,
    uf          TEXT    NOT NULL CHECK (length(uf) = 2),
    ativa       INTEGER NOT NULL DEFAULT 1 CHECK (ativa IN (0, 1)),
    criado_em   TEXT    NOT NULL
);

CREATE TABLE usuarios (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT    NOT NULL,
    email       TEXT    NOT NULL UNIQUE,
    senha_hash  TEXT    NOT NULL,
    perfil      TEXT    NOT NULL CHECK (perfil IN ('CLIENTE','ATENDENTE','COZINHA','GERENTE','ADMIN')),
    unidade_id  INTEGER REFERENCES unidades(id),
    ativo       INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
    criado_em   TEXT    NOT NULL
);

CREATE TABLE consentimentos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  INTEGER NOT NULL REFERENCES usuarios(id),
    finalidade  TEXT    NOT NULL CHECK (finalidade IN ('FIDELIDADE')),
    concedido   INTEGER NOT NULL CHECK (concedido IN (0, 1)),
    criado_em   TEXT    NOT NULL
);

CREATE TABLE produtos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nome            TEXT    NOT NULL UNIQUE,
    descricao       TEXT,
    preco_base_centavos INTEGER NOT NULL CHECK (preco_base_centavos > 0),
    ativo           INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
    criado_em       TEXT    NOT NULL
);

CREATE TABLE cardapio_unidade (
    unidade_id      INTEGER NOT NULL REFERENCES unidades(id),
    produto_id      INTEGER NOT NULL REFERENCES produtos(id),
    preco_centavos  INTEGER NOT NULL CHECK (preco_centavos > 0),
    disponivel      INTEGER NOT NULL DEFAULT 1 CHECK (disponivel IN (0, 1)),
    PRIMARY KEY (unidade_id, produto_id)
);

CREATE TABLE estoque (
    unidade_id  INTEGER NOT NULL REFERENCES unidades(id),
    produto_id  INTEGER NOT NULL REFERENCES produtos(id),
    quantidade  INTEGER NOT NULL CHECK (quantidade >= 0),
    PRIMARY KEY (unidade_id, produto_id)
);

CREATE TABLE promocoes (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo                TEXT    NOT NULL UNIQUE,
    descricao             TEXT    NOT NULL,
    percentual            INTEGER NOT NULL CHECK (percentual BETWEEN 1 AND 100),
    valor_minimo_centavos INTEGER NOT NULL DEFAULT 0 CHECK (valor_minimo_centavos >= 0),
    ativa                 INTEGER NOT NULL DEFAULT 1 CHECK (ativa IN (0, 1)),
    valido_ate            TEXT,
    criado_em             TEXT    NOT NULL
);

CREATE TABLE pedidos (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id          INTEGER NOT NULL REFERENCES usuarios(id),
    unidade_id          INTEGER NOT NULL REFERENCES unidades(id),
    canal_pedido        TEXT    NOT NULL CHECK (canal_pedido IN ('APP','TOTEM','BALCAO','PICKUP','WEB')),
    status              TEXT    NOT NULL CHECK (status IN ('AGUARDANDO_PAGAMENTO','PAGO','EM_PREPARO','PRONTO','ENTREGUE','CANCELADO','PAGAMENTO_RECUSADO')),
    subtotal_centavos   INTEGER NOT NULL CHECK (subtotal_centavos >= 0),
    desconto_centavos   INTEGER NOT NULL DEFAULT 0 CHECK (desconto_centavos >= 0),
    total_centavos      INTEGER NOT NULL CHECK (total_centavos >= 0),
    promocao_id         INTEGER REFERENCES promocoes(id),
    forma_pagamento     TEXT    NOT NULL,
    criado_em           TEXT    NOT NULL,
    atualizado_em       TEXT    NOT NULL
);
CREATE INDEX idx_pedidos_canal   ON pedidos(canal_pedido);
CREATE INDEX idx_pedidos_status  ON pedidos(status);
CREATE INDEX idx_pedidos_unidade ON pedidos(unidade_id);
CREATE INDEX idx_pedidos_cliente ON pedidos(cliente_id);

CREATE TABLE pedido_itens (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id                INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
    produto_id               INTEGER NOT NULL REFERENCES produtos(id),
    quantidade               INTEGER NOT NULL CHECK (quantidade > 0),
    preco_unitario_centavos  INTEGER NOT NULL CHECK (preco_unitario_centavos > 0)
);
CREATE INDEX idx_itens_pedido ON pedido_itens(pedido_id);

CREATE TABLE estoque_movimentos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    unidade_id  INTEGER NOT NULL REFERENCES unidades(id),
    produto_id  INTEGER NOT NULL REFERENCES produtos(id),
    tipo        TEXT    NOT NULL CHECK (tipo IN ('ENTRADA','SAIDA')),
    quantidade  INTEGER NOT NULL CHECK (quantidade > 0),
    motivo      TEXT    NOT NULL,
    pedido_id   INTEGER REFERENCES pedidos(id),
    usuario_id  INTEGER REFERENCES usuarios(id),
    criado_em   TEXT    NOT NULL
);
CREATE INDEX idx_mov_unidade_produto ON estoque_movimentos(unidade_id, produto_id);

-- Pagamento desacoplado: referencia o pedido, mas guarda apenas o que foi enviado/recebido do gateway.
CREATE TABLE pagamentos (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id        INTEGER NOT NULL REFERENCES pedidos(id),
    idempotency_key  TEXT    NOT NULL UNIQUE,
    metodo           TEXT    NOT NULL,
    status           TEXT    NOT NULL CHECK (status IN ('APROVADO','RECUSADO','FALHA')),
    valor_centavos   INTEGER NOT NULL CHECK (valor_centavos >= 0),
    payload_enviado  TEXT    NOT NULL,
    payload_recebido TEXT,
    mensagem         TEXT,
    criado_em        TEXT    NOT NULL
);
CREATE INDEX idx_pagamentos_pedido ON pagamentos(pedido_id);

CREATE TABLE fidelidade_movimentos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id  INTEGER NOT NULL REFERENCES usuarios(id),
    tipo        TEXT    NOT NULL CHECK (tipo IN ('ACUMULO','RESGATE')),
    pontos      INTEGER NOT NULL CHECK (pontos > 0),
    pedido_id   INTEGER REFERENCES pedidos(id),
    descricao   TEXT    NOT NULL,
    criado_em   TEXT    NOT NULL
);
CREATE INDEX idx_fid_cliente ON fidelidade_movimentos(cliente_id);

CREATE TABLE auditoria (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  INTEGER,
    perfil      TEXT,
    acao        TEXT    NOT NULL,
    entidade    TEXT    NOT NULL,
    entidade_id TEXT,
    detalhes    TEXT,
    request_id  TEXT,
    criado_em   TEXT    NOT NULL
);
CREATE INDEX idx_auditoria_acao ON auditoria(acao);
