# Roteiro de Teste da Autenticação

Este roteiro demonstra o serviço de autenticação sem AWS, RDS, Terraform ou deploy. Todos os eventos são sintéticos e seguem o formato de API Gateway REST API com Lambda proxy integration.

## Preparação

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

## Demonstração Local

```bash
python scripts/invoke_local.py
```

Evidências esperadas:

- Caso `200 with provided X-Correlation-Id`: retorna `status=200`, `token_type=Bearer`, `expires_in=900` e `access_token=<redacted>`.
- CPF inválido, cliente inexistente e cliente inativo retornam `status=401` com o mesmo envelope público `error.type=invalid_credentials` e a mesma mensagem genérica.
- JSON ausente, inválido, `Content-Type` incorreto ou payload inesperado retornam `status=400` com `error.type=invalid_request`; CPF com formato ou dígitos verificadores inválidos é falha de autenticação `401`.
- Caso `200 with provided X-Correlation-Id`: reaproveita o `X-Correlation-Id` recebido.
- Caso `200 with generated X-Correlation-Id`: gera novo UUIDv4 quando o header está ausente.
- O `requestId` do envelope de erro e o header `X-Request-Id` vêm primeiro de `X-Request-Id`, depois de `context.aws_request_id` e, na ausência de ambos, de um UUID novo. O `X-Correlation-Id` continua sendo independente e validado como UUIDv4.
- Logs aparecem em JSON, uma linha por cenário, com `timestamp`, `message`, `http.method`, `http.route`, `http.status_code`, `service.environment`, `correlation.id`, `request_id`, `duration_ms`, `outcome` e `auth.motivo`.
- A saída não mostra CPF completo, token real, `Authorization`, chave ou body completo.

O throttling do `POST /auth` é configurado no método do API Gateway por taxa e
burst agregados. Isso não limita cada IP individualmente. Proteção por IP
exigiria uma decisão e infraestrutura adicional, como WAF, que não pertence a
esta etapa.

## Build da Lambda

```bash
python scripts/build_lambda.py
python scripts/inspect_lambda_zip.py build/lambda/oficina_auth_lambda.zip
```

Evidências esperadas:

- Artefato em `build/lambda/oficina_auth_lambda.zip`.
- Checksum em `build/lambda/oficina_auth_lambda.zip.sha256`.
- Inspeção com `zip_inspection=ok`.
- `pg8000` é empacotado como wheel `py3-none-any` por ser puro Python; dependências com binários, como `cryptography`, são resolvidas para `manylinux2014_x86_64` e Python 3.11.
- Dois builds consecutivos devem produzir o mesmo SHA-256.
- ZIP sem `tests/`, `.git/`, `.env`, caches, `.venv`, `dist/`, `build/`, arquivos `.pem`, `.key`, `.pyc` ou `.pyo`.

O arquivo declarativo é `pyproject.toml`; `requirements.lock` é o lock versionado de runtime, com versões transitivas e hashes das wheels Linux escolhidas. O build consome somente o lock e falha se as dependências diretas declaradas mudarem sem atualização dos marcadores `# direct`. Não edite o lock manualmente. Para atualizar, faça uma nova resolução com `pip download` usando `--only-binary=:all:`, `--platform manylinux2014_x86_64`, `--implementation cp`, `--python-version 3.11` e `--abi cp311`, registre os hashes com `python -m pip hash`, e repita todos os checks. O ZIP não recebe dependências de desenvolvimento nem depende implicitamente da `.venv`.

## Validação Completa

```bash
python -m compileall -q .
ruff check .
ruff format --check .
python -m pytest --cov=oficina_auth --cov-report=term-missing --cov-fail-under=90
python -m build
```

## Diferença para AWS Real

A demonstração local usa `InMemoryClientRepository` e chave RSA efêmera apenas por composição explícita em `scripts/invoke_local.py`. A Lambda em produção não usa adapter em memória por fallback silencioso. A composição de produção usa `PostgresClientRepository`, `SecretsManagerDatabaseCredentialsProvider` e `SecretsManagerPrivateKeyProvider`. Ela exige `POSTGRES_DB=oficina`, consulta `atendimento_cliente` com `id` e `ativo`, e não aceita `POSTGRES_USER` ou `POSTGRES_PASSWORD` como configuração da Lambda.

O smoke test real só deve ser executado depois da migration e da infraestrutura existirem. Este roteiro não acessa AWS nem executa SQL de criação de usuário. O build empacota `pg8000`, driver DB-API puro Python, e `boto3` no ZIP para Python 3.11.

## Checklist de Integração AWS e Django

Os itens desta seção são um roteiro para execução autorizada. Eles não fazem
parte da demonstração local e não devem ser executados com credenciais ou
dados reais neste repositório.

### Pré-condições e responsáveis

- [ ] **K8s:** fornecer `vpc_id`, `private_subnet_ids`, `alb_arn`,
  `alb_dns_name` e `alb_security_group_id`; confirmar ALB interno, listener,
  Target Group, health-check e rota para o Service/Django.
- [ ] **Database:** fornecer `rds_endpoint`, `rds_port` e
  `rds_security_group_id`; confirmar banco `oficina`, migration de
  `Cliente.ativo` aplicada e usuário `oficina_auth` com somente `CONNECT`,
  `USAGE` e `SELECT` em `atendimento_cliente`.
- [ ] **Auth/segurança:** gerar o par RSA em procedimento aprovado fora do
  repositório; guardar a chave privada em Secret separado e conferir a chave
  pública correspondente sem exibir material criptográfico.
- [ ] **Django:** injetar a chave pública correspondente, codificada em base64,
  em `AUTH_JWT_PUBLIC_KEY_B64` no namespace `oficina` antes do rollout; validar
  `iss=oficina-auth`, `aud=oficina-api` e RS256.
- [ ] **Observabilidade:** criar `oficina/newrelic-license` pelo responsável
  autorizado, sem imprimir seu conteúdo; conferir `GetSecretValue` para os
  Secrets de licença, banco e chave JWT, permissões de ENI e escrita de logs.
- [ ] **API Gateway:** confirmar a role externa de access logs, retenção e
  formato JSON. Revisar o plan real antes de qualquer autorização de apply.

### Smoke test integrado

- [ ] Executar `terraform plan` no ambiente correto e revisar nomes, tags,
  região `us-east-1`, banco, Secrets, layer, Security Groups, API Gateway e
  VPC Link antes de autorizar apply.
- [ ] Com infraestrutura aprovada, chamar `POST /auth` com cliente sintético
  elegível e validar `200`, JWT RS256, `sub=cliente:<id>`, `cliente_id`,
  `principal_type=cliente`, `token_type=access`, `jti` e expiração de 900s.
- [ ] Repetir com CPF inválido, cliente inexistente e cliente inativo; todos
  devem ser indistinguíveis publicamente e retornar `401` genérico.
- [ ] Usar o token em consultas Django autorizadas e confirmar isolamento entre
  clientes: consulta de outro cliente retorna `404`, não `403` nem dados de
  terceiro. Tentar `INSERT`, `UPDATE` e `DELETE` com o usuário de leitura e
  confirmar negação sem alterar dados.
- [ ] Testar token adulterado, issuer/audience incorretos, algoritmo diferente,
  token expirado e path inexistente.
- [ ] Confirmar `X-Correlation-Id` preservado/gerado, `X-Request-Id` por
  requisição, `traceparent` e `tracestate` propagados sem fabricação, além do
  path original nas rotas proxy.
- [ ] Conferir CloudWatch e New Relic com Luís: logs JSON contendo os campos
  operacionais e sem CPF, token, `Authorization`, chave, senha ou Secret;
  revisar dashboards e alertas para sucesso, `401`, `429`, `5xx`, latência e
  falhas de dependência.

### Limites do roteiro

O smoke test integrado depende de outputs reais de K8s/Database, migration,
Secrets, permissões da role, rede Lambda-RDS, VPC Link-ALB, role de logs do API
Gateway, chave pública no Django e configuração New Relic. Aprovação de PR,
merge ou execução do workflow não é evidência de deploy ou de teste AWS
real; cada execução deve registrar a evidência correspondente sem expor dados.
