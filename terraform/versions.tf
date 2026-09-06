terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source = "hashicorp/aws"
      # Keep Auth aligned with the shared K8s infrastructure validation.
      version = "= 6.61.0"
    }
  }
}
