PROJECT_ID := agentic-ai-path
REGION := us-east1
INFRA_DIR := infra
AGENT_DIR := agents/chat-assistant
WEB_DIR := web
TF_VARS := vars/env.tfvars

.PHONY: help infra-init infra-plan infra sync-metadata deploy-agent deploy-web deploy-status deploy-all dev-agent dev-web

help: ## Muestra los comandos disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

infra-init: ## Inicializa Terraform en infra/
	terraform -chdir=$(INFRA_DIR) init

infra-plan: ## Previsualiza los cambios de infraestructura en GCP
	terraform -chdir=$(INFRA_DIR) plan -var-file="$(TF_VARS)"

infra: infra-init ## Aplica la infraestructura de Terraform y sincroniza el ID del Agent Runtime
	terraform -chdir=$(INFRA_DIR) apply -var-file="$(TF_VARS)"
	@$(MAKE) sync-metadata

sync-metadata: ## Sincroniza el agent_runtime_resource_name de Terraform hacia deployment_metadata.json
	@ENGINE_ID=$$(terraform -chdir=$(INFRA_DIR) output -raw agent_runtime_resource_name 2>/dev/null || true); \
	if [ -n "$$ENGINE_ID" ]; then \
		case "$$ENGINE_ID" in \
			projects/*) FULL_ID="$$ENGINE_ID" ;; \
			*) FULL_ID="projects/$(PROJECT_ID)/locations/$(REGION)/reasoningEngines/$$ENGINE_ID" ;; \
		esac; \
		printf '{\n  "remote_agent_runtime_id": "%s",\n  "deployment_target": "agent_runtime",\n  "is_a2a": true,\n  "agent_directory": "app"\n}\n' "$$FULL_ID" > $(AGENT_DIR)/deployment_metadata.json; \
		echo "✓ Sincronizado remote_agent_runtime_id: $$FULL_ID"; \
	else \
		echo "⚠️  No se encontró output agent_runtime_resource_name en Terraform."; \
	fi

deploy-agent: sync-metadata ## Empaqueta y despliega el agente chat-assistant en Agent Runtime
	cd $(AGENT_DIR) && agents-cli deploy --project $(PROJECT_ID) --region $(REGION) --no-confirm-project

deploy-web: ## Configura secretos de GCP en Cloudflare y despliega web/
	@API_URL=$$(terraform -chdir=$(INFRA_DIR) output -raw agent_runtime_api_url); \
	cd $(WEB_DIR) && printf "%s" "$$API_URL" | npx wrangler secret put AGENT_RUNTIME_API_URL
	@terraform -chdir=$(INFRA_DIR) output -raw web_caller_sa_key_json | \
		(cd $(WEB_DIR) && npx wrangler secret put GCP_SA_KEY_JSON)
	cd $(WEB_DIR) && pnpm run deploy

deploy-status: ## Consulta el estado de un despliegue en curso en Agent Runtime
	cd $(AGENT_DIR) && agents-cli deploy --status

deploy-all: infra deploy-agent deploy-web ## Aprovisiona la infraestructura, despliega el agente y despliega web/

dev-agent: ## Ejecuta el playground local del agente
	cd $(AGENT_DIR) && agents-cli playground

dev-web: ## Ejecuta el servidor de desarrollo de web/
	cd $(WEB_DIR) && pnpm dev
