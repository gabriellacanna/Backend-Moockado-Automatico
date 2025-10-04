"""
Serviço gRPC para receber dados do Envoy tap filter
Processa requests/responses capturadas do service mesh
"""
import asyncio
import json
from typing import Dict, Any, Optional
import grpc
from grpc import aio
import structlog
from datetime import datetime

# Imports para protobuf (serão gerados)
# from . import tap_pb2
# from . import tap_pb2_grpc

logger = structlog.get_logger(__name__)


class TapServicer:
    """Servicer para receber dados do Envoy tap filter"""
    
    def __init__(self, processor_queue: asyncio.Queue, config_manager):
        self.processor_queue = processor_queue
        self.config = config_manager
        self.stats = {
            'requests_received': 0,
            'requests_processed': 0,
            'requests_ignored': 0,
            'errors': 0
        }
    
    async def StreamTapData(self, request_iterator, context):
        """Stream de dados do tap filter"""
        try:
            async for tap_data in request_iterator:
                await self._process_tap_data(tap_data)
                
        except Exception as e:
            logger.error("Erro no stream de tap data", error=str(e))
            self.stats['errors'] += 1
            await context.abort(grpc.StatusCode.INTERNAL, f"Erro interno: {str(e)}")
    
    async def _process_tap_data(self, tap_data):
        """Processa dados recebidos do tap filter"""
        try:
            self.stats['requests_received'] += 1
            
            # Extrair dados da mensagem protobuf
            request_data = self._extract_request_data(tap_data)
            response_data = self._extract_response_data(tap_data)
            
            if not request_data:
                logger.debug("Dados de request inválidos, ignorando")
                self.stats['requests_ignored'] += 1
                return
            
            # Verificar se deve ignorar esta request
            host = request_data.get('host', '')
            path = request_data.get('path', '')
            
            if self.config.should_ignore_request(host, path):
                logger.debug("Request ignorada por filtro", host=host, path=path)
                self.stats['requests_ignored'] += 1
                return
            
            # Verificar sampling
            method = request_data.get('method', 'GET')
            sample_rate = self.config.get_sample_rate(path, method)
            
            if sample_rate < 1.0:
                import random
                if random.random() > sample_rate:
                    logger.debug("Request ignorada por sampling", path=path, sample_rate=sample_rate)
                    self.stats['requests_ignored'] += 1
                    return
            
            # Criar objeto para processamento
            tap_event = {
                'timestamp': datetime.utcnow().isoformat(),
                'request': request_data,
                'response': response_data,
                'metadata': {
                    'tap_id': getattr(tap_data, 'tap_id', 'unknown'),
                    'source': 'envoy_tap'
                }
            }
            
            # Enviar para fila de processamento
            try:
                await self.processor_queue.put(tap_event)
                self.stats['requests_processed'] += 1
                logger.debug("Tap event enviado para processamento", path=path, method=method)
                
            except asyncio.QueueFull:
                logger.warning("Fila de processamento cheia, descartando request", path=path)
                self.stats['requests_ignored'] += 1
                
        except Exception as e:
            logger.error("Erro ao processar tap data", error=str(e))
            self.stats['errors'] += 1
    
    def _extract_request_data(self, tap_data) -> Optional[Dict[str, Any]]:
        """Extrai dados da request do tap data"""
        try:
            # Esta implementação é um placeholder
            # Na implementação real, seria necessário parsear o protobuf do Envoy
            
            # Exemplo de estrutura esperada:
            if hasattr(tap_data, 'http_buffered_trace'):
                trace = tap_data.http_buffered_trace
                
                if hasattr(trace, 'request'):
                    request = trace.request
                    
                    # Extrair headers
                    headers = {}
                    if hasattr(request, 'headers'):
                        for header in request.headers:
                            headers[header.key] = header.value
                    
                    # Extrair body
                    body = ""
                    if hasattr(request, 'body'):
                        body = request.body.as_bytes().decode('utf-8', errors='ignore')
                    
                    # Construir dados da request
                    request_data = {
                        'method': headers.get(':method', 'GET'),
                        'path': headers.get(':path', '/'),
                        'host': headers.get(':authority') or headers.get('host', ''),
                        'scheme': headers.get(':scheme', 'http'),
                        'headers': headers,
                        'body': body,
                        'query_params': self._extract_query_params(headers.get(':path', ''))
                    }
                    
                    return request_data
            
            return None
            
        except Exception as e:
            logger.error("Erro ao extrair dados da request", error=str(e))
            return None
    
    def _extract_response_data(self, tap_data) -> Optional[Dict[str, Any]]:
        """Extrai dados da response do tap data"""
        try:
            if hasattr(tap_data, 'http_buffered_trace'):
                trace = tap_data.http_buffered_trace
                
                if hasattr(trace, 'response'):
                    response = trace.response
                    
                    # Extrair headers
                    headers = {}
                    if hasattr(response, 'headers'):
                        for header in response.headers:
                            headers[header.key] = header.value
                    
                    # Extrair body
                    body = ""
                    if hasattr(response, 'body'):
                        body = response.body.as_bytes().decode('utf-8', errors='ignore')
                    
                    # Construir dados da response
                    response_data = {
                        'status_code': int(headers.get(':status', '200')),
                        'headers': headers,
                        'body': body
                    }
                    
                    return response_data
            
            return None
            
        except Exception as e:
            logger.error("Erro ao extrair dados da response", error=str(e))
            return None
    
    def _extract_query_params(self, path: str) -> str:
        """Extrai query parameters do path"""
        if '?' in path:
            return path.split('?', 1)[1]
        return ""
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do serviço"""
        return self.stats.copy()


class MockTapServicer(TapServicer):
    """Servicer mock para desenvolvimento e testes"""
    
    async def StreamTapData(self, request_iterator, context):
        """Mock implementation para testes"""
        logger.info("Mock tap servicer recebendo dados")
        
        async for tap_data in request_iterator:
            # Simular processamento
            mock_event = {
                'timestamp': datetime.utcnow().isoformat(),
                'request': {
                    'method': 'POST',
                    'path': '/api/v1/test',
                    'host': 'test-service.default.svc.cluster.local',
                    'scheme': 'http',
                    'headers': {
                        'content-type': 'application/json',
                        'user-agent': 'test-client/1.0'
                    },
                    'body': '{"test": "data"}',
                    'query_params': ''
                },
                'response': {
                    'status_code': 200,
                    'headers': {
                        'content-type': 'application/json'
                    },
                    'body': '{"result": "success"}'
                },
                'metadata': {
                    'tap_id': 'mock-tap',
                    'source': 'mock'
                }
            }
            
            await self.processor_queue.put(mock_event)
            self.stats['requests_received'] += 1
            self.stats['requests_processed'] += 1


class GrpcServer:
    """Servidor gRPC para receber dados do Envoy"""
    
    def __init__(self, port: int, processor_queue: asyncio.Queue, config_manager):
        self.port = port
        self.processor_queue = processor_queue
        self.config = config_manager
        self.server = None
        self.servicer = None
    
    async def start(self, use_mock: bool = False):
        """Inicia o servidor gRPC"""
        try:
            self.server = aio.server()
            
            # Criar servicer
            if use_mock:
                self.servicer = MockTapServicer(self.processor_queue, self.config)
                logger.info("Usando mock tap servicer para desenvolvimento")
            else:
                self.servicer = TapServicer(self.processor_queue, self.config)
            
            # Registrar servicer
            # tap_pb2_grpc.add_StreamingTapSinkServicer_to_server(self.servicer, self.server)
            
            # Configurar porta
            listen_addr = f'[::]:{self.port}'
            self.server.add_insecure_port(listen_addr)
            
            # Iniciar servidor
            await self.server.start()
            logger.info("Servidor gRPC iniciado", port=self.port, address=listen_addr)
            
        except Exception as e:
            logger.error("Erro ao iniciar servidor gRPC", error=str(e), port=self.port)
            raise
    
    async def stop(self):
        """Para o servidor gRPC"""
        if self.server:
            logger.info("Parando servidor gRPC")
            await self.server.stop(grace=5)
            await self.server.wait_for_termination()
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do servidor"""
        if self.servicer:
            return self.servicer.get_stats()
        return {}


# Placeholder para protobuf definitions
# Em produção, estes seriam gerados a partir dos .proto files do Envoy

class TapData:
    """Placeholder para dados do tap"""
    def __init__(self):
        self.tap_id = "placeholder"
        self.http_buffered_trace = None


class HttpBufferedTrace:
    """Placeholder para trace HTTP"""
    def __init__(self):
        self.request = None
        self.response = None


class HttpRequest:
    """Placeholder para request HTTP"""
    def __init__(self):
        self.headers = []
        self.body = None


class HttpResponse:
    """Placeholder para response HTTP"""
    def __init__(self):
        self.headers = []
        self.body = None


class Header:
    """Placeholder para header"""
    def __init__(self, key: str, value: str):
        self.key = key
        self.value = value


class Body:
    """Placeholder para body"""
    def __init__(self, data: bytes):
        self._data = data
    
    def as_bytes(self) -> bytes:
        return self._data