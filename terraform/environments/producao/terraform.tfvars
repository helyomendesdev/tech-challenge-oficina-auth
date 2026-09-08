aws_region = "us-east-1"
environment = "producao"

vpc_id             = "vpc-0123456789abcdef0"
private_subnet_ids = ["subnet-0123456789abcdef0", "subnet-0123456789abcdef1"]

lambda_execution_role_arn = "arn:aws:iam::000000000000:role/oficina-auth-lambda"

rds_endpoint         = "postgres.example.internal"
rds_port             = 5432
rds_security_group_id = "sg-0123456789abcdef0"

alb_arn             = "arn:aws:elasticloadbalancing:us-east-1:000000000000:loadbalancer/app/oficina-alb/0123456789abcdef"
alb_dns_name        = "internal-oficina-alb.example.internal"
alb_security_group_id = "sg-0123456789abcdef1"
alb_port            = 8000
alb_protocol        = "HTTP"

db_secret_id               = "oficina-auth-producao"
jwt_private_key_secret_id  = "oficina-auth-jwt-key-producao"
postgres_db                = "oficina"

lambda_zip_path   = "../build/lambda/oficina_auth_lambda.zip"
lambda_zip_sha256 = "0000000000000000000000000000000000000000000000000000000000000000"

lambda_memory_size        = 512
lambda_timeout_seconds    = 10
lambda_log_retention_days = 14
lambda_architecture       = "x86_64"
stage_name                = "producao"

api_gateway_access_log_group_arn = null

tags = {
  Owner      = "Lucas"
  CostCenter = "tech-challenge"
}
