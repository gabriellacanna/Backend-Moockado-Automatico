"""
Processador principal de requests/responses
Coordena sanitização, deduplicação e geração de mappings WireMock
"""
import asyncio
import json
from typing import Dict, Any, Optional, List
import structlog
from datetime import datetime
import httpx

from .sanitizer import DataSanitizer
from .deduplicator import RequestDeduplicator

logger = structlog.get_logger(__name__)


class RequestProcessor:
    """Processador principal de requests capturadas"""
    
    def __init__(
        self,
        sanitizer: DataSanitizer,
        deduplicator: RequestDeduplicator,
        config_manager,
        output_queue: asyncio.Queue
    ):
        self.sanitizer = sanitizer
        self.deduplicator = deduplicator
        self.config = config_manager
        self.output_queue = output_queue
        
        self.stats = {
            'processed': 0,
            'duplicates': 0,
            'errors': 0,
            'sanitized': 0,
            'mappings_generated': 0
        }
    
    async def process_tap_event(self, tap_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Processa um evento de tap do Envoy"""
        try:
            request_data = tap_event.get('request', {})
            response_data = tap_event.get('response', {})
            
            if not request_data or not response_data:
                logger.debug("Evento de tap incompleto, ignorando")
                return None
            
            # Extrair dados básicos
            method = request_data.get('method', 'GET')
            path = request_data.get('path', '/')
            query_params = request_data.get('query_params', '')
            
            # Sanitizar dados sensíveis
            sanitized_request = await self._sanitize_request(request_data)
            sanitized_response = await self._sanitize_response(response_data)
            
            # Gerar hash para deduplicação
            body_hash = self.sanitizer.generate_body_hash(sanitized_request.get('body', ''))
            request_hash = await self.deduplicator.generate_request_hash(
                method=method,
                path=path.split('?')[0],  # Remove query params do path
                query_params=query_params,
                body_hash=body_hash,
                headers=sanitized_request.get('headers', {})
            )
            
            # Verificar duplicação
            if await self.deduplicator.is_duplicate(request_hash):
                logger.debug("Request duplicada, ignorando", hash=request_hash[:12])
                self.stats['duplicates'] += 1
                return None
            
            # Gerar mapping WireMock
            wiremock_mapping = self._generate_wiremock_mapping(
                sanitized_request,
                sanitized_response,
                request_hash
            )
            
            # Marcar como processado
            metadata = {
                'method': method,
                'path': path,
                'status_code': sanitized_response.get('status_code', 200),
                'timestamp': tap_event.get('timestamp')
            }
            
            await self.deduplicator.mark_as_processed(request_hash, metadata)
            
            # Enviar para fila de output
            output_event = {
                'type': 'wiremock_mapping',
                'mapping': wiremock_mapping,
                'metadata': {
                    'request_hash': request_hash,
                    'original_timestamp': tap_event.get('timestamp'),
                    'processed_timestamp': datetime.utcnow().isoformat()
                }
            }
            
            await self.output_queue.put(output_event)
            
            self.stats['processed'] += 1
            self.stats['mappings_generated'] += 1
            
            logger.info(
                "Request processada com sucesso",
                method=method,
                path=path,
                status=sanitized_response.get('status_code'),
                hash=request_hash[:12]
            )
            
            return output_event
            
        except Exception as e:
            logger.error("Erro ao processar tap event", error=str(e))
            self.stats['errors'] += 1
            return None
    
    async def _sanitize_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitiza dados da request"""
        try:
            sanitized = {
                'method': request_data.get('method', 'GET'),
                'path': request_data.get('path', '/'),
                'query_params': request_data.get('query_params', ''),
                'headers': {},
                'body': None
            }
            
            # Sanitizar headers
            original_headers = request_data.get('headers', {})
            sanitized['headers'] = self.sanitizer.sanitize_headers(original_headers)
            
            # Sanitizar query parameters
            if sanitized['query_params']:
                sanitized['query_params'] = self.sanitizer.sanitize_query_params(
                    sanitized['query_params']
                )
            
            # Sanitizar body
            original_body = request_data.get('body')
            if original_body:
                content_type = original_headers.get('content-type', '')
                
                # Limitar tamanho do body
                if isinstance(original_body, str) and len(original_body) > self.config.settings.body_size_limit:
                    original_body = original_body[:self.config.settings.body_size_limit]
                    logger.debug("Body truncado por limite de tamanho")
                
                sanitized['body'] = self.sanitizer.sanitize_body(original_body, content_type)
                self.stats['sanitized'] += 1
            
            return sanitized
            
        except Exception as e:
            logger.error("Erro ao sanitizar request", error=str(e))
            return request_data
    
    async def _sanitize_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitiza dados da response"""
        try:
            sanitized = {
                'status_code': response_data.get('status_code', 200),
                'headers': {},
                'body': None
            }
            
            # Sanitizar headers
            original_headers = response_data.get('headers', {})
            sanitized['headers'] = self.sanitizer.sanitize_headers(original_headers)
            
            # Sanitizar body
            original_body = response_data.get('body')
            if original_body:
                content_type = original_headers.get('content-type', '')
                
                # Limitar tamanho do body
                if isinstance(original_body, str) and len(original_body) > self.config.settings.body_size_limit:
                    original_body = original_body[:self.config.settings.body_size_limit]
                    logger.debug("Response body truncado por limite de tamanho")
                
                sanitized['body'] = self.sanitizer.sanitize_body(original_body, content_type)
                self.stats['sanitized'] += 1
            
            return sanitized
            
        except Exception as e:
            logger.error("Erro ao sanitizar response", error=str(e))
            return response_data
    
    def _generate_wiremock_mapping(
        self,
        request_data: Dict[str, Any],
        response_data: Dict[str, Any],
        request_hash: str
    ) -> Dict[str, Any]:
        """Gera mapping WireMock a partir dos dados sanitizados"""
        
        # Construir request matching
        request_matching = {
            'method': request_data['method'],
            'urlPath': request_data['path'].split('?')[0]  # Remove query params
        }
        
        # Adicionar query parameters se existirem
        if request_data.get('query_params'):
            query_params = self._parse_query_params(request_data['query_params'])
            if query_params:
                request_matching['queryParameters'] = query_params
        
        # Adicionar headers importantes para matching
        headers_for_matching = {}
        request_headers = request_data.get('headers', {})
        
        # Headers que podem afetar a response
        important_headers = ['content-type', 'accept', 'x-api-version']
        for header_name in important_headers:
            header_value = request_headers.get(header_name) or request_headers.get(header_name.lower())
            if header_value and not header_value.startswith('***'):  # Não incluir dados sanitizados
                headers_for_matching[header_name] = {'equalTo': header_value}
        
        if headers_for_matching:
            request_matching['headers'] = headers_for_matching
        
        # Adicionar body matching se existir
        request_body = request_data.get('body')
        if request_body and request_body != '***SANITIZED***':
            try:
                # Tentar parsear como JSON
                if isinstance(request_body, str):
                    json.loads(request_body)
                    request_matching['bodyPatterns'] = [{'equalToJson': request_body}]
                else:
                    request_matching['bodyPatterns'] = [{'equalToJson': json.dumps(request_body)}]
            except (json.JSONDecodeError, TypeError):
                # Se não for JSON válido, usar matching de texto
                request_matching['bodyPatterns'] = [{'equalTo': str(request_body)}]
        
        # Construir response
        response_definition = {
            'status': response_data.get('status_code', 200)
        }
        
        # Adicionar headers da response
        response_headers = response_data.get('headers', {})
        if response_headers:
            # Filtrar headers do sistema que não devem ser incluídos
            filtered_headers = {}
            skip_headers = ['date', 'server', 'x-envoy-', 'x-request-id']
            
            for key, value in response_headers.items():
                key_lower = key.lower()
                should_skip = any(skip_header in key_lower for skip_header in skip_headers)
                
                if not should_skip and not value.startswith('***'):
                    filtered_headers[key] = value
            
            if filtered_headers:
                response_definition['headers'] = filtered_headers
        
        # Adicionar body da response
        response_body = response_data.get('body')
        if response_body and response_body != '***SANITIZED***':
            try:
                # Tentar parsear como JSON
                if isinstance(response_body, str):
                    parsed_body = json.loads(response_body)
                    response_definition['jsonBody'] = parsed_body
                else:
                    response_definition['jsonBody'] = response_body
            except (json.JSONDecodeError, TypeError):
                # Se não for JSON válido, usar como texto
                response_definition['body'] = str(response_body)
        
        # Construir mapping completo
        mapping = {
            'id': request_hash,
            'name': f"Auto-generated mock for {request_data['method']} {request_data['path'].split('?')[0]}",
            'request': request_matching,
            'response': response_definition,
            'metadata': {
                'generated_by': 'backend-mockado-automatico',
                'generated_at': datetime.utcnow().isoformat(),
                'request_hash': request_hash,
                'original_path': request_data['path']
            }
        }
        
        return mapping
    
    def _parse_query_params(self, query_string: str) -> Dict[str, Any]:
        """Parseia query parameters para formato WireMock"""
        try:
            from urllib.parse import parse_qs
            
            parsed = parse_qs(query_string, keep_blank_values=True)
            wiremock_params = {}
            
            for key, values in parsed.items():
                if len(values) == 1:
                    # Parâmetro único
                    wiremock_params[key] = {'equalTo': values[0]}
                else:
                    # Múltiplos valores - usar regex ou contains
                    wiremock_params[key] = {'matches': '.*(' + '|'.join(values) + ').*'}
            
            return wiremock_params
            
        except Exception as e:
            logger.warning("Erro ao parsear query parameters", error=str(e))
            return {}
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do processador"""
        return self.stats.copy()


class BatchProcessor:
    """Processador em lote para melhor performance"""
    
    def __init__(
        self,
        processor: RequestProcessor,
        batch_size: int = 10,
        batch_timeout: int = 5
    ):
        self.processor = processor
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.batch = []
        self.last_flush = datetime.utcnow()
    
    async def add_event(self, tap_event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Adiciona evento ao batch e processa se necessário"""
        self.batch.append(tap_event)
        
        # Verificar se deve processar o batch
        should_flush = (
            len(self.batch) >= self.batch_size or
            (datetime.utcnow() - self.last_flush).total_seconds() >= self.batch_timeout
        )
        
        if should_flush:
            return await self.flush_batch()
        
        return []
    
    async def flush_batch(self) -> List[Dict[str, Any]]:
        """Processa todos os eventos no batch"""
        if not self.batch:
            return []
        
        results = []
        batch_to_process = self.batch.copy()
        self.batch.clear()
        self.last_flush = datetime.utcnow()
        
        logger.debug("Processando batch", size=len(batch_to_process))
        
        # Processar eventos em paralelo
        tasks = [
            self.processor.process_tap_event(event)
            for event in batch_to_process
        ]
        
        try:
            processed_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in processed_results:
                if isinstance(result, Exception):
                    logger.error("Erro no processamento em batch", error=str(result))
                elif result is not None:
                    results.append(result)
            
        except Exception as e:
            logger.error("Erro crítico no processamento em batch", error=str(e))
        
        logger.debug("Batch processado", input_size=len(batch_to_process), output_size=len(results))
        return results