# Repository Guidelines

## Repository Responsibility

This repository owns the authentication boundary and the Auth-specific infrastructure for the Tech Challenge Oficina Phase 3. Its responsibility is to define and evolve CPF-based authentication, the `POST /auth` contract, Client JWT issuing/validation rules, Lambda configuration, API Gateway REST routes, VPC Link V2, directed network rules, CloudWatch resources for Auth, and supporting tests, documentation, and CI/CD.

## Repository Boundaries

Do not implement or change the main Django application, Kubernetes repository, Database repository, or shared infrastructure outside authentication. Auth Terraform may live under `terraform/` and may create the Lambda, regional REST API Gateway, routes, VPC Link V2, Auth-specific Security Groups, directed rules to external RDS/ALB Security Groups, and Auth CloudWatch resources. External outputs must be passed as explicit variables. Do not use `terraform_remote_state`.

Do not create a VPC, subnet, NAT Gateway, EKS, ALB, RDS, IAM Role, Secret, or Secret Version in this repository. The K8s repository owns shared VPC, subnets, NAT, EKS, and ALB; the Database repository owns RDS. Auth consumes explicit values such as `vpc_id`, private subnet IDs, `alb_arn`, `alb_security_group_id`, `rds_endpoint`, `rds_port`, and `rds_security_group_id`. `alb_listener_arn` is not a REST VPC Link V2 input. Runtime adapters for PostgreSQL and Secrets Manager are allowed, but real access is exercised only after external infrastructure is available. JWT signing and verification remain provider-based; the private key must come from a separate Auth-owned runtime Secret and must never be hardcoded.

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
terraform -chdir=terraform fmt -check -recursive
terraform -chdir=terraform init -backend=false
terraform -chdir=terraform validate
```

## Security Rules

Never log or commit CPF, `Authorization`, tokens, passwords, keys, private keys, secrets, database credentials, or real production payloads. The Lambda must not receive `POSTGRES_USER` or `POSTGRES_PASSWORD` directly. Examples must be synthetic. JWT payloads represent `Cliente`; `created_by_id` is never a client identity.

## Ownership and Delivery

Lucas delivers Auth code, the reproducible Lambda build, Auth Terraform, and the commands needed to validate it. Hélio owns CI/CD workflows, branch protection, and authorized plan/apply/deploy automation. Luís owns New Relic, dashboards, alerts, and general observability; Auth still owns its JSON log and trace propagation contract. Future workflow changes must respect this split and must not block Auth Terraform.

The API Gateway forwards `Authorization`, `X-Correlation-Id`, `X-Request-Id`, `traceparent`, and `tracestate` without modification. The Lambda validates or generates UUIDv4 correlation IDs, preserves valid received text in the response, never logs CPF in clear text, and never fabricates `tracestate`.

## Git and Delivery Rules

Never work directly on `develop` or `main`. Create feature branches from `develop`, keep changes small, and preserve work from other contributors. Do not commit, push, open PRs, merge, deploy, or run `terraform apply` without explicit authorization.

Read `README.md`, `CONTRIBUTING.md`, `.github/workflows/ci.yml`, and this file before editing. Start each task by inspecting current state. Stop if you find a conflict or an unresolved architectural decision.

## Definition of Done

A task is done when the contract and documentation are updated, relevant code and Terraform validations pass locally, CI remains compatible, no secrets or personal data were created, shared resources remain external, and the final report lists changed files, commands run, and results.
