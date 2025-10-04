#!/usr/bin/env python3
"""
Exemplo básico de uso do Backend Mockado Automático.

Este exemplo demonstra como:
1. Configurar o ambiente
2. Simular tráfego HTTP
3. Verificar a captura e processamento
4. Testar os mocks gerados
"""

import asyncio
import json
import time
import uuid
from typing import Dict, Any, List
import httpx
import redis.asyncio as redis
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class BackendMockadoExample:
    """Exemplo de uso do Backend Mockado Automático."""
    
    def __init__(self):
        # URLs dos serviços (ajustar conforme seu ambiente)
        self.collector_url = "http://localhost:8080"
        self.wiremock_loader_url = "http://localhost:8081"
        self.wiremock_url = "http://localhost:8082"
        
        # Cliente Redis
        self.redis_client = redis.Redis(
            host="localhost",
            port=6379,
            decode_responses=True
        )
    
    async def check_services_health(self):
        """Verifica se todos os serviços estão funcionando."""
        logger.info("🔍 Verificando saúde dos serviços...")
        
        services = [
            ("Collector", f"{self.collector_url}/health"),
            ("WireMock Loader", f"{self.wiremock_loader_url}/health"),
            ("WireMock", f"{self.wiremock_url}/__admin/health")
        ]
        
        async with httpx.AsyncClient() as client:
            for service_name, health_url in services:
                try:
                    response = await client.get(health_url, timeout=5.0)
                    if response.status_code == 200:
                        logger.info(f"✅ {service_name} está funcionando")
                    else:
                        logger.error(f"❌ {service_name} retornou status {response.status_code}")
                        return False
                except Exception as e:
                    logger.error(f"❌ Erro ao conectar com {service_name}: {e}")
                    return False
        
        # Verificar Redis
        try:
            await self.redis_client.ping()
            logger.info("✅ Redis está funcionando")
        except Exception as e:
            logger.error(f"❌ Erro ao conectar com Redis: {e}")
            return False
        
        return True
    
    async def simulate_api_traffic(self):
        """Simula tráfego de API para demonstrar a captura."""
        logger.info("🚀 Simulando tráfego de API...")
        
        # Exemplos de requests que seriam capturadas pelo Envoy tap filter
        sample_requests = [
            {
                "method": "GET",
                "path": "/api/v1/users",
                "headers": {
                    "Accept": "application/json",
                    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
                    "User-Agent": "MyApp/1.0"
                },
                "query": {"page": "1", "limit": "10"},
                "body": None
            },
            {
                "method": "POST",
                "path": "/api/v1/users",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
                },
                "query": {},
                "body": {
                    "name": "João Silva",
                    "email": "joao.silva@example.com",
                    "password": "minha-senha-secreta",
                    "phone": "+55 11 99999-9999",
                    "document": "123.456.789-01"
                }
            },
            {
                "method": "PUT",
                "path": "/api/v1/users/123",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
                },
                "query": {},
                "body": {
                    "name": "João Silva Santos",
                    "phone": "+55 11 88888-8888"
                }
            },
            {
                "method": "POST",
                "path": "/api/v1/payments",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
                    "X-API-Key": "sk_test_123456789"
                },
                "query": {},
                "body": {
                    "amount": 10000,  # R$ 100,00 em centavos
                    "currency": "BRL",
                    "payment_method": {
                        "type": "credit_card",
                        "card_number": "4111111111111111",
                        "card_holder": "JOAO SILVA",
                        "expiry_month": "12",
                        "expiry_year": "2025",
                        "cvv": "123"
                    },
                    "customer": {
                        "name": "João Silva",
                        "email": "joao@example.com",
                        "document": "123.456.789-01"
                    }
                }
            }
        ]
        
        # Simular responses correspondentes
        sample_responses = [
            {
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "users": [
                        {"id": "user-1", "name": "João Silva", "email": "joao@example.com"},
                        {"id": "user-2", "name": "Maria Santos", "email": "maria@example.com"}
                    ],
                    "pagination": {"page": 1, "limit": 10, "total": 2}
                }
            },
            {
                "status": 201,
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "id": "user-123",
                    "name": "João Silva",
                    "email": "joao.silva@example.com",
                    "created_at": "2024-01-15T10:30:00Z"
                }
            },
            {
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "id": "user-123",
                    "name": "João Silva Santos",
                    "email": "joao.silva@example.com",
                    "phone": "+55 11 88888-8888",
                    "updated_at": "2024-01-15T11:00:00Z"
                }
            },
            {
                "status": 201,
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "id": "payment-456",
                    "status": "approved",
                    "amount": 10000,
                    "currency": "BRL",
                    "transaction_id": "txn_789",
                    "created_at": "2024-01-15T11:15:00Z"
                }
            }
        ]
        
        # Enviar capturas para o Collector
        async with httpx.AsyncClient() as client:
            for i, (request, response) in enumerate(zip(sample_requests, sample_responses)):
                capture_data = {
                    "request": request,
                    "response": response,
                    "timestamp": int(time.time()),
                    "source": "example-simulation",
                    "trace_id": str(uuid.uuid4())
                }
                
                logger.info(f"📤 Enviando captura {i+1}/4: {request['method']} {request['path']}")
                
                try:
                    response = await client.post(
                        f"{self.collector_url}/api/v1/capture",
                        json=capture_data,
                        timeout=10.0
                    )
                    
                    if response.status_code in [200, 201, 202]:
                        logger.info(f"✅ Captura {i+1} enviada com sucesso")
                    else:
                        logger.error(f"❌ Erro ao enviar captura {i+1}: {response.status_code}")
                
                except Exception as e:
                    logger.error(f"❌ Erro ao enviar captura {i+1}: {e}")
                
                # Pequena pausa entre requests
                await asyncio.sleep(1)
        
        logger.info("✅ Simulação de tráfego concluída")
    
    async def monitor_processing(self):
        """Monitora o processamento das capturas."""
        logger.info("👀 Monitorando processamento...")
        
        # Aguardar processamento inicial
        await asyncio.sleep(5)
        
        try:
            # Verificar fila de mappings no Redis
            queue_size = await self.redis_client.llen("wiremock_mappings")
            logger.info(f"📊 Tamanho da fila de mappings: {queue_size}")
            
            if queue_size > 0:
                # Mostrar alguns mappings (sem remover da fila)
                mappings_raw = await self.redis_client.lrange("wiremock_mappings", 0, 2)
                
                for i, mapping_raw in enumerate(mappings_raw):
                    mapping = json.loads(mapping_raw)
                    request_spec = mapping.get("request", {})
                    response_spec = mapping.get("response", {})
                    
                    logger.info(f"🔍 Mapping {i+1}:")
                    logger.info(f"   Request: {request_spec.get('method')} {request_spec.get('urlPath')}")
                    logger.info(f"   Response Status: {response_spec.get('status')}")
                    
                    # Verificar se dados sensíveis foram sanitizados
                    mapping_str = json.dumps(mapping)
                    if "SANITIZED" in mapping_str:
                        logger.info("   ✅ Dados sensíveis foram sanitizados")
            
            # Verificar métricas do Collector
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.collector_url}/metrics")
                if response.status_code == 200:
                    metrics = response.text
                    
                    # Extrair algumas métricas importantes
                    for line in metrics.split('\n'):
                        if 'collector_requests_total' in line and not line.startswith('#'):
                            logger.info(f"📈 {line.strip()}")
                        elif 'collector_sanitization_operations_total' in line and not line.startswith('#'):
                            logger.info(f"🔒 {line.strip()}")
                        elif 'collector_deduplication_operations_total' in line and not line.startswith('#'):
                            logger.info(f"🔄 {line.strip()}")
        
        except Exception as e:
            logger.error(f"❌ Erro ao monitorar processamento: {e}")
    
    async def wait_for_wiremock_mappings(self, timeout=30):
        """Aguarda os mappings serem carregados no WireMock."""
        logger.info("⏳ Aguardando mappings serem carregados no WireMock...")
        
        start_time = time.time()
        
        async with httpx.AsyncClient() as client:
            while time.time() - start_time < timeout:
                try:
                    response = await client.get(f"{self.wiremock_url}/__admin/mappings")
                    if response.status_code == 200:
                        mappings_data = response.json()
                        mappings_count = len(mappings_data.get("mappings", []))
                        
                        if mappings_count > 0:
                            logger.info(f"✅ {mappings_count} mappings carregados no WireMock")
                            return True
                        else:
                            logger.info(f"⏳ Aguardando mappings... ({int(time.time() - start_time)}s)")
                
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao verificar mappings: {e}")
                
                await asyncio.sleep(2)
        
        logger.warning("⚠️ Timeout aguardando mappings no WireMock")
        return False
    
    async def test_generated_mocks(self):
        """Testa os mocks gerados no WireMock."""
        logger.info("🧪 Testando mocks gerados...")
        
        async with httpx.AsyncClient() as client:
            # Listar mappings disponíveis
            response = await client.get(f"{self.wiremock_url}/__admin/mappings")
            if response.status_code != 200:
                logger.error("❌ Não foi possível listar mappings do WireMock")
                return
            
            mappings_data = response.json()
            mappings = mappings_data.get("mappings", [])
            
            if not mappings:
                logger.warning("⚠️ Nenhum mapping encontrado no WireMock")
                return
            
            logger.info(f"🎯 Testando {len(mappings)} mappings...")
            
            # Testar cada mapping
            for i, mapping in enumerate(mappings[:5]):  # Testar apenas os primeiros 5
                request_spec = mapping.get("request", {})
                method = request_spec.get("method")
                url_path = request_spec.get("urlPath")
                
                if not method or not url_path:
                    continue
                
                logger.info(f"🔧 Testando mapping {i+1}: {method} {url_path}")
                
                try:
                    # Fazer request para o mock
                    if method == "GET":
                        test_response = await client.get(f"{self.wiremock_url}{url_path}")
                    elif method == "POST":
                        test_response = await client.post(
                            f"{self.wiremock_url}{url_path}",
                            json={"test": "data"}
                        )
                    elif method == "PUT":
                        test_response = await client.put(
                            f"{self.wiremock_url}{url_path}",
                            json={"test": "data"}
                        )
                    else:
                        logger.info(f"   ⏭️ Método {method} não testado")
                        continue
                    
                    # Verificar response
                    if test_response.status_code in [200, 201]:
                        logger.info(f"   ✅ Mock funcionando - Status: {test_response.status_code}")
                        
                        # Mostrar parte da response
                        try:
                            response_json = test_response.json()
                            if isinstance(response_json, dict) and len(response_json) > 0:
                                first_key = list(response_json.keys())[0]
                                logger.info(f"   📄 Response contém: {first_key}: {response_json[first_key]}")
                        except:
                            logger.info(f"   📄 Response: {test_response.text[:100]}...")
                    else:
                        logger.warning(f"   ⚠️ Mock retornou status inesperado: {test_response.status_code}")
                
                except Exception as e:
                    logger.error(f"   ❌ Erro ao testar mock: {e}")
                
                # Pausa entre testes
                await asyncio.sleep(0.5)
    
    async def show_metrics_summary(self):
        """Mostra um resumo das métricas coletadas."""
        logger.info("📊 Resumo das métricas:")
        
        services = [
            ("Collector", f"{self.collector_url}/metrics"),
            ("WireMock Loader", f"{self.wiremock_loader_url}/metrics")
        ]
        
        async with httpx.AsyncClient() as client:
            for service_name, metrics_url in services:
                try:
                    response = await client.get(metrics_url)
                    if response.status_code == 200:
                        logger.info(f"\n📈 {service_name}:")
                        
                        metrics_lines = response.text.split('\n')
                        for line in metrics_lines:
                            if line and not line.startswith('#') and '_total' in line:
                                logger.info(f"   {line.strip()}")
                
                except Exception as e:
                    logger.error(f"❌ Erro ao obter métricas do {service_name}: {e}")
    
    async def run_example(self):
        """Executa o exemplo completo."""
        logger.info("🚀 Iniciando exemplo do Backend Mockado Automático")
        logger.info("=" * 60)
        
        try:
            # 1. Verificar saúde dos serviços
            if not await self.check_services_health():
                logger.error("❌ Nem todos os serviços estão funcionando. Verifique o ambiente.")
                return
            
            logger.info("\n" + "=" * 60)
            
            # 2. Simular tráfego de API
            await self.simulate_api_traffic()
            
            logger.info("\n" + "=" * 60)
            
            # 3. Monitorar processamento
            await self.monitor_processing()
            
            logger.info("\n" + "=" * 60)
            
            # 4. Aguardar mappings serem carregados
            if await self.wait_for_wiremock_mappings():
                logger.info("\n" + "=" * 60)
                
                # 5. Testar mocks gerados
                await self.test_generated_mocks()
            
            logger.info("\n" + "=" * 60)
            
            # 6. Mostrar resumo das métricas
            await self.show_metrics_summary()
            
            logger.info("\n" + "=" * 60)
            logger.info("🎉 Exemplo concluído com sucesso!")
            logger.info("\n💡 Próximos passos:")
            logger.info("   1. Acesse http://localhost:8082/__admin para ver os mappings")
            logger.info("   2. Teste os endpoints mockados diretamente")
            logger.info("   3. Configure o Envoy tap filter para captura automática")
            logger.info("   4. Integre com seu ambiente de canário/experimentação")
        
        except Exception as e:
            logger.error(f"❌ Erro durante execução do exemplo: {e}")
            raise
        
        finally:
            # Fechar conexão Redis
            await self.redis_client.close()


async def main():
    """Função principal."""
    example = BackendMockadoExample()
    await example.run_example()


if __name__ == "__main__":
    # Executar exemplo
    asyncio.run(main())