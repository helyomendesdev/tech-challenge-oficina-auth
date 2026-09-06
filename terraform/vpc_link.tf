resource "aws_apigatewayv2_vpc_link" "auth" {
  name               = local.vpc_link_name
  security_group_ids = [aws_security_group.vpc_link.id]
  subnet_ids         = var.private_subnet_ids
  tags               = local.tags

  lifecycle {
    create_before_destroy = true
  }
}
