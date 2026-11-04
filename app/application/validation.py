"""Validação de entrada com acúmulo de problemas (resposta 422 lista todos os campos inválidos)."""
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum

from ..domain.errors import MalformedRequestError, ValidationError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def exigir_objeto_json(data) -> dict:
    if not isinstance(data, dict):
        raise MalformedRequestError("O corpo da requisição deve ser um objeto JSON válido.", code="JSON_INVALIDO")
    return data


def paginacao(args) -> tuple[int, int, int]:
    """Retorna (page, limit, offset). page começa em 1; limit entre 1 e 100."""
    v = Validador({"page": args.get("page", "1"), "limit": args.get("limit", "10")})
    page = v.inteiro_texto("page", minimo=1)
    limit = v.inteiro_texto("limit", minimo=1, maximo=100)
    v.concluir()
    return page, limit, (page - 1) * limit


class Validador:
    def __init__(self, dados: dict):
        self.dados = dados
        self.problemas: list[dict] = []

    def _falha(self, campo, problema):
        self.problemas.append({"field": campo, "issue": problema})

    def _presente(self, campo, obrigatorio):
        valor = self.dados.get(campo)
        if valor is None or (isinstance(valor, str) and valor.strip() == ""):
            if obrigatorio:
                self._falha(campo, "campo obrigatório")
            return None
        return valor

    def texto(self, campo, minimo=1, maximo=200, obrigatorio=True):
        valor = self._presente(campo, obrigatorio)
        if valor is None:
            return None
        if not isinstance(valor, str):
            self._falha(campo, "deve ser texto")
            return None
        valor = valor.strip()
        if not minimo <= len(valor) <= maximo:
            self._falha(campo, f"deve ter entre {minimo} e {maximo} caracteres")
            return None
        return valor

    def email(self, campo, obrigatorio=True):
        valor = self.texto(campo, 5, 120, obrigatorio)
        if valor is not None and not EMAIL_RE.match(valor):
            self._falha(campo, "formato de e-mail inválido")
            return None
        return valor.lower() if valor else None

    def senha(self, campo):
        valor = self._presente(campo, True)
        if valor is None:
            return None
        if not isinstance(valor, str) or len(valor) < 8 or len(valor) > 72 \
                or not re.search(r"[A-Za-z]", valor) or not re.search(r"\d", valor):
            self._falha(campo, "mínimo de 8 caracteres, com letras e números")
            return None
        return valor

    def inteiro(self, campo, minimo=None, maximo=None, obrigatorio=True):
        valor = self._presente(campo, obrigatorio)
        if valor is None:
            return None
        if isinstance(valor, bool) or not isinstance(valor, int):
            self._falha(campo, "deve ser um número inteiro")
            return None
        if minimo is not None and valor < minimo:
            self._falha(campo, f"deve ser maior ou igual a {minimo}")
            return None
        if maximo is not None and valor > maximo:
            self._falha(campo, f"deve ser menor ou igual a {maximo}")
            return None
        return valor

    def inteiro_texto(self, campo, minimo=None, maximo=None):
        valor = self.dados.get(campo)
        try:
            numero = int(str(valor))
        except ValueError:
            self._falha(campo, "deve ser um número inteiro")
            return None
        if minimo is not None and numero < minimo or maximo is not None and numero > maximo:
            self._falha(campo, f"fora do intervalo permitido ({minimo}..{maximo})")
            return None
        return numero

    def booleano(self, campo, obrigatorio=True):
        valor = self.dados.get(campo)
        if valor is None:
            if obrigatorio:
                self._falha(campo, "campo obrigatório")
            return None
        if not isinstance(valor, bool):
            self._falha(campo, "deve ser verdadeiro ou falso")
            return None
        return valor

    def enum(self, campo, tipo: type[Enum], obrigatorio=True):
        valor = self._presente(campo, obrigatorio)
        if valor is None:
            return None
        try:
            return tipo(str(valor).upper()) if isinstance(valor, str) else tipo(valor)
        except ValueError:
            self._falha(campo, "valor inválido. Aceitos: " + ", ".join(m.value for m in tipo))
            return None

    def dinheiro_centavos(self, campo, obrigatorio=True):
        valor = self._presente(campo, obrigatorio)
        if valor is None:
            return None
        if isinstance(valor, bool) or not isinstance(valor, (int, float, str)):
            self._falha(campo, "valor monetário inválido")
            return None
        try:
            decimal = Decimal(str(valor))
        except InvalidOperation:
            self._falha(campo, "valor monetário inválido")
            return None
        if decimal <= 0 or decimal != decimal.quantize(Decimal("0.01")) or decimal > Decimal("100000"):
            self._falha(campo, "deve ser maior que zero, com até 2 casas decimais")
            return None
        return int(decimal * 100)

    def data_iso(self, campo, obrigatorio=False):
        valor = self._presente(campo, obrigatorio)
        if valor is None:
            return None
        try:
            datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
            return str(valor)
        except ValueError:
            self._falha(campo, "data inválida (use ISO-8601)")
            return None

    def concluir(self):
        if self.problemas:
            raise ValidationError("Os dados enviados são inválidos.", self.problemas)
