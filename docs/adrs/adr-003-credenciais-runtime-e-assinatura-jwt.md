# ADR-003: Credenciais de Runtime e Assinatura JWT

## Status

Aceita em 2026-09-02.

## Escopo

Este ADR registra somente os contratos consumidos pelo serviço Auth. Os adapters de PostgreSQL e Secrets Manager podem ser implementados aqui; provisionamento de banco, grants, Terraform, VPC Link e demais recursos AWS pertencem às etapas de infraestrutura.

## Decisão

O banco PostgreSQL usado pela autenticação é `oficina`. O endpoint e a porta são recebidos por `DB_HOST` e `DB_PORT`, e o nome do banco por `POSTGRES_DB`.

A Lambda recebe o identificador de credenciais em `DB_SECRET_ID`, aceitando nome ou ARN. O exemplo fictício é `oficina-auth`. O Secret de banco tem JSON no formato `{ "username": "oficina_auth", "password": "..." }`. `POSTGRES_USER` e `POSTGRES_PASSWORD` não são recebidos diretamente pela Lambda. O usuário `oficina_auth` deve possuir somente `CONNECT` no banco `oficina`, `USAGE` no schema utilizado e `SELECT` em `atendimento_cliente`; os grants são responsabilidade da infraestrutura.

O JWT de Cliente usa `iss=oficina-auth`, `aud=oficina-api` e expiração de 900 segundos. A chave privada fica em Secret separado, pertencente ao Auth, identificado por `JWT_PRIVATE_KEY_SECRET_ID`. Nenhuma chave real é hardcoded ou versionada.

Valores externos são inputs explícitos. Os inputs futuros consumidos pelo Auth são `vpc_id`, `private_subnet_ids`, `alb_arn`, `alb_security_group_id`, `rds_endpoint`, `rds_port` e `rds_security_group_id`. O ALB é gerenciado pelo Terraform do repositório K8s. `alb_listener_arn` não é input do REST VPC Link V2.

## Consequências

O Auth pode documentar e validar os nomes dos contratos sem possuir credenciais, banco ou recursos de rede. Integrações futuras devem obter credenciais em runtime e nunca replicá-las em variáveis de ambiente, código, logs ou artefatos.
