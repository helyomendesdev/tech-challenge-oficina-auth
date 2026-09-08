terraform {
  required_version = ">= 1.5.0"

  # S3 backend with DynamoDB lock. Partial configuration: bucket, key,
  # region and dynamodb_table are supplied by CI via -backend-config.
  backend "s3" {}

  required_providers {
    aws = {
      source = "hashicorp/aws"
      # Keep Auth aligned with the shared K8s infrastructure validation.
      version = "= 6.61.0"
    }
  }
}
