PROJECT_ID := agentic-ai-path
REGION := us-east1
INFRA_DIR := infra
AGENT_DIR := agents/chat-assistant
WEB_DIR := web
CHANNELS_DIR := channels
WHATSAPP_PORT := 8001
TF_VARS := vars/env.tfvars

PROJECT_NAME ?= $(shell grep 'project_name' $(INFRA_DIR)/vars/env.tfvars 2>/dev/null | cut -d '"' -f 2 || echo "chat-assistant")
WHATSAPP_SERVICE_NAME := $(PROJECT_NAME)-whatsapp
WHATSAPP_IMAGE_TAG := $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(WHATSAPP_SERVICE_NAME)/webhook:latest

.PHONY: help infra-init infra-plan infra sync-metadata sync-secrets sync-whatsapp-secrets build-whatsapp deploy-whatsapp deploy-agent deploy-web deploy-status deploy-all dev-agent dev-web dev-whatsapp tunnel-whatsapp dev-whatsapp-tunnel rename

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

infra-init: ## Initialize Terraform in infra/
	terraform -chdir=$(INFRA_DIR) init

infra-plan: ## Preview infrastructure changes in GCP
	terraform -chdir=$(INFRA_DIR) plan -var-file="$(TF_VARS)"

infra: infra-init ## Apply Terraform infrastructure and sync Agent Runtime ID
	terraform -chdir=$(INFRA_DIR) apply -var-file="$(TF_VARS)"
	@$(MAKE) sync-metadata

sync-metadata: ## Sync agent_runtime_resource_name from Terraform to deployment_metadata.json
	@ENGINE_ID=$$(terraform -chdir=$(INFRA_DIR) output -raw agent_runtime_resource_name 2>/dev/null || true); \
	if [ -n "$$ENGINE_ID" ]; then \
		case "$$ENGINE_ID" in \
			projects/*) FULL_ID="$$ENGINE_ID" ;; \
			*) FULL_ID="projects/$(PROJECT_ID)/locations/$(REGION)/reasoningEngines/$$ENGINE_ID" ;; \
		esac; \
		printf '{\n  "remote_agent_runtime_id": "%s",\n  "deployment_target": "agent_runtime",\n  "is_a2a": true,\n  "agent_directory": "app"\n}\n' "$$FULL_ID" > $(AGENT_DIR)/deployment_metadata.json; \
		echo "✓ Synchronized remote_agent_runtime_id: $$FULL_ID"; \
	else \
		echo "⚠️  No agent_runtime_resource_name output found in Terraform."; \
	fi

SECRETS_FILE := $(AGENT_DIR)/.secrets_args

sync-secrets: ## Sync all variables from $(AGENT_DIR)/.env into GCP Secret Manager
	@python3 $(INFRA_DIR)/sync_secrets.py $(AGENT_DIR)/.env $(PROJECT_ID) $(SECRETS_FILE)

deploy-agent: sync-metadata sync-secrets ## Package and deploy chat-assistant agent to Agent Runtime
	@SECRETS_ARG=""; \
	if [ -f $(SECRETS_FILE) ] && [ -s $(SECRETS_FILE) ]; then \
		SECRETS_ARG="--secrets $$(cat $(SECRETS_FILE))"; \
	fi; \
	cd $(AGENT_DIR) && agents-cli deploy \
		--project $(PROJECT_ID) \
		--region $(REGION) \
		--no-confirm-project \
		$$SECRETS_ARG

deploy-web: ## Install dependencies if missing, deploy web/, and configure GCP secrets in Cloudflare
	@[ -d $(WEB_DIR)/node_modules ] || (cd $(WEB_DIR) && pnpm install)
	cd $(WEB_DIR) && pnpm run deploy
	@API_URL=$$(terraform -chdir=$(INFRA_DIR) output -raw agent_runtime_api_url); \
	cd $(WEB_DIR) && printf "%s" "$$API_URL" | npx wrangler secret put AGENT_RUNTIME_API_URL
	@terraform -chdir=$(INFRA_DIR) output -raw web_caller_sa_key_json | \
		(cd $(WEB_DIR) && npx wrangler secret put GCP_SA_KEY_JSON)

WHATSAPP_SECRETS_FILE := $(CHANNELS_DIR)/.secrets_args

sync-whatsapp-secrets: ## Sync WhatsApp credentials from channels/whatsapp/.env into GCP Secret Manager
	@python3 $(INFRA_DIR)/sync_secrets.py $(CHANNELS_DIR)/whatsapp/.env $(PROJECT_ID) $(WHATSAPP_SECRETS_FILE)

build-whatsapp: ## Build and push WhatsApp webhook container image to Artifact Registry
	@echo "Building WhatsApp container image via Cloud Build..."
	gcloud builds submit $(CHANNELS_DIR) --tag $(WHATSAPP_IMAGE_TAG) --project $(PROJECT_ID)

deploy-whatsapp: sync-whatsapp-secrets build-whatsapp ## Build, sync secrets, and deploy WhatsApp webhook to Cloud Run
	@echo "Deploying WhatsApp service to Cloud Run..."
	gcloud run deploy $(WHATSAPP_SERVICE_NAME) \
		--image $(WHATSAPP_IMAGE_TAG) \
		--region $(REGION) \
		--project $(PROJECT_ID)
	@echo "✓ WhatsApp webhook successfully deployed to Cloud Run!"
	@echo "Webhook Callback URL:"
	@terraform -chdir=$(INFRA_DIR) output -raw whatsapp_webhook_url 2>/dev/null || gcloud run services describe $(WHATSAPP_SERVICE_NAME) --region $(REGION) --project $(PROJECT_ID) --format 'value(status.url)'/webhooks/whatsapp

subscribe-whatsapp-waba: ## Link WhatsApp Business Account (WABA) to Meta App webhooks
	@cd $(CHANNELS_DIR) && uv run python -m whatsapp.subscribe_waba

deploy-status: ## Check the status of an ongoing deployment in Agent Runtime
	cd $(AGENT_DIR) && agents-cli deploy --status

deploy-all: infra deploy-agent deploy-web ## Provision infrastructure, deploy the agent, and deploy web/

dev-agent: ## Run local agent playground
	cd $(AGENT_DIR) && agents-cli playground

dev-web: ## Run web/ development server
	cd $(WEB_DIR) && pnpm dev

dev-whatsapp: ## Run WhatsApp webhook development server
	cd $(CHANNELS_DIR) && uv run uvicorn whatsapp.main:app --host 0.0.0.0 --port $(WHATSAPP_PORT) --reload

tunnel-whatsapp: ## Expose WhatsApp webhook port via ngrok
	ngrok http $(WHATSAPP_PORT)

dev-whatsapp-tunnel: ## Run WhatsApp webhook and expose via ngrok concurrently
	@echo "Starting WhatsApp webhook server and ngrok tunnel on port $(WHATSAPP_PORT)..."; \
	(cd $(CHANNELS_DIR) && uv run uvicorn whatsapp.main:app --host 0.0.0.0 --port $(WHATSAPP_PORT) --reload) & \
	SERVER_PID=$$!; \
	trap 'kill $$SERVER_PID 2>/dev/null || true' INT TERM EXIT; \
	sleep 1; \
	ngrok http $(WHATSAPP_PORT)

rename: ## Rename the agent and web app (usage: make rename NAME=my-agent [WEB_NAME=my-web])
	@if [ -z "$(NAME)" ]; then \
		echo "❌ Usage: make rename NAME=my-agent [WEB_NAME=my-web]"; \
		exit 1; \
	fi
	@NEW_NAME="$(NAME)"; \
	SNAKE_NAME=$$(echo "$$NEW_NAME" | tr '-' '_'); \
	NEW_WEB_NAME="$${WEB_NAME:-$$NEW_NAME-web}"; \
	OLD_DIR="$(AGENT_DIR)"; \
	OLD_NAME=$$(basename "$$OLD_DIR"); \
	OLD_SNAKE=$$(echo "$$OLD_NAME" | tr '-' '_'); \
	NEW_DIR="agents/$$NEW_NAME"; \
	sed -i "s/project_name = \".*\"/project_name = \"$$NEW_NAME\"/" $(INFRA_DIR)/vars/env.tfvars; \
	sed -i "s/default     = \"$$OLD_NAME\"/default     = \"$$NEW_NAME\"/" $(INFRA_DIR)/variables.tf; \
	sed -i "s/service_name=\\\"$$OLD_NAME\\\"/service_name=\\\"$$NEW_NAME\\\"/" $(INFRA_DIR)/variables.tf; \
	sed -i "s/^name: .*/name: $$NEW_NAME/" "$$OLD_DIR/agents-cli-manifest.yaml"; \
	sed -i "s/root_agent_name: .*/root_agent_name: $$SNAKE_NAME/" "$$OLD_DIR/agents-cli-manifest.yaml"; \
	sed -i "s/^name = \".*\"/name = \"$$NEW_NAME\"/" "$$OLD_DIR/pyproject.toml"; \
	sed -i "s/name=\"$$OLD_SNAKE\"/name=\"$$SNAKE_NAME\"/" "$$OLD_DIR/app/agent.py"; \
	sed -i "s/app.title = \".*\"/app.title = \"$$NEW_NAME\"/" "$$OLD_DIR/app/fast_api_app.py"; \
	sed -i "s/Agent $$OLD_NAME/Agent $$NEW_NAME/" "$$OLD_DIR/app/fast_api_app.py"; \
	sed -i "s/\"name\": \".*\"/\"name\": \"$$NEW_WEB_NAME\"/" $(WEB_DIR)/wrangler.jsonc; \
	if [ "$$OLD_DIR" != "$$NEW_DIR" ]; then \
		mv "$$OLD_DIR" "$$NEW_DIR"; \
		sed -i "s|^AGENT_DIR := .*|AGENT_DIR := $$NEW_DIR|" Makefile; \
	fi; \
	rm -f "$$NEW_DIR/deployment_metadata.json"; \
	echo "✓ Renamed agent to '$$NEW_NAME' ($$SNAKE_NAME) in $$NEW_DIR and web to '$$NEW_WEB_NAME'"
