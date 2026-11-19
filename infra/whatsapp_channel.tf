# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

variable "whatsapp_image" {
  type        = string
  description = "Docker image for WhatsApp Cloud Run service. Defaults to hello container before first build."
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

# Artifact Registry repository for storing WhatsApp channel container images
resource "google_artifact_registry_repository" "whatsapp" {
  project       = var.project_id
  location      = var.region
  repository_id = "${var.project_name}-whatsapp"
  description   = "Docker repository for WhatsApp Webhook service"
  format        = "DOCKER"
  depends_on    = [google_project_service.services]
}

# Secret Manager resources for WhatsApp Cloud API credentials
resource "google_secret_manager_secret" "whatsapp_token" {
  secret_id = "whatsapp-token"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "whatsapp_token_initial" {
  secret      = google_secret_manager_secret.whatsapp_token.id
  secret_data = "initial_placeholder"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret" "whatsapp_phone_number_id" {
  secret_id = "whatsapp-phone-number-id"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "whatsapp_phone_number_id_initial" {
  secret      = google_secret_manager_secret.whatsapp_phone_number_id.id
  secret_data = "initial_placeholder"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret" "whatsapp_verify_token" {
  secret_id = "whatsapp-verify-token"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "whatsapp_verify_token_initial" {
  secret      = google_secret_manager_secret.whatsapp_verify_token.id
  secret_data = "initial_placeholder"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret" "whatsapp_app_secret" {
  secret_id = "whatsapp-app-secret"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "whatsapp_app_secret_initial" {
  secret      = google_secret_manager_secret.whatsapp_app_secret.id
  secret_data = "initial_placeholder"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Dedicated Service Account for WhatsApp Cloud Run Webhook
resource "google_service_account" "whatsapp_channel_sa" {
  account_id   = "${var.project_name}-whatsapp-sa"
  display_name = "Cloud Run WhatsApp Channel SA for ${var.project_name}"
  project      = var.project_id
  depends_on   = [google_project_service.services]
}

# Allow WhatsApp channel SA to invoke Vertex AI Reasoning Engine / Agent Runtime
resource "google_project_iam_member" "whatsapp_channel_aiplatform" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.whatsapp_channel_sa.email}"
}

# Allow WhatsApp channel SA to access Secret Manager secrets
resource "google_project_iam_member" "whatsapp_channel_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.whatsapp_channel_sa.email}"
}

# Allow WhatsApp channel SA to write logs
resource "google_project_iam_member" "whatsapp_channel_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.whatsapp_channel_sa.email}"
}

# Cloud Run v2 Service hosting the WhatsApp webhook
resource "google_cloud_run_v2_service" "whatsapp_channel" {
  name     = "${var.project_name}-whatsapp"
  location = var.region
  project  = var.project_id
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.whatsapp_channel_sa.email

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    containers {
      image = var.whatsapp_image

      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
      }

      env {
        name  = "ADK_API_URL"
        value = "https://${var.region}-aiplatform.googleapis.com/reasoningEngines/v1/projects/${data.google_project.project.number}/locations/${var.region}/reasoningEngines/${google_vertex_ai_reasoning_engine.app.name}/api"
      }
      env {
        name  = "ADK_APP_NAME"
        value = "app"
      }
      env {
        name  = "ADK_USER_PREFIX"
        value = "wa_"
      }
      env {
        name  = "WHATSAPP_API_VERSION"
        value = "v25.0"
      }
      env {
        name = "WHATSAPP_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.whatsapp_token.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "WHATSAPP_PHONE_NUMBER_ID"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.whatsapp_phone_number_id.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "WHATSAPP_VERIFY_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.whatsapp_verify_token.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "WHATSAPP_APP_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.whatsapp_app_secret.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      client,
      client_version,
      template[0].containers[0].image,
    ]
  }

  depends_on = [
    google_project_service.services,
    google_vertex_ai_reasoning_engine.app,
    google_secret_manager_secret_version.whatsapp_token_initial,
    google_secret_manager_secret_version.whatsapp_phone_number_id_initial,
    google_secret_manager_secret_version.whatsapp_verify_token_initial,
    google_secret_manager_secret_version.whatsapp_app_secret_initial,
    google_project_iam_member.whatsapp_channel_aiplatform,
    google_project_iam_member.whatsapp_channel_secrets,
  ]
}

# Public invocations for Meta WhatsApp Webhook
resource "google_cloud_run_v2_service_iam_member" "whatsapp_public_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.whatsapp_channel.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
