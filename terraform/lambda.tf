resource "aws_lambda_function" "auth" {
  function_name    = local.name_prefix
  description      = "CPF authentication Lambda for Oficina."
  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)
  role             = var.lambda_execution_role_arn
  runtime          = "python3.11"
  handler          = "newrelic_lambda_wrapper.handler"
  architectures    = [var.lambda_architecture]
  layers           = [var.new_relic_layer_arn]
  memory_size      = var.lambda_memory_size
  timeout          = var.lambda_timeout_seconds
  publish          = true

  environment {
    variables = local.lambda_environment
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  tags = merge(local.tags, {
    "NR.Apm.Lambda.Mode" = "true"
  })

  lifecycle {
    precondition {
      condition     = filesha256(var.lambda_zip_path) == lower(var.lambda_zip_sha256)
      error_message = "lambda_zip_sha256 must match the ZIP at lambda_zip_path."
    }
  }
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${aws_lambda_function.auth.function_name}"
  retention_in_days = var.lambda_log_retention_days
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "api_gateway_access" {
  name              = "/aws/apigateway/${local.name_prefix}"
  retention_in_days = var.api_gateway_access_log_retention_days
  tags              = local.tags
}
