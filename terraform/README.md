# Terraform do Auth

Este módulo provisiona somente a infraestrutura específica do serviço de autenticação. Ele recebe valores compartilhados por variáveis explícitas e não usa `terraform_remote_state`.

## Arquitetura

```text
Cliente
  |
  +--> API Gateway REST regional --> POST /auth --> Lambda Python 3.11 --> RDS PostgreSQL
  |
  +--> demais rotas --> VPC Link V2 --> ALB interno --> EKS/Django
```

O Auth cria a Lambda, API Gateway, recursos `/auth` e `/{proxy+}`, VPC Link V2, Security Groups próprios, regras direcionadas aos Security Groups externos, Log Groups da Lambda e de access log do API Gateway. O `POST /auth` usa integração `AWS_PROXY` direta. A raiz e o proxy usam `HTTP_PROXY` privado com `integration_target = alb_arn`.

O nome do stage é removido do path por templates de override do API Gateway. O proxy preserva o path original, query string, body e headers. `Authorization`, `X-Correlation-Id`, `X-Request-Id`, `traceparent` e `tracestate` não são remapeados nem fabricados pelo gateway. A rota explícita `/auth` tem precedência sobre `/{proxy+}`.

O ALB é interno, HTTP na porta `8000`, com Target Group/NodePort `30080` e health-check `/health/ready/`; esses recursos continuam pertencendo ao K8s e não são alterados aqui. A integração usa `alb_arn`; `alb_listener_arn` não é usado.

## Fronteiras e dependências externas

- K8s fornece `vpc_id`, subnets privadas, `alb_arn`, `alb_dns_name` e `alb_security_group_id`, além de NAT para a saída HTTPS da Lambda.
- Database fornece `rds_endpoint`, `rds_port` e `rds_security_group_id`.
- O Auth recebe `lambda_execution_role_arn`, `db_secret_id`, `jwt_private_key_secret_id` e o identificador do Secret de licença New Relic, mas não cria IAM Role, Secret ou Secret Version.
- O Secret `oficina-auth` é lido em runtime pela aplicação e deve conter o usuário `oficina_auth`; o Terraform apenas injeta seu identificador.
- A chave privada JWT fica em Secret separado. O código aplica `iss=oficina-auth`, `aud=oficina-api` e expiração de 900 segundos.
- A configuração canônica aceita `environment = "homologacao"` ou `"producao"`. O serviço usa esses valores em `APP_ENV` e `service.environment`; o tag AWS `Environment` e os nomes de recursos usam `hml` ou `prd`, respectivamente. A Lambda resulta em `oficina-auth-cpf-hml` ou `oficina-auth-cpf-prd`.
- A alteração dos nomes para o contrato `oficina-auth-cpf-hml/prd` deve ser revisada no primeiro plano; este módulo não renomeia workspaces nem state existentes silenciosamente.
- O throttling de `POST /auth` é agregado no método do stage e parametrizado por `auth_throttle_rate_limit` e `auth_throttle_burst_limit`; ele não é uma limitação individual por IP. Uma política por IP, se exigida, deve ser decidida e implementada fora desta mudança.
- New Relic usa `new_relic_account_id`, `new_relic_layer_arn` e `new_relic_license_key_secret_id`. Os valores alinhados são `8430077`, `arn:aws:lambda:us-east-1:451483290750:layer:NewRelicPython311:90` e `oficina/newrelic-license` como exemplo de identificador. A licença não entra no Terraform nem em `NEW_RELIC_LICENSE_KEY`; o runtime recebe apenas `NEW_RELIC_LICENSE_KEY_SECRET`.
- A saída para Secrets Manager/New Relic depende do NAT das subnets privadas. Este módulo não cria NAT Gateway ou VPC Endpoint.

As regras da Lambda para o SG do RDS e do VPC Link para o SG do ALB são independentes e restritas às portas configuradas. Nenhuma regra abre PostgreSQL ou ALB para `0.0.0.0/0`.

## Build e configuração

Na raiz do repositório, gere o artefato e o checksum:

```bash
python scripts/build_lambda.py
python scripts/inspect_lambda_zip.py build/lambda/oficina_auth_lambda.zip
```

Copie `terraform.tfvars.example` para um arquivo local ignorado e substitua todos os placeholders por valores fornecidos pelos repositórios proprietários. O `lambda_zip_sha256` deve ser o SHA-256 hexadecimal emitido pelo build; o Terraform valida que ele corresponde ao arquivo indicado. Não informe username, senha, PEM, token ou conteúdo de Secret.

## Validação e entrega

```bash
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
terraform test
```

`terraform test` usa mock provider e precisa do ZIP local gerado pelo build; não acessa a AWS. O lock `.terraform.lock.hcl` é versionado e mantém o provider AWS na versão validada. Depois que a sessão AWS Academy e todos os inputs externos estiverem disponíveis, os comandos de entrega são:

```bash
terraform plan
terraform apply
```

Eles devem ser executados somente pelo workflow autorizado do Hélio. Este repositório não executa AWS CLI nem acessa Secrets durante a validação local.

O Auth cria o Log Group de access logs do REST API com retenção configurável e o stage o habilita por padrão. O formato JSON contém `requestId`, `httpMethod`, `path`, `status`, `responseLatency`, `integrationLatency`, `error.message` e `service.environment`. A role de logging no nível da conta do API Gateway deve ser configurada externamente; nenhuma role é inventada neste módulo.

O layer New Relic usa `newrelic_lambda_wrapper.handler` como handler da função, preservando `oficina_auth.handlers.auth.lambda_handler` em `NEW_RELIC_LAMBDA_HANDLER`. Também são configurados `NEW_RELIC_ACCOUNT_ID`, `NEW_RELIC_APP_NAME`, `NEW_RELIC_APM_LAMBDA_MODE`, `NEW_RELIC_LAMBDA_EXTENSION_ENABLED`, `NEW_RELIC_EXTENSION_SEND_FUNCTION_LOGS` e `NEW_RELIC_LICENSE_KEY_SECRET`, além da tag `NR.Apm.Lambda.Mode=true`. A role de execução externa da Lambda precisa de `secretsmanager:GetSecretValue` limitado ao Secret da licença e aos Secrets de banco/chave; o código e os logs não contêm CPF, token, `Authorization` ou conteúdo de Secret. Consulte a [documentação oficial de variáveis da New Relic](https://docs.newrelic.com/docs/serverless-function-monitoring/aws-lambda-monitoring/instrument-lambda-function/env-variables-lambda/) e o [guia oficial de instrumentação](https://docs.newrelic.com/docs/serverless-function-monitoring/aws-lambda-monitoring/instrument-lambda-function/instrument-your-own/).

## Rollback e AWS Academy

O rollback deve usar uma versão anterior do ZIP e do deployment/stage por workflow autorizado. Não destrua VPC, NAT, EKS, ALB ou RDS a partir deste módulo. Em AWS Academy, credenciais são temporárias; renove a sessão antes de qualquer plan/apply e confirme os custos de ENIs, NAT, CloudWatch e API Gateway. O NAT/EIP compartilhado permanece sob controle do repositório K8s.

Permissões mínimas da role externa da Lambda: execução básica, criação/remoção de interfaces de rede, escrita em CloudWatch Logs e `secretsmanager:GetSecretValue` restrito aos dois Secrets. `kms:Decrypt` só é necessário quando os Secrets usam uma chave KMS própria.
