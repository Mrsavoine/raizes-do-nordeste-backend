# Changelog

## [1.0.0] — 2026-11-04
- API REST em camadas (Domain, Application, Infrastructure, API) com Flask e SQLite.
- Autenticação JWT, perfis (CLIENTE, ATENDENTE, COZINHA, GERENTE, ADMIN) e hash scrypt.
- Fluxo MVP: pedido → pagamento mock (idempotente) → atualização de status.
- Estoque por unidade com movimentação rastreável, fidelidade com consentimento, promoções e auditoria.
- OpenAPI gerado do código, coleção Postman, 40 testes automatizados, diagramas e documentação.
