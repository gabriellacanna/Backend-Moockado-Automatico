"""
Consumidor de fila para processamento de mappings WireMock
Consome mensagens do Redis/Kafka e processa mappings
"""
import asyncio
import json
from typing import Dict, Any, Optional, List
import aioredis
import structlog
from datetime import datetime, timedelta

from .wiremock_client import WireMockClient, BatchWireMockClient
from .backup_manager import BackupManager

logger = structlog.get_logger(__name__)


class RedisQueueConsumer:
    """Consumidor de fila Redis para mappings WireMock"""
    
    def __init__(
        self,
        redis_client: aioredis.Redis,
        wiremock_client: WireMockClient,
        backup_manager: Optional[BackupManager] = None,
        queue_name: str = "wiremock_mappings",
        consumer_group: str = "wiremock_loader",
        consumer_name: str = "loader-1",
        batch_size: int = 5,
        max_retries: int = 3
    ):
        self.redis = redis_client
        self.wiremock_client = wiremock_client
        self.backup_manager = backup_manager
        self.queue_name = queue_name
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        self.batch_size = batch_size
        self.max_retries = max_retries
        
        # Cliente batch para processamento eficiente
        self.batch_client = BatchWireMockClient(wiremock_client, batch_size)
        
        # Controle de execução
        self.running = False
        self.shutdown_event = asyncio.Event()
        
        # Estatísticas
        self.stats = {
            'messages_processed': 0,
            'messages_failed': 0,
            'messages_retried': 0,
            'batches_processed': 0,
            'last_processed': None,
            'errors': []
        }
    
    async def initialize(self):
        """Inicializa o consumidor"""
        try:
            # Criar consumer group se não existir
            try:
                await self.redis.xgroup_create(
                    self.queue_name,
                    self.consumer_group,
                    id='0',
                    mkstream=True
                )
                logger.info("Consumer group criado", group=self.consumer_group)
            except aioredis.ResponseError as e:
                if "BUSYGROUP" in str(e):
                    logger.info("Consumer group já existe", group=self.consumer_group)
                else:
                    raise
            
            logger.info("Consumidor Redis inicializado", 
                       queue=self.queue_name, 
                       group=self.consumer_group,
                       consumer=self.consumer_name)
            
        except Exception as e:
            logger.error("Erro ao inicializar consumidor Redis", error=str(e))
            raise
    
    async def start(self):
        """Inicia o consumidor"""
        if self.running:
            logger.warning("Consumidor já está executando")
            return
        
        self.running = True
        logger.info("Iniciando consumidor de fila")
        
        try:
            # Task principal de consumo
            consume_task = asyncio.create_task(self._consume_loop())
            
            # Task de processamento de mensagens pendentes
            pending_task = asyncio.create_task(self._process_pending_messages())
            
            # Task de limpeza periódica
            cleanup_task = asyncio.create_task(self._periodic_cleanup())
            
            # Aguardar até shutdown
            await asyncio.gather(consume_task, pending_task, cleanup_task)
            
        except Exception as e:
            logger.error("Erro no consumidor", error=str(e))
        finally:
            self.running = False
    
    async def stop(self):
        """Para o consumidor gracefully"""
        logger.info("Parando consumidor de fila")
        self.running = False
        self.shutdown_event.set()
        
        # Processar batch pendente
        await self.batch_client.flush_batch()
    
    async def _consume_loop(self):
        """Loop principal de consumo"""
        while self.running and not self.shutdown_event.is_set():
            try:
                # Ler mensagens da fila
                messages = await self.redis.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {self.queue_name: '>'},
                    count=self.batch_size,
                    block=1000  # 1 segundo de timeout
                )
                
                if messages:
                    await self._process_messages(messages)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Erro no loop de consumo", error=str(e))
                self._add_error(str(e))
                await asyncio.sleep(1)  # Evitar loop infinito de erros
    
    async def _process_messages(self, messages):
        """Processa mensagens recebidas"""
        for stream_name, stream_messages in messages:
            for message_id, fields in stream_messages:
                try:
                    await self._process_single_message(message_id, fields)
                except Exception as e:
                    logger.error("Erro ao processar mensagem", 
                               message_id=message_id, error=str(e))
                    self._add_error(f"Message {message_id}: {str(e)}")
    
    async def _process_single_message(self, message_id: str, fields: Dict[str, Any]):
        """Processa uma única mensagem"""
        try:
            # Extrair dados da mensagem
            mapping_data = fields.get('mapping')
            if not mapping_data:
                logger.warning("Mensagem sem dados de mapping", message_id=message_id)
                await self._ack_message(message_id)
                return
            
            # Parsear JSON se necessário
            if isinstance(mapping_data, (str, bytes)):
                mapping = json.loads(mapping_data)
            else:
                mapping = mapping_data
            
            # Fazer backup se configurado
            if self.backup_manager:
                await self.backup_manager.backup_mapping(mapping)
            
            # Adicionar ao batch para processamento
            success = await self.batch_client.add_mapping(mapping)
            
            if success:
                # Confirmar processamento da mensagem
                await self._ack_message(message_id)
                self.stats['messages_processed'] += 1
                self.stats['last_processed'] = datetime.utcnow().isoformat()
                
                logger.debug("Mensagem processada com sucesso", 
                           message_id=message_id, 
                           mapping_id=mapping.get('id', 'unknown'))
            else:
                # Tentar novamente ou mover para DLQ
                await self._handle_failed_message(message_id, fields, "Erro no processamento em batch")
                
        except json.JSONDecodeError as e:
            logger.error("Erro ao parsear JSON da mensagem", 
                        message_id=message_id, error=str(e))
            await self._handle_failed_message(message_id, fields, f"JSON inválido: {str(e)}")
            
        except Exception as e:
            logger.error("Erro inesperado ao processar mensagem", 
                        message_id=message_id, error=str(e))
            await self._handle_failed_message(message_id, fields, f"Erro inesperado: {str(e)}")
    
    async def _ack_message(self, message_id: str):
        """Confirma processamento da mensagem"""
        try:
            await self.redis.xack(self.queue_name, self.consumer_group, message_id)
        except Exception as e:
            logger.error("Erro ao confirmar mensagem", message_id=message_id, error=str(e))
    
    async def _handle_failed_message(self, message_id: str, fields: Dict[str, Any], error: str):
        """Trata mensagem que falhou no processamento"""
        try:
            # Obter contador de tentativas
            retry_count = int(fields.get('retry_count', 0))
            
            if retry_count < self.max_retries:
                # Incrementar contador e reenviar
                fields['retry_count'] = str(retry_count + 1)
                fields['last_error'] = error
                fields['retry_timestamp'] = datetime.utcnow().isoformat()
                
                # Reenviar para a fila com delay
                delay_seconds = min(2 ** retry_count, 60)  # Backoff exponencial
                await asyncio.sleep(delay_seconds)
                
                await self.redis.xadd(self.queue_name, fields)
                await self._ack_message(message_id)  # Ack da mensagem original
                
                self.stats['messages_retried'] += 1
                logger.info("Mensagem reenviada para retry", 
                          message_id=message_id, 
                          retry_count=retry_count + 1,
                          delay=delay_seconds)
            else:
                # Máximo de tentativas atingido, mover para DLQ
                await self._move_to_dlq(message_id, fields, error)
                await self._ack_message(message_id)
                
                self.stats['messages_failed'] += 1
                logger.error("Mensagem movida para DLQ após esgotar tentativas", 
                           message_id=message_id, 
                           retry_count=retry_count,
                           error=error)
                
        except Exception as e:
            logger.error("Erro ao tratar mensagem falhada", 
                        message_id=message_id, error=str(e))
    
    async def _move_to_dlq(self, message_id: str, fields: Dict[str, Any], error: str):
        """Move mensagem para Dead Letter Queue"""
        try:
            dlq_name = f"{self.queue_name}:dlq"
            dlq_fields = {
                **fields,
                'original_message_id': message_id,
                'final_error': error,
                'dlq_timestamp': datetime.utcnow().isoformat()
            }
            
            await self.redis.xadd(dlq_name, dlq_fields)
            logger.info("Mensagem movida para DLQ", 
                       message_id=message_id, 
                       dlq=dlq_name)
            
        except Exception as e:
            logger.error("Erro ao mover mensagem para DLQ", 
                        message_id=message_id, error=str(e))
    
    async def _process_pending_messages(self):
        """Processa mensagens pendentes (que não foram confirmadas)"""
        while self.running and not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(30)  # Verificar a cada 30 segundos
                
                # Buscar mensagens pendentes
                pending = await self.redis.xpending_range(
                    self.queue_name,
                    self.consumer_group,
                    min='-',
                    max='+',
                    count=10
                )
                
                if pending:
                    logger.info("Processando mensagens pendentes", count=len(pending))
                    
                    for message_info in pending:
                        message_id = message_info['message_id']
                        idle_time = message_info['time_since_delivered']
                        
                        # Se a mensagem está pendente há mais de 5 minutos, reprocessar
                        if idle_time > 300000:  # 5 minutos em millisegundos
                            await self._claim_and_process_message(message_id)
                
            except Exception as e:
                logger.error("Erro ao processar mensagens pendentes", error=str(e))
    
    async def _claim_and_process_message(self, message_id: str):
        """Reivindica e processa uma mensagem pendente"""
        try:
            # Reivindicar a mensagem
            claimed = await self.redis.xclaim(
                self.queue_name,
                self.consumer_group,
                self.consumer_name,
                min_idle_time=300000,  # 5 minutos
                message_ids=[message_id]
            )
            
            if claimed:
                for stream_name, messages in claimed:
                    for msg_id, fields in messages:
                        await self._process_single_message(msg_id, fields)
                        
        except Exception as e:
            logger.error("Erro ao reivindicar mensagem pendente", 
                        message_id=message_id, error=str(e))
    
    async def _periodic_cleanup(self):
        """Limpeza periódica de mensagens antigas"""
        while self.running and not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(3600)  # 1 hora
                
                # Remover mensagens processadas antigas (mais de 24 horas)
                cutoff_time = int((datetime.utcnow() - timedelta(hours=24)).timestamp() * 1000)
                
                deleted = await self.redis.xtrim(
                    self.queue_name,
                    minid=cutoff_time,
                    approximate=True
                )
                
                if deleted > 0:
                    logger.info("Limpeza periódica executada", messages_deleted=deleted)
                
            except Exception as e:
                logger.error("Erro na limpeza periódica", error=str(e))
    
    def _add_error(self, error: str):
        """Adiciona erro à lista de erros recentes"""
        self.stats['errors'].append({
            'error': error,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Manter apenas os últimos 100 erros
        if len(self.stats['errors']) > 100:
            self.stats['errors'] = self.stats['errors'][-100:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do consumidor"""
        return {
            **self.stats,
            'running': self.running,
            'queue_name': self.queue_name,
            'consumer_group': self.consumer_group,
            'consumer_name': self.consumer_name,
            'batch_size': self.batch_size,
            'max_retries': self.max_retries,
            'batch_client_stats': self.batch_client.get_stats()
        }


class MockQueueConsumer:
    """Consumidor mock para desenvolvimento e testes"""
    
    def __init__(self, wiremock_client: WireMockClient):
        self.wiremock_client = wiremock_client
        self.running = False
        self.stats = {
            'messages_processed': 0,
            'messages_failed': 0
        }
    
    async def initialize(self):
        """Inicialização mock"""
        logger.info("Mock queue consumer inicializado")
    
    async def start(self):
        """Inicia consumidor mock"""
        self.running = True
        logger.info("Mock queue consumer iniciado")
        
        # Simular processamento de algumas mensagens de teste
        test_mappings = [
            {
                'id': 'test-mapping-1',
                'name': 'Test GET /api/test',
                'request': {
                    'method': 'GET',
                    'urlPath': '/api/test'
                },
                'response': {
                    'status': 200,
                    'jsonBody': {'message': 'Test response'},
                    'headers': {'Content-Type': 'application/json'}
                }
            },
            {
                'id': 'test-mapping-2',
                'name': 'Test POST /api/data',
                'request': {
                    'method': 'POST',
                    'urlPath': '/api/data'
                },
                'response': {
                    'status': 201,
                    'jsonBody': {'id': 123, 'status': 'created'},
                    'headers': {'Content-Type': 'application/json'}
                }
            }
        ]
        
        for mapping in test_mappings:
            if not self.running:
                break
                
            success, error = await self.wiremock_client.create_mapping(mapping)
            if success:
                self.stats['messages_processed'] += 1
                logger.info("Mapping de teste criado", mapping_id=mapping['id'])
            else:
                self.stats['messages_failed'] += 1
                logger.error("Erro ao criar mapping de teste", 
                           mapping_id=mapping['id'], error=error)
            
            await asyncio.sleep(2)  # Simular delay
    
    async def stop(self):
        """Para consumidor mock"""
        self.running = False
        logger.info("Mock queue consumer parado")
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas mock"""
        return {
            **self.stats,
            'running': self.running,
            'type': 'mock'
        }