PROJECT_ID := agentic-ai-path
REGION := us-east1
INFRA_DIR := infra
AGENT_DIR := agents/chat-assistant
WEB_DIR := web
TF_VARS := vars/env.tfvars

.PHONY: help infra-init infra-plan infra sync-metadata sync-secrets deploy-agent deploy-web deploy-status deploy-all dev-agent dev-web rename

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

sync-secrets: ## Sync Upstash secrets from $(AGENT_DIR)/.env into GCP Secret Manager
	@if [ -f $(AGENT_DIR)/.env ]; then \
		URL=$$(grep -E '^UPSTASH_REDIS_REST_URL=' $(AGENT_DIR)/.env | head -n 1 | cut -d '=' -f2- | tr -d '"' | tr -d "'"); \
		TOKEN=$$(grep -E '^UPSTASH_REDIS_REST_TOKEN=' $(AGENT_DIR)/.env | head -n 1 | cut -d '=' -f2- | tr -d '"' | tr -d "'"); \
		if [ -n "$$URL" ]; then \
			echo "Syncing upstash-redis-url to GCP Secret Manager..."; \
			printf "%s" "$$URL" | gcloud secrets versions add upstash-redis-url --data-file=- --project=$(PROJECT_ID) 2>/dev/null || \
			(gcloud secrets create upstash-redis-url --data-file=- --replication-policy=automatic --project=$(PROJECT_ID) 2>/dev/null && printf "%s" "$$URL" | gcloud secrets versions add upstash-redis-url --data-file=- --project=$(PROJECT_ID) 2>/dev/null || true); \
		fi; \
		if [ -n "$$TOKEN" ]; then \
			echo "Syncing upstash-redis-token to GCP Secret Manager..."; \
			printf "%s" "$$TOKEN" | gcloud secrets versions add upstash-redis-token --data-file=- --project=$(PROJECT_ID) 2>/dev/null || \
			(gcloud secrets create upstash-redis-token --data-file=- --replication-policy=automatic --project=$(PROJECT_ID) 2>/dev/null && printf "%s" "$$TOKEN" | gcloud secrets versions add upstash-redis-token --data-file=- --project=$(PROJECT_ID) 2>/dev/null || true); \
		fi; \
		echo "✓ Upstash secrets synced to GCP Secret Manager"; \
	fi

deploy-agent: sync-metadata sync-secrets ## Package and deploy chat-assistant agent to Agent Runtime
	cd $(AGENT_DIR) && agents-cli deploy \
		--project $(PROJECT_ID) \
		--region $(REGION) \
		--no-confirm-project \
		--secrets "UPSTASH_REDIS_REST_URL=upstash-redis-url,UPSTASH_REDIS_REST_TOKEN=upstash-redis-token"

deploy-web: ## Install dependencies if missing, deploy web/, and configure GCP secrets in Cloudflare
	@[ -d $(WEB_DIR)/node_modules ] || (cd $(WEB_DIR) && pnpm install)
	cd $(WEB_DIR) && pnpm run deploy
	@API_URL=$$(terraform -chdir=$(INFRA_DIR) output -raw agent_runtime_api_url); \
	cd $(WEB_DIR) && printf "%s" "$$API_URL" | npx wrangler secret put AGENT_RUNTIME_API_URL
	@terraform -chdir=$(INFRA_DIR) output -raw web_caller_sa_key_json | \
		(cd $(WEB_DIR) && npx wrangler secret put GCP_SA_KEY_JSON)

deploy-status: ## Check the status of an ongoing deployment in Agent Runtime
	cd $(AGENT_DIR) && agents-cli deploy --status

deploy-all: infra deploy-agent deploy-web ## Provision infrastructure, deploy the agent, and deploy web/

dev-agent: ## Run local agent playground
	cd $(AGENT_DIR) && agents-cli playground

dev-web: ## Run web/ development server
	cd $(WEB_DIR) && pnpm dev

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
