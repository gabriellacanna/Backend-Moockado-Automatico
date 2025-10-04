#!/usr/bin/env python3
"""
Simulação do Envoy Tap Filter para testes.

Este script simula o comportamento do Envoy tap filter,
capturando tráfego HTTP e enviando para o Collector via gRPC.
"""

import asyncio
import json
import time
import uuid
from typing import Dict, Any, List, Optional
import grpc
import logging
from dataclasses import dataclass

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class HttpRequest:
    """Representa uma request HTTP capturada."""
    method: str
    path: str
    headers: Dict[str, str]
    query_params: Dict[str, str]
    body: Optional[Any] = None


@dataclass
class HttpResponse:
    """Representa uma response HTTP capturada."""
    status_code: int
    headers: Dict[str, str]
    body: Optional[Any] = None


@dataclass
class TrafficCapture:
    """Representa uma captura de tráfego completa."""
    request: HttpRequest
    response: HttpResponse
    timestamp: int
    trace_id: str
    source_service: str
    destination_service: str


class EnvoyTapSimulator:
    """Simulador do Envoy tap filter."""
    
    def __init__(self, collector_grpc_endpoint: str = "localhost:50051"):
        self.collector_endpoint = collector_grpc_endpoint
        self.running = False
        
    def generate_realistic_traffic(self) -> List[TrafficCapture]:
        """Gera tráfego HTTP realista para simulação."""
        
        # Simular diferentes tipos de APIs
        captures = []
        
        # 1. API de Usuários
        user_captures = self._generate_user_api_traffic()
        captures.extend(user_captures)
        
        # 2. API de Produtos
        product_captures = self._generate_product_api_traffic()
        captures.extend(product_captures)
        
        # 3. API de Pagamentos
        payment_captures = self._generate_payment_api_traffic()
        captures.extend(payment_captures)
        
        # 4. API de Pedidos
        order_captures = self._generate_order_api_traffic()
        captures.extend(order_captures)
        
        # 5. API de Autenticação
        auth_captures = self._generate_auth_api_traffic()
        captures.extend(auth_captures)
        
        return captures
    
    def _generate_user_api_traffic(self) -> List[TrafficCapture]:
        """Gera tráfego da API de usuários."""
        captures = []
        
        # GET /api/v1/users - Listar usuários
        captures.append(TrafficCapture(
            request=HttpRequest(
                method="GET",
                path="/api/v1/users",
                headers={
                    "Accept": "application/json",
                    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
                    "User-Agent": "MyApp/1.0.0",
                    "X-Request-ID": str(uuid.uuid4())
                },
                query_params={"page": "1", "limit": "20", "sort": "created_at"}
            ),
            response=HttpResponse(
                status_code=200,
                headers={
                    "Content-Type": "application/json",
                    "X-Total-Count": "150",
                    "Cache-Control": "max-age=300"
                },
                body={
                    "users": [
                        {
                            "id": "user-001",
                            "name": "João Silva",
                            "email": "joao.silva@example.com",
                            "created_at": "2024-01-15T10:30:00Z",
                            "status": "active"
                        },
                        {
                            "id": "user-002",
                            "name": "Maria Santos",
                            "email": "maria.santos@example.com",
                            "created_at": "2024-01-14T15:20:00Z",
                            "status": "active"
                        }
                    ],
                    "pagination": {
                        "page": 1,
                        "limit": 20,
                        "total": 150,
                        "pages": 8
                    }
                }
            ),
            timestamp=int(time.time()),
            trace_id=str(uuid.uuid4()),
            source_service="frontend-app",
            destination_service="user-service"
        ))
        
        # POST /api/v1/users - Criar usuário
        captures.append(TrafficCapture(
            request=HttpRequest(
                method="POST",
                path="/api/v1/users",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
                    "User-Agent": "MyApp/1.0.0",
                    "X-Request-ID": str(uuid.uuid4())
                },
                query_params={},
                body={
                    "name": "Carlos Oliveira",
                    "email": "carlos.oliveira@example.com",
                    "password": "minha-senha-super-secreta-123",
                    "phone": "+55 11 98765-4321",
                    "document": "987.654.321-00",
                    "address": {
                        "street": "Rua das Flores, 123",
                        "city": "São Paulo",
                        "state": "SP",
                        "zip_code": "01234-567"
                    }
                }
            ),
            response=HttpResponse(
                status_code=201,
                headers={
                    "Content-Type": "application/json",
                    "Location": "/api/v1/users/user-003"
                },
                body={
                    "id": "user-003",
                    "name": "Carlos Oliveira",
                    "email": "carlos.oliveira@example.com",
                    "created_at": "2024-01-15T11:45:00Z",
                    "status": "active"
                }
            ),
            timestamp=int(time.time()),
            trace_id=str(uuid.uuid4()),
            source_service="admin-panel",
            destination_service="user-service"
        ))
        
        return captures
    
    def _generate_product_api_traffic(self) -> List[TrafficCapture]:
        """Gera tráfego da API de produtos."""
        captures = []
        
        # GET /api/v1/products - Listar produtos
        captures.append(TrafficCapture(
            request=HttpRequest(
                method="GET",
                path="/api/v1/products",
                headers={
                    "Accept": "application/json",
                    "User-Agent": "MyApp/1.0.0",
                    "X-Request-ID": str(uuid.uuid4())
                },
                query_params={"category": "electronics", "price_min": "100", "price_max": "1000"}
            ),
            response=HttpResponse(
                status_code=200,
                headers={
                    "Content-Type": "application/json",
                    "Cache-Control": "max-age=600"
                },
                body={
                    "products": [
                        {
                            "id": "prod-001",
                            "name": "Smartphone XYZ",
                            "price": 899.99,
                            "category": "electronics",
                            "stock": 50
                        },
                        {
                            "id": "prod-002",
                            "name": "Laptop ABC",
                            "price": 1299.99,
                            "category": "electronics",
                            "stock": 25
                        }
                    ]
                }
            ),
            timestamp=int(time.time()),
            trace_id=str(uuid.uuid4()),
            source_service="mobile-app",
            destination_service="product-service"
        ))
        
        return captures
    
    def _generate_payment_api_traffic(self) -> List[TrafficCapture]:
        """Gera tráfego da API de pagamentos."""
        captures = []
        
        # POST /api/v1/payments - Processar pagamento
        captures.append(TrafficCapture(
            request=HttpRequest(
                method="POST",
                path="/api/v1/payments",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
                    "X-API-Key": "sk_live_abcdef123456789",
                    "User-Agent": "PaymentGateway/2.1.0",
                    "X-Request-ID": str(uuid.uuid4())
                },
                query_params={},
                body={
                    "amount": 15999,  # R$ 159,99 em centavos
                    "currency": "BRL",
                    "payment_method": {
                        "type": "credit_card",
                        "card": {
                            "number": "4111111111111111",
                            "holder_name": "JOAO SILVA",
                            "expiry_month": "12",
                            "expiry_year": "2026",
                            "cvv": "123"
                        }
                    },
                    "customer": {
                        "id": "user-001",
                        "name": "João Silva",
                        "email": "joao.silva@example.com",
                        "document": "123.456.789-01",
                        "phone": "+55 11 99999-9999"
                    },
                    "billing_address": {
                        "street": "Rua das Palmeiras, 456",
                        "city": "São Paulo",
                        "state": "SP",
                        "zip_code": "01234-567",
                        "country": "BR"
                    }
                }
            ),
            response=HttpResponse(
                status_code=201,
                headers={
                    "Content-Type": "application/json",
                    "X-Transaction-ID": "txn_789abc123def456"
                },
                body={
                    "id": "payment-789",
                    "status": "approved",
                    "amount": 15999,
                    "currency": "BRL",
                    "transaction_id": "txn_789abc123def456",
                    "authorization_code": "AUTH123456",
                    "created_at": "2024-01-15T12:30:00Z",
                    "gateway_response": {
                        "code": "00",
                        "message": "Transaction approved"
                    }
                }
            ),
            timestamp=int(time.time()),
            trace_id=str(uuid.uuid4()),
            source_service="checkout-service",
            destination_service="payment-service"
        ))
        
        return captures
    
    def _generate_order_api_traffic(self) -> List[TrafficCapture]:
        """Gera tráfego da API de pedidos."""
        captures = []
        
        # POST /api/v1/orders - Criar pedido
        captures.append(TrafficCapture(
            request=HttpRequest(
                method="POST",
                path="/api/v1/orders",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
                    "User-Agent": "MyApp/1.0.0",
                    "X-Request-ID": str(uuid.uuid4())
                },
                query_params={},
                body={
                    "customer_id": "user-001",
                    "items": [
                        {
                            "product_id": "prod-001",
                            "quantity": 1,
                            "price": 899.99
                        },
                        {
                            "product_id": "prod-002",
                            "quantity": 1,
                            "price": 1299.99
                        }
                    ],
                    "shipping_address": {
                        "street": "Rua das Palmeiras, 456",
                        "city": "São Paulo",
                        "state": "SP",
                        "zip_code": "01234-567"
                    },
                    "payment_method": "credit_card"
                }
            ),
            response=HttpResponse(
                status_code=201,
                headers={
                    "Content-Type": "application/json",
                    "Location": "/api/v1/orders/order-456"
                },
                body={
                    "id": "order-456",
                    "status": "confirmed",
                    "total": 2199.98,
                    "items_count": 2,
                    "created_at": "2024-01-15T13:00:00Z",
                    "estimated_delivery": "2024-01-20T00:00:00Z"
                }
            ),
            timestamp=int(time.time()),
            trace_id=str(uuid.uuid4()),
            source_service="mobile-app",
            destination_service="order-service"
        ))
        
        return captures
    
    def _generate_auth_api_traffic(self) -> List[TrafficCapture]:
        """Gera tráfego da API de autenticação."""
        captures = []
        
        # POST /api/v1/auth/login - Login
        captures.append(TrafficCapture(
            request=HttpRequest(
                method="POST",
                path="/api/v1/auth/login",
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "MyApp/1.0.0",
                    "X-Request-ID": str(uuid.uuid4())
                },
                query_params={},
                body={
                    "email": "joao.silva@example.com",
                    "password": "minha-senha-secreta-123",
                    "remember_me": True
                }
            ),
            response=HttpResponse(
                status_code=200,
                headers={
                    "Content-Type": "application/json",
                    "Set-Cookie": "session_id=sess_abc123def456; HttpOnly; Secure; SameSite=Strict"
                },
                body={
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
                    "refresh_token": "rt_xyz789abc123def456ghi789",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "user": {
                        "id": "user-001",
                        "name": "João Silva",
                        "email": "joao.silva@example.com"
                    }
                }
            ),
            timestamp=int(time.time()),
            trace_id=str(uuid.uuid4()),
            source_service="frontend-app",
            destination_service="auth-service"
        ))
        
        return captures
    
    def convert_to_grpc_format(self, capture: TrafficCapture) -> Dict[str, Any]:
        """Converte uma captura para o formato esperado pelo gRPC."""
        return {
            "request": {
                "method": capture.request.method,
                "path": capture.request.path,
                "headers": capture.request.headers,
                "query": capture.request.query_params,
                "body": capture.request.body
            },
            "response": {
                "status": capture.response.status_code,
                "headers": capture.response.headers,
                "body": capture.response.body
            },
            "timestamp": capture.timestamp,
            "trace_id": capture.trace_id,
            "source": capture.source_service,
            "destination": capture.destination_service
        }
    
    async def send_to_collector_http(self, captures: List[TrafficCapture], collector_http_url: str = "http://localhost:8080"):
        """Envia capturas para o Collector via HTTP (para testes)."""
        import httpx
        
        logger.info(f"📤 Enviando {len(captures)} capturas para o Collector via HTTP...")
        
        async with httpx.AsyncClient() as client:
            for i, capture in enumerate(captures):
                grpc_data = self.convert_to_grpc_format(capture)
                
                logger.info(f"📤 Enviando captura {i+1}/{len(captures)}: {capture.request.method} {capture.request.path}")
                
                try:
                    response = await client.post(
                        f"{collector_http_url}/api/v1/capture",
                        json=grpc_data,
                        timeout=10.0
                    )
                    
                    if response.status_code in [200, 201, 202]:
                        logger.info(f"✅ Captura {i+1} enviada com sucesso")
                    else:
                        logger.error(f"❌ Erro ao enviar captura {i+1}: {response.status_code} - {response.text}")
                
                except Exception as e:
                    logger.error(f"❌ Erro ao enviar captura {i+1}: {e}")
                
                # Pausa entre envios para simular tráfego real
                await asyncio.sleep(0.5)
        
        logger.info("✅ Todas as capturas foram enviadas")
    
    async def simulate_continuous_traffic(self, duration_seconds: int = 60, interval_seconds: int = 10):
        """Simula tráfego contínuo por um período determinado."""
        logger.info(f"🔄 Iniciando simulação de tráfego contínuo por {duration_seconds} segundos...")
        
        start_time = time.time()
        self.running = True
        
        try:
            while self.running and (time.time() - start_time) < duration_seconds:
                # Gerar novo lote de tráfego
                captures = self.generate_realistic_traffic()
                
                # Enviar para o Collector
                await self.send_to_collector_http(captures)
                
                # Aguardar próximo intervalo
                logger.info(f"⏳ Aguardando {interval_seconds} segundos para próximo lote...")
                await asyncio.sleep(interval_seconds)
        
        except KeyboardInterrupt:
            logger.info("⏹️ Simulação interrompida pelo usuário")
        
        finally:
            self.running = False
            logger.info("🏁 Simulação de tráfego finalizada")
    
    def stop(self):
        """Para a simulação de tráfego."""
        self.running = False


async def main():
    """Função principal para executar a simulação."""
    simulator = EnvoyTapSimulator()
    
    logger.info("🚀 Iniciando simulação do Envoy Tap Filter")
    logger.info("=" * 60)
    
    try:
        # Opção 1: Enviar um lote único de tráfego
        logger.info("📊 Gerando tráfego realista...")
        captures = simulator.generate_realistic_traffic()
        logger.info(f"✅ Geradas {len(captures)} capturas de tráfego")
        
        await simulator.send_to_collector_http(captures)
        
        logger.info("\n" + "=" * 60)
        logger.info("🎉 Simulação concluída!")
        logger.info("\n💡 Para simulação contínua, descomente a linha abaixo:")
        logger.info("# await simulator.simulate_continuous_traffic(duration_seconds=300, interval_seconds=15)")
        
        # Opção 2: Simulação contínua (descomente para usar)
        # await simulator.simulate_continuous_traffic(duration_seconds=300, interval_seconds=15)
    
    except Exception as e:
        logger.error(f"❌ Erro durante simulação: {e}")
        raise


if __name__ == "__main__":
    # Executar simulação
    asyncio.run(main())