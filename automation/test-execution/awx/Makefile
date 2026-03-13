# Makefile for AWX Development Environment
# Automatically detects and uses Docker or Podman

# ============================================================================
# Configuration
# ============================================================================

AWX_VERSION ?= 24.6.1
AWX_DIR ?= /tmp/awx
AWX_PORT ?= 8052
AWX_ADMIN_USER ?= admin
AWX_ADMIN_PASSWORD ?= password

# KIND configuration (macOS-friendly approach)
KIND_CLUSTER_NAME ?= awx
KIND_AWX_PORT ?= 30080
AWX_OPERATOR_DIR ?= /tmp/awx-operator

# Project settings
PROJECT_ROOT := $(shell git rev-parse --show-toplevel 2>/dev/null || echo "../../../")
PROJECT_NAME := vllm-cpu-perf-eval

# ============================================================================
# Container Engine Detection
# ============================================================================

# Detect container engine (prefer podman, fallback to docker)
CONTAINER_ENGINE := $(shell command -v podman 2>/dev/null || command -v docker 2>/dev/null)
CONTAINER_TYPE := $(shell if command -v podman >/dev/null 2>&1; then echo "podman"; elif command -v docker >/dev/null 2>&1; then echo "docker"; else echo "none"; fi)
COMPOSE_CMD := $(shell if [ "$(CONTAINER_TYPE)" = "podman" ]; then echo "podman-compose"; else echo "docker compose"; fi)

# Colors for output
COLOR_RESET := \033[0m
COLOR_INFO := \033[36m
COLOR_SUCCESS := \033[32m
COLOR_WARNING := \033[33m
COLOR_ERROR := \033[31m

# ============================================================================
# Targets
# ============================================================================

.PHONY: help
help: ## Show this help message
	@echo "$(COLOR_INFO)AWX Development Environment$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_SUCCESS)Recommended Quick Start:$(COLOR_RESET)"
	@echo "  make kind-quickstart    - Full KIND setup (AWX 24.x+ recommended)"
	@echo ""
	@echo "$(COLOR_INFO)AWX Version:$(COLOR_RESET) $(AWX_VERSION)"
	@echo "$(COLOR_WARNING)Note: AWX 24.x+ removed docker-compose support. Use KIND targets.$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_INFO)Available targets:$(COLOR_RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(COLOR_SUCCESS)%-25s$(COLOR_RESET) %s\n", $$1, $$2}'

.PHONY: check-requirements
check-requirements: ## Check if required tools are installed
	@echo "$(COLOR_INFO)Checking requirements...$(COLOR_RESET)"
	@if [ "$(CONTAINER_TYPE)" = "none" ]; then \
		echo "$(COLOR_ERROR)Error: Neither Docker nor Podman found!$(COLOR_RESET)"; \
		echo "$(COLOR_INFO)Install one of:$(COLOR_RESET)"; \
		echo "  - Docker: https://docs.docker.com/get-docker/"; \
		echo "  - Podman: https://podman.io/getting-started/installation"; \
		exit 1; \
	fi
	@echo "$(COLOR_SUCCESS)✓ Container engine: $(CONTAINER_TYPE)$(COLOR_RESET)"
	@if [ "$(CONTAINER_TYPE)" = "podman" ]; then \
		if ! command -v podman-compose >/dev/null 2>&1; then \
			echo "$(COLOR_WARNING)⚠ podman-compose not found, installing...$(COLOR_RESET)"; \
			pip3 install --user --break-system-packages podman-compose 2>/dev/null || \
			pip3 install --user podman-compose 2>/dev/null || true; \
		fi; \
		if command -v podman-compose >/dev/null 2>&1; then \
			echo "$(COLOR_SUCCESS)✓ podman-compose installed$(COLOR_RESET)"; \
		else \
			echo "$(COLOR_WARNING)⚠ podman-compose not available$(COLOR_RESET)"; \
		fi; \
	fi
	@if ! command -v git >/dev/null 2>&1; then \
		echo "$(COLOR_ERROR)Error: git not found!$(COLOR_RESET)"; \
		exit 1; \
	fi
	@echo "$(COLOR_SUCCESS)✓ git installed$(COLOR_RESET)"
	@echo "$(COLOR_SUCCESS)All requirements met!$(COLOR_RESET)"

.PHONY: clone-awx
clone-awx: check-requirements ## Clone AWX repository (if not already cloned)
	@if [ ! -d "$(AWX_DIR)" ]; then \
		echo "$(COLOR_INFO)Cloning AWX $(AWX_VERSION)...$(COLOR_RESET)"; \
		git clone --depth 1 --branch $(AWX_VERSION) https://github.com/ansible/awx.git $(AWX_DIR); \
		echo "$(COLOR_SUCCESS)✓ AWX cloned to $(AWX_DIR)$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_INFO)AWX already cloned at $(AWX_DIR)$(COLOR_RESET)"; \
	fi

.PHONY: start
start: ## Start AWX (DEPRECATED - use kind-start instead)
	@echo "$(COLOR_ERROR)ERROR: Docker Compose is not supported in AWX $(AWX_VERSION)$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_INFO)AWX 24.x+ removed docker-compose development environment.$(COLOR_RESET)"
	@echo "$(COLOR_INFO)Use KIND (Kubernetes) instead:$(COLOR_RESET)"
	@echo ""
	@echo "  make kind-quickstart    - Complete setup (recommended)"
	@echo "  make kind-start         - Start AWX in KIND"
	@echo ""
	@exit 1

.PHONY: wait-ready
wait-ready: ## Wait for AWX to be ready (checks every 5 seconds)
	@echo "$(COLOR_INFO)Waiting for AWX to be ready...$(COLOR_RESET)"
	@attempt=1; \
	max_attempts=60; \
	while [ $$attempt -le $$max_attempts ]; do \
		if $(CONTAINER_ENGINE) logs awx_task 2>/dev/null | grep -q "Successfully registered instance"; then \
			echo "$(COLOR_SUCCESS)✓ AWX is ready!$(COLOR_RESET)"; \
			echo ""; \
			echo "$(COLOR_INFO)Access AWX:$(COLOR_RESET)"; \
			echo "  URL:      http://localhost:$(AWX_PORT)"; \
			echo "  Username: $(AWX_ADMIN_USER)"; \
			echo "  Password: $(AWX_ADMIN_PASSWORD)"; \
			echo ""; \
			echo "$(COLOR_INFO)Next steps:$(COLOR_RESET) Follow QUICKSTART.md to configure AWX"; \
			exit 0; \
		fi; \
		printf "$(COLOR_INFO)Waiting... (attempt $$attempt/$$max_attempts)$(COLOR_RESET)\r"; \
		sleep 5; \
		attempt=$$((attempt + 1)); \
	done; \
	echo "$(COLOR_ERROR)✗ Timeout waiting for AWX to be ready$(COLOR_RESET)"; \
	echo "$(COLOR_INFO)Check logs:$(COLOR_RESET) make logs"; \
	exit 1

.PHONY: status
status: ## Check AWX container status
	@echo "$(COLOR_INFO)AWX Container Status:$(COLOR_RESET)"
	@$(CONTAINER_ENGINE) ps -a --filter "name=awx" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

.PHONY: logs
logs: ## Show AWX logs (task worker)
	@echo "$(COLOR_INFO)AWX Task Logs (Ctrl+C to exit):$(COLOR_RESET)"
	@$(CONTAINER_ENGINE) logs -f awx_task

.PHONY: logs-web
logs-web: ## Show AWX web server logs
	@echo "$(COLOR_INFO)AWX Web Logs (Ctrl+C to exit):$(COLOR_RESET)"
	@$(CONTAINER_ENGINE) logs -f awx_web

.PHONY: logs-all
logs-all: ## Show all AWX container logs
	@echo "$(COLOR_INFO)All AWX Container Logs:$(COLOR_RESET)"
	@for container in $$($(CONTAINER_ENGINE) ps --filter "name=awx" --format "{{.Names}}"); do \
		echo ""; \
		echo "$(COLOR_INFO)=== $$container ===$(COLOR_RESET)"; \
		$(CONTAINER_ENGINE) logs --tail 50 $$container; \
	done

.PHONY: shell
shell: ## Open shell in AWX task container
	@echo "$(COLOR_INFO)Opening shell in AWX task container...$(COLOR_RESET)"
	@$(CONTAINER_ENGINE) exec -it awx_task /bin/bash

.PHONY: stop
stop: ## Stop AWX containers
	@echo "$(COLOR_INFO)Stopping AWX...$(COLOR_RESET)"
	@cd $(AWX_DIR)/tools/docker-compose && $(COMPOSE_CMD) stop
	@echo "$(COLOR_SUCCESS)✓ AWX stopped$(COLOR_RESET)"

.PHONY: restart
restart: stop start ## Restart AWX containers

.PHONY: clean
clean: ## Stop and remove AWX containers (keeps data volumes)
	@echo "$(COLOR_WARNING)Stopping and removing AWX containers...$(COLOR_RESET)"
	@cd $(AWX_DIR)/tools/docker-compose && $(COMPOSE_CMD) down
	@echo "$(COLOR_SUCCESS)✓ AWX containers removed$(COLOR_RESET)"
	@echo "$(COLOR_INFO)Data volumes preserved. To remove data: make clean-all$(COLOR_RESET)"

.PHONY: clean-all
clean-all: ## Stop and remove AWX containers AND data volumes (DESTRUCTIVE!)
	@echo "$(COLOR_ERROR)WARNING: This will delete all AWX data (jobs, credentials, etc.)!$(COLOR_RESET)"
	@read -p "Are you sure? (type 'yes' to confirm): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		echo "$(COLOR_INFO)Removing AWX containers and volumes...$(COLOR_RESET)"; \
		cd $(AWX_DIR)/tools/docker-compose && $(COMPOSE_CMD) down -v; \
		echo "$(COLOR_SUCCESS)✓ AWX completely removed$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_INFO)Cancelled.$(COLOR_RESET)"; \
	fi

.PHONY: uninstall
uninstall: clean-all ## Remove AWX completely (containers, volumes, and cloned repo)
	@echo "$(COLOR_WARNING)Removing AWX repository...$(COLOR_RESET)"
	@rm -rf $(AWX_DIR)
	@echo "$(COLOR_SUCCESS)✓ AWX completely uninstalled$(COLOR_RESET)"

.PHONY: install
install: ## Install AWX (DEPRECATED - use kind-quickstart instead)
	@echo "$(COLOR_ERROR)ERROR: Docker Compose is not supported in AWX $(AWX_VERSION)$(COLOR_RESET)"
	@echo "$(COLOR_INFO)Use: make kind-quickstart$(COLOR_RESET)"
	@exit 1

.PHONY: url
url: ## Show AWX access URL and credentials
	@echo "$(COLOR_INFO)AWX Access Information:$(COLOR_RESET)"
	@echo "  URL:      http://localhost:$(AWX_PORT)"
	@echo "  Username: $(AWX_ADMIN_USER)"
	@echo "  Password: $(AWX_ADMIN_PASSWORD)"

.PHONY: open
open: ## Open AWX in browser (macOS/Linux)
	@if command -v open >/dev/null 2>&1; then \
		open http://localhost:$(AWX_PORT); \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open http://localhost:$(AWX_PORT); \
	else \
		echo "$(COLOR_INFO)Open in browser:$(COLOR_RESET) http://localhost:$(AWX_PORT)"; \
	fi

.PHONY: stats
stats: ## Show container resource usage
	@echo "$(COLOR_INFO)AWX Container Resource Usage:$(COLOR_RESET)"
	@$(CONTAINER_ENGINE) stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}" \
		$$($(CONTAINER_ENGINE) ps --filter "name=awx" --format "{{.Names}}")

.PHONY: health
health: ## Check AWX health endpoint
	@echo "$(COLOR_INFO)Checking AWX health...$(COLOR_RESET)"
	@if curl -s http://localhost:$(AWX_PORT)/api/v2/ping/ | grep -q "ha_enabled"; then \
		echo "$(COLOR_SUCCESS)✓ AWX is healthy!$(COLOR_RESET)"; \
		curl -s http://localhost:$(AWX_PORT)/api/v2/ping/ | python3 -m json.tool; \
	else \
		echo "$(COLOR_ERROR)✗ AWX health check failed$(COLOR_RESET)"; \
		exit 1; \
	fi

.PHONY: test-ansible
test-ansible: ## Test running an Ansible playbook from this repo
	@echo "$(COLOR_INFO)Testing Ansible playbook execution...$(COLOR_RESET)"
	@echo "$(COLOR_WARNING)This requires AWX to be configured with project, inventory, and credentials$(COLOR_RESET)"
	@echo "$(COLOR_INFO)Follow QUICKSTART.md first, then use AWX UI to launch jobs$(COLOR_RESET)"

.PHONY: backup
backup: ## Backup AWX data (exports to awx-backup-YYYYMMDD.tar.gz)
	@BACKUP_FILE="awx-backup-$$(date +%Y%m%d-%H%M%S).tar.gz"; \
	echo "$(COLOR_INFO)Backing up AWX data to $$BACKUP_FILE...$(COLOR_RESET)"; \
	$(CONTAINER_ENGINE) run --rm --volumes-from awx_postgres \
		-v $$(pwd):/backup \
		alpine tar czf /backup/$$BACKUP_FILE /var/lib/postgresql/data; \
	echo "$(COLOR_SUCCESS)✓ Backup saved to $$BACKUP_FILE$(COLOR_RESET)"

.PHONY: quickstart
quickstart: kind-quickstart ## Full quick start (use KIND - recommended for AWX 24.x+)

# ============================================================================
# KIND Targets (macOS-friendly Kubernetes approach)
# ============================================================================

.PHONY: check-kind-requirements
check-kind-requirements: ## Check if KIND dependencies are installed
	@echo "$(COLOR_INFO)Checking KIND requirements...$(COLOR_RESET)"
	@if ! command -v kind >/dev/null 2>&1; then \
		echo "$(COLOR_ERROR)Error: KIND not found!$(COLOR_RESET)"; \
		echo "$(COLOR_INFO)Install KIND:$(COLOR_RESET)"; \
		echo "  brew install kind"; \
		echo "  or visit: https://kind.sigs.k8s.io/docs/user/quick-start/"; \
		exit 1; \
	fi
	@echo "$(COLOR_SUCCESS)✓ KIND installed: $$(kind version)$(COLOR_RESET)"
	@if ! command -v kubectl >/dev/null 2>&1; then \
		echo "$(COLOR_ERROR)Error: kubectl not found!$(COLOR_RESET)"; \
		echo "$(COLOR_INFO)Install kubectl:$(COLOR_RESET)"; \
		echo "  brew install kubectl"; \
		exit 1; \
	fi
	@echo "$(COLOR_SUCCESS)✓ kubectl installed$(COLOR_RESET)"
	@if ! python3 -c "import openshift" 2>/dev/null; then \
		echo "$(COLOR_WARNING)⚠ openshift Python module not found, installing...$(COLOR_RESET)"; \
		pip3 install --user --break-system-packages openshift 2>/dev/null || \
		pip3 install --user openshift 2>/dev/null || \
		echo "$(COLOR_WARNING)⚠ Could not install openshift module. Continuing anyway...$(COLOR_RESET)"; \
	fi
	@if python3 -c "import openshift" 2>/dev/null; then \
		echo "$(COLOR_SUCCESS)✓ openshift Python module installed$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_WARNING)⚠ openshift module not available (configure step may fail)$(COLOR_RESET)"; \
	fi
	@echo "$(COLOR_SUCCESS)All KIND requirements met!$(COLOR_RESET)"

.PHONY: kind-create-cluster
kind-create-cluster: check-kind-requirements ## Create KIND cluster for AWX
	@echo "$(COLOR_INFO)Creating KIND cluster '$(KIND_CLUSTER_NAME)'...$(COLOR_RESET)"
	@if kind get clusters | grep -q "^$(KIND_CLUSTER_NAME)$$"; then \
		echo "$(COLOR_INFO)KIND cluster '$(KIND_CLUSTER_NAME)' already exists$(COLOR_RESET)"; \
	else \
		kind create cluster --config kind-cluster.yaml --name $(KIND_CLUSTER_NAME); \
		echo "$(COLOR_SUCCESS)✓ KIND cluster created$(COLOR_RESET)"; \
	fi
	@kubectl cluster-info --context kind-$(KIND_CLUSTER_NAME)

.PHONY: kind-deploy-operator
kind-deploy-operator: ## Deploy AWX operator to KIND cluster
	@echo "$(COLOR_INFO)Deploying AWX operator...$(COLOR_RESET)"
	@if [ -d "$(AWX_OPERATOR_DIR)" ] && [ ! -f "$(AWX_OPERATOR_DIR)/config/default/kustomization.yaml" ]; then \
		echo "$(COLOR_WARNING)Incomplete AWX operator directory found, cleaning up...$(COLOR_RESET)"; \
		rm -rf "$(AWX_OPERATOR_DIR)"; \
	fi
	@if [ ! -d "$(AWX_OPERATOR_DIR)" ]; then \
		echo "$(COLOR_INFO)Cloning AWX operator (v2.19.1)...$(COLOR_RESET)"; \
		git clone --depth 1 --branch 2.19.1 https://github.com/ansible/awx-operator.git $(AWX_OPERATOR_DIR); \
	fi
	@echo "$(COLOR_INFO)Deploying operator using kubectl...$(COLOR_RESET)"
	@kubectl config use-context kind-$(KIND_CLUSTER_NAME)
	@cd $(AWX_OPERATOR_DIR) && KUBECONFIG=~/.kube/config kubectl apply -k config/default
	@echo "$(COLOR_INFO)Waiting for operator to be ready...$(COLOR_RESET)"
	@sleep 10
	@kubectl wait --for=condition=available --timeout=180s deployment/awx-operator-controller-manager -n awx-operator-system 2>/dev/null || \
		(echo "$(COLOR_INFO)Checking operator status...$(COLOR_RESET)" && kubectl get pods -n awx-operator-system)
	@echo "$(COLOR_SUCCESS)✓ AWX operator deployed$(COLOR_RESET)"

.PHONY: kind-build-ee
kind-build-ee: ## Build custom execution environment with required collections
	@echo "$(COLOR_INFO)Building custom execution environment...$(COLOR_RESET)"
	@if ! python3 -m ansible_builder --version >/dev/null 2>&1; then \
		echo "$(COLOR_WARNING)ansible-builder not found, installing...$(COLOR_RESET)"; \
		pip3 install --user --break-system-packages ansible-builder 2>/dev/null || \
		pip3 install --user ansible-builder 2>/dev/null || \
		(echo "$(COLOR_ERROR)Failed to install ansible-builder$(COLOR_RESET)" && exit 1); \
	fi
	@echo "$(COLOR_INFO)Building image vllm-awx-ee:latest...$(COLOR_RESET)"
	@cd $(PROJECT_ROOT) && python3 -m ansible_builder build \
		-f automation/test-execution/awx/execution-environment.yml \
		-t vllm-awx-ee:latest \
		-v 3
	@if [ "$(CONTAINER_TYPE)" = "podman" ]; then \
		echo "$(COLOR_INFO)Ensuring image is tagged without localhost prefix...$(COLOR_RESET)"; \
		$(CONTAINER_ENGINE) tag localhost/vllm-awx-ee:latest vllm-awx-ee:latest 2>/dev/null || true; \
	fi
	@echo "$(COLOR_SUCCESS)✓ Execution environment built$(COLOR_RESET)"

.PHONY: kind-load-ee
kind-load-ee: kind-build-ee ## Load custom execution environment into KIND cluster
	@echo "$(COLOR_INFO)Loading execution environment into KIND cluster...$(COLOR_RESET)"
	@kind load docker-image vllm-awx-ee:latest --name $(KIND_CLUSTER_NAME)
	@echo "$(COLOR_SUCCESS)✓ Execution environment loaded into KIND$(COLOR_RESET)"

.PHONY: kind-deploy-awx
kind-deploy-awx: kind-load-ee ## Deploy AWX instance to KIND cluster
	@echo "$(COLOR_INFO)Creating awx namespace...$(COLOR_RESET)"
	@kubectl create namespace awx --dry-run=client -o yaml | kubectl apply -f -
	@echo "$(COLOR_INFO)Creating AWX secrets...$(COLOR_RESET)"
	@kubectl create secret generic awx-admin-password \
		--from-literal=password=$(AWX_ADMIN_PASSWORD) \
		-n awx --dry-run=client -o yaml | kubectl apply -f -
	@kubectl create secret generic awx-postgres-configuration \
		--from-literal=host=awx-postgres-15 \
		--from-literal=port=5432 \
		--from-literal=database=awx \
		--from-literal=username=awx \
		--from-literal=password=awxpass \
		--from-literal=type=managed \
		-n awx --dry-run=client -o yaml | kubectl apply -f -
	@echo "$(COLOR_INFO)Deploying AWX instance...$(COLOR_RESET)"
	@kubectl apply -f awx-instance.yaml
	@echo "$(COLOR_INFO)Waiting for AWX to be ready (this may take 3-5 minutes)...$(COLOR_RESET)"
	@echo "$(COLOR_INFO)Monitor progress: make kind-status$(COLOR_RESET)"

.PHONY: kind-wait-ready
kind-wait-ready: ## Wait for AWX to be ready in KIND
	@echo "$(COLOR_INFO)Waiting for AWX pods to be ready...$(COLOR_RESET)"
	@timeout=300; \
	elapsed=0; \
	while [ $$elapsed -lt $$timeout ]; do \
		if kubectl get pods -n awx -l app.kubernetes.io/name=awx-web -o jsonpath='{.items[*].status.containerStatuses[*].ready}' 2>/dev/null | grep -q "true"; then \
			echo "$(COLOR_SUCCESS)✓ AWX is ready!$(COLOR_RESET)"; \
			echo ""; \
			echo "$(COLOR_INFO)Access AWX:$(COLOR_RESET)"; \
			echo "  URL:      http://localhost:$(KIND_AWX_PORT)"; \
			echo "  Username: $(AWX_ADMIN_USER)"; \
			echo "  Password: $(AWX_ADMIN_PASSWORD)"; \
			echo ""; \
			exit 0; \
		fi; \
		printf "$(COLOR_INFO)Waiting... ($$elapsed/$$timeout seconds)$(COLOR_RESET)\r"; \
		sleep 5; \
		elapsed=$$((elapsed + 5)); \
	done; \
	echo "$(COLOR_ERROR)✗ Timeout waiting for AWX$(COLOR_RESET)"; \
	exit 1

.PHONY: kind-start
kind-start: kind-create-cluster kind-deploy-operator kind-deploy-awx kind-wait-ready ## Start AWX in KIND (all-in-one)
	@echo ""
	@echo "$(COLOR_SUCCESS)=====================================$(COLOR_RESET)"
	@echo "$(COLOR_SUCCESS)  AWX on KIND is Ready!$(COLOR_RESET)"
	@echo "$(COLOR_SUCCESS)=====================================$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_INFO)Access:$(COLOR_RESET) http://localhost:$(KIND_AWX_PORT)"
	@echo "$(COLOR_INFO)Login:$(COLOR_RESET) admin / password"
	@echo ""
	@echo "$(COLOR_INFO)Useful commands:$(COLOR_RESET)"
	@echo "  make kind-status   - Check AWX status"
	@echo "  make kind-logs     - View AWX logs"
	@echo "  make kind-open     - Open in browser"
	@echo "  make kind-stop     - Stop KIND cluster"

.PHONY: kind-status
kind-status: ## Show KIND cluster and AWX status
	@echo "$(COLOR_INFO)KIND Cluster Status:$(COLOR_RESET)"
	@kind get clusters | grep "^$(KIND_CLUSTER_NAME)$$" || echo "Cluster not running"
	@echo ""
	@echo "$(COLOR_INFO)AWX Pods Status:$(COLOR_RESET)"
	@kubectl get pods -n awx 2>/dev/null || echo "No pods found (cluster may not be running)"
	@echo ""
	@echo "$(COLOR_INFO)AWX Services:$(COLOR_RESET)"
	@kubectl get svc -n awx 2>/dev/null || echo "No services found"

.PHONY: kind-logs
kind-logs: ## Show AWX logs from KIND
	@echo "$(COLOR_INFO)AWX Web Logs (Ctrl+C to exit):$(COLOR_RESET)"
	@kubectl logs -n awx -l app.kubernetes.io/name=awx-web --tail=50 -f

.PHONY: kind-logs-task
kind-logs-task: ## Show AWX task logs from KIND
	@echo "$(COLOR_INFO)AWX Task Logs (Ctrl+C to exit):$(COLOR_RESET)"
	@kubectl logs -n awx -l app.kubernetes.io/name=awx-task --tail=50 -f

.PHONY: kind-shell
kind-shell: ## Open shell in AWX web pod
	@echo "$(COLOR_INFO)Opening shell in AWX web pod...$(COLOR_RESET)"
	@kubectl exec -it -n awx $$(kubectl get pods -n awx -l app.kubernetes.io/name=awx-web -o jsonpath='{.items[0].metadata.name}') -- /bin/bash

.PHONY: kind-stop
kind-stop: ## Stop KIND cluster
	@echo "$(COLOR_WARNING)Stopping KIND cluster '$(KIND_CLUSTER_NAME)'...$(COLOR_RESET)"
	@kind delete cluster --name $(KIND_CLUSTER_NAME)
	@echo "$(COLOR_SUCCESS)✓ KIND cluster stopped and removed$(COLOR_RESET)"

.PHONY: kind-restart
kind-restart: kind-stop kind-start ## Restart KIND cluster with AWX

.PHONY: kind-open
kind-open: ## Open AWX in browser (KIND)
	@if command -v open >/dev/null 2>&1; then \
		open http://localhost:$(KIND_AWX_PORT); \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open http://localhost:$(KIND_AWX_PORT); \
	else \
		echo "$(COLOR_INFO)Open in browser:$(COLOR_RESET) http://localhost:$(KIND_AWX_PORT)"; \
	fi

.PHONY: kind-health
kind-health: ## Check AWX health in KIND
	@echo "$(COLOR_INFO)Checking AWX health...$(COLOR_RESET)"
	@if curl -s http://localhost:$(KIND_AWX_PORT)/api/v2/ping/ | grep -q "ha_enabled"; then \
		echo "$(COLOR_SUCCESS)✓ AWX is healthy!$(COLOR_RESET)"; \
		curl -s http://localhost:$(KIND_AWX_PORT)/api/v2/ping/ | python3 -m json.tool; \
	else \
		echo "$(COLOR_ERROR)✗ AWX health check failed$(COLOR_RESET)"; \
		exit 1; \
	fi

.PHONY: kind-configure
kind-configure: ## Configure AWX with projects, inventories, and job templates (KIND)
	@echo "$(COLOR_INFO)Configuring AWX...$(COLOR_RESET)"
	@CURRENT_BRANCH=$$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main"); \
	echo "$(COLOR_INFO)Using branch: $$CURRENT_BRANCH$(COLOR_RESET)"; \
	export CONTROLLER_HOST=http://localhost:$(KIND_AWX_PORT); \
	export CONTROLLER_USERNAME=$(AWX_ADMIN_USER); \
	export CONTROLLER_PASSWORD=$(AWX_ADMIN_PASSWORD); \
	export AWX_PROJECT_BRANCH=$$CURRENT_BRANCH; \
	ansible-playbook configure-awx.yml
	@echo ""
	@echo "$(COLOR_SUCCESS)✓ AWX configuration complete!$(COLOR_RESET)"
	@echo "$(COLOR_INFO)Ready to launch jobs from:$(COLOR_RESET) http://localhost:$(KIND_AWX_PORT)"

.PHONY: configure
configure: ## Configure AWX with projects, inventories, and job templates (Docker Compose)
	@echo "$(COLOR_INFO)Configuring AWX...$(COLOR_RESET)"
	@CURRENT_BRANCH=$$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main"); \
	echo "$(COLOR_INFO)Using branch: $$CURRENT_BRANCH$(COLOR_RESET)"; \
	export CONTROLLER_HOST=http://localhost:$(AWX_PORT); \
	export CONTROLLER_USERNAME=$(AWX_ADMIN_USER); \
	export CONTROLLER_PASSWORD=$(AWX_ADMIN_PASSWORD); \
	export AWX_PROJECT_BRANCH=$$CURRENT_BRANCH; \
	ansible-playbook configure-awx.yml
	@echo ""
	@echo "$(COLOR_SUCCESS)✓ AWX configuration complete!$(COLOR_RESET)"
	@echo "$(COLOR_INFO)Ready to launch jobs from:$(COLOR_RESET) http://localhost:$(AWX_PORT)"

.PHONY: kind-quickstart
kind-quickstart: kind-start kind-configure ## Complete KIND setup (start + configure)
	@echo ""
	@echo "$(COLOR_SUCCESS)=====================================$(COLOR_RESET)"
	@echo "$(COLOR_SUCCESS)  KIND AWX Quickstart Complete!$(COLOR_RESET)"
	@echo "$(COLOR_SUCCESS)=====================================$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_INFO)Access AWX:$(COLOR_RESET) http://localhost:$(KIND_AWX_PORT)"
	@echo "$(COLOR_INFO)Login:$(COLOR_RESET) admin / password"
	@echo ""
	@echo "$(COLOR_SUCCESS)✓ Custom execution environment with pre-installed collections$(COLOR_RESET)"
	@echo "$(COLOR_INFO)  (vLLM AWX EE includes: containers.podman, ansible.posix)$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_INFO)Next: Edit host variables in AWX UI, then launch a job!$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_INFO)Commands:$(COLOR_RESET)"
	@echo "  make kind-open     - Open AWX in browser"
	@echo "  make kind-logs     - View AWX logs"
	@echo "  make kind-status   - Check status"

# Default target
.DEFAULT_GOAL := help
