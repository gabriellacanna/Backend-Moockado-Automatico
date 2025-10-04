"""
Módulo de deduplicação de requests/responses
Evita criar múltiplos stubs para o mesmo endpoint
"""
import hashlib
import json
from typing import Dict, Any, Optional, List
import aioredis
import structlog
from datetime import datetime, timedelta

logger = structlog.get_logger(__name__)


class RequestDeduplicator:
    """Deduplicador de requests usando Redis como backend"""
    
    def __init__(self, redis_client: aioredis.Redis, ttl: int = 3600):
        self.redis = redis_client
        self.ttl = ttl
        self.key_prefix = "mock:dedup:"
    
    async def generate_request_hash(
        self,
        method: str,
        path: str,
        query_params: str = "",
        body_hash: str = "",
        headers: Optional[Dict[str, str]] = None
    ) -> str:
        """Gera hash único para uma request"""
        
        # Normalizar dados para hash consistente
        normalized_method = method.upper()
        normalized_path = path.lower().rstrip('/')
        
        # Ordenar query parameters para consistência
        if query_params:
            try:
                from urllib.parse import parse_qs, urlencode
                parsed_params = parse_qs(query_params, keep_blank_values=True)
                # Ordenar parâmetros e valores
                sorted_params = {}
                for key in sorted(parsed_params.keys()):
                    sorted_params[key] = sorted(parsed_params[key])
                normalized_query = urlencode(sorted_params, doseq=True)
            except Exception:
                normalized_query = query_params
        else:
            normalized_query = ""
        
        # Incluir headers relevantes para diferenciação (opcional)
        relevant_headers = {}
        if headers:
            # Apenas alguns headers que podem afetar a response
            relevant_header_names = [
                'content-type', 'accept', 'accept-language',
                'user-agent', 'x-api-version', 'x-client-version'
            ]
            for header_name in relevant_header_names:
                header_value = headers.get(header_name) or headers.get(header_name.lower())
                if header_value:
                    relevant_headers[header_name] = header_value
        
        # Criar string para hash
        hash_components = [
            normalized_method,
            normalized_path,
            normalized_query,
            body_hash or "",
            json.dumps(relevant_headers, sort_keys=True) if relevant_headers else ""
        ]
        
        hash_string = "|".join(hash_components)
        
        # Gerar hash SHA-256
        request_hash = hashlib.sha256(hash_string.encode('utf-8')).hexdigest()
        
        logger.debug(
            "Hash gerado para request",
            method=method,
            path=path,
            hash=request_hash[:12],
            components=hash_components
        )
        
        return request_hash
    
    async def is_duplicate(self, request_hash: str) -> bool:
        """Verifica se a request já foi processada"""
        try:
            key = f"{self.key_prefix}{request_hash}"
            exists = await self.redis.exists(key)
            
            if exists:
                logger.debug("Request duplicada encontrada", hash=request_hash[:12])
                return True
            
            return False
            
        except Exception as e:
            logger.error("Erro ao verificar duplicação", error=str(e), hash=request_hash[:12])
            # Em caso de erro, assumir que não é duplicata para não perder dados
            return False
    
    async def mark_as_processed(
        self,
        request_hash: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Marca uma request como processada"""
        try:
            key = f"{self.key_prefix}{request_hash}"
            
            # Dados para armazenar
            data = {
                'processed_at': datetime.utcnow().isoformat(),
                'hash': request_hash,
                'metadata': metadata or {}
            }
            
            # Armazenar com TTL
            await self.redis.setex(
                key,
                self.ttl,
                json.dumps(data, separators=(',', ':'))
            )
            
            logger.debug(
                "Request marcada como processada",
                hash=request_hash[:12],
                ttl=self.ttl
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Erro ao marcar request como processada",
                error=str(e),
                hash=request_hash[:12]
            )
            return False
    
    async def get_processed_info(self, request_hash: str) -> Optional[Dict[str, Any]]:
        """Obtém informações sobre uma request processada"""
        try:
            key = f"{self.key_prefix}{request_hash}"
            data = await self.redis.get(key)
            
            if data:
                return json.loads(data)
            
            return None
            
        except Exception as e:
            logger.error(
                "Erro ao obter informações da request processada",
                error=str(e),
                hash=request_hash[:12]
            )
            return None
    
    async def cleanup_expired(self) -> int:
        """Remove entradas expiradas (executado periodicamente)"""
        try:
            pattern = f"{self.key_prefix}*"
            keys = await self.redis.keys(pattern)
            
            expired_count = 0
            for key in keys:
                ttl = await self.redis.ttl(key)
                if ttl == -1:  # Sem TTL definido
                    await self.redis.delete(key)
                    expired_count += 1
            
            if expired_count > 0:
                logger.info("Limpeza de entradas expiradas", removed_count=expired_count)
            
            return expired_count
            
        except Exception as e:
            logger.error("Erro na limpeza de entradas expiradas", error=str(e))
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas de deduplicação"""
        try:
            pattern = f"{self.key_prefix}*"
            keys = await self.redis.keys(pattern)
            
            total_entries = len(keys)
            
            # Contar por idade
            now = datetime.utcnow()
            age_buckets = {
                'last_hour': 0,
                'last_day': 0,
                'older': 0
            }
            
            for key in keys[:100]:  # Limitar para performance
                try:
                    data = await self.redis.get(key)
                    if data:
                        entry = json.loads(data)
                        processed_at = datetime.fromisoformat(entry['processed_at'])
                        age = now - processed_at
                        
                        if age < timedelta(hours=1):
                            age_buckets['last_hour'] += 1
                        elif age < timedelta(days=1):
                            age_buckets['last_day'] += 1
                        else:
                            age_buckets['older'] += 1
                except Exception:
                    continue
            
            return {
                'total_entries': total_entries,
                'age_distribution': age_buckets,
                'ttl_seconds': self.ttl
            }
            
        except Exception as e:
            logger.error("Erro ao obter estatísticas", error=str(e))
            return {'error': str(e)}


class InMemoryDeduplicator:
    """Deduplicador em memória para desenvolvimento/testes"""
    
    def __init__(self, ttl: int = 3600):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = ttl
    
    async def generate_request_hash(
        self,
        method: str,
        path: str,
        query_params: str = "",
        body_hash: str = "",
        headers: Optional[Dict[str, str]] = None
    ) -> str:
        """Gera hash único para uma request (mesmo algoritmo do Redis)"""
        normalized_method = method.upper()
        normalized_path = path.lower().rstrip('/')
        
        if query_params:
            try:
                from urllib.parse import parse_qs, urlencode
                parsed_params = parse_qs(query_params, keep_blank_values=True)
                sorted_params = {}
                for key in sorted(parsed_params.keys()):
                    sorted_params[key] = sorted(parsed_params[key])
                normalized_query = urlencode(sorted_params, doseq=True)
            except Exception:
                normalized_query = query_params
        else:
            normalized_query = ""
        
        relevant_headers = {}
        if headers:
            relevant_header_names = [
                'content-type', 'accept', 'accept-language',
                'user-agent', 'x-api-version', 'x-client-version'
            ]
            for header_name in relevant_header_names:
                header_value = headers.get(header_name) or headers.get(header_name.lower())
                if header_value:
                    relevant_headers[header_name] = header_value
        
        hash_components = [
            normalized_method,
            normalized_path,
            normalized_query,
            body_hash or "",
            json.dumps(relevant_headers, sort_keys=True) if relevant_headers else ""
        ]
        
        hash_string = "|".join(hash_components)
        return hashlib.sha256(hash_string.encode('utf-8')).hexdigest()
    
    async def is_duplicate(self, request_hash: str) -> bool:
        """Verifica se a request já foi processada"""
        self._cleanup_expired()
        return request_hash in self.cache
    
    async def mark_as_processed(
        self,
        request_hash: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Marca uma request como processada"""
        self.cache[request_hash] = {
            'processed_at': datetime.utcnow(),
            'hash': request_hash,
            'metadata': metadata or {}
        }
        return True
    
    async def get_processed_info(self, request_hash: str) -> Optional[Dict[str, Any]]:
        """Obtém informações sobre uma request processada"""
        self._cleanup_expired()
        entry = self.cache.get(request_hash)
        if entry:
            # Converter datetime para string para compatibilidade
            entry_copy = entry.copy()
            entry_copy['processed_at'] = entry['processed_at'].isoformat()
            return entry_copy
        return None
    
    def _cleanup_expired(self):
        """Remove entradas expiradas"""
        now = datetime.utcnow()
        expired_keys = []
        
        for key, entry in self.cache.items():
            if now - entry['processed_at'] > timedelta(seconds=self.ttl):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
    
    async def cleanup_expired(self) -> int:
        """Remove entradas expiradas"""
        initial_count = len(self.cache)
        self._cleanup_expired()
        return initial_count - len(self.cache)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas de deduplicação"""
        self._cleanup_expired()
        
        now = datetime.utcnow()
        age_buckets = {
            'last_hour': 0,
            'last_day': 0,
            'older': 0
        }
        
        for entry in self.cache.values():
            age = now - entry['processed_at']
            if age < timedelta(hours=1):
                age_buckets['last_hour'] += 1
            elif age < timedelta(days=1):
                age_buckets['last_day'] += 1
            else:
                age_buckets['older'] += 1
        
        return {
            'total_entries': len(self.cache),
            'age_distribution': age_buckets,
            'ttl_seconds': self.ttl
        }