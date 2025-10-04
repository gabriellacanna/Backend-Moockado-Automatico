# Guia de Deployment - Backend Mockado Automático

## 🚀 Visão Geral

Este guia fornece instruções detalhadas para deploy do Backend Mockado Automático em diferentes ambientes, desde desenvolvimento local até produção em Kubernetes com Istio/ASM.

## 📋 Pré-requisitos

### Ambiente Local (Docker)
- Docker 20.10+
- Docker Compose 2.0+
- 4GB RAM disponível
- 10GB espaço em disco

### Ambiente Kubernetes
- Kubernetes 1.24+
- Helm 3.8+
- Istio 1.16+ ou Anthos Service Mesh
- kubectl configurado
- 8GB RAM disponível no cluster
- Prometheus Operator (opcional, para monitoramento)

### Ferramentas de Desenvolvimento
```bash
# Instalar ferramentas necessárias
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
chmod 700 get_helm.sh
./get_helm.sh

# Verificar instalação
helm version
kubectl version --client
```

## 🐳 Deployment Local com Docker

### 1. Clone do Repositório
```bash
git clone https://github.com/gabriellacanna/Backend-Moockado-Automatico.git
cd Backend-Moockado-Automatico
```

### 2. Configuração do Ambiente
```bash
# Copiar arquivo de configuração
cp config/local.env.example .env

# Editar configurações se necessário
vim .env
```

### 3. Build e Start dos Serviços
```bash
# Build das imagens
docker-compose build

# Iniciar todos os serviços
docker-compose up -d

# Verificar status
docker-compose ps
```

### 4. Verificação da Instalação
```bash
# Testar saúde dos serviços
curl http://localhost:8080/health  # Collector
curl http://localhost:8081/health  # WireMock Loader
curl http://localhost:8082/__admin/health  # WireMock

# Verificar Redis
docker-compose exec redis redis-cli ping
```

### 5. Executar Exemplo
```bash
# Instalar dependências Python
pip install -r tests/requirements.txt

# Executar exemplo básico
python examples/basic_usage.py
```

## ☸️ Deployment em Kubernetes

### 1. Preparação do Namespace
```bash
# Criar namespace
kubectl create namespace backend-mockado

# Configurar como padrão (opcional)
kubectl config set-context --current --namespace=backend-mockado
```

### 2. Configuração de Secrets
```bash
# Criar secret para registry (se necessário)
kubectl create secret docker-registry regcred \
  --docker-server=your-registry.com \
  --docker-username=your-username \
  --docker-password=your-password \
  --docker-email=your-email@example.com

# Criar secret para configurações sensíveis
kubectl create secret generic backend-mockado-secrets \
  --from-literal=redis-password=your-redis-password \
  --from-literal=api-key=your-api-key
```

### 3. Instalação via Helm

#### Configuração Básica
```bash
# Adicionar repositório Helm (se publicado)
helm repo add backend-mockado https://charts.backend-mockado.com
helm repo update

# Ou usar charts locais
cd helm-charts/backend-mockado
```

#### Valores de Configuração
```yaml
# values-production.yaml
global:
  imageRegistry: "your-registry.com"
  imagePullSecrets:
    - regcred

collector:
  replicaCount: 3
  image:
    tag: "v1.0.0"
  resources:
    requests:
      memory: "256Mi"
      cpu: "250m"
    limits:
      memory: "512Mi"
      cpu: "500m"
  
  config:
    redis_url: "redis://backend-mockado-redis:6379"
    grpc_port: 50051
    log_level: "INFO"

wireMockLoader:
  replicaCount: 2
  image:
    tag: "v1.0.0"
  resources:
    requests:
      memory: "128Mi"
      cpu: "100m"
    limits:
      memory: "256Mi"
      cpu: "200m"

wiremock:
  replicaCount: 2
  image:
    tag: "2.35.0"
  resources:
    requests:
      memory: "256Mi"
      cpu: "200m"
    limits:
      memory: "512Mi"
      cpu: "400m"

redis:
  enabled: true
  auth:
    enabled: true
    password: "your-redis-password"
  master:
    persistence:
      enabled: true
      size: 8Gi

# Configurações de monitoramento
monitoring:
  enabled: true
  prometheus:
    enabled: true
  grafana:
    enabled: true

# Configurações de rede
networkPolicy:
  enabled: true

# Autoscaling
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
```

#### Instalação
```bash
# Instalar com Helm
helm install backend-mockado ./helm-charts/backend-mockado \
  -f values-production.yaml \
  --namespace backend-mockado \
  --create-namespace

# Verificar instalação
helm status backend-mockado -n backend-mockado
kubectl get pods -n backend-mockado
```

### 4. Configuração do Istio/ASM

#### Habilitar Injection do Sidecar
```bash
# Habilitar injection automática no namespace
kubectl label namespace backend-mockado istio-injection=enabled

# Verificar injection
kubectl get namespace backend-mockado --show-labels
```

#### Aplicar EnvoyFilter
```bash
# Aplicar configuração do tap filter
kubectl apply -f envoy-filters/tap-filter-global.yaml

# Ou por namespace específico
kubectl apply -f envoy-filters/tap-filter-namespace.yaml
```

#### Configurar Destinação Rules
```yaml
# destination-rule.yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: backend-mockado-collector
  namespace: backend-mockado
spec:
  host: backend-mockado-collector
  trafficPolicy:
    loadBalancer:
      simple: LEAST_CONN
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        http1MaxPendingRequests: 50
        maxRequestsPerConnection: 10
```

### 5. Configuração de Monitoramento

#### ServiceMonitor para Prometheus
```yaml
# Já incluído no Helm chart
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: backend-mockado
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: backend-mockado
  endpoints:
  - port: metrics
    interval: 30s
    path: /metrics
```

#### Dashboard Grafana
```bash
# Importar dashboard
kubectl create configmap grafana-dashboard-backend-mockado \
  --from-file=monitoring/grafana-dashboard.json \
  -n monitoring

# Aplicar labels para auto-discovery
kubectl label configmap grafana-dashboard-backend-mockado \
  grafana_dashboard=1 \
  -n monitoring
```

## 🔧 Configurações Avançadas

### 1. Configuração de Performance

#### Para Alto Volume (>10k req/s)
```yaml
collector:
  replicaCount: 10
  resources:
    requests:
      memory: "512Mi"
      cpu: "500m"
    limits:
      memory: "1Gi"
      cpu: "1000m"
  
  config:
    grpc_max_workers: 20
    async_workers: 10
    batch_size: 200

redis:
  master:
    resources:
      requests:
        memory: "1Gi"
        cpu: "500m"
      limits:
        memory: "2Gi"
        cpu: "1000m"
    persistence:
      size: 20Gi
```

#### Para Baixa Latência
```yaml
collector:
  config:
    batch_size: 1
    flush_interval: 1
    
wiremock:
  config:
    jetty:
      acceptors: 4
      selectors: 8
      maxThreads: 200
```

### 2. Configuração de Segurança

#### Network Policies Restritivas
```yaml
networkPolicy:
  enabled: true
  ingress:
    - from:
      - namespaceSelector:
          matchLabels:
            name: istio-system
      - namespaceSelector:
          matchLabels:
            name: your-app-namespace
  egress:
    - to:
      - namespaceSelector:
          matchLabels:
            name: backend-mockado
    - to: []
      ports:
      - protocol: TCP
        port: 53
      - protocol: UDP
        port: 53
```

#### Pod Security Standards
```yaml
podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  fsGroup: 1000
  seccompProfile:
    type: RuntimeDefault

securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop:
    - ALL
  readOnlyRootFilesystem: true
  runAsNonRoot: true
  runAsUser: 1000
```

### 3. Configuração de Backup

#### Backup Automático do Redis
```yaml
redis:
  master:
    persistence:
      enabled: true
      size: 20Gi
      storageClass: "fast-ssd"
    
    # Configurar backup para S3
    extraEnvVars:
    - name: REDIS_BACKUP_ENABLED
      value: "true"
    - name: REDIS_BACKUP_S3_BUCKET
      value: "your-backup-bucket"
    - name: REDIS_BACKUP_INTERVAL
      value: "3600"
```

#### Backup dos Mappings WireMock
```yaml
wireMockLoader:
  config:
    backup:
      enabled: true
      storage: "s3"
      s3_bucket: "your-wiremock-backups"
      interval: 3600
      retention_days: 30
```

## 🔍 Verificação e Troubleshooting

### 1. Health Checks
```bash
# Verificar saúde de todos os componentes
kubectl get pods -n backend-mockado
kubectl get svc -n backend-mockado

# Testar endpoints de saúde
kubectl port-forward svc/backend-mockado-collector 8080:8080 &
curl http://localhost:8080/health

kubectl port-forward svc/backend-mockado-wiremock-loader 8081:8080 &
curl http://localhost:8081/health

kubectl port-forward svc/backend-mockado-wiremock 8082:8080 &
curl http://localhost:8082/__admin/health
```

### 2. Logs e Debugging
```bash
# Ver logs dos serviços
kubectl logs -f deployment/backend-mockado-collector -n backend-mockado
kubectl logs -f deployment/backend-mockado-wiremock-loader -n backend-mockado
kubectl logs -f deployment/backend-mockado-wiremock -n backend-mockado

# Ver logs do Envoy sidecar
kubectl logs -f deployment/your-app -c istio-proxy -n your-namespace

# Verificar configuração do Envoy
kubectl exec -it deployment/your-app -c istio-proxy -n your-namespace -- \
  curl localhost:15000/config_dump | jq '.configs[].dynamic_listeners'
```

### 3. Métricas e Monitoramento
```bash
# Verificar métricas Prometheus
kubectl port-forward svc/prometheus 9090:9090 -n monitoring &
# Acessar http://localhost:9090

# Verificar dashboard Grafana
kubectl port-forward svc/grafana 3000:3000 -n monitoring &
# Acessar http://localhost:3000

# Métricas específicas do sistema
curl http://localhost:8080/metrics | grep collector_
curl http://localhost:8081/metrics | grep wiremock_loader_
```

### 4. Testes de Integração
```bash
# Executar testes automatizados
kubectl apply -f helm-charts/backend-mockado/templates/tests/

# Verificar resultados
kubectl get pods -l app.kubernetes.io/component=test -n backend-mockado
kubectl logs -l app.kubernetes.io/component=test -n backend-mockado
```

## 🔄 Atualizações e Rollbacks

### 1. Atualização via Helm
```bash
# Atualizar para nova versão
helm upgrade backend-mockado ./helm-charts/backend-mockado \
  -f values-production.yaml \
  --namespace backend-mockado

# Verificar status da atualização
helm status backend-mockado -n backend-mockado
kubectl rollout status deployment/backend-mockado-collector -n backend-mockado
```

### 2. Rollback
```bash
# Ver histórico de releases
helm history backend-mockado -n backend-mockado

# Fazer rollback para versão anterior
helm rollback backend-mockado 1 -n backend-mockado

# Verificar rollback
kubectl get pods -n backend-mockado
```

### 3. Blue-Green Deployment
```bash
# Instalar nova versão em namespace separado
kubectl create namespace backend-mockado-green
helm install backend-mockado-green ./helm-charts/backend-mockado \
  -f values-production.yaml \
  --namespace backend-mockado-green

# Testar nova versão
# ... executar testes ...

# Trocar tráfego (atualizar EnvoyFilter)
kubectl patch envoyfilter tap-filter -n istio-system --type='merge' -p='
{
  "spec": {
    "configPatches": [{
      "patch": {
        "value": {
          "typed_config": {
            "common_config": {
              "static_config": {
                "record_headers_received_trailers": true,
                "record_downstream_connection": true
              },
              "transport_socket": {
                "name": "envoy.transport_sockets.tls",
                "typed_config": {
                  "@type": "type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.UpstreamTlsContext"
                }
              }
            }
          }
        }
      }
    }]
  }
}'

# Remover versão antiga após validação
helm uninstall backend-mockado -n backend-mockado
kubectl delete namespace backend-mockado
```

## 📊 Configurações por Ambiente

### Desenvolvimento
```yaml
# values-dev.yaml
global:
  environment: development

collector:
  replicaCount: 1
  resources:
    requests:
      memory: "128Mi"
      cpu: "100m"
    limits:
      memory: "256Mi"
      cpu: "200m"

redis:
  master:
    persistence:
      enabled: false

monitoring:
  enabled: false

autoscaling:
  enabled: false
```

### Staging
```yaml
# values-staging.yaml
global:
  environment: staging

collector:
  replicaCount: 2
  resources:
    requests:
      memory: "256Mi"
      cpu: "200m"
    limits:
      memory: "512Mi"
      cpu: "400m"

redis:
  master:
    persistence:
      enabled: true
      size: 4Gi

monitoring:
  enabled: true

autoscaling:
  enabled: true
  minReplicas: 1
  maxReplicas: 5
```

### Produção
```yaml
# values-production.yaml
global:
  environment: production

collector:
  replicaCount: 5
  resources:
    requests:
      memory: "512Mi"
      cpu: "500m"
    limits:
      memory: "1Gi"
      cpu: "1000m"

redis:
  master:
    persistence:
      enabled: true
      size: 20Gi
      storageClass: "fast-ssd"
  
  backup:
    enabled: true

monitoring:
  enabled: true
  alerting:
    enabled: true

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 20

networkPolicy:
  enabled: true

podDisruptionBudget:
  enabled: true
  minAvailable: 2
```

## 🚨 Troubleshooting Comum

### Problema: Pods não iniciam
```bash
# Verificar eventos
kubectl describe pod <pod-name> -n backend-mockado

# Verificar recursos
kubectl top nodes
kubectl top pods -n backend-mockado

# Verificar imagens
kubectl get pods -o jsonpath='{.items[*].spec.containers[*].image}' -n backend-mockado
```

### Problema: Envoy não captura tráfego
```bash
# Verificar se EnvoyFilter foi aplicado
kubectl get envoyfilter -A

# Verificar configuração do Envoy
kubectl exec -it <pod-with-sidecar> -c istio-proxy -- \
  curl localhost:15000/config_dump | jq '.configs[].dynamic_listeners'

# Verificar logs do sidecar
kubectl logs <pod-with-sidecar> -c istio-proxy
```

### Problema: Redis connection failed
```bash
# Verificar status do Redis
kubectl get pods -l app=redis -n backend-mockado

# Testar conectividade
kubectl exec -it deployment/backend-mockado-collector -n backend-mockado -- \
  redis-cli -h backend-mockado-redis ping

# Verificar configuração
kubectl get secret backend-mockado-redis -o yaml -n backend-mockado
```

### Problema: WireMock não recebe mappings
```bash
# Verificar fila Redis
kubectl exec -it deployment/backend-mockado-redis -n backend-mockado -- \
  redis-cli llen wiremock_mappings

# Verificar logs do WireMock Loader
kubectl logs -f deployment/backend-mockado-wiremock-loader -n backend-mockado

# Testar conectividade com WireMock
kubectl exec -it deployment/backend-mockado-wiremock-loader -n backend-mockado -- \
  curl http://backend-mockado-wiremock:8080/__admin/health
```

Este guia fornece uma base sólida para deployment em diferentes ambientes. Ajuste as configurações conforme suas necessidades específicas de infraestrutura e segurança.