resource "railway_project" "fuccina_project" {
  name        = "fuccina"
  description = "Fuccina Software Suite"
}

resource "railway_service" "slancio_api" {
    project_id        = railway_project.fuccina_project.id
      name              = "slancio"
        source_repo       = var.github_repo
}

resource "railway_variable" "db_url" {
  service_id     = railway_service.slancio_api.id
  environment_id = railway_project.fuccina_project.default_environment.id
  name           = "DATABASE_URL"
  value          = var.database_url
}

resource "railway_variable" "supabase_url" {
  service_id     = railway_service.slancio_api.id
  environment_id = railway_project.fuccina_project.default_environment.id
  name           = "SUPABASE_URL"
  value          = var.supabase_url
}

resource "railway_variable" "supabase_jwt_secret" {
  service_id     = railway_service.slancio_api.id
  environment_id = railway_project.fuccina_project.default_environment.id
  name           = "SUPABASE_JWT_SECRET"
  value          = var.supabase_jwt_secret
}

resource "railway_variable" "api_key" {
  service_id     = railway_service.slancio_api.id
  environment_id = railway_project.fuccina_project.default_environment.id
  name           = "API_KEY"
  value          = var.api_key
}

resource "railway_variable" "webhook_secret" {
  service_id     = railway_service.slancio_api.id
  environment_id = railway_project.fuccina_project.default_environment.id
  name           = "WEBHOOK_SECRET"
  value          = var.webhook_secret
}

resource "railway_variable" "shopify_webhook_secret" {
  service_id     = railway_service.slancio_api.id
  environment_id = railway_project.fuccina_project.default_environment.id
  name           = "SHOPIFY_WEBHOOK_SECRET"
  value          = var.shopify_webhook_secret
}

resource "railway_variable" "tiendanube_webhook_secret" {
  service_id     = railway_service.slancio_api.id
  environment_id = railway_project.fuccina_project.default_environment.id
  name           = "TIENDANUBE_WEBHOOK_SECRET"
  value          = var.tiendanube_webhook_secret
}

resource "railway_variable" "qstash_token" {
  service_id     = railway_service.slancio_api.id
  environment_id = railway_project.fuccina_project.default_environment.id
  name           = "QSTASH_TOKEN"
  value          = var.qstash_token
}

resource "railway_variable" "qstash_curr_key" {
  service_id     = railway_service.slancio_api.id
  environment_id = railway_project.fuccina_project.default_environment.id
  name           = "QSTASH_CURRENT_SIGNING_KEY"
  value          = var.qstash_current_signing_key
}

resource "railway_variable" "qstash_next_key" {
  service_id     = railway_service.slancio_api.id
  environment_id = railway_project.fuccina_project.default_environment.id
  name           = "QSTASH_NEXT_SIGNING_KEY"
  value          = var.qstash_next_signing_key
}

# La URL pública generada dinámicamente
resource "railway_variable" "public_api_url" {
  service_id     = railway_service.slancio_api.id
  environment_id = railway_project.fuccina_project.default_environment.id
  name           = "PUBLIC_API_URL"
  value          = "https://${railway_service.slancio_api.name}.up.railway.app" 
}