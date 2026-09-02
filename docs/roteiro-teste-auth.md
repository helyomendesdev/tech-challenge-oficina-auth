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
- Caso `400 invalid CPF`: retorna `status=400` com mensagem pública `Payload ou CPF invalido.`.
- Caso `401 generic client failure`: retorna `status=401` com mensagem pública `Credenciais invalidas ou cliente nao elegivel.`.
- Caso `200 with provided X-Correlation-Id`: reaproveita o `X-Correlation-Id` recebido.
- Caso `200 with generated X-Correlation-Id`: gera novo UUIDv4 quando o header está ausente.
- Logs aparecem em JSON, uma linha por cenário, com `correlation.id`, `request_id`, `duration_ms`, `status_code` e `outcome`.
- A saída não mostra CPF completo, token real, `Authorization`, chave ou body completo.

## Build da Lambda

```bash
python scripts/build_lambda.py
python scripts/inspect_lambda_zip.py build/lambda/oficina_auth_lambda.zip
```

Evidências esperadas:

- Artefato em `build/lambda/oficina_auth_lambda.zip`.
- Checksum em `build/lambda/oficina_auth_lambda.zip.sha256`.
- Inspeção com `zip_inspection=ok`.
- Dependências empacotadas como wheels Linux `manylinux2014_x86_64` para Python 3.11.
- Dois builds consecutivos devem produzir o mesmo SHA-256.
- ZIP sem `tests/`, `.git/`, `.env`, caches, `.venv`, `dist/`, `build/`, arquivos `.pem`, `.key`, `.pyc` ou `.pyo`.

## Validação Completa

```bash
python -m compileall -q .
ruff check .
ruff format --check .
python -m pytest --cov=oficina_auth --cov-report=term-missing --cov-fail-under=90
python -m build
```

## Diferença para AWS Real

A demonstração local usa `InMemoryClientRepository` e chave RSA efêmera apenas por composição explícita em `scripts/invoke_local.py`. A Lambda em produção não usa adapter em memória por fallback silencioso. Integrações reais com banco, secrets, API Gateway implantado, Authorizer e Terraform pertencem a etapas futuras.
