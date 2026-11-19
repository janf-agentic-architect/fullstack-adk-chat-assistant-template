# Secret Manager resources for Upstash Redis

resource "google_secret_manager_secret" "upstash_redis_url" {
  secret_id = "upstash-redis-url"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret" "upstash_redis_token" {
  secret_id = "upstash-redis-token"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}
