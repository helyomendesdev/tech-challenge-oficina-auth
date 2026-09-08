# ADR-001: Identidade do Cliente

## Status

Aceita.

## Contexto

O serviço de autenticação emite credenciais para consumo das APIs protegidas da Oficina. A identidade do token precisa representar o cliente autenticado, sem acoplar o domínio de cliente a usuários internos, operadores ou campos de auditoria.

## Decisão

O principal autenticado é `Cliente`. O JWT deve identificar o cliente pelo identificador interno mínimo necessário, `cliente_id`.

`created_by_id` nunca representa a identidade do cliente e não deve ser usado como subject, claim de autorização ou fallback de identidade.

Nenhuma informação pessoal deve ser incluída no JWT além do identificador interno necessário para autorização. CPF, nome, e-mail, telefone e outros dados pessoais ficam fora do token.

## Consequências

Serviços consumidores devem validar autorização a partir de `cliente_id` e demais claims técnicas estritamente necessárias. Qualquer necessidade adicional de dados pessoais deve ser buscada em serviço apropriado, com controle de acesso e sem depender do JWT.
