# vLLM CPU Performance Evaluation Framework - Main Makefile
# Top-level Makefile for common operations

# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT := $(shell pwd)
AWX_DIR := $(PROJECT_ROOT)/automation/test-execution/awx
ANSIBLE_DIR := $(PROJECT_ROOT)/automation/test-execution/ansible

# Colors for output
COLOR_RESET := \033[0m
COLOR_INFO := \033[36m
COLOR_SUCCESS := \033[32m
COLOR_WARNING := \033[33m

# ============================================================================
# Help Target
# ============================================================================

.PHONY: help
help: ## Show this help message
	@echo "$(COLOR_INFO)vLLM CPU Performance Evaluation Framework$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_INFO)Available targets:$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_SUCCESS)AWX Web UI:$(COLOR_RESET)"
	@grep -E '^awx-[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(COLOR_SUCCESS)%-20s$(COLOR_RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(COLOR_SUCCESS)Testing:$(COLOR_RESET)"
	@grep -E '^test-[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(COLOR_SUCCESS)%-20s$(COLOR_RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(COLOR_SUCCESS)Development:$(COLOR_RESET)"
	@grep -E '^dev-[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(COLOR_SUCCESS)%-20s$(COLOR_RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(COLOR_INFO)Quick Start:$(COLOR_RESET)"
	@echo "  1. make awx-quickstart   - Install AWX web UI"
	@echo "  2. make awx-open         - Open AWX in browser"
	@echo "  3. Configure AWX via web UI (see automation/test-execution/awx/QUICKSTART.md)"
	@echo ""
	@echo "$(COLOR_INFO)Or run tests manually:$(COLOR_RESET)"
	@echo "  make test-llm MODEL=Qwen/Qwen3-0.6B WORKLOAD=chat CORES=16cores-single-socket"

# ============================================================================
# AWX Targets (delegate to AWX Makefile)
# ============================================================================

.PHONY: awx-quickstart
awx-quickstart: ## Install and start AWX (one command setup)
	@$(MAKE) -C $(AWX_DIR) quickstart

.PHONY: awx-start
awx-start: ## Start AWX containers
	@$(MAKE) -C $(AWX_DIR) start

.PHONY: awx-stop
awx-stop: ## Stop AWX containers
	@$(MAKE) -C $(AWX_DIR) stop

.PHONY: awx-restart
awx-restart: ## Restart AWX containers
	@$(MAKE) -C $(AWX_DIR) restart

.PHONY: awx-logs
awx-logs: ## View AWX logs
	@$(MAKE) -C $(AWX_DIR) logs

.PHONY: awx-status
awx-status: ## Check AWX container status
	@$(MAKE) -C $(AWX_DIR) status

.PHONY: awx-health
awx-health: ## Check AWX health endpoint
	@$(MAKE) -C $(AWX_DIR) health

.PHONY: awx-open
awx-open: ## Open AWX in browser
	@$(MAKE) -C $(AWX_DIR) open

.PHONY: awx-clean
awx-clean: ## Stop and remove AWX containers (keeps data)
	@$(MAKE) -C $(AWX_DIR) clean

.PHONY: awx-clean-all
awx-clean-all: ## Remove AWX completely (DESTRUCTIVE!)
	@$(MAKE) -C $(AWX_DIR) clean-all

.PHONY: awx-help
awx-help: ## Show AWX-specific commands
	@$(MAKE) -C $(AWX_DIR) help

# ============================================================================
# Testing Targets (run Ansible playbooks directly)
# ============================================================================

.PHONY: test-llm
test-llm: ## Run LLM test (usage: make test-llm MODEL=Qwen/Qwen3-0.6B WORKLOAD=chat CORES=16cores-single-socket)
	@if [ -z "$(MODEL)" ] || [ -z "$(WORKLOAD)" ] || [ -z "$(CORES)" ]; then \
		echo "$(COLOR_WARNING)Usage: make test-llm MODEL=<model> WORKLOAD=<workload> CORES=<cores>$(COLOR_RESET)"; \
		echo ""; \
		echo "Examples:"; \
		echo "  make test-llm MODEL=Qwen/Qwen3-0.6B WORKLOAD=chat CORES=16cores-single-socket"; \
		echo "  make test-llm MODEL=meta-llama/Llama-3.2-1B-Instruct WORKLOAD=summarization CORES=32cores-single-socket"; \
		echo ""; \
		echo "Available workloads: chat, summarization, code, rag"; \
		echo "Available cores: 8cores-single-socket, 16cores-single-socket, 32cores-single-socket"; \
		exit 1; \
	fi
	@echo "$(COLOR_INFO)Running LLM test...$(COLOR_RESET)"
	@cd $(ANSIBLE_DIR) && ansible-playbook -i inventory/hosts.yml \
		playbooks/llm/run-guidellm-test.yml \
		-e "test_model=$(MODEL)" \
		-e "workload_type=$(WORKLOAD)" \
		-e "core_config_name=$(CORES)"

.PHONY: test-embedding
test-embedding: ## Run embedding test (usage: make test-embedding MODEL=ibm-granite/granite-embedding-english-r2 CORES=16cores-single-socket)
	@if [ -z "$(MODEL)" ] || [ -z "$(CORES)" ]; then \
		echo "$(COLOR_WARNING)Usage: make test-embedding MODEL=<model> CORES=<cores>$(COLOR_RESET)"; \
		echo ""; \
		echo "Examples:"; \
		echo "  make test-embedding MODEL=ibm-granite/granite-embedding-english-r2 CORES=16cores-single-socket"; \
		echo ""; \
		echo "Available cores: 8cores-single-socket, 16cores-single-socket, 32cores-single-socket"; \
		exit 1; \
	fi
	@echo "$(COLOR_INFO)Running embedding test...$(COLOR_RESET)"
	@cd $(ANSIBLE_DIR) && ansible-playbook -i inventory/hosts.yml \
		playbooks/embedding/run-tests.yml \
		-e "test_model=$(MODEL)" \
		-e "core_config_name=$(CORES)"

.PHONY: test-check-inventory
test-check-inventory: ## Validate Ansible inventory configuration
	@echo "$(COLOR_INFO)Checking Ansible inventory...$(COLOR_RESET)"
	@cd $(ANSIBLE_DIR) && ansible-inventory -i inventory/hosts.yml --list | head -50
	@echo ""
	@echo "$(COLOR_SUCCESS)✓ Inventory loaded successfully$(COLOR_RESET)"

.PHONY: test-ping
test-ping: ## Test connectivity to DUT and load generator
	@echo "$(COLOR_INFO)Testing connectivity...$(COLOR_RESET)"
	@cd $(ANSIBLE_DIR) && ansible -i inventory/hosts.yml all -m ping

# ============================================================================
# Development Targets
# ============================================================================

.PHONY: dev-lint
dev-lint: ## Run linters (pre-commit hooks)
	@echo "$(COLOR_INFO)Running linters...$(COLOR_RESET)"
	@pre-commit run --all-files

.PHONY: dev-setup
dev-setup: ## Setup development environment
	@echo "$(COLOR_INFO)Setting up development environment...$(COLOR_RESET)"
	@if ! command -v pre-commit >/dev/null 2>&1; then \
		echo "Installing pre-commit..."; \
		pip3 install pre-commit; \
	fi
	@pre-commit install
	@echo "$(COLOR_SUCCESS)✓ Development environment ready$(COLOR_RESET)"

.PHONY: dev-clean
dev-clean: ## Clean temporary files and caches
	@echo "$(COLOR_INFO)Cleaning temporary files...$(COLOR_RESET)"
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -delete
	@find . -type d -name ".pytest_cache" -delete
	@find . -type f -name ".DS_Store" -delete
	@echo "$(COLOR_SUCCESS)✓ Cleanup complete$(COLOR_RESET)"

.PHONY: dev-docs
dev-docs: ## Open documentation in browser
	@echo "$(COLOR_INFO)Opening documentation...$(COLOR_RESET)"
	@if command -v open >/dev/null 2>&1; then \
		open README.md; \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open README.md; \
	else \
		echo "Documentation: README.md"; \
	fi

# ============================================================================
# Git Workflow Targets
# ============================================================================

.PHONY: git-status
git-status: ## Show git status and recent commits
	@echo "$(COLOR_INFO)Git Status:$(COLOR_RESET)"
	@git status -sb
	@echo ""
	@echo "$(COLOR_INFO)Recent Commits:$(COLOR_RESET)"
	@git log --oneline -10

.PHONY: git-branch
git-branch: ## Show current branch and commits ahead/behind
	@git status -sb
	@git log --oneline -5

# ============================================================================
# Information Targets
# ============================================================================

.PHONY: info
info: ## Show project information
	@echo "$(COLOR_INFO)Project Information$(COLOR_RESET)"
	@echo ""
	@echo "Project Root: $(PROJECT_ROOT)"
	@echo "AWX Directory: $(AWX_DIR)"
	@echo "Ansible Directory: $(ANSIBLE_DIR)"
	@echo ""
	@echo "$(COLOR_INFO)Git Branch:$(COLOR_RESET)"
	@git branch --show-current
	@echo ""
	@echo "$(COLOR_INFO)Available Documentation:$(COLOR_RESET)"
	@echo "  - README.md (main project documentation)"
	@echo "  - automation/test-execution/awx/README.md (AWX setup guide)"
	@echo "  - automation/test-execution/awx/QUICKSTART.md (AWX quick start)"
	@echo "  - automation/test-execution/ansible/inventory/README.md (inventory guide)"

.PHONY: list-models
list-models: ## List available LLM and embedding models
	@echo "$(COLOR_INFO)Available LLM Models:$(COLOR_RESET)"
	@grep -A 1 "name:" models/llm-models/model-matrix.yaml | grep "full_name:" | sed 's/.*full_name: "/  - /' | sed 's/".*//'
	@echo ""
	@echo "$(COLOR_INFO)Available Embedding Models:$(COLOR_RESET)"
	@grep -A 1 "name:" models/embedding-models/model-matrix.yaml | grep "full_name:" | sed 's/.*full_name: "/  - /' | sed 's/".*//'

# Default target
.DEFAULT_GOAL := help
