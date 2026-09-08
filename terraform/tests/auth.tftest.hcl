mock_provider "aws" {}

variables {
  aws_region                = "us-east-1"
  environment               = "dev"
  vpc_id                    = "vpc-0123456789abcdef0"
  private_subnet_ids        = ["subnet-0123456789abcdef0", "subnet-abcdef0123456789a"]
  lambda_execution_role_arn = "arn:aws:iam::000000000000:role/oficina-auth-lambda"
  rds_endpoint              = "db.synthetic.internal"
  rds_port                  = 5432
  rds_security_group_id     = "sg-0123456789abcdef0"
  alb_arn                   = "arn:aws:elasticloadbalancing:us-east-1:000000000000:loadbalancer/app/synthetic/0123456789abcdef"
  alb_dns_name              = "internal-synthetic-alb.local"
  alb_security_group_id     = "sg-abcdef0123456789a"
  alb_port                  = 8000
  alb_protocol              = "HTTP"
  db_secret_id              = "oficina-auth"
  jwt_private_key_secret_id = "oficina-auth-jwt-private-key"
  postgres_db               = "oficina"
  lambda_zip_path           = "../build/lambda/oficina_auth_lambda.zip"
  lambda_zip_sha256         = filesha256("../build/lambda/oficina_auth_lambda.zip")
  lambda_memory_size        = 512
  lambda_timeout_seconds    = 10
  lambda_log_retention_days = 14
  lambda_architecture       = "x86_64"
  stage_name                = "dev"
  tags                      = { Test = "synthetic" }
}

run "valid_auth_topology" {
  command = plan

  assert {
    condition     = toset(aws_api_gateway_rest_api.auth.endpoint_configuration[0].types) == toset(["REGIONAL"])
    error_message = "The Auth API must be a regional REST API."
  }

  assert {
    condition     = aws_api_gateway_resource.auth.path_part == "auth"
    error_message = "The explicit auth resource must remain separate."
  }

  assert {
    condition     = aws_api_gateway_resource.proxy.path_part == "{proxy+}"
    error_message = "The Django proxy resource must be catch-all."
  }

  assert {
    condition     = aws_api_gateway_method.auth_post.http_method == "POST"
    error_message = "POST /auth must use POST."
  }

  assert {
    condition     = aws_api_gateway_integration.auth_lambda.type == "AWS_PROXY" && aws_api_gateway_integration.auth_lambda.integration_http_method == "POST"
    error_message = "POST /auth must invoke the Lambda through AWS_PROXY."
  }

  assert {
    condition     = aws_api_gateway_integration.root_private.type == "HTTP_PROXY" && aws_api_gateway_integration.root_private.connection_type == "VPC_LINK"
    error_message = "The root proxy must use a private HTTP proxy integration."
  }

  assert {
    condition     = aws_api_gateway_integration.proxy_private.integration_target == var.alb_arn
    error_message = "The proxy must target the externally supplied ALB ARN."
  }

  assert {
    condition     = aws_api_gateway_integration.proxy_private.uri == "http://internal-synthetic-alb.local:8000"
    error_message = "The proxy URI must use the supplied ALB protocol, DNS name, and port."
  }

  assert {
    condition     = strcontains(aws_api_gateway_integration.proxy_private.request_templates["*/*"], "requestOverride.path")
    error_message = "The REST private integration must remove the stage from the forwarded path."
  }

  assert {
    condition     = aws_apigatewayv2_vpc_link.auth.subnet_ids == toset(var.private_subnet_ids)
    error_message = "The VPC Link must use the externally supplied private subnets."
  }

  assert {
    condition     = aws_lambda_function.auth.runtime == "python3.11" && aws_lambda_function.auth.handler == "oficina_auth.handlers.auth.lambda_handler"
    error_message = "The Lambda runtime and handler must match the Auth artifact."
  }

  assert {
    condition     = aws_lambda_function.auth.vpc_config[0].subnet_ids == toset(var.private_subnet_ids)
    error_message = "The Lambda must run in the supplied private subnets."
  }

  assert {
    condition     = aws_vpc_security_group_egress_rule.lambda_to_rds.from_port == var.rds_port && aws_vpc_security_group_ingress_rule.rds_from_lambda.from_port == var.rds_port
    error_message = "Lambda to RDS rules must use only the configured PostgreSQL port."
  }

  assert {
    condition     = aws_vpc_security_group_egress_rule.vpc_link_to_alb.from_port == var.alb_port && aws_vpc_security_group_ingress_rule.alb_from_vpc_link.from_port == var.alb_port
    error_message = "VPC Link to ALB rules must use only the configured ALB port."
  }
}

run "reject_non_oficina_database" {
  command = plan

  variables {
    postgres_db = "other"
  }

  expect_failures = [var.postgres_db]
}

run "reject_invalid_rds_port" {
  command = plan

  variables {
    rds_port = 0
  }

  expect_failures = [var.rds_port]
}

run "reject_port_above_range" {
  command = plan

  variables {
    alb_port = 65536
  }

  expect_failures = [var.alb_port]
}

run "reject_empty_private_subnets" {
  command = plan

  variables {
    private_subnet_ids = []
  }

  expect_failures = [var.private_subnet_ids]
}

run "reject_invalid_alb_protocol" {
  command = plan

  variables {
    alb_protocol = "TCP"
  }

  expect_failures = [var.alb_protocol]
}

run "reject_invalid_environment" {
  command = plan

  variables {
    environment = "qa"
  }

  expect_failures = [var.environment]
}

run "reject_invalid_stage" {
  command = plan

  variables {
    stage_name = "stage with spaces"
  }

  expect_failures = [var.stage_name]
}

run "reject_invalid_memory" {
  command = plan

  variables {
    lambda_memory_size = 127
  }

  expect_failures = [var.lambda_memory_size]
}

run "reject_invalid_timeout" {
  command = plan

  variables {
    lambda_timeout_seconds = 901
  }

  expect_failures = [var.lambda_timeout_seconds]
}
