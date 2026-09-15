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

  # Uma GitHub Variable nao cadastrada chega como TF_VAR_x="" -- string vazia, nao
  # null. Sem normalizar, "" passaria pelo teste de null e quebraria a validacao de
  # ARN, ou criaria um aws_api_gateway_account com ARN vazio. Estes locals sao a
  # unica forma de ler estas quatro entradas no resto do modulo.
  nr_layer_arn         = trimspace(coalesce(var.new_relic_layer_arn, "")) == "" ? null : trimspace(var.new_relic_layer_arn)
  nr_account_id        = trimspace(coalesce(var.new_relic_account_id, "")) == "" ? null : trimspace(var.new_relic_account_id)
  nr_license_secret    = trimspace(coalesce(var.new_relic_license_key_secret_id, "")) == "" ? null : trimspace(var.new_relic_license_key_secret_id)
  apigw_cw_role_arn    = trimspace(coalesce(var.api_gateway_cloudwatch_role_arn, "")) == "" ? null : trimspace(var.api_gateway_cloudwatch_role_arn)
  access_log_arn_input = trimspace(coalesce(var.api_gateway_access_log_group_arn, "")) == "" ? null : trimspace(var.api_gateway_access_log_group_arn)

  # Requisito L1: a New Relic Lambda Layer so entra quando o ARN da layer e a
  # conta forem informados. Sem isso a function sobe igual a antes, sem wrapper.
  new_relic_enabled = local.nr_layer_arn != null && local.nr_account_id != null

  lambda_handler_original = "oficina_auth.handlers.auth.lambda_handler"

  new_relic_environment = local.new_relic_enabled ? merge(
    {
      NEW_RELIC_ACCOUNT_ID                   = local.nr_account_id
      NEW_RELIC_LAMBDA_HANDLER               = local.lambda_handler_original
      NEW_RELIC_EXTENSION_SEND_FUNCTION_LOGS = "true"
      NEW_RELIC_DISTRIBUTED_TRACING_ENABLED  = "true"
    },
    # A license key nunca vai em texto puro: a extensao le do Secrets Manager.
    local.nr_license_secret == null ? {} : {
      NEW_RELIC_LICENSE_KEY_SECRET_ID = local.nr_license_secret
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
  api_access_log_group_arn = local.access_log_arn_input != null ? local.access_log_arn_input : (
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
