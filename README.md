# Tech Challenge Oficina — Autenticação Serverless

Function Serverless responsável pela autenticação por CPF na Fase 3 do Tech Challenge FIAP.

## Responsabilidade

- Validar o CPF recebido.
- Consultar existência e status do cliente na base de dados.
- Rejeitar clientes inexistentes ou inativos.
- Gerar JWT válido para consumo das APIs protegidas.
- Produzir logs estruturados com identificador de correlação.

Responsável técnico: Lucas Marques (`O-marqs`).

## Contrato inicial

Entrada:

```json
{
  "cpf": "00000000000"
}
```

Saída esperada em caso de sucesso:

```json
{
  "access_token": "<jwt>",
  "token_type": "Bearer",
  "expires_in": 900
}
```

Claims, algoritmo, expiração, integração com o banco e provedor serverless serão definidos em RFC/ADR com o grupo.

## Integrações

- API Gateway: entrada da requisição de autenticação.
- Banco gerenciado: consulta do cliente.
- Aplicação principal: validação e consumo do JWT.
- Observabilidade: logs, erros, latência e correlação.

## Branches e ambientes

- `develop`: homologação.
- `main`: produção.
- Mudanças entram exclusivamente por Pull Request.

## Status

Estrutura inicial criada. Implementação e CI/CD serão adicionados após as decisões de nuvem e autenticação.
