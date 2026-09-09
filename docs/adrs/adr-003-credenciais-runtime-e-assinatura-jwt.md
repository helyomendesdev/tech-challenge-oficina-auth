# ADR-003: Credenciais de Runtime e Assinatura JWT

## Status

Aceita em 2026-09-02. Revisada em 2026-09-09 com o contrato observado no primeiro deploy real (coluna de consulta, TLS e tipo do claim `cliente_id`).

## Escopo

Este ADR registra os contratos consumidos pelo serviço Auth. Os adapters de PostgreSQL e Secrets Manager e o Terraform específico do Auth podem ser implementados aqui. Provisionamento de RDS, VPC, subnets, NAT, EKS e ALB compartilhados permanece nos repositórios Database e K8s; o Auth não cria esses recursos.

## Decisão

O banco PostgreSQL usado pela autenticação é `oficina`. O endpoint e a porta são recebidos por `DB_HOST` e `DB_PORT`, e o nome do banco por `POSTGRES_DB`.

A Lambda recebe o identificador de credenciais em `DB_SECRET_ID`, aceitando nome ou ARN. O exemplo fictício é `oficina-auth`. O Secret de banco tem JSON no formato `{ "username": "oficina_auth", "password": "..." }`. `POSTGRES_USER` e `POSTGRES_PASSWORD` não são recebidos diretamente pela Lambda. O usuário `oficina_auth` deve possuir somente `CONNECT` no banco `oficina`, `USAGE` no schema utilizado e `SELECT` em `atendimento_cliente`; os grants são responsabilidade da infraestrutura.

A consulta usa a coluna `documento` de `atendimento_cliente` (varchar 14, única), que guarda o CPF com ou sem pontuação; por isso o Auth consulta os dois formatos e lê apenas `id` e `ativo`. A conexão com o PostgreSQL exige TLS: o RDS PostgreSQL 17 aplica `rds.force_ssl=1` e recusa conexões sem criptografia, então o adapter `pg8000` conecta com `ssl_context=True` (verificação padrão de certificado).

O JWT de Cliente usa `iss=oficina-auth`, `aud=oficina-api` e expiração de 900 segundos. A chave privada fica em Secret separado, pertencente ao Auth, identificado por `JWT_PRIVATE_KEY_SECRET_ID`. Nenhuma chave real é hardcoded ou versionada. O claim `cliente_id` é emitido como inteiro (o `id` de `atendimento_cliente`) e `sub` como `cliente:<id>`; o consumidor Django (`atendimento/authentication.py`) rejeita com 401 um `cliente_id` que não seja inteiro, e o verificador local aplica a mesma regra.

Valores externos são inputs explícitos. Os inputs futuros consumidos pelo Auth são `vpc_id`, `private_subnet_ids`, `alb_arn`, `alb_security_group_id`, `rds_endpoint`, `rds_port` e `rds_security_group_id`. O ALB é gerenciado pelo Terraform do repositório K8s, enquanto o Auth gerencia seu VPC Link e as regras direcionadas aos Security Groups externos. `alb_listener_arn` não é input do REST VPC Link V2.

## Consequências

O Auth pode documentar e validar os nomes dos contratos sem possuir credenciais, banco ou recursos de rede. Integrações futuras devem obter credenciais em runtime e nunca replicá-las em variáveis de ambiente, código, logs ou artefatos.
