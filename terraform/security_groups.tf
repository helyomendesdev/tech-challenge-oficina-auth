resource "aws_security_group" "lambda" {
  name        = "${local.name_prefix}-lambda-sg"
  description = "Egress restricted to Auth dependencies."
  vpc_id      = var.vpc_id

  ingress = []
  egress  = []

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-lambda-sg"
  })
}

resource "aws_security_group" "vpc_link" {
  name        = "${local.name_prefix}-vpc-link-sg"
  description = "Egress restricted to the existing internal ALB."
  vpc_id      = var.vpc_id

  ingress = []
  egress  = []

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-vpc-link-sg"
  })
}

resource "aws_vpc_security_group_egress_rule" "lambda_to_rds" {
  security_group_id            = aws_security_group.lambda.id
  referenced_security_group_id = var.rds_security_group_id
  from_port                    = var.rds_port
  to_port                      = var.rds_port
  ip_protocol                  = "tcp"
  description                  = "Lambda to the existing PostgreSQL Security Group."
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_lambda" {
  security_group_id            = var.rds_security_group_id
  referenced_security_group_id = aws_security_group.lambda.id
  from_port                    = var.rds_port
  to_port                      = var.rds_port
  ip_protocol                  = "tcp"
  description                  = "Auth Lambda access to PostgreSQL."
}

resource "aws_vpc_security_group_egress_rule" "lambda_to_aws_https" {
  security_group_id = aws_security_group.lambda.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  description       = "Lambda access to AWS APIs and New Relic through existing NAT."
}

resource "aws_vpc_security_group_egress_rule" "vpc_link_to_alb" {
  security_group_id            = aws_security_group.vpc_link.id
  referenced_security_group_id = var.alb_security_group_id
  from_port                    = var.alb_port
  to_port                      = var.alb_port
  ip_protocol                  = "tcp"
  description                  = "VPC Link to the existing internal ALB."
}

resource "aws_vpc_security_group_ingress_rule" "alb_from_vpc_link" {
  security_group_id            = var.alb_security_group_id
  referenced_security_group_id = aws_security_group.vpc_link.id
  from_port                    = var.alb_port
  to_port                      = var.alb_port
  ip_protocol                  = "tcp"
  description                  = "Existing ALB access from the Auth VPC Link."
}
