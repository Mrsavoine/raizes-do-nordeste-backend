import os
import tempfile
import unittest

os.environ.setdefault("JWT_SECRET", "segredo-de-teste-com-mais-de-trinta-e-dois-caracteres")

from app.api import create_app  # noqa: E402
from app.config import Settings  # noqa: E402
from app.infrastructure.db import connect  # noqa: E402
from app.infrastructure.seed import aplicar_seed  # noqa: E402

SENHAS = {"admin": "Admin@123", "gerente": "Gerente@123", "atendente": "Atendente@123", "cozinha": "Cozinha@123", "cliente": "Cliente@123", "cliente2": "Cliente@123"}


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._dir.name, "teste.db")
        settings = Settings(self.db_path, os.environ["JWT_SECRET"], 3600, True)
        self.app = create_app(settings)
        conn = connect(self.db_path)
        aplicar_seed(conn)
        conn.close()
        self.client = self.app.test_client()
        self._tokens = {}

    def tearDown(self):
        self._dir.cleanup()

    def db(self):
        return connect(self.db_path)

    def token(self, quem):
        if quem not in self._tokens:
            r = self.client.post("/auth/login", json={"email": f"{quem}@raizes.example", "senha": SENHAS[quem]})
            self.assertEqual(r.status_code, 200, r.get_json())
            self._tokens[quem] = r.get_json()["accessToken"]
        return {"Authorization": f"Bearer {self._tokens[quem]}"}

    def pedido(self, quem="cliente", canal="TOTEM", itens=None, **extra):
        corpo = {"canalPedido": canal, "unidadeId": 1, "itens": itens or [{"produtoId": 1, "quantidade": 2}], "formaPagamento": "MOCK", **extra}
        return self.client.post("/pedidos", json=corpo, headers=self.token(quem))

    def pagar(self, pedido_id, chave="chave-pagamento-01", quem="cliente", **corpo):
        return self.client.post("/pagamentos", json={"pedidoId": pedido_id, **corpo}, headers={**self.token(quem), "Idempotency-Key": chave})

    def saldo(self, unidade=1, produto=1):
        c = self.db()
        v = c.execute("SELECT quantidade FROM estoque WHERE unidade_id=? AND produto_id=?", (unidade, produto)).fetchone()[0]
        c.close()
        return v

    def assertErro(self, resp, status, codigo):
        corpo = resp.get_json()
        self.assertEqual(resp.status_code, status, corpo)
        self.assertEqual(corpo["error"], codigo)
        for chave in ("message", "details", "timestamp", "path", "requestId"):
            self.assertIn(chave, corpo)
