# Makefile para Backend Mockado Automático

.PHONY: help build test clean deploy lint format check-deps

# Variáveis
DOCKER_REGISTRY ?= your-registry.com
IMAGE_TAG ?= latest
NAMESPACE ?= backend-mockado

# Cores para output
RED=\033[0;31m
GREEN=\033[0;32m
YELLOW=\033[1;33m
BLUE=\033[0;34m
NC=\033[0m # No Color

help: ## Mostra esta mensagem de ajuda
	@echo "$(BLUE)Backend Mockado Automático - Makefile$(NC)"
	@echo ""
	@echo "$(YELLOW)Comandos disponíveis:$(NC)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Desenvolvimento
install: ## Instala dependências de desenvolvimento
	@echo "$(BLUE)Instalando dependências...$(NC)"
	python -m pip install --upgrade pip
	pip install -r collector/requirements.txt
	pip install -r wiremock-loader/requirements.txt
	pip install -r tests/requirements.txt
	pip install pre-commit black flake8 mypy pytest-cov
	pre-commit install

format: ## Formata código com black
	@echo "$(BLUE)Formatando código...$(NC)"
	black collector/ wiremock-loader/ tests/ examples/
	@echo "$(GREEN)Código formatado!$(NC)"

lint: ## Executa linting com flake8 e mypy
	@echo "$(BLUE)Executando linting...$(NC)"
	flake8 collector/ wiremock-loader/ tests/ examples/
	mypy collector/ wiremock-loader/
	@echo "$(GREEN)Linting concluído!$(NC)"

check-deps: ## Verifica dependências de segurança
	@echo "$(BLUE)Verificando dependências...$(NC)"
	pip-audit
	safety check
	@echo "$(GREEN)Dependências verificadas!$(NC)"

# Testes
test: ## Executa todos os testes
	@echo "$(BLUE)Executando testes...$(NC)"
	cd tests && python -m pytest unit/ -v
	cd tests && python -m pytest integration/ -v
	@echo "$(GREEN)Testes concluídos!$(NC)"

test-unit: ## Executa apenas testes unitários
	@echo "$(BLUE)Executando testes unitários...$(NC)"
	cd tests && python -m pytest unit/ -v

test-integration: ## Executa apenas testes de integração
	@echo "$(BLUE)Executando testes de integração...$(NC)"
	cd tests && python -m pytest integration/ -v

test-coverage: ## Executa testes com cobertura
	@echo "$(BLUE)Executando testes com cobertura...$(NC)"
	cd tests && python -m pytest --cov=../collector --cov=../wiremock-loader --cov-report=html --cov-report=term
	@echo "$(GREEN)Relatório de cobertura gerado em tests/htmlcov/$(NC)"

# Docker
build: ## Constrói todas as imagens Docker
	@echo "$(BLUE)Construindo imagens Docker...$(NC)"
	docker build -t $(DOCKER_REGISTRY)/backend-mockado-collector:$(IMAGE_TAG) collector/
	docker build -t $(DOCKER_REGISTRY)/backend-mockado-wiremock-loader:$(IMAGE_TAG) wiremock-loader/
	@echo "$(GREEN)Imagens construídas!$(NC)"

build-collector: ## Constrói apenas a imagem do Collector
	@echo "$(BLUE)Construindo imagem do Collector...$(NC)"
	docker build -t $(DOCKER_REGISTRY)/backend-mockado-collector:$(IMAGE_TAG) collector/

build-wiremock-loader: ## Constrói apenas a imagem do WireMock Loader
	@echo "$(BLUE)Construindo imagem do WireMock Loader...$(NC)"
	docker build -t $(DOCKER_REGISTRY)/backend-mockado-wiremock-loader:$(IMAGE_TAG) wiremock-loader/

push: ## Faz push das imagens para o registry
	@echo "$(BLUE)Fazendo push das imagens...$(NC)"
	docker push $(DOCKER_REGISTRY)/backend-mockado-collector:$(IMAGE_TAG)
	docker push $(DOCKER_REGISTRY)/backend-mockado-wiremock-loader:$(IMAGE_TAG)
	@echo "$(GREEN)Push concluído!$(NC)"

# Docker Compose
up: ## Inicia serviços com docker-compose
	@echo "$(BLUE)Iniciando serviços...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)Serviços iniciados!$(NC)"

down: ## Para serviços do docker-compose
	@echo "$(BLUE)Parando serviços...$(NC)"
	docker-compose down
	@echo "$(GREEN)Serviços parados!$(NC)"

logs: ## Mostra logs dos serviços
	docker-compose logs -f

restart: ## Reinicia serviços
	@echo "$(BLUE)Reiniciando serviços...$(NC)"
	docker-compose restart
	@echo "$(GREEN)Serviços reiniciados!$(NC)"

# Kubernetes
k8s-deploy: ## Deploy no Kubernetes via Helm
	@echo "$(BLUE)Fazendo deploy no Kubernetes...$(NC)"
	helm upgrade --install backend-mockado ./helm-charts/backend-mockado \
		--namespace $(NAMESPACE) \
		--create-namespace \
		--set global.imageRegistry=$(DOCKER_REGISTRY) \
		--set global.imageTag=$(IMAGE_TAG)
	@echo "$(GREEN)Deploy concluído!$(NC)"

k8s-status: ## Verifica status do deployment
	@echo "$(BLUE)Status do deployment:$(NC)"
	kubectl get pods -n $(NAMESPACE)
	kubectl get svc -n $(NAMESPACE)
	helm status backend-mockado -n $(NAMESPACE)

k8s-logs: ## Mostra logs dos pods
	@echo "$(BLUE)Logs do Collector:$(NC)"
	kubectl logs -f deployment/backend-mockado-collector -n $(NAMESPACE)

k8s-logs-loader: ## Mostra logs do WireMock Loader
	@echo "$(BLUE)Logs do WireMock Loader:$(NC)"
	kubectl logs -f deployment/backend-mockado-wiremock-loader -n $(NAMESPACE)

k8s-uninstall: ## Remove deployment do Kubernetes
	@echo "$(YELLOW)Removendo deployment...$(NC)"
	helm uninstall backend-mockado -n $(NAMESPACE)
	kubectl delete namespace $(NAMESPACE)
	@echo "$(GREEN)Deployment removido!$(NC)"

# Envoy Filters
envoy-apply: ## Aplica EnvoyFilters
	@echo "$(BLUE)Aplicando EnvoyFilters...$(NC)"
	kubectl apply -f envoy-filters/tap-filter-global.yaml
	@echo "$(GREEN)EnvoyFilters aplicados!$(NC)"

envoy-remove: ## Remove EnvoyFilters
	@echo "$(YELLOW)Removendo EnvoyFilters...$(NC)"
	kubectl delete -f envoy-filters/tap-filter-global.yaml
	@echo "$(GREEN)EnvoyFilters removidos!$(NC)"

# Monitoramento
metrics: ## Mostra métricas dos serviços
	@echo "$(BLUE)Métricas do Collector:$(NC)"
	curl -s http://localhost:8080/metrics | grep collector_
	@echo ""
	@echo "$(BLUE)Métricas do WireMock Loader:$(NC)"
	curl -s http://localhost:8081/metrics | grep wiremock_loader_

health: ## Verifica saúde dos serviços
	@echo "$(BLUE)Verificando saúde dos serviços...$(NC)"
	@echo -n "Collector: "
	@curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health && echo " $(GREEN)OK$(NC)" || echo " $(RED)FAIL$(NC)"
	@echo -n "WireMock Loader: "
	@curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/health && echo " $(GREEN)OK$(NC)" || echo " $(RED)FAIL$(NC)"
	@echo -n "WireMock: "
	@curl -s -o /dev/null -w "%{http_code}" http://localhost:8082/__admin/health && echo " $(GREEN)OK$(NC)" || echo " $(RED)FAIL$(NC)"

# Exemplos
example-basic: ## Executa exemplo básico
	@echo "$(BLUE)Executando exemplo básico...$(NC)"
	python examples/basic_usage.py

example-envoy: ## Executa simulação do Envoy
	@echo "$(BLUE)Executando simulação do Envoy...$(NC)"
	python examples/envoy_tap_simulation.py

# Limpeza
clean: ## Remove arquivos temporários e cache
	@echo "$(BLUE)Limpando arquivos temporários...$(NC)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	@echo "$(GREEN)Limpeza concluída!$(NC)"

clean-docker: ## Remove imagens Docker locais
	@echo "$(YELLOW)Removendo imagens Docker...$(NC)"
	docker rmi $(DOCKER_REGISTRY)/backend-mockado-collector:$(IMAGE_TAG) || true
	docker rmi $(DOCKER_REGISTRY)/backend-mockado-wiremock-loader:$(IMAGE_TAG) || true
	docker system prune -f
	@echo "$(GREEN)Imagens removidas!$(NC)"

# Segurança
security-scan: ## Executa scan de segurança nas imagens
	@echo "$(BLUE)Executando scan de segurança...$(NC)"
	docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
		aquasec/trivy image $(DOCKER_REGISTRY)/backend-mockado-collector:$(IMAGE_TAG)
	docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
		aquasec/trivy image $(DOCKER_REGISTRY)/backend-mockado-wiremock-loader:$(IMAGE_TAG)

# CI/CD
ci: lint test build ## Pipeline completo de CI
	@echo "$(GREEN)Pipeline de CI concluído!$(NC)"

cd: push k8s-deploy ## Pipeline completo de CD
	@echo "$(GREEN)Pipeline de CD concluído!$(NC)"

# Desenvolvimento completo
dev-setup: install ## Setup completo do ambiente de desenvolvimento
	@echo "$(BLUE)Configurando ambiente de desenvolvimento...$(NC)"
	cp config/local.env.example .env
	@echo "$(GREEN)Ambiente configurado!$(NC)"
	@echo "$(YELLOW)Próximos passos:$(NC)"
	@echo "  1. Edite o arquivo .env conforme necessário"
	@echo "  2. Execute 'make up' para iniciar os serviços"
	@echo "  3. Execute 'make example-basic' para testar"

dev-test: format lint test ## Executa todos os checks de desenvolvimento
	@echo "$(GREEN)Todos os checks de desenvolvimento passaram!$(NC)"

# Release
release: ## Cria uma nova release
	@echo "$(BLUE)Criando release...$(NC)"
	@read -p "Versão da release (ex: v1.0.0): " version; \
	git tag -a $$version -m "Release $$version"; \
	git push origin $$version; \
	echo "$(GREEN)Release $$version criada!$(NC)"

# Backup
backup: ## Cria backup dos dados Redis
	@echo "$(BLUE)Criando backup...$(NC)"
	docker-compose exec redis redis-cli BGSAVE
	docker cp $$(docker-compose ps -q redis):/data/dump.rdb ./backup-$$(date +%Y%m%d-%H%M%S).rdb
	@echo "$(GREEN)Backup criado!$(NC)"

# Documentação
docs: ## Gera documentação
	@echo "$(BLUE)Gerando documentação...$(NC)"
	# Adicionar comando para gerar docs se necessário
	@echo "$(GREEN)Documentação disponível em docs/$(NC)"

# Default target
.DEFAULT_GOAL := help