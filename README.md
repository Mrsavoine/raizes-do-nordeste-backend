# Raízes do Nordeste — Back-End

API REST do **Projeto Multidisciplinar (trilha Back-End)** — Análise e Desenvolvimento de Sistemas, 2026.
Estudo de caso: rede de lanchonetes nordestinas em expansão, com pedidos em vários canais (APP, TOTEM, BALCAO, PICKUP, WEB), estoque por unidade, pagamento externo **simulado**, fidelização com consentimento (LGPD), promoções e auditoria.

> **Identificação acadêmica:** aluno: `[NOME COMPLETO]` · RU: `[RU]` · polo: `[POLO]` · semestre: `[SEMESTRE]` · professora: Prof. Me. Luciane Yanase Kanashiro. *(preencher antes da entrega)*
> **Repositório público:** `[URL DO REPOSITÓRIO — preencher após publicar]`

## Decisão de tecnologia (desvio justificado)
O prompt do projeto preferia Java/Spring Boot. O ambiente em que este trabalho foi construído **não tinha Maven nem acesso à internet**, o que impede baixar dependências, compilar e **executar testes de verdade**. Para entregar um sistema comprovadamente executado, foi usado **Python 3.12 + Flask + SQLite**, mantendo a mesma arquitetura em camadas (Domain, Application, Infrastructure, API), JWT, migrations versionadas, OpenAPI e testes. Os conceitos mapeiam 1:1 para Spring (Controller → API, Service → Application, Repository → Infrastructure, Entity → Domain).

## Arquitetura
```
app/
  domain/          entidades, enums, máquina de estados do pedido, regras (promoção, pontos), erros
  application/     casos de uso (services), validação de entrada, transações e auditoria
  infrastructure/  SQLite, migrations, repositórios, JWT/scrypt, gateway de pagamento mock, seed
  api/             controllers REST, registro de endpoints, serializers, OpenAPI, tratamento de erros
database/migrations/   V1__schema_inicial.sql
tests/                 40 testes automatizados (unittest)
postman/               coleção + ambiente
scripts/               migrate, seed, diagramas, coleção, execução da coleção, docs
docs/                  diagramas, DER, evidências, API_ENDPOINTS.md
```
Dependências: API → Application → Domain; Infrastructure implementa persistência e integrações usadas pela Application.

## Pré-requisitos
- Python 3.12+ (testado com 3.12) e `pip`. Nenhum banco externo (SQLite embutido).
- Opcional: Graphviz (`dot`) e matplotlib para regenerar diagramas.

## Instalação e configuração
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                    # edite JWT_SECRET (mín. 32 caracteres)
```
Variáveis (`.env.example`): `JWT_SECRET`, `JWT_EXPIRES_SECONDS`, `DATABASE_PATH`, `HOST`, `PORT`, `SEED_ON_START`, `MOCK_PAYMENT_ALLOW_SIMULATION`.

## Banco de dados, migrations e seed
```bash
python -m scripts.migrate     # aplica database/migrations/V*.sql (controle em schema_migrations)
python -m scripts.seed        # dados de demonstração (idempotente)
```
Com `SEED_ON_START=true`, `python run.py` já executa migrations e seed na primeira subida.

**Usuários de demonstração (apenas ambiente local):**

| Perfil | E-mail | Senha |
|---|---|---|
| ADMIN | admin@raizes.example | Admin@123 |
| GERENTE (unidade 1) | gerente@raizes.example | Gerente@123 |
| ATENDENTE (unidade 1) | atendente@raizes.example | Atendente@123 |
| COZINHA (unidade 1) | cozinha@raizes.example | Cozinha@123 |
| CLIENTE | cliente@raizes.example / cliente2@raizes.example | Cliente@123 |

Seed: 2 unidades, 4 produtos, cardápio e estoque (40 un.) na unidade 1, 5 un. do produto 1 na unidade 2, promoção `RAIZES10`.

## Executar
```bash
python run.py        # http://localhost:8080
```
- **Swagger UI:** http://localhost:8080/docs (carrega a UI via CDN jsDelivr; requer internet no navegador)
- **OpenAPI JSON:** http://localhost:8080/openapi.json (gerado do código; teste garante que toda rota está documentada)
- **Saúde:** `GET /health`
- Docker (arquivos fornecidos, **não executados** no ambiente de construção): `JWT_SECRET=... docker compose up --build`

## Fluxo principal (MVP)
Pedido → Pagamento mock → Atualização de status.
```bash
TOKEN=$(curl -s localhost:8080/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"cliente@raizes.example","senha":"Cliente@123"}' | python -c "import sys,json;print(json.load(sys.stdin)['accessToken'])")
curl -s localhost:8080/pedidos -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"canalPedido":"TOTEM","unidadeId":1,"itens":[{"produtoId":1,"quantidade":2}],"formaPagamento":"MOCK"}'
curl -s localhost:8080/pagamentos -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: minha-chave-0001' -d '{"pedidoId":1,"simulacao":"APROVADO"}'
```

## Testes
```bash
python -m unittest discover -s tests -t . -v      # 40 testes automatizados
python -m scripts.run_collection                   # executa a coleção Postman contra a API real (57 verificações)
```
- **Postman:** importe `postman/raizes-do-nordeste.postman_collection.json` e `postman/local.postman_environment.json`; rode as pastas na ordem (Auth → Cardápio → Pedidos → Pagamento → Estoque → Fidelidade → Auditoria → Erros) com **banco recém-criado e seed aplicado**.
- Evidências reais de execução: `docs/evidencias/`. O `run_collection` é um executor próprio (subconjunto do JS da coleção); **não foi usado Newman**.

## Endpoints
Resumo por recurso: `/auth`, `/usuarios`, `/unidades`, `/produtos`, `/estoque`, `/pedidos`, `/pagamentos`, `/fidelidade`, `/promocoes`, `/auditoria`. Detalhes completos em [`docs/API_ENDPOINTS.md`](docs/API_ENDPOINTS.md) e no Swagger.

## Segurança e LGPD (resumo)
Senhas com scrypt; JWT HS256 com expiração; perfis aplicados por endpoint; respostas sem `senha_hash`; consentimento de fidelidade registrado e revogável; anonimização de conta (`DELETE /usuarios/me`); auditoria de ações sensíveis e de consultas a dados de usuários; erros sem vazar detalhes internos.

## Limitações conhecidas
Sem refresh/logout de token; sem estorno real de pagamento ao cancelar pedido já pago (registrado como "NAO_IMPLEMENTADO" na auditoria); promoções apenas percentuais, uma por pedido, sem segmentação por idade/perfil; pontos acumulam no pagamento aprovado; SQLite não é indicado para múltiplas instâncias (para escalar, migrar para PostgreSQL e adicionar cache/fila); sem rate limiting; relatórios para a matriz não implementados (apenas auditoria e consultas filtradas); Docker não testado.

## Referências
Documentos oficiais da disciplina (Estudo de Caso e Roteiro Back-End 2026); documentação oficial de Flask, PyJWT, Werkzeug, SQLite e OpenAPI 3.0; Lei nº 13.709/2018 (LGPD).
