"""Executa a coleção Postman contra a API REAL (processo `python run.py` em banco temporário) e confere os testes.

Não substitui o Newman/Postman: interpreta apenas o subconjunto de JavaScript usado pela coleção gerada por
scripts/build_collection.py (status, igualdade de campos e captura de variáveis). Uso: python -m scripts.run_collection
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTA = os.environ.get("RUNNER_PORT", "8099")
BASE = f"http://127.0.0.1:{PORTA}"


def caminho_json(dados, expr):
    atual = dados
    for parte in re.findall(r"[^.\[\]]+|\[\d+\]", expr):
        atual = atual[int(parte[1:-1])] if parte.startswith("[") else atual[parte]
    return atual


def subst(texto, variaveis):
    texto = texto.replace("{{$guid}}", str(uuid.uuid4()))
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(variaveis[m.group(1)]), texto)


def achatar(itens):
    for it in itens:
        if "item" in it:
            yield from ((it["name"], sub) for sub in achatar(it["item"]))
        else:
            yield None, it


def main() -> int:
    tmp = tempfile.mkdtemp()
    env = {**os.environ, "DATABASE_PATH": os.path.join(tmp, "colecao.db"), "PORT": PORTA, "SEED_ON_START": "true",
           "JWT_SECRET": "segredo-do-runner-com-mais-de-trinta-e-dois-caracteres"}
    proc = subprocess.Popen([sys.executable, "run.py"], cwd=RAIZ, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(80):
            try:
                urllib.request.urlopen(BASE + "/health", timeout=1)
                break
            except Exception:
                time.sleep(0.25)
        else:
            print("API não iniciou")
            return 2
        with open(os.path.join(RAIZ, "postman", "raizes-do-nordeste.postman_collection.json"), encoding="utf-8") as f:
            colecao = json.load(f)
        variaveis, ok, total = {"baseUrl": BASE}, 0, 0
        for pasta in colecao["item"]:
            for it in pasta["item"]:
                req = it["request"]
                url = subst(req["url"]["raw"], variaveis)
                corpo = subst(req["body"]["raw"], variaveis).encode() if "body" in req else None
                headers = {h["key"]: subst(h["value"], variaveis) for h in req["header"]}
                try:
                    resp = urllib.request.urlopen(urllib.request.Request(url, data=corpo, headers=headers, method=req["method"]), timeout=15)
                    status, texto = resp.status, resp.read().decode()
                except urllib.error.HTTPError as erro:
                    status, texto = erro.code, erro.read().decode()
                dados = json.loads(texto) if texto else None
                for linha in it["event"][0]["script"]["exec"]:
                    m = re.search(r"have\.status\((\d+)\)", linha)
                    a = re.search(r"pm\.response\.json\(\)\.(.+?)\)\.to\.eql\((.+)\); \}\);$", linha)
                    v = re.search(r'collectionVariables\.set\("(\w+)", pm\.response\.json\(\)\.(.+)\);', linha)
                    if m:
                        total += 1
                        passou = status == int(m.group(1))
                        detalhe = f"HTTP {status}"
                    elif a:
                        total += 1
                        try:
                            real = caminho_json(dados, a.group(1))
                        except Exception:
                            real = "<ausente>"
                        passou, detalhe = real == json.loads(a.group(2)), f"{a.group(1)} = {real!r}"
                    elif v:
                        variaveis[v.group(1)] = caminho_json(dados, v.group(2))
                        continue
                    else:
                        continue
                    ok += passou
                    print(f"[{'PASS' if passou else 'FAIL'}] {pasta['name']} / {it['name']} — {detalhe}")
        print(f"\nResumo: {ok}/{total} verificações aprovadas")
        return 0 if ok == total else 1
    finally:
        proc.terminate()


if __name__ == "__main__":
    sys.exit(main())
