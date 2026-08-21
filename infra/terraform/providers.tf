terraform {
  required_version = ">= 1.5.0"

  required_providers {
    upstash = {
      source  = "upstash/upstash"
      version = "~> 1.5.0"
    }
    supabase = {
      source  = "supabase/supabase"
      version = "~> 1.0"
    }
    railway = {
      source  = "terraform-community-providers/railway"
      version = "~> 0.3.0"
    }
  }
}

provider "upstash" {
  email   = var.upstash_email
  api_key = var.upstash_api_key
}

provider "supabase" {
  access_token = var.supabase_access_token
}

provider "railway" {
  token = var.railway_token
} 