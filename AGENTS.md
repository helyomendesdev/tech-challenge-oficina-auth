# Repository Guidelines

## Repository Responsibility

This repository owns only the serverless authentication boundary for the Tech Challenge Oficina Phase 3. Its responsibility is to define and evolve CPF-based authentication, the `POST /auth` contract, Client JWT issuing/validation rules, and supporting tests, documentation, and CI/CD.

## Repository Boundaries

Do not implement or change the main Django application, Kubernetes repository, Database repository, or shared infrastructure outside authentication. External outputs must be passed as explicit variables. Do not use `terraform_remote_state`.

Do not implement AWS resources, RDS access, Lambda runtime logic, JWT signing, or Terraform until the corresponding contract or ADR is confirmed. VPC Link work is blocked until the `alb_arn` ownership contract is agreed.

## Official Commands

Use Python 3.11.

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e .[dev]
ruff check .
ruff format --check .
python -m compileall -q .
python -m pytest --cov=oficina_auth --cov-report=term-missing
python scripts/invoke_local.py
python scripts/build_lambda.py
python scripts/inspect_lambda_zip.py build/lambda/oficina_auth_lambda.zip
python -m build
```

## Security Rules

Never log or commit CPF, `Authorization`, tokens, passwords, keys, private keys, secrets, or real production payloads. Examples must be synthetic. JWT payloads represent `Cliente`; `created_by_id` is never a client identity.

## Git and Delivery Rules

Never work directly on `develop` or `main`. Create feature branches from `develop`, keep changes small, and preserve work from other contributors. Do not commit, push, open PRs, merge, deploy, or run `terraform apply` without explicit authorization.

Read `README.md`, `CONTRIBUTING.md`, `.github/workflows/ci.yml`, and this file before editing. Start each task by inspecting current state. Stop if you find a conflict or an unresolved architectural decision.

## Definition of Done

A task is done when the contract and documentation are updated, tests and validation commands pass locally, CI remains compatible, no secrets or personal data were created, and the final report lists changed files, commands run, and results.
