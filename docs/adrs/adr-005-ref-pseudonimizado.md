# ADR-005: Referência pseudonimizada do Cliente

## Status

Dependente de configuração segura externa.

## Contexto

Logs de autenticação precisam permitir correlação operacional sem registrar
CPF em claro. O repositório não possui ainda um provider seguro para a chave
de pseudonimização nem um contrato final de retenção/rotação.

## Decisão

O Auth não emitirá `cliente.ref` enquanto essa configuração não estiver
disponível. Não será usado CPF em claro, hash sem chave, salt fixo ou qualquer
valor derivado que possa ser revertido ou correlacionado fora de um mecanismo
controlado.

A implementação futura deve receber uma chave por provider de segredo com
rotação definida e produzir uma referência pseudonimizada, preferencialmente
por um MAC com contexto/versionamento. A chave não pode aparecer em variável
de log, Terraform, código, teste ou ZIP.

## Consequências

Os logs atuais continuam sem `cliente.ref`, CPF e identificadores pessoais.
O grupo precisa aprovar o provider, o Secret, a rotação e o formato antes de
habilitar esse campo. Essa lacuna não altera as claims JWT nem a regra de
autenticação.
