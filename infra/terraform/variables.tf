variable "upstash_email" {
	type = string
}
variable "upstash_api_key" {
	type      = string
	sensitive = true
}
variable "supabase_access_token" {
	type      = string
	sensitive = true
}
variable "railway_token" {
	type      = string
	sensitive = true
}

variable "database_url" {
	type      = string
	sensitive = true
}
variable "supabase_url" {
	type = string
}
variable "supabase_jwt_secret" {
	type      = string
	sensitive = true
}

variable "api_key" {
	type      = string
	sensitive = true
}
variable "webhook_secret" {
	type      = string
	sensitive = true
}
variable "shopify_webhook_secret" {
	type      = string
	sensitive = true
}
variable "tiendanube_webhook_secret" {
	type      = string
	sensitive = true
}

variable "qstash_token" {
	type      = string
	sensitive = true
}
variable "qstash_current_signing_key" {
	type      = string
	sensitive = true
}
variable "qstash_next_signing_key" {
	type      = string
	sensitive = true
}
variable "qstash_url" {
	type = string
}

variable "github_repo" {
	type = string
}