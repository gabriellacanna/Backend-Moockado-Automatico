"""
Cliente para interação com WireMock
Gerencia criação, atualização e remoção de mappings
"""
import asyncio
import json
from typing import Dict, Any, List, Optional, Tuple
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from datetime import datetime

logger = structlog.get_logger(__name__)


class WireMockClient:
    """Cliente para API do WireMock"""
    
    def __init__(self, base_url: str, timeout: int = 30, max_retries: int = 3):
        self.base_url = base_url.rstrip('/')
        self.admin_url = f"{self.base_url}/__admin"
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Configurar cliente HTTP
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
        )
        
        self.stats = {
            'mappings_created': 0,
            'mappings_updated': 0,
            'mappings_deleted': 0,
            'requests_failed': 0,
            'last_error': None
        }
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def close(self):
        """Fecha o cliente HTTP"""
        await self.client.aclose()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError))
    )
    async def health_check(self) -> bool:
        """Verifica se o WireMock está disponível"""
        try:
            response = await self.client.get(f"{self.admin_url}/health")
            response.raise_for_status()
            return True
            
        except Exception as e:
            logger.warning("WireMock health check falhou", error=str(e))
            return False
    
    async def create_mapping(self, mapping: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Cria um novo mapping no WireMock"""
        try:
            # Validar estrutura básica do mapping
            if not self._validate_mapping_structure(mapping):
                return False, "Estrutura de mapping inválida"
            
            # Fazer request para criar mapping
            response = await self.client.post(
                f"{self.admin_url}/mappings",
                json=mapping,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 201:
                self.stats['mappings_created'] += 1
                mapping_id = mapping.get('id', 'unknown')
                logger.info("Mapping criado com sucesso", mapping_id=mapping_id)
                return True, None
            else:
                error_msg = f"Erro HTTP {response.status_code}: {response.text}"
                self.stats['requests_failed'] += 1
                self.stats['last_error'] = error_msg
                logger.error("Erro ao criar mapping", error=error_msg, mapping_id=mapping.get('id'))
                return False, error_msg
                
        except httpx.RequestError as e:
            error_msg = f"Erro de conexão: {str(e)}"
            self.stats['requests_failed'] += 1
            self.stats['last_error'] = error_msg
            logger.error("Erro de conexão ao criar mapping", error=error_msg)
            return False, error_msg
        
        except Exception as e:
            error_msg = f"Erro inesperado: {str(e)}"
            self.stats['requests_failed'] += 1
            self.stats['last_error'] = error_msg
            logger.error("Erro inesperado ao criar mapping", error=error_msg)
            return False, error_msg
    
    async def update_mapping(self, mapping_id: str, mapping: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Atualiza um mapping existente"""
        try:
            if not self._validate_mapping_structure(mapping):
                return False, "Estrutura de mapping inválida"
            
            response = await self.client.put(
                f"{self.admin_url}/mappings/{mapping_id}",
                json=mapping,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                self.stats['mappings_updated'] += 1
                logger.info("Mapping atualizado com sucesso", mapping_id=mapping_id)
                return True, None
            else:
                error_msg = f"Erro HTTP {response.status_code}: {response.text}"
                self.stats['requests_failed'] += 1
                self.stats['last_error'] = error_msg
                logger.error("Erro ao atualizar mapping", error=error_msg, mapping_id=mapping_id)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Erro ao atualizar mapping: {str(e)}"
            self.stats['requests_failed'] += 1
            self.stats['last_error'] = error_msg
            logger.error("Erro ao atualizar mapping", error=error_msg, mapping_id=mapping_id)
            return False, error_msg
    
    async def delete_mapping(self, mapping_id: str) -> Tuple[bool, Optional[str]]:
        """Remove um mapping"""
        try:
            response = await self.client.delete(f"{self.admin_url}/mappings/{mapping_id}")
            
            if response.status_code == 200:
                self.stats['mappings_deleted'] += 1
                logger.info("Mapping removido com sucesso", mapping_id=mapping_id)
                return True, None
            else:
                error_msg = f"Erro HTTP {response.status_code}: {response.text}"
                self.stats['requests_failed'] += 1
                self.stats['last_error'] = error_msg
                logger.error("Erro ao remover mapping", error=error_msg, mapping_id=mapping_id)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Erro ao remover mapping: {str(e)}"
            self.stats['requests_failed'] += 1
            self.stats['last_error'] = error_msg
            logger.error("Erro ao remover mapping", error=error_msg, mapping_id=mapping_id)
            return False, error_msg
    
    async def get_mapping(self, mapping_id: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Obtém um mapping específico"""
        try:
            response = await self.client.get(f"{self.admin_url}/mappings/{mapping_id}")
            
            if response.status_code == 200:
                mapping_data = response.json()
                return True, mapping_data, None
            elif response.status_code == 404:
                return False, None, "Mapping não encontrado"
            else:
                error_msg = f"Erro HTTP {response.status_code}: {response.text}"
                return False, None, error_msg
                
        except Exception as e:
            error_msg = f"Erro ao obter mapping: {str(e)}"
            logger.error("Erro ao obter mapping", error=error_msg, mapping_id=mapping_id)
            return False, None, error_msg
    
    async def list_mappings(self, limit: int = 100, offset: int = 0) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """Lista mappings existentes"""
        try:
            params = {'limit': limit, 'offset': offset}
            response = await self.client.get(f"{self.admin_url}/mappings", params=params)
            
            if response.status_code == 200:
                data = response.json()
                mappings = data.get('mappings', [])
                return True, mappings, None
            else:
                error_msg = f"Erro HTTP {response.status_code}: {response.text}"
                return False, [], error_msg
                
        except Exception as e:
            error_msg = f"Erro ao listar mappings: {str(e)}"
            logger.error("Erro ao listar mappings", error=error_msg)
            return False, [], error_msg
    
    async def reset_mappings(self) -> Tuple[bool, Optional[str]]:
        """Remove todos os mappings (cuidado!)"""
        try:
            response = await self.client.delete(f"{self.admin_url}/mappings")
            
            if response.status_code == 200:
                logger.warning("Todos os mappings foram removidos")
                return True, None
            else:
                error_msg = f"Erro HTTP {response.status_code}: {response.text}"
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Erro ao resetar mappings: {str(e)}"
            logger.error("Erro ao resetar mappings", error=error_msg)
            return False, error_msg
    
    async def get_requests(self, limit: int = 100) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """Obtém requests recebidas pelo WireMock"""
        try:
            params = {'limit': limit}
            response = await self.client.get(f"{self.admin_url}/requests", params=params)
            
            if response.status_code == 200:
                data = response.json()
                requests = data.get('requests', [])
                return True, requests, None
            else:
                error_msg = f"Erro HTTP {response.status_code}: {response.text}"
                return False, [], error_msg
                
        except Exception as e:
            error_msg = f"Erro ao obter requests: {str(e)}"
            logger.error("Erro ao obter requests", error=error_msg)
            return False, [], error_msg
    
    async def find_unmatched_requests(self) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """Encontra requests que não foram atendidas por nenhum mapping"""
        try:
            response = await self.client.get(f"{self.admin_url}/requests/unmatched")
            
            if response.status_code == 200:
                data = response.json()
                unmatched = data.get('requests', [])
                return True, unmatched, None
            else:
                error_msg = f"Erro HTTP {response.status_code}: {response.text}"
                return False, [], error_msg
                
        except Exception as e:
            error_msg = f"Erro ao obter requests não atendidas: {str(e)}"
            logger.error("Erro ao obter requests não atendidas", error=error_msg)
            return False, [], error_msg
    
    def _validate_mapping_structure(self, mapping: Dict[str, Any]) -> bool:
        """Valida estrutura básica do mapping"""
        try:
            # Verificar campos obrigatórios
            if 'request' not in mapping or 'response' not in mapping:
                return False
            
            request = mapping['request']
            response = mapping['response']
            
            # Verificar request
            if 'method' not in request:
                return False
            
            if 'urlPath' not in request and 'url' not in request and 'urlPattern' not in request:
                return False
            
            # Verificar response
            if 'status' not in response:
                return False
            
            # Verificar se status é um número válido
            status = response['status']
            if not isinstance(status, int) or status < 100 or status > 599:
                return False
            
            return True
            
        except Exception as e:
            logger.error("Erro na validação da estrutura do mapping", error=str(e))
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cliente"""
        return {
            **self.stats,
            'base_url': self.base_url,
            'timeout': self.timeout,
            'max_retries': self.max_retries
        }


class BatchWireMockClient:
    """Cliente para operações em lote no WireMock"""
    
    def __init__(self, wiremock_client: WireMockClient, batch_size: int = 5):
        self.client = wiremock_client
        self.batch_size = batch_size
        self.pending_mappings = []
        self.stats = {
            'batches_processed': 0,
            'mappings_in_batch': 0,
            'batch_errors': 0
        }
    
    async def add_mapping(self, mapping: Dict[str, Any]) -> bool:
        """Adiciona mapping ao batch"""
        self.pending_mappings.append(mapping)
        
        # Processar batch se atingiu o tamanho limite
        if len(self.pending_mappings) >= self.batch_size:
            return await self.flush_batch()
        
        return True
    
    async def flush_batch(self) -> bool:
        """Processa todos os mappings pendentes"""
        if not self.pending_mappings:
            return True
        
        batch_to_process = self.pending_mappings.copy()
        self.pending_mappings.clear()
        
        logger.info("Processando batch de mappings", size=len(batch_to_process))
        
        success_count = 0
        error_count = 0
        
        # Processar mappings em paralelo (com limite de concorrência)
        semaphore = asyncio.Semaphore(5)  # Máximo 5 requests simultâneas
        
        async def process_mapping(mapping):
            async with semaphore:
                success, error = await self.client.create_mapping(mapping)
                return success, error, mapping.get('id', 'unknown')
        
        # Executar todas as tasks
        tasks = [process_mapping(mapping) for mapping in batch_to_process]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Processar resultados
        for result in results:
            if isinstance(result, Exception):
                logger.error("Erro no processamento em batch", error=str(result))
                error_count += 1
            else:
                success, error, mapping_id = result
                if success:
                    success_count += 1
                else:
                    error_count += 1
                    logger.error("Erro ao processar mapping no batch", 
                               mapping_id=mapping_id, error=error)
        
        # Atualizar estatísticas
        self.stats['batches_processed'] += 1
        self.stats['mappings_in_batch'] += len(batch_to_process)
        if error_count > 0:
            self.stats['batch_errors'] += 1
        
        logger.info("Batch processado", 
                   total=len(batch_to_process), 
                   success=success_count, 
                   errors=error_count)
        
        return error_count == 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do batch client"""
        return {
            **self.stats,
            'pending_mappings': len(self.pending_mappings),
            'batch_size': self.batch_size
        }