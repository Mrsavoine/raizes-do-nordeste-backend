"""Dados de demonstração. As senhas abaixo são APENAS para ambiente local/avaliação; troque em qualquer implantação real."""
from ..domain.entities import Perfil
from .db import agora_iso, transaction
from .security import hash_senha

USUARIOS_DEMO = [
    ("Administrador Demo", "admin@raizes.example", "Admin@123", Perfil.ADMIN, None),
    ("Gerente Boa Viagem", "gerente@raizes.example", "Gerente@123", Perfil.GERENTE, 1),
    ("Atendente Balcão", "atendente@raizes.example", "Atendente@123", Perfil.ATENDENTE, 1),
    ("Cozinha Boa Viagem", "cozinha@raizes.example", "Cozinha@123", Perfil.COZINHA, 1),
    ("Cliente Demo", "cliente@raizes.example", "Cliente@123", Perfil.CLIENTE, None),
    ("Cliente Dois", "cliente2@raizes.example", "Cliente@123", Perfil.CLIENTE, None),
]
PRODUTOS_DEMO = [
    ("Tapioca de carne de sol", "Com queijo coalho", 1850),
    ("Cuscuz recheado", "Cuscuz com frango e requeijão", 2200),
    ("Bolo de macaxeira", "Fatia individual", 1200),
    ("Suco de caju", "Copo de 400 ml", 900),
]


def aplicar_seed(conn) -> bool:
    """Idempotente: não executa se já houver unidades cadastradas."""
    if conn.execute("SELECT COUNT(*) FROM unidades").fetchone()[0]:
        return False
    agora = agora_iso()
    with transaction(conn):
        conn.execute("INSERT INTO unidades (nome,cidade,uf,criado_em) VALUES ('Raízes Boa Viagem','Recife','PE',?)", (agora,))
        conn.execute("INSERT INTO unidades (nome,cidade,uf,criado_em) VALUES ('Raízes Pelourinho','Salvador','BA',?)", (agora,))
        for nome, email, senha, perfil, unidade in USUARIOS_DEMO:
            conn.execute("INSERT INTO usuarios (nome,email,senha_hash,perfil,unidade_id,criado_em) VALUES (?,?,?,?,?,?)",
                         (nome, email, hash_senha(senha), perfil.value, unidade, agora))
        for nome, desc, preco in PRODUTOS_DEMO:
            conn.execute("INSERT INTO produtos (nome,descricao,preco_base_centavos,criado_em) VALUES (?,?,?,?)", (nome, desc, preco, agora))
        for produto_id, (_, _, preco) in enumerate(PRODUTOS_DEMO, start=1):
            conn.execute("INSERT INTO cardapio_unidade (unidade_id,produto_id,preco_centavos,disponivel) VALUES (1,?,?,1)", (produto_id, preco))
            conn.execute("INSERT INTO estoque (unidade_id,produto_id,quantidade) VALUES (1,?,?)", (produto_id, 40))
            conn.execute("INSERT INTO estoque_movimentos (unidade_id,produto_id,tipo,quantidade,motivo,criado_em) VALUES (1,?,'ENTRADA',40,'SEED_INICIAL',?)",
                         (produto_id, agora))
        conn.execute("INSERT INTO cardapio_unidade (unidade_id,produto_id,preco_centavos,disponivel) VALUES (2,1,1990,1)")
        conn.execute("INSERT INTO estoque (unidade_id,produto_id,quantidade) VALUES (2,1,5)")
        conn.execute("INSERT INTO promocoes (codigo,descricao,percentual,valor_minimo_centavos,criado_em) VALUES ('RAIZES10','10% em pedidos acima de R$ 30',10,3000,?)", (agora,))
    return True
