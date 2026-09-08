# Smoke Test RDS Real

Este roteiro prepara uma verificação manual e mínima do RDS. O script não é executado pela demo local, pela CI ou automaticamente pela Lambda. Ele só aceita execução com confirmação explícita e uma sessão AWS válida.

## Pré-condições

Confirme no Lab, antes de executar:

- a migration criou `Cliente.ativo` em `atendimento_cliente`, com `default=True`;
- o usuário `oficina_auth` existe e sua senha não é `ALTERAR_SENHA`;
- o Secret `oficina-auth` contém `{ "username": "oficina_auth", "password": "..." }` com a mesma senha do usuário;
- o usuário possui somente `CONNECT` em `oficina`, `USAGE` em `public` e `SELECT` em `atendimento_cliente`;
- o cliente usado é exclusivamente sintético, está ativo e seu CPF/ID são fornecidos apenas por variáveis locais;
- rede, security groups e rota Lambda -> RDS estão disponíveis;
- a sessão AWS atual pode ler o Secret.

Não execute migration, SQL de criação de usuário, grants, deploy ou alterações no banco durante este roteiro.

## Configuração local

Defina as variáveis na sessão atual, sem colocá-las no Git ou em mensagens:

```powershell
$env:DB_HOST = "<endpoint-fornecido-pelo-lab>"
$env:DB_PORT = "5432"
$env:POSTGRES_DB = "oficina"
$env:DB_SECRET_ID = "oficina-auth"
$env:SMOKE_TEST_CPF = "<cpf-sintetico-do-lab>"
$env:SMOKE_TEST_CLIENT_ID = "<id-sintetico-do-lab>"
$env:RUN_REAL_RDS_SMOKE = "I_UNDERSTAND_REAL_RDS_SMOKE"
```

O script não imprime CPF, senha, conteúdo do Secret, endpoint, token ou SQL.

## Execução autorizada

Somente depois de confirmar as pré-condições e fornecer/autenticar a sessão AWS:

```powershell
python scripts/smoke_test_rds.py --confirm
```

Saída esperada, sem dados sensíveis:

```text
rds_smoke=passed connectivity=ok client_lookup=ok write_permissions=denied
```

O teste consulta somente `id` e `ativo` por CPF normalizado/formatado, e tenta `INSERT`, `UPDATE` e `DELETE` em transações revertidas. Cada operação deve falhar por falta de privilégio (`42501`). Nenhuma alteração persistida é permitida.

Qualquer falha encerra com código diferente de zero e mensagem genérica. A ausência da confirmação encerra sem acessar AWS ou RDS.
