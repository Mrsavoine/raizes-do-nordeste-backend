# Raízes do Nordeste — Back-End

API REST do **Projeto Multidisciplinar (trilha Back-End)** do curso de Análise e Desenvolvimento de Sistemas, 2026. O estudo de caso é a Rede Raízes do Nordeste, uma rede fictícia de lanchonetes nordestinas em expansão, que vende por vários canais e precisa de padronização, rastreabilidade e controle por unidade.

## O problema que o projeto resolve
O cliente compra pelo aplicativo, totem, balcão, retirada ou web, e espera a mesma experiência em todos. A matriz precisa garantir que as regras de negócio sejam únicas, que o estoque de cada unidade seja respeitado e que ações sensíveis (cancelamentos, descontos, ajustes) possam ser auditadas, protegendo os dados pessoais.

## Fluxo principal (MVP)
**Pedido → Pagamento mock → Atualização de status**
1. O cliente (ou o atendente em seu nome) cria o pedido com `canalPedido` obrigatório.
2. O servidor valida unidade, cardápio e estoque, calcula os valores (valores enviados pelo cliente são ignorados) e baixa o estoque de forma atômica.
3. O pagamento é solicitado a um gateway simulado, que responde aprovado, recusado ou falha.
4. Cozinha e atendente conduzem o pedido até ENTREGUE, ou o pedido é cancelado.

## Funcionalidades implementadas
| Área | O que existe |
|---|---|
| Autenticação | Cadastro de cliente com aceite da política de privacidade, login, JWT HS256 com expiração, senha com scrypt |
| Autorização | 5 perfis: CLIENTE, ATENDENTE, COZINHA, GERENTE, ADMIN; escopo por unidade para a equipe |
| Unidades e cardápio | Cadastro e ativação de unidades, catálogo global, preço e disponibilidade por unidade |
| Pedidos | Criação, consulta, filtro por canal/status/unidade com paginação, máquina de estados, cancelamento com devolução de estoque |
| Estoque | Saldo por unidade, entrada e saída manual, movimentações rastreáveis, baixa condicional que impede saldo negativo |
| Pagamento mock | Aprovação, recusa e falha simuladas, registro dos payloads enviado e recebido, cabeçalho `Idempotency-Key`, nova tentativa após falha |
| Fidelidade | Consentimento revogável, 1 ponto por real pago, saldo, histórico, resgate simples |
| Promoções | Desconto percentual com valor mínimo e validade, uma por pedido |
| Auditoria | Usuário, perfil, ação, entidade, `requestId` e horário UTC |
| LGPD | Minimização, consentimento, anonimização de conta (`DELETE /usuarios/me`), consultas a dados de usuários auditadas |
| Contrato | OpenAPI 3.0.3 gerado do código, Swagger UI em `/docs`, erro padronizado `{error, message, details, timestamp, path, requestId}` |

## Arquitetura
Camadas com dependência em um só sentido: **API → Application → Domain**, com **Infrastructure** implementando persistência e integrações.
- `app/domain` — entidades, enums, máquina de estados, regras de promoção e pontos, erros. Não importa Flask, SQLite nem JWT.
- `app/application` — casos de uso, validação de entrada, transações e auditoria.
- `app/infrastructure` — repositórios SQL parametrizados, migrations, hash e JWT, gateway mock, seed.
- `app/api` — controllers REST, registro de endpoints, serializers, OpenAPI e tratamento central de erros.

Decisões de projeto:
- O registro único de endpoints gera a rota e o OpenAPI a partir da mesma declaração, e um teste garante que nenhuma rota fica sem documentação.
- Os valores monetários são guardados em centavos inteiros.
- A baixa de estoque é um `UPDATE` condicional dentro de `BEGIN IMMEDIATE`, validada por um teste com 10 requisições simultâneas.
- O pagamento é desacoplado do pedido e a auditoria não tem chaves estrangeiras, para sobreviver à anonimização.

## Tecnologias
Python 3.12 · Flask 3.1.3 · SQLite 3 (migrations SQL versionadas) · PyJWT 2.7.0 · Werkzeug 3.1.9 (scrypt) · OpenAPI 3.0.3 · unittest · Postman v2.1 · Graphviz e matplotlib (diagramas).

> **Por que não Java/Spring Boot?** O ambiente de construção não tinha Maven nem internet, o que impedia compilar e executar testes. Por isso foi usada uma stack executável, mantendo a mesma arquitetura, os mesmos contratos e as mesmas regras.

## Qualidade e testes
- **40 testes automatizados**, todos aprovados. Cobrem login, 401/403/404/409/422/502, estoque insuficiente, concorrência, idempotência, fidelidade, promoções, anonimização e consistência entre rotas e OpenAPI.
- **Coleção Postman** com 28 requisições, executada contra a API real: 57 de 57 verificações aprovadas.
- Evidências em `docs/evidencias/`. A coleção foi executada por `scripts/run_collection.py`, que interpreta o subconjunto de JavaScript da coleção. Não foi usado o Newman.

## Início rápido
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # defina JWT_SECRET (mínimo 32 caracteres)
python run.py               # http://localhost:8080 · Swagger em /docs

Usuários de demonstração (apenas ambiente local) estão no README. Execute os testes com `python -m unittest discover -s tests -t . -v`.

## Estrutura do repositório
app/ (domain, application, infrastructure, api) · database/migrations/ · tests/ · postman/ · scripts/ · docs/ (diagramas, DER, evidências, API_ENDPOINTS.md) · Dockerfile · docker-compose.yml · .env.example · CHANGELOG.md ·