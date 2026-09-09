# ADR-002: Correlação e Observabilidade

## Status

Aceita.

## Contexto

As chamadas de autenticação passam pelo API Gateway e chegam à Lambda. A rastreabilidade precisa funcionar entre serviços sem expor CPF, token ou segredos em logs.

## Decisão

O API Gateway encaminha headers de observabilidade sem modificar seus valores. A Lambda aceita `X-Correlation-Id` quando ele contém um UUIDv4 válido e devolve exatamente o valor recebido. Quando o header está ausente ou inválido, a Lambda gera um novo UUIDv4.

A comparação de UUID pode ser case-insensitive para validação, mas o retorno preserva o texto válido recebido.

`X-Request-Id` identifica uma requisição específica. O `requestId` retornado
no envelope de erro e o header de resposta usam, nesta ordem, o
`X-Request-Id` recebido, `context.aws_request_id` ou um UUID novo. Isso não
substitui a correlação. `traceparent` e `tracestate` são propagados quando
recebidos. `tracestate` nunca é fabricado.

Logs estruturados devem conter `timestamp`, `message`, `http.method`,
`http.route`, `http.status_code`, `service.environment`, `correlation.id`,
`request_id`, `duration_ms`, `outcome` e `auth.motivo`. Logs não devem conter
CPF, `Authorization`, tokens, senhas, chaves ou segredos.

## Consequências

Diagnósticos devem usar `correlation.id`, `X-Request-Id` e headers de tracing. Falhas de autenticação devem manter mensagens genéricas e não revelar se o cliente existe, está inativo ou falhou por outro critério de elegibilidade.
