locals {
  environment_suffix  = var.environment == "homologacao" ? "hml" : "prd"
  service_environment = var.environment
  name_prefix         = "oficina-auth-cpf-${local.environment_suffix}"

  tags = merge(var.tags, {
    Project            = "tech-challenge-oficina"
    Component          = "auth"
    Environment        = local.environment_suffix
    ServiceEnvironment = local.service_environment
    ManagedBy          = "terraform"
  })

  alb_uri = format(
    "%s://%s:%d",
    lower(var.alb_protocol),
    var.alb_dns_name,
    var.alb_port,
  )

  vpc_link_name = format(
    "%s-vpc-%s",
    local.name_prefix,
    substr(sha1(jsonencode({
      private_subnet_ids = var.private_subnet_ids
      security_group_id  = aws_security_group.vpc_link.id
    })), 0, 8),
  )

  lambda_environment = {
    APP_ENV                                = var.environment
    DB_HOST                                = var.rds_endpoint
    DB_PORT                                = tostring(var.rds_port)
    POSTGRES_DB                            = var.postgres_db
    DB_SECRET_ID                           = var.db_secret_id
    JWT_PRIVATE_KEY_SECRET_ID              = var.jwt_private_key_secret_id
    NEW_RELIC_ACCOUNT_ID                   = tostring(var.new_relic_account_id)
    NEW_RELIC_APP_NAME                     = local.name_prefix
    NEW_RELIC_APM_LAMBDA_MODE              = "true"
    NEW_RELIC_LAMBDA_EXTENSION_ENABLED     = "true"
    NEW_RELIC_EXTENSION_SEND_FUNCTION_LOGS = "true"
    NEW_RELIC_LAMBDA_HANDLER               = "oficina_auth.handlers.auth.lambda_handler"
    NEW_RELIC_LICENSE_KEY_SECRET           = var.new_relic_license_key_secret_id
  }

  api_gateway_access_log_format = jsonencode({
    requestId             = "$context.requestId"
    extendedRequestId     = "$context.extendedRequestId"
    httpMethod            = "$context.httpMethod"
    path                  = "$context.path"
    status                = "$context.status"
    responseLatency       = "$context.responseLatency"
    integrationLatency    = "$context.integrationLatency"
    "error.message"       = "$context.error.message"
    "service.environment" = local.service_environment
  })

  root_path_override_template = <<-VTL
    #set($context.requestOverride.path = "/")
    $input.body
  VTL

  proxy_path_override_template = <<-VTL
    #set($proxyPath = $input.params('proxy'))
    #set($context.requestOverride.path = "/$proxyPath")
    $input.body
  VTL
}
