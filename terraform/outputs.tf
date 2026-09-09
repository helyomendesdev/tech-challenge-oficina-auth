output "lambda_function_name" {
  description = "Auth Lambda function name."
  value       = aws_lambda_function.auth.function_name
}

output "lambda_function_arn" {
  description = "Auth Lambda function ARN."
  value       = aws_lambda_function.auth.arn
}

output "lambda_zip_sha256" {
  description = "SHA-256 checksum supplied and verified for the Lambda ZIP."
  value       = var.lambda_zip_sha256
}

output "rest_api_id" {
  description = "Regional REST API ID."
  value       = aws_api_gateway_rest_api.auth.id
}

output "rest_api_name" {
  description = "Regional REST API name."
  value       = aws_api_gateway_rest_api.auth.name
}

output "rest_api_invoke_url" {
  description = "Non-sensitive base URL for the configured REST API stage."
  value       = "https://${aws_api_gateway_rest_api.auth.id}.execute-api.${var.aws_region}.amazonaws.com/${var.stage_name}"
}

output "auth_invoke_url" {
  description = "Non-sensitive POST /auth URL for smoke-test setup."
  value       = "https://${aws_api_gateway_rest_api.auth.id}.execute-api.${var.aws_region}.amazonaws.com/${var.stage_name}/auth"
}

output "stage_name" {
  description = "Configured REST API stage name."
  value       = aws_api_gateway_stage.auth.stage_name
}

output "vpc_link_id" {
  description = "Auth VPC Link V2 ID."
  value       = aws_apigatewayv2_vpc_link.auth.id
}

output "lambda_security_group_id" {
  description = "Security Group created for the Auth Lambda."
  value       = aws_security_group.lambda.id
}

output "vpc_link_security_group_id" {
  description = "Security Group created for the Auth VPC Link."
  value       = aws_security_group.vpc_link.id
}

output "lambda_log_group_name" {
  description = "CloudWatch Log Group created for the Auth Lambda."
  value       = aws_cloudwatch_log_group.lambda.name
}

output "api_gateway_access_log_group_name" {
  description = "CloudWatch Log Group created for API Gateway access logs."
  value       = aws_cloudwatch_log_group.api_gateway_access.name
}
