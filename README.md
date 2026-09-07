# Tech Challenge Oficina — Autenticação Serverless

Projeto Python 3.11 responsável pelo contrato de autenticação por CPF da Fase 3 do Tech Challenge FIAP.

Responsável técnico: Lucas Marques (`O-marqs`).

## Responsabilidade

- Receber solicitações `POST /auth` com CPF.
- Validar payload e formato do CPF.
- Representar a identidade autenticada como `Cliente`.
- Emitir e validar JWT de Cliente por providers de chave.
- Padronizar correlação, observabilidade e respostas de erro.

Este repositório não implementa a aplicação principal, VPC, subnets, NAT, EKS, ALB ou RDS. Ele é responsável pela Lambda, API Gateway REST regional, rotas, VPC Link V2, Terraform específico, Security Groups específicos, regras direcionadas aos SGs externos e CloudWatch específicos do Auth. A composição da Lambda para produção já está preparada com adapters de PostgreSQL e Secrets Manager, mas seu acesso real depende da infraestrutura externa.

O Terraform específico do Auth já existe sob `terraform/` e recebe os valores compartilhados por variáveis explícitas. Ele não cria VPC, subnets, NAT Gateway, EKS, ALB, RDS, IAM Role, Secret ou Secret Version e não usa `terraform_remote_state`.

## Estado da Entrega

Já estão implementados e validados localmente: o núcleo de autenticação, o handler Lambda de `POST /auth`, adapters PostgreSQL e Secrets Manager, JWT RS256, documentação, testes, build reproduzível e Terraform específico do Auth.

Ainda não foram implantados ou testados contra a AWS: os recursos Terraform, RDS, Secrets Manager, permissões da LabRole, backend durável do state, `terraform plan`, `terraform apply`, deploy e smoke test integrado. Nenhum deploy é pressuposto por este README.

As fronteiras permanecem explícitas: Auth entrega código e infraestrutura específica; K8s entrega VPC, subnets, NAT, EKS e ALB; Database entrega RDS e grants; CI/CD entrega workflows e automação autorizada; Observabilidade entrega New Relic, dashboards e alertas gerais.

## Arquitetura

A estrutura inicial separa domínio, casos de uso, adaptadores e handlers:

```text
src/oficina_auth/domain/          Regras de domínio
src/oficina_auth/application/     Casos de uso
src/oficina_auth/infrastructure/  Adapters PostgreSQL, Secrets Manager e JWT
src/oficina_auth/handlers/        Handler Lambda implementado
tests/unit/                       Testes unitários
tests/contract/                   Testes do contrato público
openapi/                          Contrato OpenAPI
docs/adrs/                        Decisões arquiteturais
scripts/                          Scripts locais seguros
terraform/                        Infraestrutura específica do Auth
```

## Núcleo de Autenticação

O núcleo atual é independente de AWS e frameworks web. Ele contém:

- Value object `CPF`, com normalização e validação de dígitos verificadores.
- Registro mínimo `AuthenticationRecord`, com `cliente_id` e `can_authenticate`.
- Ports `ClientRepository` e `TokenIssuer`.
- Caso de uso `AuthenticateClient`.
- Adapter `InMemoryClientRepository`, somente para testes e desenvolvimento local.
- Adapter `PostgresClientRepository`, para a tabela Django `atendimento_cliente`, lendo apenas `id` e `ativo`.
- Providers de credenciais e chave privada via Secrets Manager, com cache temporário no processo aquecido.
- Emissor `Rs256TokenIssuer` e verificador `TokenVerifier`, com chaves fornecidas por providers.
- Handler `POST /auth` para API Gateway REST API com Lambda proxy integration.

Clientes inexistentes e clientes não elegíveis retornam o mesmo erro público genérico. O núcleo não registra CPF, `Authorization`, tokens ou segredos.

## Handler Lambda

O handler em `oficina_auth.handlers.auth.lambda_handler` trata eventos REST API proxy, valida método, `Content-Type`, JSON, body base64, payload exato com `cpf`, correlação e logs JSON seguros para stdout/CloudWatch/New Relic.

Para testes e demonstração local, use `create_local_demo_handler(...)` com dependências explícitas. A `lambda_handler` de produção exige `DB_HOST`, `DB_PORT`, `POSTGRES_DB=oficina`, `DB_SECRET_ID` e `JWT_PRIVATE_KEY_SECRET_ID`, e compõe PostgreSQL, Secrets Manager e JWT. Produção não usa `InMemoryClientRepository` por fallback silencioso.

O PostgreSQL usa `pg8000`, um driver DB-API puro Python adequado ao empacotamento da Lambda, sem dependência de wheel nativo do sistema operacional. O build instala as dependências de runtime para Python 3.11 e o inspetor exige `pg8000` e `boto3` no ZIP.

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

## Configuração de Runtime

- PostgreSQL usa banco `oficina`, com endpoint e porta em `DB_HOST` e `DB_PORT`, e nome em `POSTGRES_DB`.
- A Lambda recebe apenas `DB_SECRET_ID`, que aceita nome ou ARN. O exemplo fictício é `oficina-auth`.
- O Secret de banco tem o formato JSON `{ "username": "oficina_auth", "password": "..." }`. `POSTGRES_USER` e `POSTGRES_PASSWORD` não são variáveis da Lambda.
- O usuário `oficina_auth` deve ter somente `CONNECT` no banco `oficina`, `USAGE` no schema utilizado e `SELECT` em `atendimento_cliente`; os grants serão provisionados fora deste repositório.
- A chave privada JWT fica em Secret separado, pertencente ao Auth, identificado por `JWT_PRIVATE_KEY_SECRET_ID`; a resposta do Secrets Manager nunca é registrada.
- Inputs externos futuros são variáveis explícitas: `vpc_id`, `private_subnet_ids`, `alb_arn`, `alb_security_group_id`, `rds_endpoint`, `rds_port` e `rds_security_group_id`.
- O ALB é gerenciado pelo Terraform do repositório K8s; o Auth cria apenas a integração VPC Link e a regra direcionada ao SG externo do ALB. `alb_listener_arn` não é usado como input do REST VPC Link V2.

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
terraform -chdir=terraform fmt -check -recursive
terraform -chdir=terraform init -backend=false
terraform -chdir=terraform validate
```

## Demonstração Local e Build Lambda

Use `python scripts/invoke_local.py` para executar uma demonstração independente da AWS com eventos sintéticos de API Gateway REST. A saída redige tokens como `<redacted>` e não imprime CPF completo.

Use `python scripts/build_lambda.py` para gerar `build/lambda/oficina_auth_lambda.zip` e seu checksum SHA-256. O diretório `build/` é ignorado pelo Git. Depois execute `python scripts/inspect_lambda_zip.py build/lambda/oficina_auth_lambda.zip` para bloquear testes, caches, `.env`, Git, chaves e arquivos locais no pacote, além de confirmar os módulos `pg8000` e `boto3`.

As dependências declaradas ficam no `pyproject.toml`; as dependências de runtime resolvidas, incluindo transitivas, ficam fixadas em [`requirements.lock`](requirements.lock). O build instala exclusivamente esse lock com hashes, sem usar a `.venv` como fonte do ZIP, e falha se os marcadores de dependência direta estiverem desatualizados. Não edite o lock manualmente: para atualizá-lo, resolva novamente as versões para `manylinux2014_x86_64`, Python 3.11 e ABI `cp311` com `pip download --only-binary=:all: --platform manylinux2014_x86_64 --implementation cp --python-version 3.11 --abi cp311`, registre os hashes com `python -m pip hash` e valide com o build e o inspetor. Dependências de desenvolvimento nunca entram no ZIP.

## Documentação

- [`AGENTS.md`](AGENTS.md): regras operacionais para contribuidores e agentes.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): fluxo de branches e pull requests.
- [`docs/roteiro-teste-auth.md`](docs/roteiro-teste-auth.md): roteiro da demonstração local.
- [`docs/smoke-test-rds.md`](docs/smoke-test-rds.md): smoke test manual e protegido do RDS real.
- [`docs/adrs/adr-001-identidade-cliente.md`](docs/adrs/adr-001-identidade-cliente.md): identidade mínima do Cliente.
- [`docs/adrs/adr-002-correlacao-observabilidade.md`](docs/adrs/adr-002-correlacao-observabilidade.md): correlação e propagação de headers.
- [`docs/adrs/adr-003-credenciais-runtime-e-assinatura-jwt.md`](docs/adrs/adr-003-credenciais-runtime-e-assinatura-jwt.md): credenciais externas e assinatura JWT.
- [`terraform/README.md`](terraform/README.md): Terraform específico do Auth e contratos de integração.

## Branches e Ambientes

- `develop`: homologação.
- `main`: produção.
- Mudanças entram exclusivamente por Pull Request.

Não trabalhe diretamente em `develop` ou `main`. Não faça push, merge, deploy ou `terraform apply` sem autorização explícita.

## Divisão de Responsabilidades

- **Auth:** código da Lambda, autenticação por CPF, consulta do Cliente, JWT, API Gateway, rotas, VPC Link, Terraform específico, Security Groups e CloudWatch do Auth.
- **K8s:** VPC, subnets, NAT, EKS, Kubernetes e ALB compartilhado.
- **Database:** RDS PostgreSQL e sua configuração.
- **CI/CD:** workflows, proteção de branches e automação autorizada de plan/apply/deploy.
- **Observabilidade:** New Relic, dashboards, alertas e observabilidade geral.
