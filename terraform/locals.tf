locals {
  name_prefix = "oficina-auth-${var.environment}"

  # Sufixo curto por ambiente. As NRQL do dashboard de autenticacao (D6) e do
  # alerta A7 fazem facet por entityName 'oficina-auth-cpf-hml' / '-prd', e no
  # New Relic a entity de uma Lambda e o nome da function -- por isso a function
  # foge do name_prefix e usa este nome. Requisito L8.
  env_short = {
    dev         = "dev"
    homologacao = "hml"
    producao    = "prd"
  }

  function_name = "oficina-auth-cpf-${local.env_short[var.environment]}"

  # Requisito L1: a New Relic Lambda Layer so entra quando o ARN da layer e a
  # conta forem informados. Sem isso a function sobe igual a antes, sem wrapper.
  new_relic_enabled = var.new_relic_layer_arn != null && var.new_relic_account_id != null

  lambda_handler_original = "oficina_auth.handlers.auth.lambda_handler"

  new_relic_environment = local.new_relic_enabled ? merge(
    {
      NEW_RELIC_ACCOUNT_ID                   = var.new_relic_account_id
      NEW_RELIC_LAMBDA_HANDLER               = local.lambda_handler_original
      NEW_RELIC_EXTENSION_SEND_FUNCTION_LOGS = "true"
      NEW_RELIC_DISTRIBUTED_TRACING_ENABLED  = "true"
    },
    # A license key nunca vai em texto puro: a extensao le do Secrets Manager.
    var.new_relic_license_key_secret_id == null ? {} : {
      NEW_RELIC_LICENSE_KEY_SECRET_ID = var.new_relic_license_key_secret_id
    },
  ) : {}

  tags = merge(var.tags, {
    Project     = "tech-challenge-oficina"
    Component   = "auth"
    Environment = var.environment
    ManagedBy   = "terraform"
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

  # O atributo .arn do log group vem com ":*" no fim, e o access_log_settings do
  # API Gateway recusa esse sufixo.
  api_access_log_group_arn = var.api_gateway_access_log_group_arn != null ? var.api_gateway_access_log_group_arn : (
    var.enable_api_gateway_access_log ? replace(aws_cloudwatch_log_group.api_access[0].arn, ":*", "") : null
  )

  lambda_environment = merge({
    APP_ENV                   = var.environment
    DB_HOST                   = var.rds_endpoint
    DB_PORT                   = tostring(var.rds_port)
    POSTGRES_DB               = var.postgres_db
    DB_SECRET_ID              = var.db_secret_id
    JWT_PRIVATE_KEY_SECRET_ID = var.jwt_private_key_secret_id
  }, local.new_relic_environment)
}
