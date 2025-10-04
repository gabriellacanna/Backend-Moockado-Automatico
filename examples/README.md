# Exemplos de Uso - Backend Mockado Automático

Este diretório contém exemplos práticos de como usar o Backend Mockado Automático em diferentes cenários.

## 📁 Arquivos de Exemplo

### 1. `basic_usage.py`
**Exemplo básico completo** que demonstra todo o fluxo do sistema:

- ✅ Verificação da saúde dos serviços
- 🚀 Simulação de tráfego HTTP realista
- 👀 Monitoramento do processamento
- 🧪 Teste dos mocks gerados
- 📊 Visualização de métricas

**Como executar:**
```bash
# Certifique-se que os serviços estão rodando
docker-compose up -d

# Execute o exemplo
cd examples
python basic_usage.py
```

### 2. `envoy_tap_simulation.py`
**Simulador do Envoy Tap Filter** que gera tráfego HTTP realista:

- 🔄 Simulação de diferentes APIs (usuários, produtos, pagamentos, pedidos, auth)
- 📤 Envio de capturas para o Collector
- ⏰ Simulação contínua ou em lotes
- 🎯 Dados realistas com informações sensíveis para testar sanitização

**Como executar:**
```bash
cd examples
python envoy_tap_simulation.py
```

## 🚀 Cenários de Uso

### Cenário 1: Teste Básico do Sistema
Use o `basic_usage.py` para:
- Verificar se todos os componentes estão funcionando
- Entender o fluxo completo do sistema
- Ver exemplos de sanitização de dados
- Testar mocks gerados automaticamente

### Cenário 2: Simulação de Produção
Use o `envoy_tap_simulation.py` para:
- Simular tráfego realista de produção
- Testar performance com volume de dados
- Validar sanitização com dados sensíveis reais
- Testar deduplicação com requests similares

### Cenário 3: Desenvolvimento e Debug
Combine ambos os exemplos para:
- Debugar problemas de sanitização
- Testar novos padrões de dados sensíveis
- Validar configurações de deduplicação
- Monitorar métricas em tempo real

## 📊 Dados de Exemplo

Os exemplos incluem dados realistas para testar:

### 🔒 Dados Sensíveis (que devem ser sanitizados)
- **Tokens JWT**: `Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`
- **API Keys**: `sk_live_abcdef123456789`
- **Senhas**: `minha-senha-super-secreta-123`
- **Cartões de Crédito**: `4111111111111111`
- **CPF/CNPJ**: `123.456.789-01`, `98.765.432/0001-10`
- **Telefones**: `+55 11 99999-9999`
- **Emails**: `joao.silva@example.com`
- **Cookies**: `session_id=abc123; user_token=xyz789`

### ✅ Dados Não Sensíveis (que devem permanecer)
- **IDs**: `user-001`, `prod-123`
- **Nomes**: `João Silva`
- **Valores**: `899.99`, `2199.98`
- **Status**: `active`, `approved`
- **Timestamps**: `2024-01-15T10:30:00Z`

## 🔧 Configuração dos Exemplos

### Variáveis de Ambiente
Os exemplos usam as seguintes URLs padrão:
```python
collector_url = "http://localhost:8080"
wiremock_loader_url = "http://localhost:8081"
wiremock_url = "http://localhost:8082"
redis_host = "localhost"
redis_port = 6379
```

### Personalização
Para usar em outros ambientes, modifique as URLs nos arquivos:

```python
# Para Kubernetes
collector_url = "http://backend-mockado-collector:8080"
wiremock_url = "http://backend-mockado-wiremock:8080"

# Para ambiente de desenvolvimento
collector_url = "http://collector.dev.local:8080"
```

## 📈 Métricas Monitoradas

Os exemplos mostram como monitorar:

### Collector
- `collector_requests_total`: Total de requests processadas
- `collector_sanitization_operations_total`: Operações de sanitização
- `collector_deduplication_operations_total`: Operações de deduplicação
- `collector_queue_size`: Tamanho da fila Redis

### WireMock Loader
- `wiremock_loader_mappings_processed_total`: Mappings processados
- `wiremock_loader_mappings_errors_total`: Erros no processamento
- `wiremock_loader_wiremock_requests_duration_seconds`: Latência das requests

## 🧪 Testes Incluídos

### Testes de Saúde
- ✅ Collector health check
- ✅ WireMock Loader health check
- ✅ WireMock health check
- ✅ Redis connectivity

### Testes de Funcionalidade
- 🔒 Sanitização de dados sensíveis
- 🔄 Deduplicação de requests
- 📤 Envio para fila Redis
- 🎯 Criação de mappings WireMock
- 🧪 Teste de mocks funcionais

### Testes de Performance
- ⚡ Latência de processamento
- 📊 Throughput de requests
- 💾 Uso de memória Redis
- 🔄 Performance de deduplicação

## 🚨 Troubleshooting

### Problema: Serviços não respondem
```bash
# Verificar se os containers estão rodando
docker-compose ps

# Ver logs dos serviços
docker-compose logs collector
docker-compose logs wiremock-loader
docker-compose logs wiremock
```

### Problema: Redis não conecta
```bash
# Testar conexão Redis
redis-cli ping

# Verificar configuração
docker-compose logs redis
```

### Problema: Mappings não aparecem no WireMock
```bash
# Verificar fila Redis
redis-cli llen wiremock_mappings

# Ver logs do WireMock Loader
docker-compose logs wiremock-loader

# Verificar mappings no WireMock
curl http://localhost:8082/__admin/mappings
```

## 📚 Próximos Passos

Após executar os exemplos:

1. **Configure o Envoy Tap Filter** real no seu ambiente
2. **Integre com seu service mesh** (Istio/ASM)
3. **Configure monitoramento** com Prometheus/Grafana
4. **Ajuste configurações** de sanitização conforme necessário
5. **Implemente em ambiente de canário** para testes A/B

## 🤝 Contribuindo

Para adicionar novos exemplos:

1. Crie um novo arquivo `.py` neste diretório
2. Siga o padrão de logging e estrutura dos exemplos existentes
3. Inclua documentação inline explicando o cenário
4. Adicione o exemplo neste README
5. Teste com diferentes volumes de dados

## 📞 Suporte

Se encontrar problemas com os exemplos:

1. Verifique os logs dos serviços
2. Confirme que todas as dependências estão instaladas
3. Teste a conectividade de rede entre os componentes
4. Consulte a documentação principal do projeto