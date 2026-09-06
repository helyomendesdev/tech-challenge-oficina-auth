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

O Auth cria a Lambda, API Gateway, recursos `/auth` e `/{proxy+}`, VPC Link V2, Security Groups próprios, regras direcionadas aos Security Groups externos e Log Group da Lambda. O `POST /auth` usa integração `AWS_PROXY` direta. A raiz e o proxy usam `HTTP_PROXY` privado com `integration_target = alb_arn`.

O nome do stage é removido do path por templates de override do API Gateway. O proxy preserva o path original, query string, body e headers. `Authorization`, `X-Correlation-Id`, `X-Request-Id`, `traceparent` e `tracestate` não são remapeados nem fabricados pelo gateway. A rota explícita `/auth` tem precedência sobre `/{proxy+}`.

O ALB é interno, HTTP na porta `8000`, com Target Group/NodePort `30080` e health-check `/health/ready/`; esses recursos continuam pertencendo ao K8s e não são alterados aqui. A integração usa `alb_arn`; `alb_listener_arn` não é usado.

## Fronteiras e dependências externas

- K8s fornece `vpc_id`, subnets privadas, `alb_arn`, `alb_dns_name` e `alb_security_group_id`, além de NAT para a saída HTTPS da Lambda.
- Database fornece `rds_endpoint`, `rds_port` e `rds_security_group_id`.
- O Auth recebe `lambda_execution_role_arn`, `db_secret_id` e `jwt_private_key_secret_id`, mas não cria IAM Role, Secret ou Secret Version.
- O Secret `oficina-auth` é lido em runtime pela aplicação e deve conter o usuário `oficina_auth`; o Terraform apenas injeta seu identificador.
- A chave privada JWT fica em Secret separado. O código aplica `iss=oficina-auth`, `aud=oficina-api` e expiração de 900 segundos.
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

Access logs do REST API são opcionais: `api_gateway_access_log_group_arn` aponta para um Log Group existente, mas a role de logging no nível da conta deve ser configurada externamente. Nenhuma role é inventada neste módulo.

## Rollback e AWS Academy

O rollback deve usar uma versão anterior do ZIP e do deployment/stage por workflow autorizado. Não destrua VPC, NAT, EKS, ALB ou RDS a partir deste módulo. Em AWS Academy, credenciais são temporárias; renove a sessão antes de qualquer plan/apply e confirme os custos de ENIs, NAT, CloudWatch e API Gateway. O NAT/EIP compartilhado permanece sob controle do repositório K8s.

Permissões mínimas da role externa da Lambda: execução básica, criação/remoção de interfaces de rede, escrita em CloudWatch Logs e `secretsmanager:GetSecretValue` restrito aos dois Secrets. `kms:Decrypt` só é necessário quando os Secrets usam uma chave KMS própria.
