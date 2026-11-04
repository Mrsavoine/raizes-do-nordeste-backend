# Endpoints da API

Gerado automaticamente a partir do código (`python -m scripts.gerar_docs_api`). Erro padrão em todas as falhas: `{error, message, details[], timestamp, path, requestId}`.

## Infra

### GET /health

- **Finalidade:** Verifica a disponibilidade da API e do banco.
- **Autenticação/perfis:** público
- **Sucesso:** 200

**Response 200**

```json
{
  "status": "UP",
  "database": "UP"
}
```

## Auth

### POST /auth/register

- **Finalidade:** Cadastra um cliente (perfil CLIENTE) com aceite da política de privacidade.
- **Autenticação/perfis:** público
- **Sucesso:** 201
- **Erros:** 409 `EMAIL_JA_CADASTRADO`; 422 `VALIDACAO_INVALIDA`

**Request**

```json
{
  "nome": "Maria Souza",
  "email": "maria@exemplo.com",
  "senha": "Senha@123",
  "aceitePoliticaPrivacidade": true
}
```

**Response 201**

```json
{
  "id": 3,
  "nome": "Maria Souza",
  "email": "maria@exemplo.com",
  "perfil": "CLIENTE",
  "unidadeId": null,
  "ativo": true,
  "criadoEm": "2026-11-04T12:00:00.000000Z"
}
```

### POST /auth/login

- **Finalidade:** Autentica o usuário e devolve um JWT Bearer.
- **Autenticação/perfis:** público
- **Sucesso:** 200
- **Erros:** 401 `CREDENCIAIS_INVALIDAS`; 422 `VALIDACAO_INVALIDA`

**Request**

```json
{
  "email": "cliente@raizes.example",
  "senha": "Cliente@123"
}
```

**Response 200**

```json
{
  "accessToken": "eyJhbGciOi...",
  "tokenType": "Bearer",
  "expiresIn": 3600,
  "user": {
    "id": 4,
    "nome": "Cliente Demo",
    "perfil": "CLIENTE"
  }
}
```

## Usuários

### GET /usuarios/me

- **Finalidade:** Consulta o próprio perfil (minimização: sem hash de senha).
- **Autenticação/perfis:** JWT — qualquer perfil autenticado
- **Sucesso:** 200
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`

**Response 200**

```json
{
  "id": 3,
  "nome": "Maria Souza",
  "email": "maria@exemplo.com",
  "perfil": "CLIENTE",
  "unidadeId": null,
  "ativo": true,
  "criadoEm": "2026-11-04T12:00:00.000000Z"
}
```

### DELETE /usuarios/me

- **Finalidade:** Anonimiza a própria conta (direito de eliminação, LGPD art. 18).
- **Autenticação/perfis:** JWT — qualquer perfil autenticado
- **Sucesso:** 204
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`

### GET /usuarios

- **Finalidade:** Lista usuários (auditada).
- **Autenticação/perfis:** JWT — ADMIN
- **Sucesso:** 200
- **Query:** `page` (integer) — Página (>=1). Padrão 1; `limit` (integer) — Itens por página (1-100). Padrão 10
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 403 `PERFIL_SEM_PERMISSAO`

**Response 200**

```json
{
  "items": [
    {
      "id": 3,
      "nome": "Maria Souza",
      "email": "maria@exemplo.com",
      "perfil": "CLIENTE",
      "unidadeId": null,
      "ativo": true,
      "criadoEm": "2026-11-04T12:00:00.000000Z"
    }
  ],
  "page": 1,
  "limit": 10,
  "total": 1
}
```

### POST /usuarios

- **Finalidade:** Cria usuário de equipe (ATENDENTE, COZINHA, GERENTE, ADMIN).
- **Autenticação/perfis:** JWT — ADMIN
- **Sucesso:** 201
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 403 `PERFIL_SEM_PERMISSAO`; 409 `EMAIL_JA_CADASTRADO`; 422 `VALIDACAO_INVALIDA`

**Request**

```json
{
  "nome": "Ana Cozinha",
  "email": "ana@raizes.example",
  "senha": "Cozinha@123",
  "perfil": "COZINHA",
  "unidadeId": 1
}
```

**Response 201**

```json
{
  "id": 3,
  "nome": "Maria Souza",
  "email": "maria@exemplo.com",
  "perfil": "COZINHA",
  "unidadeId": 1,
  "ativo": true,
  "criadoEm": "2026-11-04T12:00:00.000000Z"
}
```

### GET /usuarios/{uid}

- **Finalidade:** Consulta um usuário (gera registro de auditoria de acesso).
- **Autenticação/perfis:** JWT — ADMIN
- **Sucesso:** 200
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 403 `PERFIL_SEM_PERMISSAO`; 404 `USUARIO_NAO_ENCONTRADO`

**Response 200**

```json
{
  "id": 3,
  "nome": "Maria Souza",
  "email": "maria@exemplo.com",
  "perfil": "CLIENTE",
  "unidadeId": null,
  "ativo": true,
  "criadoEm": "2026-11-04T12:00:00.000000Z"
}
```

## Unidades

### GET /unidades

- **Finalidade:** Lista unidades ativas da rede.
- **Autenticação/perfis:** público
- **Sucesso:** 200
- **Query:** `page` (integer) — Página (>=1). Padrão 1; `limit` (integer) — Itens por página (1-100). Padrão 10

**Response 200**

```json
{
  "items": [
    {
      "id": 1,
      "nome": "Raízes Boa Viagem",
      "cidade": "Recife",
      "uf": "PE",
      "ativa": true
    }
  ],
  "page": 1,
  "limit": 10,
  "total": 1
}
```

### POST /unidades

- **Finalidade:** Cadastra uma unidade.
- **Autenticação/perfis:** JWT — ADMIN
- **Sucesso:** 201
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 403 `PERFIL_SEM_PERMISSAO`; 409 `UNIDADE_DUPLICADA`; 422 `VALIDACAO_INVALIDA`

**Request**

```json
{
  "nome": "Raízes Pelourinho",
  "cidade": "Salvador",
  "uf": "BA"
}
```

**Response 201**

```json
{
  "id": 2,
  "nome": "Raízes Pelourinho",
  "cidade": "Salvador",
  "uf": "BA",
  "ativa": true
}
```

### GET /unidades/{uid}

- **Finalidade:** Consulta uma unidade (informa se está ativa).
- **Autenticação/perfis:** público
- **Sucesso:** 200
- **Erros:** 404 `UNIDADE_NAO_ENCONTRADA`

**Response 200**

```json
{
  "id": 1,
  "nome": "Raízes Boa Viagem",
  "cidade": "Recife",
  "uf": "PE",
  "ativa": true
}
```

### PATCH /unidades/{uid}

- **Finalidade:** Atualiza nome ou situação (ativa) da unidade.
- **Autenticação/perfis:** JWT — ADMIN
- **Sucesso:** 200
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 403 `PERFIL_SEM_PERMISSAO`; 404 `UNIDADE_NAO_ENCONTRADA`; 422 `VALIDACAO_INVALIDA`

**Request**

```json
{
  "ativa": false
}
```

**Response 200**

```json
{
  "id": 1,
  "nome": "Raízes Boa Viagem",
  "cidade": "Recife",
  "uf": "PE",
  "ativa": false
}
```

## Cardápio

### GET /unidades/{uid}/cardapio

- **Finalidade:** Consulta o cardápio da unidade (preço local e disponibilidade).
- **Autenticação/perfis:** público
- **Sucesso:** 200
- **Query:** `page` (integer) — Página (>=1). Padrão 1; `limit` (integer) — Itens por página (1-100). Padrão 10
- **Erros:** 404 `UNIDADE_NAO_ENCONTRADA`

**Response 200**

```json
{
  "items": [
    {
      "produtoId": 1,
      "nome": "Tapioca de carne de sol",
      "descricao": "Com queijo coalho",
      "preco": 18.5,
      "disponivel": true,
      "saldoEstoque": 40
    }
  ],
  "page": 1,
  "limit": 10,
  "total": 1
}
```

### PUT /unidades/{unidadeId}/cardapio/{produtoId}

- **Finalidade:** Define preço e disponibilidade de um produto na unidade.
- **Autenticação/perfis:** JWT — GERENTE, ADMIN
- **Sucesso:** 200
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 403 `PERFIL_SEM_PERMISSAO`; 404 `UNIDADE_NAO_ENCONTRADA | PRODUTO_NAO_ENCONTRADO`; 422 `VALIDACAO_INVALIDA`

**Request**

```json
{
  "preco": 19.9,
  "disponivel": true
}
```

**Response 200**

```json
{
  "unidadeId": 1,
  "produtoId": 1,
  "preco": 19.9,
  "disponivel": true
}
```

## Produtos

### GET /produtos

- **Finalidade:** Lista o catálogo de produtos da rede.
- **Autenticação/perfis:** público
- **Sucesso:** 200
- **Query:** `page` (integer) — Página (>=1). Padrão 1; `limit` (integer) — Itens por página (1-100). Padrão 10

**Response 200**

```json
{
  "items": [
    {
      "id": 1,
      "nome": "Tapioca de carne de sol",
      "descricao": "Com queijo coalho",
      "precoBase": 18.5
    }
  ],
  "page": 1,
  "limit": 10,
  "total": 1
}
```

### POST /produtos

- **Finalidade:** Cadastra um produto no catálogo.
- **Autenticação/perfis:** JWT — GERENTE, ADMIN
- **Sucesso:** 201
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 403 `PERFIL_SEM_PERMISSAO`; 409 `PRODUTO_DUPLICADO`; 422 `VALIDACAO_INVALIDA`

**Request**

```json
{
  "nome": "Bolo de rolo",
  "descricao": "Fatia individual",
  "precoBase": 12.0
}
```

**Response 201**

```json
{
  "id": 5,
  "nome": "Bolo de rolo",
  "descricao": "Fatia individual",
  "precoBase": 12.0
}
```

### GET /produtos/{pid}

- **Finalidade:** Consulta um produto.
- **Autenticação/perfis:** público
- **Sucesso:** 200
- **Erros:** 404 `PRODUTO_NAO_ENCONTRADO`

**Response 200**

```json
{
  "id": 1,
  "nome": "Tapioca de carne de sol",
  "descricao": "Com queijo coalho",
  "precoBase": 18.5
}
```

## Estoque

### GET /estoque

- **Finalidade:** Consulta saldos de estoque de uma unidade.
- **Autenticação/perfis:** JWT — ATENDENTE, COZINHA, GERENTE, ADMIN
- **Sucesso:** 200
- **Query:** `unidadeId` (integer) — Obrigatório. Unidade consultada; `page` (integer) — Página (>=1). Padrão 1; `limit` (integer) — Itens por página (1-100). Padrão 10
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 403 `PERFIL_SEM_PERMISSAO`; 422 `VALIDACAO_INVALIDA`

**Response 200**

```json
{
  "items": [
    {
      "unidadeId": 1,
      "produtoId": 1,
      "produto": "Tapioca de carne de sol",
      "saldo": 40
    }
  ],
  "page": 1,
  "limit": 10,
  "total": 1
}
```

### POST /estoque/movimentacoes

- **Finalidade:** Registra entrada ou saída manual de estoque.
- **Autenticação/perfis:** JWT — GERENTE, ADMIN
- **Sucesso:** 201
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 403 `PERFIL_SEM_PERMISSAO`; 404 `UNIDADE_NAO_ENCONTRADA | PRODUTO_NAO_ENCONTRADO`; 409 `ESTOQUE_INSUFICIENTE`; 422 `VALIDACAO_INVALIDA`

**Request**

```json
{
  "unidadeId": 1,
  "produtoId": 1,
  "tipo": "ENTRADA",
  "quantidade": 20,
  "motivo": "Reposição semanal"
}
```

**Response 201**

```json
{
  "unidadeId": 1,
  "produtoId": 1,
  "saldo": 60
}
```

### GET /estoque/movimentacoes

- **Finalidade:** Lista movimentações rastreáveis de estoque.
- **Autenticação/perfis:** JWT — GERENTE, ADMIN
- **Sucesso:** 200
- **Query:** `unidadeId` (integer) — Obrigatório; `produtoId` (integer) — Opcional; `page` (integer) — Página (>=1). Padrão 1; `limit` (integer) — Itens por página (1-100). Padrão 10
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 403 `PERFIL_SEM_PERMISSAO`; 422 `VALIDACAO_INVALIDA`

**Response 200**

```json
{
  "items": [
    {
      "id": 1,
      "unidadeId": 1,
      "produtoId": 1,
      "tipo": "ENTRADA",
      "quantidade": 20,
      "motivo": "Reposição semanal",
      "pedidoId": null,
      "usuarioId": 2,
      "createdAt": "2026-11-04T12:00:00.000000Z"
    }
  ],
  "page": 1,
  "limit": 10,
  "total": 1
}
```

## Pedidos

### POST /pedidos

- **Finalidade:** Cria pedido: valida cardápio e estoque, calcula valores no servidor e baixa o estoque.
- **Autenticação/perfis:** JWT — CLIENTE, ATENDENTE, GERENTE, ADMIN
- **Sucesso:** 201
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 403 `PERFIL_SEM_PERMISSAO`; 404 `UNIDADE_NAO_ENCONTRADA | PRODUTO_NAO_ENCONTRADO | PRODUTO_FORA_DO_CARDAPIO | PROMOCAO_NAO_ENCONTRADA`; 409 `ESTOQUE_INSUFICIENTE | PRODUTO_INDISPONIVEL | UNIDADE_INATIVA | PROMOCAO_*`; 422 `VALIDACAO_INVALIDA`

**Request**

```json
{
  "canalPedido": "TOTEM",
  "unidadeId": 1,
  "itens": [
    {
      "produtoId": 1,
      "quantidade": 2
    },
    {
      "produtoId": 3,
      "quantidade": 1
    }
  ],
  "formaPagamento": "MOCK",
  "codigoPromocao": "RAIZES10"
}
```

**Response 201**

```json
{
  "pedidoId": 9001,
  "clienteId": 3,
  "unidadeId": 1,
  "canalPedido": "TOTEM",
  "status": "AGUARDANDO_PAGAMENTO",
  "subtotal": 62.5,
  "desconto": 0.0,
  "total": 62.5,
  "formaPagamento": "MOCK",
  "promocaoId": null,
  "itens": [
    {
      "produtoId": 1,
      "quantidade": 2,
      "precoUnitario": 18.5
    },
    {
      "produtoId": 3,
      "quantidade": 1,
      "precoUnitario": 25.5
    }
  ],
  "createdAt": "2026-11-04T12:00:00.000000Z",
  "updatedAt": "2026-11-04T12:00:00.000000Z"
}
```

### GET /pedidos

- **Finalidade:** Lista pedidos com filtros por canal, status e unidade (cliente vê apenas os próprios).
- **Autenticação/perfis:** JWT — qualquer perfil autenticado
- **Sucesso:** 200
- **Query:** `canalPedido` (string) — APP | TOTEM | BALCAO | PICKUP | WEB; `status` (string) — Status do pedido; `unidadeId` (integer) — Filtra por unidade; `page` (integer) — Página (>=1). Padrão 1; `limit` (integer) — Itens por página (1-100). Padrão 10
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 422 `VALIDACAO_INVALIDA`

**Response 200**

```json
{
  "items": [
    {
      "pedidoId": 9001,
      "clienteId": 3,
      "unidadeId": 1,
      "canalPedido": "TOTEM",
      "status": "AGUARDANDO_PAGAMENTO",
      "subtotal": 62.5,
      "desconto": 0.0,
      "total": 62.5,
      "formaPagamento": "MOCK",
      "promocaoId": null,
      "itens": [
        {
          "produtoId": 1,
          "quantidade": 2,
          "precoUnitario": 18.5
        },
        {
          "produtoId": 3,
          "quantidade": 1,
          "precoUnitario": 25.5
        }
      ],
      "createdAt": "2026-11-04T12:00:00.000000Z",
      "updatedAt": "2026-11-04T12:00:00.000000Z"
    }
  ],
  "page": 1,
  "limit": 10,
  "total": 1
}
```

### GET /pedidos/{pid}

- **Finalidade:** Consulta um pedido e seus pagamentos.
- **Autenticação/perfis:** JWT — qualquer perfil autenticado
- **Sucesso:** 200
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 403 `UNIDADE_FORA_DO_ESCOPO`; 404 `PEDIDO_NAO_ENCONTRADO`

**Response 200**

```json
{
  "pedidoId": 9001,
  "clienteId": 3,
  "unidadeId": 1,
  "canalPedido": "TOTEM",
  "status": "AGUARDANDO_PAGAMENTO",
  "subtotal": 62.5,
  "desconto": 0.0,
  "total": 62.5,
  "formaPagamento": "MOCK",
  "promocaoId": null,
  "itens": [
    {
      "produtoId": 1,
      "quantidade": 2,
      "precoUnitario": 18.5
    },
    {
      "produtoId": 3,
      "quantidade": 1,
      "precoUnitario": 25.5
    }
  ],
  "createdAt": "2026-11-04T12:00:00.000000Z",
  "updatedAt": "2026-11-04T12:00:00.000000Z",
  "pagamentos": []
}
```

### PATCH /pedidos/{pid}/status

- **Finalidade:** Atualiza o status (cozinha → pronto → entregue) ou cancela, conforme perfil e máquina de estados.
- **Autenticação/perfis:** JWT — qualquer perfil autenticado
- **Sucesso:** 200
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 403 `PERFIL_SEM_PERMISSAO_PARA_STATUS | CANCELAMENTO_NAO_PERMITIDO`; 404 `PEDIDO_NAO_ENCONTRADO`; 409 `TRANSICAO_DE_STATUS_INVALIDA | STATUS_RESERVADO_AO_PAGAMENTO`; 422 `VALIDACAO_INVALIDA`

**Request**

```json
{
  "status": "EM_PREPARO",
  "motivo": "Pedido iniciado na chapa"
}
```

**Response 200**

```json
{
  "pedidoId": 9001,
  "clienteId": 3,
  "unidadeId": 1,
  "canalPedido": "TOTEM",
  "status": "EM_PREPARO",
  "subtotal": 62.5,
  "desconto": 0.0,
  "total": 62.5,
  "formaPagamento": "MOCK",
  "promocaoId": null,
  "itens": [
    {
      "produtoId": 1,
      "quantidade": 2,
      "precoUnitario": 18.5
    },
    {
      "produtoId": 3,
      "quantidade": 1,
      "precoUnitario": 25.5
    }
  ],
  "createdAt": "2026-11-04T12:00:00.000000Z",
  "updatedAt": "2026-11-04T12:00:00.000000Z"
}
```

## Pagamentos

### POST /pagamentos

- **Finalidade:** Solicita pagamento ao gateway SIMULADO (campo simulacao: APROVADO, RECUSADO ou FALHA). Exige cabeçalho Idempotency-Key.
- **Autenticação/perfis:** JWT — CLIENTE, ATENDENTE, GERENTE, ADMIN
- **Sucesso:** 201
- **Cabeçalhos:** `Idempotency-Key` — Obrigatório. 8 a 100 caracteres. Repetir a chave devolve o mesmo resultado (200).
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 404 `PEDIDO_NAO_ENCONTRADO`; 409 `PEDIDO_NAO_AGUARDA_PAGAMENTO | IDEMPOTENCY_KEY_REUTILIZADA`; 422 `VALIDACAO_INVALIDA`; 502 `GATEWAY_PAGAMENTO_INDISPONIVEL`

**Request**

```json
{
  "pedidoId": 9001,
  "metodo": "MOCK",
  "simulacao": "APROVADO"
}
```

**Response 201**

```json
{
  "pagamentoId": 1,
  "pedidoId": 9001,
  "metodo": "MOCK",
  "status": "APROVADO",
  "valor": 62.5,
  "mensagem": "Pagamento aprovado (simulação).",
  "payloadEnviado": {
    "pedidoId": 9001,
    "valor": 62.5,
    "moeda": "BRL",
    "metodo": "MOCK"
  },
  "payloadRecebido": {
    "transactionId": "7d1c...",
    "status": "APROVADO",
    "motivo": null,
    "mensagem": "Pagamento aprovado (simulação)."
  },
  "createdAt": "2026-11-04T12:01:00.000000Z",
  "pedidoStatus": "PAGO",
  "reaproveitado": false
}
```

### GET /pagamentos/{pid}

- **Finalidade:** Consulta um pagamento registrado.
- **Autenticação/perfis:** JWT — qualquer perfil autenticado
- **Sucesso:** 200
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 404 `PAGAMENTO_NAO_ENCONTRADO`

**Response 200**

```json
{
  "pagamentoId": 1,
  "pedidoId": 9001,
  "metodo": "MOCK",
  "status": "APROVADO",
  "valor": 62.5,
  "mensagem": "Pagamento aprovado (simulação).",
  "payloadEnviado": {
    "pedidoId": 9001,
    "valor": 62.5,
    "moeda": "BRL",
    "metodo": "MOCK"
  },
  "payloadRecebido": {
    "transactionId": "7d1c...",
    "status": "APROVADO",
    "motivo": null,
    "mensagem": "Pagamento aprovado (simulação)."
  },
  "createdAt": "2026-11-04T12:01:00.000000Z",
  "pedidoStatus": "PAGO",
  "reaproveitado": false
}
```

## Fidelidade

### POST /fidelidade/consentimento

- **Finalidade:** Concede ou revoga o consentimento para o programa de fidelidade.
- **Autenticação/perfis:** JWT — CLIENTE
- **Sucesso:** 200
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 403 `PERFIL_SEM_PERMISSAO`; 422 `VALIDACAO_INVALIDA`

**Request**

```json
{
  "aceito": true
}
```

**Response 200**

```json
{
  "consentimentoFidelidade": true
}
```

### GET /fidelidade/saldo

- **Finalidade:** Consulta o saldo de pontos.
- **Autenticação/perfis:** JWT — CLIENTE
- **Sucesso:** 200
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 403 `PERFIL_SEM_PERMISSAO`

**Response 200**

```json
{
  "consentimentoFidelidade": true,
  "saldoPontos": 62
}
```

### GET /fidelidade/historico

- **Finalidade:** Histórico de acúmulos e resgates.
- **Autenticação/perfis:** JWT — CLIENTE
- **Sucesso:** 200
- **Query:** `page` (integer) — Página (>=1). Padrão 1; `limit` (integer) — Itens por página (1-100). Padrão 10
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 403 `PERFIL_SEM_PERMISSAO`

**Response 200**

```json
{
  "items": [
    {
      "id": 1,
      "tipo": "ACUMULO",
      "pontos": 62,
      "pedidoId": 9001,
      "descricao": "Pontos por pedido pago",
      "createdAt": "2026-11-04T12:01:00.000000Z"
    }
  ],
  "page": 1,
  "limit": 10,
  "total": 1
}
```

### POST /fidelidade/resgates

- **Finalidade:** Resgata pontos (mínimo 10) com consentimento vigente.
- **Autenticação/perfis:** JWT — CLIENTE
- **Sucesso:** 201
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 403 `PERFIL_SEM_PERMISSAO`; 409 `SALDO_PONTOS_INSUFICIENTE | CONSENTIMENTO_AUSENTE`; 422 `VALIDACAO_INVALIDA`

**Request**

```json
{
  "pontos": 20
}
```

**Response 201**

```json
{
  "pontosResgatados": 20,
  "saldoPontos": 42
}
```

## Promoções

### GET /promocoes

- **Finalidade:** Lista promoções ativas.
- **Autenticação/perfis:** público
- **Sucesso:** 200
- **Query:** `page` (integer) — Página (>=1). Padrão 1; `limit` (integer) — Itens por página (1-100). Padrão 10

**Response 200**

```json
{
  "items": [
    {
      "id": 1,
      "codigo": "RAIZES10",
      "descricao": "10% em pedidos acima de R$ 30",
      "percentual": 10,
      "valorMinimo": 30.0,
      "ativa": true,
      "validoAte": null
    }
  ],
  "page": 1,
  "limit": 10,
  "total": 1
}
```

### POST /promocoes

- **Finalidade:** Cria regra promocional (desconto percentual com valor mínimo e validade).
- **Autenticação/perfis:** JWT — GERENTE, ADMIN
- **Sucesso:** 201
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 403 `PERFIL_SEM_PERMISSAO`; 409 `PROMOCAO_DUPLICADA`; 422 `VALIDACAO_INVALIDA`

**Request**

```json
{
  "codigo": "JUNINA15",
  "descricao": "15% no período junino",
  "percentual": 15,
  "valorMinimo": 25.0,
  "validoAte": "2027-06-30T23:59:59Z"
}
```

**Response 201**

```json
{
  "id": 2,
  "codigo": "JUNINA15",
  "descricao": "15% no período junino",
  "percentual": 15,
  "valorMinimo": 25.0,
  "ativa": true,
  "validoAte": "2027-06-30T23:59:59Z"
}
```

### PATCH /promocoes/{pid}

- **Finalidade:** Ativa ou desativa uma promoção.
- **Autenticação/perfis:** JWT — GERENTE, ADMIN
- **Sucesso:** 200
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 403 `PERFIL_SEM_PERMISSAO`; 404 `PROMOCAO_NAO_ENCONTRADA`; 422 `VALIDACAO_INVALIDA`

**Request**

```json
{
  "ativa": false
}
```

**Response 200**

```json
{
  "id": 1,
  "codigo": "RAIZES10",
  "descricao": "10% em pedidos acima de R$ 30",
  "percentual": 10,
  "valorMinimo": 30.0,
  "ativa": false,
  "validoAte": null
}
```

## Auditoria

### GET /auditoria

- **Finalidade:** Consulta trilha de auditoria de ações sensíveis.
- **Autenticação/perfis:** JWT — GERENTE, ADMIN
- **Sucesso:** 200
- **Query:** `acao` (string) — Ex.: PEDIDO_CRIADO; `entidade` (string) — Ex.: pedido; `entidadeId` (string) — Id da entidade; `page` (integer) — Página (>=1). Padrão 1; `limit` (integer) — Itens por página (1-100). Padrão 10
- **Erros:** 401 `TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO`; 403 `PERFIL_SEM_PERMISSAO`

**Response 200**

```json
{
  "items": [
    {
      "id": 7,
      "usuarioId": 4,
      "perfil": "CLIENTE",
      "acao": "PEDIDO_CRIADO",
      "entidade": "pedido",
      "entidadeId": "9001",
      "detalhes": {
        "canalPedido": "TOTEM",
        "unidadeId": 1,
        "totalCentavos": 6250
      },
      "requestId": "2f0c1a4e-...",
      "createdAt": "2026-11-04T12:00:00.000000Z"
    }
  ],
  "page": 1,
  "limit": 10,
  "total": 1
}
```

