# ADR-004: New Relic e access logs do API Gateway

## Status

Aceito para a infraestrutura do Auth.

## Contexto

A Lambda Python 3.11 precisa ser instrumentada sem que licença, CPF, token,
`Authorization` ou outros segredos sejam incluídos no Terraform ou nos logs.
O API Gateway REST também precisa de access logs estruturados para os ambientes
de homologação e produção.

## Decisão

- O account ID, o ARN versionado do layer e o nome/ARN do Secret da licença são
  variáveis Terraform. O exemplo alinhado é account `8430077`, layer
  `NewRelicPython311:90` em `us-east-1` e Secret `oficina/newrelic-license`.
- O handler Terraform é `newrelic_lambda_wrapper.handler`; o handler original
  fica em `NEW_RELIC_LAMBDA_HANDLER`.
- A licença é resolvida em runtime por `NEW_RELIC_LICENSE_KEY_SECRET`. O
  Terraform não usa `NEW_RELIC_LICENSE_KEY`, não lê Secret com data source e
  não cria Secret ou Secret Version.
- `NEW_RELIC_EXTENSION_SEND_FUNCTION_LOGS` permanece habilitado, mas a
  aplicação só emite logs JSON sanitizados. A role externa deve permitir
  `secretsmanager:GetSecretValue` nos Secrets necessários.
- O Auth cria e configura por padrão o Log Group de access logs do API Gateway,
  com retenção. O formato contém request ID, método, path, status, latências,
  `error.message` e `service.environment`.
- `homologacao` e `producao` são os valores de serviço; os sufixos AWS e nomes
  da Lambda/New Relic são `hml` e `prd`.

## Consequências

A role de logs do API Gateway no nível da conta continua sendo uma configuração
externa. O grupo, a licença e as permissões reais não são verificados por
`terraform validate` ou pelos testes com mock provider.
