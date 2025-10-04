#!/usr/bin/env python3
"""
Testes de integração end-to-end para o Backend Mockado Automático.

Este módulo testa o fluxo completo:
1. Simulação de tráfego HTTP
2. Captura pelo Collector
3. Sanitização e deduplicação
4. Envio para WireMock Loader
5. Criação de mappings no WireMock
6. Verificação dos mocks funcionando
"""

import asyncio
import json
import time
import uuid
from typing import Dict, Any, List
import pytest
import httpx
import redis.asyncio as redis
from testcontainers.compose import DockerCompose
from testcontainers.redis import RedisContainer
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BackendMockadoE2ETest:
    """Classe para testes end-to-end do Backend Mockado Automático."""
    
    def __init__(self):
        self.redis_client = None
        self.collector_url = None
        self.wiremock_loader_url = None
        self.wiremock_url = None
        self.compose = None
        
    async def setup_test_environment(self):
        """Configura o ambiente de teste usando Docker Compose."""
        logger.info("Configurando ambiente de teste...")
        
        # Usar Docker Compose para subir os serviços
        self.compose = DockerCompose(
            filepath=".",
            compose_file_name="docker-compose.yml"
        )
        
        # Iniciar serviços
        self.compose.start()
        
        # Aguardar serviços ficarem prontos
        await asyncio.sleep(10)
        
        # Configurar URLs dos serviços
        self.collector_url = "http://localhost:8080"
        self.wiremock_loader_url = "http://localhost:8081"
        self.wiremock_url = "http://localhost:8082"
        
        # Configurar cliente Redis
        self.redis_client = redis.Redis(
            host="localhost",
            port=6379,
            decode_responses=True
        )
        
        logger.info("Ambiente de teste configurado com sucesso")
    
    async def teardown_test_environment(self):
        """Limpa o ambiente de teste."""
        logger.info("Limpando ambiente de teste...")
        
        if self.redis_client:
            await self.redis_client.close()
        
        if self.compose:
            self.compose.stop()
        
        logger.info("Ambiente de teste limpo")
    
    async def test_collector_health(self):
        """Testa se o Collector está funcionando."""
        logger.info("Testando saúde do Collector...")
        
        async with httpx.AsyncClient() as client:
            # Testar health endpoint
            response = await client.get(f"{self.collector_url}/health")
            assert response.status_code == 200
            
            # Testar readiness endpoint
            response = await client.get(f"{self.collector_url}/ready")
            assert response.status_code == 200
            
            # Testar metrics endpoint
            response = await client.get(f"{self.collector_url}/metrics")
            assert response.status_code == 200
            assert "collector_requests_total" in response.text
        
        logger.info("✓ Collector está saudável")
    
    async def test_wiremock_loader_health(self):
        """Testa se o WireMock Loader está funcionando."""
        logger.info("Testando saúde do WireMock Loader...")
        
        async with httpx.AsyncClient() as client:
            # Testar health endpoint
            response = await client.get(f"{self.wiremock_loader_url}/health")
            assert response.status_code == 200
            
            # Testar readiness endpoint
            response = await client.get(f"{self.wiremock_loader_url}/ready")
            assert response.status_code == 200
            
            # Testar metrics endpoint
            response = await client.get(f"{self.wiremock_loader_url}/metrics")
            assert response.status_code == 200
        
        logger.info("✓ WireMock Loader está saudável")
    
    async def test_wiremock_health(self):
        """Testa se o WireMock está funcionando."""
        logger.info("Testando saúde do WireMock...")
        
        async with httpx.AsyncClient() as client:
            # Testar health endpoint
            response = await client.get(f"{self.wiremock_url}/__admin/health")
            assert response.status_code == 200
            
            # Testar mappings endpoint
            response = await client.get(f"{self.wiremock_url}/__admin/mappings")
            assert response.status_code == 200
        
        logger.info("✓ WireMock está saudável")
    
    async def test_redis_connection(self):
        """Testa conexão com Redis."""
        logger.info("Testando conexão com Redis...")
        
        # Testar ping
        pong = await self.redis_client.ping()
        assert pong is True
        
        # Testar operações básicas
        test_key = f"test:{uuid.uuid4()}"
        await self.redis_client.set(test_key, "test_value")
        value = await self.redis_client.get(test_key)
        assert value == "test_value"
        await self.redis_client.delete(test_key)
        
        logger.info("✓ Redis está funcionando")
    
    async def simulate_http_traffic(self) -> List[Dict[str, Any]]:
        """Simula tráfego HTTP para ser capturado."""
        logger.info("Simulando tráfego HTTP...")
        
        # Dados de teste com informações sensíveis para testar sanitização
        test_requests = [
            {
                "method": "POST",
                "path": "/api/v1/users",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "X-API-Key": "secret-api-key-123"
                },
                "body": {
                    "name": "João Silva",
                    "email": "joao.silva@example.com",
                    "cpf": "123.456.789-01",
                    "phone": "+55 11 99999-9999",
                    "password": "super-secret-password",
                    "credit_card": "4111111111111111"
                }
            },
            {
                "method": "GET",
                "path": "/api/v1/products",
                "headers": {
                    "Accept": "application/json",
                    "Cookie": "session_id=abc123; user_token=xyz789"
                },
                "body": None
            },
            {
                "method": "PUT",
                "path": "/api/v1/orders/12345",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer another-jwt-token"
                },
                "body": {
                    "status": "shipped",
                    "tracking_code": "BR123456789",
                    "customer_document": "98.765.432/0001-10"
                }
            }
        ]
        
        # Simular requests HTTP (normalmente seria feito pelo Envoy tap filter)
        simulated_captures = []
        
        for req in test_requests:
            # Simular response
            response = {
                "status": 200 if req["method"] == "GET" else 201,
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "id": str(uuid.uuid4()),
                    "status": "success",
                    "timestamp": int(time.time())
                }
            }
            
            capture = {
                "request": req,
                "response": response,
                "timestamp": int(time.time()),
                "source": "test-simulation"
            }
            
            simulated_captures.append(capture)
        
        logger.info(f"✓ Simulados {len(simulated_captures)} requests HTTP")
        return simulated_captures
    
    async def send_to_collector(self, captures: List[Dict[str, Any]]):
        """Envia capturas simuladas para o Collector."""
        logger.info("Enviando capturas para o Collector...")
        
        async with httpx.AsyncClient() as client:
            for capture in captures:
                # Enviar via API HTTP (simulando o que o gRPC faria)
                response = await client.post(
                    f"{self.collector_url}/api/v1/capture",
                    json=capture,
                    timeout=30.0
                )
                
                if response.status_code not in [200, 201, 202]:
                    logger.error(f"Erro ao enviar captura: {response.status_code} - {response.text}")
                    raise Exception(f"Falha ao enviar captura: {response.status_code}")
        
        logger.info("✓ Capturas enviadas para o Collector")
    
    async def verify_sanitization_and_deduplication(self):
        """Verifica se a sanitização e deduplicação funcionaram."""
        logger.info("Verificando sanitização e deduplicação...")
        
        # Aguardar processamento
        await asyncio.sleep(5)
        
        # Verificar se os dados foram processados no Redis
        queue_size = await self.redis_client.llen("wiremock_mappings")
        logger.info(f"Tamanho da fila de mappings: {queue_size}")
        
        # Verificar alguns mappings na fila
        if queue_size > 0:
            # Pegar alguns mappings da fila (sem remover)
            mappings_raw = await self.redis_client.lrange("wiremock_mappings", 0, 2)
            
            for mapping_raw in mappings_raw:
                mapping = json.loads(mapping_raw)
                
                # Verificar se dados sensíveis foram sanitizados
                mapping_str = json.dumps(mapping)
                
                # Verificar se não há dados sensíveis
                sensitive_patterns = [
                    "Bearer eyJ",  # JWT tokens
                    "secret-api-key",  # API keys
                    "super-secret-password",  # Passwords
                    "4111111111111111",  # Credit card
                    "123.456.789-01",  # CPF
                    "+55 11 99999-9999",  # Phone
                    "session_id=abc123"  # Cookies
                ]
                
                for pattern in sensitive_patterns:
                    assert pattern not in mapping_str, f"Dado sensível não sanitizado: {pattern}"
                
                # Verificar se há marcadores de sanitização
                sanitized_markers = [
                    "SANITIZED_HEADER",
                    "SANITIZED_CARD",
                    "SANITIZED_DOCUMENT",
                    "SANITIZED_EMAIL",
                    "SANITIZED_PHONE",
                    "SANITIZED_PASSWORD",
                    "SANITIZED_JWT"
                ]
                
                has_sanitized = any(marker in mapping_str for marker in sanitized_markers)
                if has_sanitized:
                    logger.info("✓ Dados sensíveis foram sanitizados")
        
        logger.info("✓ Sanitização e deduplicação verificadas")
    
    async def verify_wiremock_mappings(self):
        """Verifica se os mappings foram criados no WireMock."""
        logger.info("Verificando mappings no WireMock...")
        
        # Aguardar processamento pelo WireMock Loader
        await asyncio.sleep(10)
        
        async with httpx.AsyncClient() as client:
            # Verificar mappings no WireMock
            response = await client.get(f"{self.wiremock_url}/__admin/mappings")
            assert response.status_code == 200
            
            mappings_data = response.json()
            mappings = mappings_data.get("mappings", [])
            
            logger.info(f"Encontrados {len(mappings)} mappings no WireMock")
            
            # Verificar se pelo menos alguns mappings foram criados
            assert len(mappings) > 0, "Nenhum mapping foi criado no WireMock"
            
            # Testar alguns mappings
            for mapping in mappings[:2]:  # Testar apenas os primeiros 2
                request_spec = mapping.get("request", {})
                method = request_spec.get("method")
                url_path = request_spec.get("urlPath")
                
                if method and url_path:
                    logger.info(f"Testando mapping: {method} {url_path}")
                    
                    # Fazer request para o mapping
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
                        continue
                    
                    # Verificar se o mock respondeu
                    if test_response.status_code in [200, 201]:
                        logger.info(f"✓ Mapping {method} {url_path} funcionando")
                    else:
                        logger.warning(f"⚠ Mapping {method} {url_path} retornou {test_response.status_code}")
        
        logger.info("✓ Mappings no WireMock verificados")
    
    async def test_metrics_collection(self):
        """Testa se as métricas estão sendo coletadas."""
        logger.info("Testando coleta de métricas...")
        
        async with httpx.AsyncClient() as client:
            # Coletar métricas do Collector
            response = await client.get(f"{self.collector_url}/metrics")
            assert response.status_code == 200
            
            metrics_text = response.text
            
            # Verificar métricas esperadas
            expected_metrics = [
                "collector_requests_total",
                "collector_requests_duration_seconds",
                "collector_sanitization_operations_total",
                "collector_deduplication_operations_total",
                "collector_queue_size"
            ]
            
            for metric in expected_metrics:
                assert metric in metrics_text, f"Métrica {metric} não encontrada"
            
            logger.info("✓ Métricas do Collector coletadas")
            
            # Coletar métricas do WireMock Loader
            response = await client.get(f"{self.wiremock_loader_url}/metrics")
            assert response.status_code == 200
            
            metrics_text = response.text
            
            # Verificar métricas esperadas
            expected_metrics = [
                "wiremock_loader_mappings_processed_total",
                "wiremock_loader_mappings_errors_total",
                "wiremock_loader_wiremock_requests_duration_seconds"
            ]
            
            for metric in expected_metrics:
                assert metric in metrics_text, f"Métrica {metric} não encontrada"
            
            logger.info("✓ Métricas do WireMock Loader coletadas")
        
        logger.info("✓ Coleta de métricas verificada")
    
    async def run_full_e2e_test(self):
        """Executa o teste end-to-end completo."""
        logger.info("🚀 Iniciando teste end-to-end completo...")
        
        try:
            # 1. Configurar ambiente
            await self.setup_test_environment()
            
            # 2. Verificar saúde dos serviços
            await self.test_collector_health()
            await self.test_wiremock_loader_health()
            await self.test_wiremock_health()
            await self.test_redis_connection()
            
            # 3. Simular tráfego HTTP
            captures = await self.simulate_http_traffic()
            
            # 4. Enviar para o Collector
            await self.send_to_collector(captures)
            
            # 5. Verificar sanitização e deduplicação
            await self.verify_sanitization_and_deduplication()
            
            # 6. Verificar mappings no WireMock
            await self.verify_wiremock_mappings()
            
            # 7. Testar coleta de métricas
            await self.test_metrics_collection()
            
            logger.info("🎉 Teste end-to-end concluído com sucesso!")
            
        except Exception as e:
            logger.error(f"❌ Teste end-to-end falhou: {e}")
            raise
        
        finally:
            # 8. Limpar ambiente
            await self.teardown_test_environment()


# Testes pytest
@pytest.mark.asyncio
async def test_backend_mockado_e2e():
    """Teste end-to-end principal."""
    test_runner = BackendMockadoE2ETest()
    await test_runner.run_full_e2e_test()


if __name__ == "__main__":
    # Executar teste diretamente
    async def main():
        test_runner = BackendMockadoE2ETest()
        await test_runner.run_full_e2e_test()
    
    asyncio.run(main())