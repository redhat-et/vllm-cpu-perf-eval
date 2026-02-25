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
	@echo "$(COLOR_INFO)Container Engine:$(COLOR_RESET) $(CONTAINER_TYPE)"
	@echo "$(COLOR_INFO)Compose Command:$(COLOR_RESET) $(COMPOSE_CMD)"
	@echo ""
	@echo "$(COLOR_INFO)Available targets:$(COLOR_RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(COLOR_SUCCESS)%-20s$(COLOR_RESET) %s\n", $$1, $$2}'

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
			pip3 install podman-compose; \
		fi; \
		echo "$(COLOR_SUCCESS)✓ podman-compose installed$(COLOR_RESET)"; \
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
start: clone-awx ## Start AWX (Docker/Podman Compose)
	@echo "$(COLOR_INFO)Starting AWX with $(CONTAINER_TYPE)...$(COLOR_RESET)"
	@echo "$(COLOR_WARNING)This may take 5-10 minutes on first run (downloading images)$(COLOR_RESET)"
	@cd $(AWX_DIR) && \
		if [ "$(CONTAINER_TYPE)" = "docker" ]; then \
			make docker-compose; \
		else \
			make docker-compose COMPOSE_TAG=$(AWX_VERSION); \
		fi
	@echo ""
	@echo "$(COLOR_SUCCESS)✓ AWX is starting!$(COLOR_RESET)"
	@echo "$(COLOR_INFO)Monitor startup progress:$(COLOR_RESET) make logs"
	@echo "$(COLOR_INFO)Check status:$(COLOR_RESET) make status"
	@echo "$(COLOR_INFO)When ready, access:$(COLOR_RESET) http://localhost:$(AWX_PORT)"

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
	@cd $(AWX_DIR) && $(COMPOSE_CMD) -f tools/docker-compose/_sources/docker-compose.yml stop
	@echo "$(COLOR_SUCCESS)✓ AWX stopped$(COLOR_RESET)"

.PHONY: restart
restart: stop start ## Restart AWX containers

.PHONY: clean
clean: ## Stop and remove AWX containers (keeps data volumes)
	@echo "$(COLOR_WARNING)Stopping and removing AWX containers...$(COLOR_RESET)"
	@cd $(AWX_DIR) && $(COMPOSE_CMD) -f tools/docker-compose/_sources/docker-compose.yml down
	@echo "$(COLOR_SUCCESS)✓ AWX containers removed$(COLOR_RESET)"
	@echo "$(COLOR_INFO)Data volumes preserved. To remove data: make clean-all$(COLOR_RESET)"

.PHONY: clean-all
clean-all: ## Stop and remove AWX containers AND data volumes (DESTRUCTIVE!)
	@echo "$(COLOR_ERROR)WARNING: This will delete all AWX data (jobs, credentials, etc.)!$(COLOR_RESET)"
	@read -p "Are you sure? (type 'yes' to confirm): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		echo "$(COLOR_INFO)Removing AWX containers and volumes...$(COLOR_RESET)"; \
		cd $(AWX_DIR) && $(COMPOSE_CMD) -f tools/docker-compose/_sources/docker-compose.yml down -v; \
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
install: start wait-ready ## Install AWX and wait for it to be ready (one command setup)
	@echo "$(COLOR_SUCCESS)AWX installation complete!$(COLOR_RESET)"

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
quickstart: install ## Full quick start (install + show next steps)
	@echo ""
	@echo "$(COLOR_SUCCESS)=====================================$(COLOR_RESET)"
	@echo "$(COLOR_SUCCESS)  AWX Quick Start Complete!$(COLOR_RESET)"
	@echo "$(COLOR_SUCCESS)=====================================$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_INFO)Next steps:$(COLOR_RESET)"
	@echo "  1. Open AWX: make open (or visit http://localhost:$(AWX_PORT))"
	@echo "  2. Login with: admin / password"
	@echo "  3. Follow: QUICKSTART.md to configure your first test"
	@echo ""
	@echo "$(COLOR_INFO)Useful commands:$(COLOR_RESET)"
	@echo "  make logs      - View AWX logs"
	@echo "  make status    - Check container status"
	@echo "  make stop      - Stop AWX"
	@echo "  make restart   - Restart AWX"
	@echo "  make help      - Show all commands"

# Default target
.DEFAULT_GOAL := help
