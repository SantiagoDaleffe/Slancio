terraform {
  required_version = ">= 1.5.0"

  required_providers {
    koyeb = {
      source  = "koyeb/koyeb"
      version = "~> 1.0"
    }
  }
}

provider "koyeb" {
  api_token = var.koyeb_token
}