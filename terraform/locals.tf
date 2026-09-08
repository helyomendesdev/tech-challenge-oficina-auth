locals {
  name_prefix = "oficina-auth-${var.environment}"

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

  lambda_environment = {
    APP_ENV                   = var.environment
    DB_HOST                   = var.rds_endpoint
    DB_PORT                   = tostring(var.rds_port)
    POSTGRES_DB               = var.postgres_db
    DB_SECRET_ID              = var.db_secret_id
    JWT_PRIVATE_KEY_SECRET_ID = var.jwt_private_key_secret_id
  }

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
