"""
Aplicação principal do WireMock Loader Service
Consome mappings da fila e os registra no WireMock
"""
import asyncio
import signal
import sys
from typing import Optional
import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import aioredis

from .config import config_manager
from .wiremock_client import WireMockClient, BatchWireMockClient
from .queue_consumer import RedisQueueConsumer, MockQueueConsumer
from .backup_manager import BackupManager

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

logger = structlog.get_logger(__name__)

# Métricas Prometheus
MAPPINGS_PROCESSED = Counter('wiremock_loader_mappings_processed_total', 'Total mappings processed')
MAPPINGS_FAILED = Counter('wiremock_loader_mappings_failed_total', 'Total mappings failed')
WIREMOCK_REQUESTS = Counter('wiremock_loader_wiremock_requests_total', 'Total requests to WireMock', ['operation'])
PROCESSING_TIME = Histogram('wiremock_loader_processing_seconds', 'Time spent processing mappings')
QUEUE_SIZE = Gauge('wiremock_loader_queue_size', 'Current size of processing queue')
WIREMOCK_HEALTH = Gauge('wiremock_loader_wiremock_health', 'WireMock health status (1=healthy, 0=unhealthy)')


class WireMockLoaderApp:
    """Aplicação principal do WireMock Loader"""
    
    def __init__(self):
        self.config = config_manager
        self.app = FastAPI(
            title="Backend Mockado Automático - WireMock Loader",
            description="Serviço de carregamento de mappings para WireMock",
            version="1.0.0"
        )
        
        # Componentes principais
        self.redis_client: Optional[aioredis.Redis] = None
        self.wiremock_client: Optional[WireMockClient] = None
        self.backup_manager: Optional[BackupManager] = None
        self.queue_consumer = None
        
        # Tasks de background
        self.background_tasks = []
        self.shutdown_event = asyncio.Event()
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Configura rotas da API HTTP"""
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {
                "status": "healthy",
                "timestamp": structlog.get_logger().info("Health check"),
                "version": "1.0.0"
            }
        
        @self.app.get("/ready")
        async def readiness_check():
            """Readiness check endpoint"""
            checks = {
                "redis": False,
                "wiremock": False,
                "queue_consumer": False
            }
            
            # Verificar Redis
            if self.redis_client:
                try:
                    await self.redis_client.ping()
                    checks["redis"] = True
                except Exception:
                    pass
            
            # Verificar WireMock
            if self.wiremock_client:
                checks["wiremock"] = await self.wiremock_client.health_check()
                WIREMOCK_HEALTH.set(1 if checks["wiremock"] else 0)
            
            # Verificar queue consumer
            if self.queue_consumer:
                checks["queue_consumer"] = getattr(self.queue_consumer, 'running', False)
            
            all_ready = all(checks.values())
            status_code = 200 if all_ready else 503
            
            return JSONResponse(
                status_code=status_code,
                content={
                    "ready": all_ready,
                    "checks": checks
                }
            )
        
        @self.app.get("/metrics")
        async def metrics():
            """Endpoint de métricas Prometheus"""
            return generate_latest()
        
        @self.app.get("/stats")
        async def get_stats():
            """Endpoint de estatísticas detalhadas"""
            stats = {
                "loader": {
                    "config": {
                        "wiremock_url": self.config.settings.wiremock_url,
                        "batch_size": self.config.settings.batch_size,
                        "backup_enabled": self.config.settings.backup_mappings
                    }
                }
            }
            
            if self.wiremock_client:
                stats["wiremock"] = self.wiremock_client.get_stats()
            
            if self.queue_consumer:
                stats["queue_consumer"] = self.queue_consumer.get_stats()
            
            if self.backup_manager:
                stats["backup"] = self.backup_manager.get_stats()
                stats["backup_summary"] = await self.backup_manager.get_backup_summary()
            
            return stats
        
        @self.app.post("/mappings")
        async def create_mapping_direct(mapping: dict, background_tasks: BackgroundTasks):
            """Endpoint para criar mapping diretamente (bypass da fila)"""
            if not self.wiremock_client:
                raise HTTPException(status_code=503, detail="WireMock client not available")
            
            # Validar mapping
            is_valid, errors = self.config.validate_mapping(mapping)
            if not is_valid:
                raise HTTPException(status_code=400, detail={"errors": errors})
            
            # Criar mapping
            success, error = await self.wiremock_client.create_mapping(mapping)
            
            if success:
                MAPPINGS_PROCESSED.inc()
                WIREMOCK_REQUESTS.labels(operation='create').inc()
                
                # Fazer backup se configurado
                if self.backup_manager:
                    background_tasks.add_task(self.backup_manager.backup_mapping, mapping)
                
                return {"status": "created", "mapping_id": mapping.get('id')}
            else:
                MAPPINGS_FAILED.inc()
                raise HTTPException(status_code=500, detail={"error": error})
        
        @self.app.get("/mappings")
        async def list_mappings(limit: int = 100, offset: int = 0):
            """Lista mappings do WireMock"""
            if not self.wiremock_client:
                raise HTTPException(status_code=503, detail="WireMock client not available")
            
            success, mappings, error = await self.wiremock_client.list_mappings(limit, offset)
            
            if success:
                WIREMOCK_REQUESTS.labels(operation='list').inc()
                return {"mappings": mappings, "count": len(mappings)}
            else:
                raise HTTPException(status_code=500, detail={"error": error})
        
        @self.app.get("/mappings/{mapping_id}")
        async def get_mapping(mapping_id: str):
            """Obtém mapping específico"""
            if not self.wiremock_client:
                raise HTTPException(status_code=503, detail="WireMock client not available")
            
            success, mapping, error = await self.wiremock_client.get_mapping(mapping_id)
            
            if success:
                WIREMOCK_REQUESTS.labels(operation='get').inc()
                return mapping
            elif error == "Mapping não encontrado":
                raise HTTPException(status_code=404, detail={"error": error})
            else:
                raise HTTPException(status_code=500, detail={"error": error})
        
        @self.app.delete("/mappings/{mapping_id}")
        async def delete_mapping(mapping_id: str):
            """Remove mapping específico"""
            if not self.wiremock_client:
                raise HTTPException(status_code=503, detail="WireMock client not available")
            
            success, error = await self.wiremock_client.delete_mapping(mapping_id)
            
            if success:
                WIREMOCK_REQUESTS.labels(operation='delete').inc()
                return {"status": "deleted", "mapping_id": mapping_id}
            else:
                raise HTTPException(status_code=500, detail={"error": error})
        
        @self.app.get("/backups")
        async def list_backups(mapping_id: str = None, days: int = 7):
            """Lista backups disponíveis"""
            if not self.backup_manager:
                raise HTTPException(status_code=503, detail="Backup manager not available")
            
            backups = await self.backup_manager.list_backups(mapping_id, days)
            return {"backups": backups, "count": len(backups)}
        
        @self.app.post("/backups/{backup_file}/restore")
        async def restore_backup(backup_file: str, background_tasks: BackgroundTasks):
            """Restaura mapping de backup"""
            if not self.backup_manager or not self.wiremock_client:
                raise HTTPException(status_code=503, detail="Services not available")
            
            # Restaurar mappings do backup
            mappings = await self.backup_manager.restore_batch(backup_file)
            
            if not mappings:
                raise HTTPException(status_code=404, detail="Backup not found or empty")
            
            # Criar mappings no WireMock
            created_count = 0
            failed_count = 0
            
            for mapping in mappings:
                success, error = await self.wiremock_client.create_mapping(mapping)
                if success:
                    created_count += 1
                    MAPPINGS_PROCESSED.inc()
                else:
                    failed_count += 1
                    MAPPINGS_FAILED.inc()
                    logger.error("Erro ao restaurar mapping", 
                               mapping_id=mapping.get('id'), error=error)
            
            return {
                "status": "restored",
                "created_count": created_count,
                "failed_count": failed_count,
                "total_mappings": len(mappings)
            }
        
        @self.app.delete("/backups/cleanup")
        async def cleanup_backups():
            """Executa limpeza de backups antigos"""
            if not self.backup_manager:
                raise HTTPException(status_code=503, detail="Backup manager not available")
            
            removed_count = await self.backup_manager.cleanup_old_backups()
            return {"status": "cleaned", "removed_count": removed_count}
        
        @self.app.get("/wiremock/requests")
        async def get_wiremock_requests(limit: int = 100):
            """Obtém requests recebidas pelo WireMock"""
            if not self.wiremock_client:
                raise HTTPException(status_code=503, detail="WireMock client not available")
            
            success, requests, error = await self.wiremock_client.get_requests(limit)
            
            if success:
                return {"requests": requests, "count": len(requests)}
            else:
                raise HTTPException(status_code=500, detail={"error": error})
        
        @self.app.get("/wiremock/requests/unmatched")
        async def get_unmatched_requests():
            """Obtém requests não atendidas por mappings"""
            if not self.wiremock_client:
                raise HTTPException(status_code=503, detail="WireMock client not available")
            
            success, unmatched, error = await self.wiremock_client.find_unmatched_requests()
            
            if success:
                return {"unmatched_requests": unmatched, "count": len(unmatched)}
            else:
                raise HTTPException(status_code=500, detail={"error": error})
    
    async def initialize(self):
        """Inicializa todos os componentes"""
        logger.info("Inicializando WireMock Loader Service")
        
        try:
            # Inicializar Redis
            await self._init_redis()
            
            # Inicializar WireMock client
            self.wiremock_client = WireMockClient(
                base_url=self.config.settings.wiremock_url,
                timeout=self.config.settings.wiremock_timeout,
                max_retries=self.config.settings.wiremock_retry_attempts
            )
            
            # Verificar conectividade com WireMock
            wiremock_healthy = await self.wiremock_client.health_check()
            if wiremock_healthy:
                logger.info("Conexão com WireMock estabelecida")
                WIREMOCK_HEALTH.set(1)
            else:
                logger.warning("WireMock não está disponível, continuando mesmo assim")
                WIREMOCK_HEALTH.set(0)
            
            # Inicializar backup manager
            if self.config.settings.backup_mappings:
                self.backup_manager = BackupManager(
                    backup_path=self.config.settings.backup_path,
                    retention_days=self.config.settings.backup_retention_days,
                    compress_backups=True
                )
                logger.info("Backup manager inicializado")
            
            # Inicializar queue consumer
            if self.redis_client:
                self.queue_consumer = RedisQueueConsumer(
                    redis_client=self.redis_client,
                    wiremock_client=self.wiremock_client,
                    backup_manager=self.backup_manager,
                    queue_name=self.config.settings.queue_name,
                    consumer_group=self.config.settings.queue_consumer_group,
                    batch_size=self.config.settings.batch_size,
                    max_retries=self.config.settings.queue_max_retries
                )
            else:
                # Usar mock consumer para desenvolvimento
                self.queue_consumer = MockQueueConsumer(self.wiremock_client)
                logger.warning("Usando mock queue consumer (desenvolvimento)")
            
            await self.queue_consumer.initialize()
            logger.info("Queue consumer inicializado")
            
            # Iniciar tasks de background
            await self._start_background_tasks()
            
            logger.info("WireMock Loader Service inicializado com sucesso")
            
        except Exception as e:
            logger.error("Erro na inicialização", error=str(e))
            raise
    
    async def _init_redis(self):
        """Inicializa conexão com Redis"""
        try:
            self.redis_client = aioredis.from_url(
                self.config.settings.redis_url,
                db=self.config.settings.redis_db,
                password=self.config.settings.redis_password,
                decode_responses=True
            )
            
            # Testar conexão
            await self.redis_client.ping()
            logger.info("Conexão com Redis estabelecida")
            
        except Exception as e:
            logger.warning("Erro ao conectar com Redis, usando mock consumer", error=str(e))
            self.redis_client = None
    
    async def _start_background_tasks(self):
        """Inicia tasks de background"""
        
        # Task do queue consumer
        consumer_task = asyncio.create_task(self.queue_consumer.start())
        self.background_tasks.append(consumer_task)
        
        # Task de limpeza periódica de backups
        if self.backup_manager:
            cleanup_task = asyncio.create_task(self._periodic_backup_cleanup())
            self.background_tasks.append(cleanup_task)
        
        # Task de monitoramento de saúde do WireMock
        health_task = asyncio.create_task(self._monitor_wiremock_health())
        self.background_tasks.append(health_task)
        
        logger.info("Tasks de background iniciadas", count=len(self.background_tasks))
    
    async def _periodic_backup_cleanup(self):
        """Executa limpeza periódica de backups"""
        logger.info("Iniciando task de limpeza periódica de backups")
        
        while not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(3600)  # 1 hora
                
                if self.backup_manager:
                    removed = await self.backup_manager.cleanup_old_backups()
                    if removed > 0:
                        logger.info("Limpeza periódica de backups executada", removed_count=removed)
                
            except Exception as e:
                logger.error("Erro na limpeza periódica de backups", error=str(e))
    
    async def _monitor_wiremock_health(self):
        """Monitora saúde do WireMock periodicamente"""
        while not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(30)  # 30 segundos
                
                if self.wiremock_client:
                    healthy = await self.wiremock_client.health_check()
                    WIREMOCK_HEALTH.set(1 if healthy else 0)
                
            except Exception as e:
                logger.error("Erro no monitoramento de saúde do WireMock", error=str(e))
                WIREMOCK_HEALTH.set(0)
    
    async def shutdown(self):
        """Shutdown graceful da aplicação"""
        logger.info("Iniciando shutdown do WireMock Loader Service")
        
        # Sinalizar shutdown
        self.shutdown_event.set()
        
        # Parar queue consumer
        if self.queue_consumer:
            await self.queue_consumer.stop()
        
        # Aguardar tasks de background
        if self.background_tasks:
            logger.info("Aguardando finalização das tasks de background")
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
        
        # Fechar clientes
        if self.wiremock_client:
            await self.wiremock_client.close()
        
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("WireMock Loader Service finalizado")


# Instância global da aplicação
loader_app = WireMockLoaderApp()


async def main():
    """Função principal"""
    
    # Configurar handlers de sinal
    def signal_handler(signum, frame):
        logger.info("Sinal recebido, iniciando shutdown", signal=signum)
        asyncio.create_task(loader_app.shutdown())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Inicializar aplicação
        await loader_app.initialize()
        
        # Iniciar servidor HTTP
        config = uvicorn.Config(
            loader_app.app,
            host=loader_app.config.settings.host,
            port=loader_app.config.settings.port,
            log_level=loader_app.config.settings.log_level.lower(),
            access_log=True
        )
        
        server = uvicorn.Server(config)
        
        logger.info(
            "Iniciando servidor HTTP",
            host=loader_app.config.settings.host,
            port=loader_app.config.settings.port
        )
        
        await server.serve()
        
    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuário")
    except Exception as e:
        logger.error("Erro crítico na aplicação", error=str(e))
        sys.exit(1)
    finally:
        await loader_app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())