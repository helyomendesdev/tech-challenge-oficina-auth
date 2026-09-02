# Tech Challenge Oficina — Autenticação Serverless

Projeto Python 3.11 responsável pelo contrato de autenticação por CPF da Fase 3 do Tech Challenge FIAP.

Responsável técnico: Lucas Marques (`O-marqs`).

## Responsabilidade

- Receber solicitações `POST /auth` com CPF.
- Validar payload e formato do CPF.
- Representar a identidade autenticada como `Cliente`.
- Definir a emissão futura de JWT de Cliente.
- Padronizar correlação, observabilidade e respostas de erro.

Este repositório não implementa a aplicação principal, K8s, Database, RDS, Lambda real, JWT real, API Gateway real ou Terraform neste momento.

## Arquitetura

A estrutura inicial separa domínio, casos de uso, adaptadores e handlers:

```text
src/oficina_auth/domain/          Regras de domínio
src/oficina_auth/application/     Casos de uso
src/oficina_auth/infrastructure/  Integrações futuras
src/oficina_auth/handlers/        Entrypoints futuros
tests/unit/                       Testes unitários
tests/contract/                   Testes do contrato público
openapi/                          Contrato OpenAPI
docs/adrs/                        Decisões arquiteturais
scripts/                          Scripts locais seguros
```

## Núcleo de Autenticação

O núcleo atual é independente de AWS e frameworks web. Ele contém:

- Value object `CPF`, com normalização e validação de dígitos verificadores.
- Registro mínimo `AuthenticationRecord`, com `cliente_id` e `can_authenticate`.
- Ports `ClientRepository` e `TokenIssuer`.
- Caso de uso `AuthenticateClient`.
- Adapter `InMemoryClientRepository`, somente para testes e desenvolvimento local.
- Emissor `Rs256TokenIssuer` e verificador `TokenVerifier`, com chaves fornecidas por providers.
- Handler `POST /auth` para API Gateway REST API com Lambda proxy integration.

Clientes inexistentes e clientes não elegíveis retornam o mesmo erro público genérico. O núcleo não registra CPF, `Authorization`, tokens ou segredos.

## Handler Lambda

O handler em `oficina_auth.handlers.auth.lambda_handler` trata eventos REST API proxy, valida método, `Content-Type`, JSON, body base64, payload exato com `cpf`, correlação e logs JSON seguros para stdout/CloudWatch/New Relic.

Para testes e demonstração local, use `create_local_demo_handler(...)` com dependências explícitas. Produção não usa `InMemoryClientRepository` por fallback silencioso; dependências reais deverão ser configuradas em etapa futura.

## JWT de Cliente

A primeira versão emite somente access tokens RS256, sem refresh token no fluxo por CPF. O emissor usa `iss=oficina-auth`, `aud=oficina-api`, expiração de 900 segundos e `sub=cliente:<id>`.

Claims obrigatórias:

- `iss`
- `aud`
- `sub`
- `cliente_id`
- `principal_type=cliente`
- `token_type=access`
- `iat`
- `exp`
- `jti` UUIDv4

As chaves são obtidas por provider e não ficam hardcoded. O token não inclui CPF, nome, e-mail ou `created_by_id`.

## Contrato do POST /auth

O contrato está documentado em [`openapi/openapi.yaml`](openapi/openapi.yaml).

Entrada sintética:

```json
{
  "cpf": "00000000000"
}
```

Saída `200`:

```json
{
  "access_token": "synthetic.jwt.value",
  "token_type": "Bearer",
  "expires_in": 900
}
```

Clientes inexistentes e não elegíveis usam a mesma resposta genérica `401`. Todas as respostas retornam `X-Correlation-Id`.

## Execução Local

Use Python 3.11:

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e .[dev]
ruff check .
ruff format --check .
python -m compileall -q .
python -m pytest --cov=oficina_auth --cov-report=term-missing
python scripts/invoke_local.py
python scripts/build_lambda.py
python scripts/inspect_lambda_zip.py build/lambda/oficina_auth_lambda.zip
python -m build
```

## Demonstração Local e Build Lambda

Use `python scripts/invoke_local.py` para executar uma demonstração independente da AWS com eventos sintéticos de API Gateway REST. A saída redige tokens como `<redacted>` e não imprime CPF completo.

Use `python scripts/build_lambda.py` para gerar `build/lambda/oficina_auth_lambda.zip` e seu checksum SHA-256. O diretório `build/` é ignorado pelo Git. Depois execute `python scripts/inspect_lambda_zip.py build/lambda/oficina_auth_lambda.zip` para bloquear testes, caches, `.env`, Git, chaves e arquivos locais no pacote.

## Documentação

- [`AGENTS.md`](AGENTS.md): regras operacionais para contribuidores e agentes.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): fluxo de branches e pull requests.
- [`docs/roteiro-teste-auth.md`](docs/roteiro-teste-auth.md): roteiro da demonstração local.
- [`docs/adrs/adr-001-identidade-cliente.md`](docs/adrs/adr-001-identidade-cliente.md): identidade mínima do Cliente.
- [`docs/adrs/adr-002-correlacao-observabilidade.md`](docs/adrs/adr-002-correlacao-observabilidade.md): correlação e propagação de headers.

## Branches e Ambientes

- `develop`: homologação.
- `main`: produção.
- Mudanças entram exclusivamente por Pull Request.

Não trabalhe diretamente em `develop` ou `main`. Não faça push, merge, deploy ou `terraform apply` sem autorização explícita.
