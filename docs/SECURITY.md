# Guia de Segurança - Backend Mockado Automático

## 🔒 Visão Geral de Segurança

O Backend Mockado Automático foi projetado com segurança como prioridade, implementando múltiplas camadas de proteção para garantir que dados sensíveis nunca sejam expostos ou persistidos de forma insegura.

## 🛡️ Princípios de Segurança

### 1. **Defense in Depth (Defesa em Profundidade)**
- Múltiplas camadas de segurança independentes
- Falha segura em caso de comprometimento de uma camada
- Validação em cada ponto de processamento

### 2. **Principle of Least Privilege (Princípio do Menor Privilégio)**
- Containers executam como usuário não-root
- Permissões mínimas necessárias para cada componente
- Network policies restritivas

### 3. **Data Minimization (Minimização de Dados)**
- Sanitização automática de dados sensíveis
- Não persistência de dados originais
- Retenção mínima necessária

### 4. **Zero Trust Architecture**
- Verificação contínua de identidade e autorização
- Criptografia em trânsito e em repouso
- Monitoramento e auditoria contínuos

## 🔐 Sanitização de Dados Sensíveis

### Categorias de Dados Protegidos

#### 1. **Credenciais e Tokens**
```python
CREDENTIAL_PATTERNS = {
    'jwt_token': r'eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*',
    'api_key': r'(api[_-]?key|apikey)["\s]*[:=]["\s]*[A-Za-z0-9_-]{16,}',
    'bearer_token': r'Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*',
    'basic_auth': r'Basic\s+[A-Za-z0-9+/]+=*',
    'oauth_token': r'oauth[_-]?token["\s]*[:=]["\s]*[A-Za-z0-9_-]{16,}'
}
```

#### 2. **Informações Pessoais (PII)**
```python
PII_PATTERNS = {
    'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    'cpf': r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b',
    'cnpj': r'\b\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2}\b',
    'phone_br': r'\+?55\s?\(?\d{2}\)?\s?\d{4,5}-?\d{4}',
    'phone_intl': r'\+\d{1,3}\s?\(?\d{1,4}\)?\s?\d{1,4}-?\d{1,4}',
    'ssn': r'\b\d{3}-?\d{2}-?\d{4}\b'
}
```

#### 3. **Dados Financeiros**
```python
FINANCIAL_PATTERNS = {
    'credit_card': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
    'bank_account': r'\b\d{4,12}-?\d{1,2}\b',
    'routing_number': r'\b\d{9}\b',
    'iban': r'\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b'
}
```

#### 4. **Senhas e Secrets**
```python
PASSWORD_PATTERNS = {
    'password': r'(password|passwd|pwd)["\s]*[:=]["\s]*[^\s"\']{6,}',
    'secret': r'(secret|private[_-]?key)["\s]*[:=]["\s]*[A-Za-z0-9+/=]{16,}',
    'hash': r'\b[a-fA-F0-9]{32,128}\b'
}
```

### Algoritmo de Sanitização

```python
class DataSanitizer:
    def __init__(self):
        self.patterns = {
            **CREDENTIAL_PATTERNS,
            **PII_PATTERNS,
            **FINANCIAL_PATTERNS,
            **PASSWORD_PATTERNS
        }
        
        self.replacements = {
            'jwt_token': 'SANITIZED_JWT',
            'api_key': 'SANITIZED_API_KEY',
            'email': 'SANITIZED_EMAIL',
            'credit_card': 'SANITIZED_CARD',
            'password': 'SANITIZED_PASSWORD',
            # ... outros replacements
        }
    
    def sanitize_recursive(self, data):
        """Sanitiza dados recursivamente em estruturas aninhadas."""
        if isinstance(data, dict):
            return {k: self.sanitize_recursive(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.sanitize_recursive(item) for item in data]
        elif isinstance(data, str):
            return self.sanitize_string(data)
        else:
            return data
    
    def sanitize_string(self, text):
        """Aplica padrões de sanitização em strings."""
        for pattern_name, pattern in self.patterns.items():
            replacement = self.replacements.get(pattern_name, 'SANITIZED_DATA')
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text
```

### Validação de Sanitização

```python
def validate_sanitization(original_data, sanitized_data):
    """Valida se a sanitização foi efetiva."""
    original_str = json.dumps(original_data, default=str)
    sanitized_str = json.dumps(sanitized_data, default=str)
    
    # Verificar se padrões sensíveis ainda existem
    for pattern_name, pattern in SENSITIVE_PATTERNS.items():
        matches = re.findall(pattern, sanitized_str, re.IGNORECASE)
        if matches:
            raise SecurityError(f"Sanitization failed for pattern {pattern_name}: {matches}")
    
    # Verificar se marcadores de sanitização estão presentes
    sanitized_markers = ['SANITIZED_', 'REDACTED_', 'MASKED_']
    has_markers = any(marker in sanitized_str for marker in sanitized_markers)
    
    if not has_markers and original_str != sanitized_str:
        logger.warning("Data was modified but no sanitization markers found")
    
    return True
```

## 🔒 Segurança de Containers

### 1. **Imagens Base Seguras**
```dockerfile
# Usar imagens distroless ou alpine
FROM gcr.io/distroless/python3-debian11:latest

# Ou Alpine com atualizações de segurança
FROM python:3.11-alpine
RUN apk update && apk upgrade && apk add --no-cache \
    && rm -rf /var/cache/apk/*
```

### 2. **Usuário Não-Root**
```dockerfile
# Criar usuário não-privilegiado
RUN addgroup -g 1000 appgroup && \
    adduser -u 1000 -G appgroup -s /bin/sh -D appuser

# Definir ownership dos arquivos
COPY --chown=appuser:appgroup . /app
WORKDIR /app

# Executar como usuário não-root
USER appuser
```

### 3. **Filesystem Read-Only**
```yaml
# Kubernetes SecurityContext
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities:
    drop:
    - ALL
  seccompProfile:
    type: RuntimeDefault
```

### 4. **Volumes Temporários**
```yaml
# Montar volumes temporários para escrita
volumeMounts:
- name: tmp-volume
  mountPath: /tmp
- name: var-log
  mountPath: /var/log
- name: app-cache
  mountPath: /app/cache

volumes:
- name: tmp-volume
  emptyDir: {}
- name: var-log
  emptyDir: {}
- name: app-cache
  emptyDir:
    sizeLimit: 1Gi
```

## 🌐 Segurança de Rede

### 1. **Network Policies**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-mockado-netpol
  namespace: backend-mockado
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: backend-mockado
  policyTypes:
  - Ingress
  - Egress
  
  # Regras de entrada
  ingress:
  # Permitir tráfego do Istio sidecar
  - from:
    - namespaceSelector:
        matchLabels:
          name: istio-system
    ports:
    - protocol: TCP
      port: 50051  # gRPC Collector
    - protocol: TCP
      port: 8080   # HTTP APIs
  
  # Permitir tráfego de aplicações monitoradas
  - from:
    - namespaceSelector:
        matchLabels:
          monitored: "true"
    ports:
    - protocol: TCP
      port: 50051
  
  # Regras de saída
  egress:
  # Permitir comunicação interna
  - to:
    - podSelector:
        matchLabels:
          app.kubernetes.io/name: backend-mockado
    ports:
    - protocol: TCP
      port: 6379   # Redis
    - protocol: TCP
      port: 8080   # WireMock
  
  # Permitir DNS
  - to: []
    ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
  
  # Permitir HTTPS para APIs externas (se necessário)
  - to: []
    ports:
    - protocol: TCP
      port: 443
```

### 2. **Service Mesh Security (Istio)**
```yaml
# PeerAuthentication - mTLS obrigatório
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: backend-mockado-mtls
  namespace: backend-mockado
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: backend-mockado
  mtls:
    mode: STRICT

---
# AuthorizationPolicy - Controle de acesso
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: backend-mockado-authz
  namespace: backend-mockado
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: backend-mockado
  rules:
  # Permitir tráfego do Istio gateway
  - from:
    - source:
        principals: ["cluster.local/ns/istio-system/sa/istio-ingressgateway-service-account"]
  
  # Permitir tráfego de aplicações autorizadas
  - from:
    - source:
        namespaces: ["production", "staging"]
    to:
    - operation:
        methods: ["POST"]
        paths: ["/api/v1/capture"]
  
  # Permitir health checks
  - to:
    - operation:
        methods: ["GET"]
        paths: ["/health", "/ready", "/metrics"]
```

### 3. **TLS/SSL Configuration**
```yaml
# Certificate para TLS
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: backend-mockado-tls
  namespace: backend-mockado
spec:
  secretName: backend-mockado-tls-secret
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - backend-mockado.yourdomain.com
  - collector.backend-mockado.yourdomain.com
  - wiremock.backend-mockado.yourdomain.com

---
# Gateway com TLS
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: backend-mockado-gateway
  namespace: backend-mockado
spec:
  selector:
    istio: ingressgateway
  servers:
  - port:
      number: 443
      name: https
      protocol: HTTPS
    tls:
      mode: SIMPLE
      credentialName: backend-mockado-tls-secret
    hosts:
    - backend-mockado.yourdomain.com
```

## 🔑 Gerenciamento de Secrets

### 1. **Kubernetes Secrets**
```yaml
# Secret para configurações sensíveis
apiVersion: v1
kind: Secret
metadata:
  name: backend-mockado-secrets
  namespace: backend-mockado
type: Opaque
data:
  redis-password: <base64-encoded-password>
  api-key: <base64-encoded-api-key>
  jwt-secret: <base64-encoded-jwt-secret>

---
# Secret para registry privado
apiVersion: v1
kind: Secret
metadata:
  name: regcred
  namespace: backend-mockado
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: <base64-encoded-docker-config>
```

### 2. **External Secrets Operator**
```yaml
# SecretStore para AWS Secrets Manager
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets-manager
  namespace: backend-mockado
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa

---
# ExternalSecret
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: backend-mockado-external-secrets
  namespace: backend-mockado
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: backend-mockado-secrets
    creationPolicy: Owner
  data:
  - secretKey: redis-password
    remoteRef:
      key: backend-mockado/redis
      property: password
  - secretKey: api-key
    remoteRef:
      key: backend-mockado/api
      property: key
```

### 3. **Sealed Secrets**
```bash
# Instalar Sealed Secrets Controller
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.18.0/controller.yaml

# Criar SealedSecret
echo -n mypassword | kubectl create secret generic mysecret --dry-run=client --from-file=password=/dev/stdin -o yaml | kubeseal -o yaml > mysealedsecret.yaml

# Aplicar SealedSecret
kubectl apply -f mysealedsecret.yaml
```

## 🔍 Monitoramento e Auditoria

### 1. **Logging de Segurança**
```python
import structlog
from pythonjsonlogger import jsonlogger

# Configurar logging estruturado
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Log de eventos de segurança
def log_security_event(event_type, details, severity="INFO"):
    logger.info(
        "security_event",
        event_type=event_type,
        details=details,
        severity=severity,
        timestamp=datetime.utcnow().isoformat(),
        component="backend-mockado"
    )

# Exemplos de uso
log_security_event("data_sanitization", {
    "patterns_detected": ["jwt_token", "credit_card"],
    "request_id": "req-123",
    "source_ip": "10.0.1.100"
})

log_security_event("unauthorized_access", {
    "endpoint": "/api/v1/capture",
    "source_ip": "192.168.1.100",
    "user_agent": "curl/7.68.0"
}, severity="WARNING")
```

### 2. **Métricas de Segurança**
```python
from prometheus_client import Counter, Histogram, Gauge

# Métricas de sanitização
sanitization_operations = Counter(
    'sanitization_operations_total',
    'Total sanitization operations',
    ['pattern_type', 'status']
)

# Métricas de acesso
access_attempts = Counter(
    'access_attempts_total',
    'Total access attempts',
    ['endpoint', 'status', 'source']
)

# Métricas de dados sensíveis detectados
sensitive_data_detected = Counter(
    'sensitive_data_detected_total',
    'Total sensitive data patterns detected',
    ['pattern_type', 'component']
)

# Uso das métricas
sanitization_operations.labels(pattern_type='jwt_token', status='success').inc()
access_attempts.labels(endpoint='/api/v1/capture', status='authorized', source='istio').inc()
sensitive_data_detected.labels(pattern_type='credit_card', component='collector').inc()
```

### 3. **Alertas de Segurança**
```yaml
# PrometheusRule para alertas de segurança
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: backend-mockado-security-alerts
  namespace: backend-mockado
spec:
  groups:
  - name: security
    rules:
    # Alerta para muitos dados sensíveis detectados
    - alert: HighSensitiveDataDetection
      expr: rate(sensitive_data_detected_total[5m]) > 10
      for: 2m
      labels:
        severity: warning
        component: backend-mockado
      annotations:
        summary: "High rate of sensitive data detection"
        description: "Detected {{ $value }} sensitive data patterns per second in the last 5 minutes"
    
    # Alerta para falhas de sanitização
    - alert: SanitizationFailure
      expr: rate(sanitization_operations_total{status="error"}[5m]) > 0
      for: 1m
      labels:
        severity: critical
        component: backend-mockado
      annotations:
        summary: "Sanitization failures detected"
        description: "{{ $value }} sanitization failures per second in the last 5 minutes"
    
    # Alerta para tentativas de acesso não autorizado
    - alert: UnauthorizedAccess
      expr: rate(access_attempts_total{status="unauthorized"}[5m]) > 1
      for: 1m
      labels:
        severity: warning
        component: backend-mockado
      annotations:
        summary: "Unauthorized access attempts"
        description: "{{ $value }} unauthorized access attempts per second"
```

## 🛡️ Hardening e Best Practices

### 1. **Container Hardening**
```dockerfile
# Multi-stage build para reduzir superfície de ataque
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM gcr.io/distroless/python3-debian11:latest
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --chown=1000:1000 . /app
WORKDIR /app
USER 1000
EXPOSE 8080
CMD ["python", "main.py"]
```

### 2. **Kubernetes Security Policies**
```yaml
# Pod Security Policy (deprecated, use Pod Security Standards)
apiVersion: policy/v1beta1
kind: PodSecurityPolicy
metadata:
  name: backend-mockado-psp
spec:
  privileged: false
  allowPrivilegeEscalation: false
  requiredDropCapabilities:
    - ALL
  volumes:
    - 'configMap'
    - 'emptyDir'
    - 'projected'
    - 'secret'
    - 'downwardAPI'
    - 'persistentVolumeClaim'
  runAsUser:
    rule: 'MustRunAsNonRoot'
  seLinux:
    rule: 'RunAsAny'
  fsGroup:
    rule: 'RunAsAny'
```

### 3. **Resource Limits**
```yaml
# Limites de recursos para prevenir DoS
resources:
  requests:
    memory: "256Mi"
    cpu: "250m"
    ephemeral-storage: "1Gi"
  limits:
    memory: "512Mi"
    cpu: "500m"
    ephemeral-storage: "2Gi"

# Limites de conexão
env:
- name: MAX_CONNECTIONS
  value: "1000"
- name: CONNECTION_TIMEOUT
  value: "30"
- name: REQUEST_TIMEOUT
  value: "60"
```

### 4. **Backup e Recovery Seguro**
```yaml
# CronJob para backup seguro
apiVersion: batch/v1
kind: CronJob
metadata:
  name: secure-backup
  namespace: backend-mockado
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          securityContext:
            runAsNonRoot: true
            runAsUser: 1000
            fsGroup: 1000
          containers:
          - name: backup
            image: backup-tool:latest
            command:
            - /bin/sh
            - -c
            - |
              # Backup com criptografia
              kubectl exec deployment/backend-mockado-redis -- \
                redis-cli --rdb /tmp/backup.rdb
              
              # Criptografar backup
              gpg --cipher-algo AES256 --compress-algo 1 --s2k-mode 3 \
                  --s2k-digest-algo SHA512 --s2k-count 65536 --force-mdc \
                  --quiet --no-greeting --batch --yes \
                  --passphrase-file /secrets/backup-passphrase \
                  --output /backups/backup-$(date +%Y%m%d).rdb.gpg \
                  --symmetric /tmp/backup.rdb
              
              # Upload para storage seguro
              aws s3 cp /backups/backup-$(date +%Y%m%d).rdb.gpg \
                s3://secure-backups/backend-mockado/ \
                --server-side-encryption AES256
            
            volumeMounts:
            - name: backup-secrets
              mountPath: /secrets
              readOnly: true
            - name: backup-storage
              mountPath: /backups
          
          volumes:
          - name: backup-secrets
            secret:
              secretName: backup-secrets
          - name: backup-storage
            emptyDir: {}
          
          restartPolicy: OnFailure
```

## 🚨 Incident Response

### 1. **Plano de Resposta a Incidentes**
```yaml
# Runbook para resposta a incidentes
apiVersion: v1
kind: ConfigMap
metadata:
  name: incident-response-runbook
  namespace: backend-mockado
data:
  security-incident.md: |
    # Security Incident Response
    
    ## 1. Immediate Actions
    - [ ] Isolate affected components
    - [ ] Preserve evidence
    - [ ] Notify security team
    
    ## 2. Assessment
    - [ ] Determine scope of breach
    - [ ] Identify compromised data
    - [ ] Assess impact
    
    ## 3. Containment
    ```bash
    # Isolate pods
    kubectl patch deployment backend-mockado-collector -p '{"spec":{"replicas":0}}'
    
    # Block network access
    kubectl apply -f emergency-network-policy.yaml
    
    # Rotate secrets
    kubectl delete secret backend-mockado-secrets
    kubectl create secret generic backend-mockado-secrets --from-literal=...
    ```
    
    ## 4. Recovery
    - [ ] Deploy clean images
    - [ ] Restore from secure backups
    - [ ] Verify system integrity
    
    ## 5. Post-Incident
    - [ ] Document lessons learned
    - [ ] Update security measures
    - [ ] Conduct security review
```

### 2. **Emergency Network Policy**
```yaml
# emergency-network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: emergency-lockdown
  namespace: backend-mockado
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  # Bloquear todo tráfego (apenas DNS permitido)
  egress:
  - to: []
    ports:
    - protocol: UDP
      port: 53
```

### 3. **Forensic Data Collection**
```bash
#!/bin/bash
# forensic-collect.sh

NAMESPACE="backend-mockado"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
EVIDENCE_DIR="/tmp/evidence-${TIMESTAMP}"

mkdir -p "${EVIDENCE_DIR}"

# Coletar logs
kubectl logs -n ${NAMESPACE} --all-containers=true --previous > "${EVIDENCE_DIR}/logs-previous.txt"
kubectl logs -n ${NAMESPACE} --all-containers=true > "${EVIDENCE_DIR}/logs-current.txt"

# Coletar eventos
kubectl get events -n ${NAMESPACE} --sort-by='.lastTimestamp' > "${EVIDENCE_DIR}/events.txt"

# Coletar configurações
kubectl get all -n ${NAMESPACE} -o yaml > "${EVIDENCE_DIR}/resources.yaml"
kubectl get secrets -n ${NAMESPACE} -o yaml > "${EVIDENCE_DIR}/secrets.yaml"
kubectl get configmaps -n ${NAMESPACE} -o yaml > "${EVIDENCE_DIR}/configmaps.yaml"

# Coletar métricas
curl -s http://prometheus:9090/api/v1/query_range?query=up&start=$(date -d '1 hour ago' +%s)&end=$(date +%s)&step=60 > "${EVIDENCE_DIR}/metrics.json"

# Criar arquivo compactado e criptografado
tar -czf "${EVIDENCE_DIR}.tar.gz" "${EVIDENCE_DIR}"
gpg --cipher-algo AES256 --compress-algo 1 --s2k-mode 3 \
    --s2k-digest-algo SHA512 --s2k-count 65536 --force-mdc \
    --quiet --no-greeting --batch --yes \
    --passphrase-file /secrets/forensic-passphrase \
    --output "${EVIDENCE_DIR}.tar.gz.gpg" \
    --symmetric "${EVIDENCE_DIR}.tar.gz"

echo "Evidence collected: ${EVIDENCE_DIR}.tar.gz.gpg"
```

## ✅ Security Checklist

### Pré-Deployment
- [ ] Imagens escaneadas por vulnerabilidades
- [ ] Secrets configurados corretamente
- [ ] Network policies definidas
- [ ] Resource limits configurados
- [ ] Security contexts aplicados
- [ ] TLS/mTLS configurado
- [ ] Backup e recovery testados

### Pós-Deployment
- [ ] Health checks funcionando
- [ ] Logs de segurança configurados
- [ ] Métricas de segurança coletadas
- [ ] Alertas de segurança ativos
- [ ] Testes de penetração executados
- [ ] Documentação atualizada
- [ ] Equipe treinada em incident response

### Manutenção Contínua
- [ ] Atualizações de segurança aplicadas
- [ ] Logs de segurança revisados
- [ ] Métricas de segurança analisadas
- [ ] Testes de backup executados
- [ ] Revisão de acessos realizada
- [ ] Auditoria de configurações
- [ ] Treinamento de segurança atualizado

Este guia de segurança fornece uma base sólida para proteger o Backend Mockado Automático em ambientes de produção. Adapte as configurações conforme suas necessidades específicas de segurança e compliance.