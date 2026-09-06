resource "aws_api_gateway_rest_api" "auth" {
  name                         = "${local.name_prefix}-api"
  description                  = "Regional REST API for Oficina authentication and Django routes."
  disable_execute_api_endpoint = false

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = local.tags
}

resource "aws_api_gateway_resource" "auth" {
  rest_api_id = aws_api_gateway_rest_api.auth.id
  parent_id   = aws_api_gateway_rest_api.auth.root_resource_id
  path_part   = "auth"
}

resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.auth.id
  parent_id   = aws_api_gateway_rest_api.auth.root_resource_id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "auth_post" {
  rest_api_id   = aws_api_gateway_rest_api.auth.id
  resource_id   = aws_api_gateway_resource.auth.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.auth.id
  resource_id             = aws_api_gateway_resource.auth.id
  http_method             = aws_api_gateway_method.auth_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.auth.invoke_arn
}

resource "aws_lambda_permission" "api_gateway_auth" {
  statement_id  = "AllowApiGatewayInvokeAuth"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auth.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.auth.execution_arn}/*/POST/auth"
}

resource "aws_api_gateway_method" "root_any" {
  rest_api_id   = aws_api_gateway_rest_api.auth.id
  resource_id   = aws_api_gateway_rest_api.auth.root_resource_id
  http_method   = "ANY"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "root_private" {
  rest_api_id             = aws_api_gateway_rest_api.auth.id
  resource_id             = aws_api_gateway_rest_api.auth.root_resource_id
  http_method             = aws_api_gateway_method.root_any.http_method
  integration_http_method = "ANY"
  type                    = "HTTP_PROXY"
  connection_type         = "VPC_LINK"
  connection_id           = aws_apigatewayv2_vpc_link.auth.id
  integration_target      = var.alb_arn
  uri                     = local.alb_uri
  passthrough_behavior    = "WHEN_NO_MATCH"

  request_templates = {
    "*/*" = local.root_path_override_template
  }
}

resource "aws_api_gateway_method" "proxy_any" {
  rest_api_id   = aws_api_gateway_rest_api.auth.id
  resource_id   = aws_api_gateway_resource.proxy.id
  http_method   = "ANY"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.proxy" = true
  }
}

resource "aws_api_gateway_integration" "proxy_private" {
  rest_api_id             = aws_api_gateway_rest_api.auth.id
  resource_id             = aws_api_gateway_resource.proxy.id
  http_method             = aws_api_gateway_method.proxy_any.http_method
  integration_http_method = "ANY"
  type                    = "HTTP_PROXY"
  connection_type         = "VPC_LINK"
  connection_id           = aws_apigatewayv2_vpc_link.auth.id
  integration_target      = var.alb_arn
  uri                     = local.alb_uri
  passthrough_behavior    = "WHEN_NO_MATCH"

  request_templates = {
    "*/*" = local.proxy_path_override_template
  }
}

resource "aws_api_gateway_deployment" "auth" {
  rest_api_id = aws_api_gateway_rest_api.auth.id

  triggers = {
    redeployment = sha1(jsonencode({
      api_id              = aws_api_gateway_rest_api.auth.id
      auth_method         = aws_api_gateway_method.auth_post.id
      auth_integration    = aws_api_gateway_integration.auth_lambda.id
      root_method         = aws_api_gateway_method.root_any.id
      root_integration    = aws_api_gateway_integration.root_private.id
      proxy_method        = aws_api_gateway_method.proxy_any.id
      proxy_integration   = aws_api_gateway_integration.proxy_private.id
      vpc_link_id         = aws_apigatewayv2_vpc_link.auth.id
      alb_arn             = var.alb_arn
      alb_uri             = local.alb_uri
      root_path_template  = local.root_path_override_template
      proxy_path_template = local.proxy_path_override_template
      stage_name          = var.stage_name
    }))
  }

  depends_on = [
    aws_api_gateway_integration.auth_lambda,
    aws_api_gateway_integration.root_private,
    aws_api_gateway_integration.proxy_private,
  ]

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "auth" {
  rest_api_id   = aws_api_gateway_rest_api.auth.id
  deployment_id = aws_api_gateway_deployment.auth.id
  stage_name    = var.stage_name
  tags          = local.tags

  dynamic "access_log_settings" {
    for_each = var.api_gateway_access_log_group_arn == null ? [] : [var.api_gateway_access_log_group_arn]

    content {
      destination_arn = access_log_settings.value
      format = jsonencode({
        requestId         = "$context.requestId"
        extendedRequestId = "$context.extendedRequestId"
        httpMethod        = "$context.httpMethod"
        path              = "$context.path"
        status            = "$context.status"
        responseLatency   = "$context.responseLatency"
      })
    }
  }
}
