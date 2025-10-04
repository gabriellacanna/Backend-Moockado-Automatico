"""
Aplicação principal do Collector Service
Coordena todos os componentes: gRPC, HTTP API, processamento e monitoramento
"""
import asyncio
import signal
import sys
from typing import Optional
import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import aioredis

from .config import config_manager
from .sanitizer import create_sanitizer
from .deduplicator import RequestDeduplicator, InMemoryDeduplicator
from .grpc_service import GrpcServer
from .processor import RequestProcessor, BatchProcessor
from .metrics import MetricsCollector

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
REQUESTS_RECEIVED = Counter('collector_requests_received_total', 'Total requests received from Envoy')
REQUESTS_PROCESSED = Counter('collector_requests_processed_total', 'Total requests processed successfully')
REQUESTS_DUPLICATED = Counter('collector_requests_duplicated_total', 'Total duplicate requests ignored')
REQUESTS_ERRORS = Counter('collector_requests_errors_total', 'Total request processing errors')
PROCESSING_TIME = Histogram('collector_processing_seconds', 'Time spent processing requests')
QUEUE_SIZE = Gauge('collector_queue_size', 'Current size of processing queue')


class CollectorApp:
    """Aplicação principal do Collector"""
    
    def __init__(self):
        self.config = config_manager
        self.app = FastAPI(
            title="Backend Mockado Automático - Collector",
            description="Serviço de coleta e processamento de tráfego para geração automática de mocks",
            version="1.0.0"
        )
        
        # Componentes principais
        self.redis_client: Optional[aioredis.Redis] = None
        self.sanitizer = None
        self.deduplicator = None
        self.processor = None
        self.batch_processor = None
        self.grpc_server = None
        self.metrics_collector = None
        
        # Filas de processamento
        self.input_queue = asyncio.Queue(maxsize=1000)
        self.output_queue = asyncio.Queue(maxsize=1000)
        
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
                "grpc_server": False,
                "processor": False
            }
            
            # Verificar Redis
            if self.redis_client:
                try:
                    await self.redis_client.ping()
                    checks["redis"] = True
                except Exception:
                    pass
            
            # Verificar gRPC server
            if self.grpc_server:
                checks["grpc_server"] = True
            
            # Verificar processor
            if self.processor:
                checks["processor"] = True
            
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
                "collector": {
                    "queue_sizes": {
                        "input": self.input_queue.qsize(),
                        "output": self.output_queue.qsize()
                    }
                }
            }
            
            if self.grpc_server:
                stats["grpc"] = self.grpc_server.get_stats()
            
            if self.processor:
                stats["processor"] = self.processor.get_stats()
            
            if self.deduplicator:
                stats["deduplicator"] = await self.deduplicator.get_stats()
            
            if self.metrics_collector:
                stats["metrics"] = self.metrics_collector.get_stats()
            
            return stats
        
        @self.app.post("/debug/inject")
        async def inject_test_event(event_data: dict, background_tasks: BackgroundTasks):
            """Endpoint para injetar eventos de teste (apenas desenvolvimento)"""
            if not self.config.settings.log_level == "DEBUG":
                raise HTTPException(status_code=403, detail="Debug endpoint disabled")
            
            try:
                await self.input_queue.put(event_data)
                return {"status": "injected", "queue_size": self.input_queue.qsize()}
            except asyncio.QueueFull:
                raise HTTPException(status_code=503, detail="Queue is full")
        
        @self.app.delete("/debug/clear-cache")
        async def clear_dedup_cache():
            """Endpoint para limpar cache de deduplicação (apenas desenvolvimento)"""
            if not self.config.settings.log_level == "DEBUG":
                raise HTTPException(status_code=403, detail="Debug endpoint disabled")
            
            if self.deduplicator:
                cleared = await self.deduplicator.cleanup_expired()
                return {"status": "cleared", "entries_removed": cleared}
            
            return {"status": "no_deduplicator"}
    
    async def initialize(self):
        """Inicializa todos os componentes"""
        logger.info("Inicializando Collector Service")
        
        try:
            # Inicializar Redis
            await self._init_redis()
            
            # Inicializar sanitizador
            self.sanitizer = create_sanitizer(
                self.config.settings.sensitive_headers,
                self.config.settings.sensitive_fields
            )
            logger.info("Sanitizador inicializado")
            
            # Inicializar deduplicador
            if self.redis_client:
                self.deduplicator = RequestDeduplicator(
                    self.redis_client,
                    self.config.settings.dedup_ttl
                )
            else:
                self.deduplicator = InMemoryDeduplicator(self.config.settings.dedup_ttl)
                logger.warning("Usando deduplicador em memória (não recomendado para produção)")
            
            logger.info("Deduplicador inicializado")
            
            # Inicializar processador
            self.processor = RequestProcessor(
                self.sanitizer,
                self.deduplicator,
                self.config,
                self.output_queue
            )
            
            self.batch_processor = BatchProcessor(
                self.processor,
                self.config.settings.batch_size,
                self.config.settings.batch_timeout
            )
            
            logger.info("Processador inicializado")
            
            # Inicializar servidor gRPC
            self.grpc_server = GrpcServer(
                self.config.settings.grpc_port,
                self.input_queue,
                self.config
            )
            
            # Usar mock em desenvolvimento se não houver protobuf
            use_mock = self.config.settings.log_level == "DEBUG"
            await self.grpc_server.start(use_mock=use_mock)
            
            logger.info("Servidor gRPC inicializado")
            
            # Inicializar coletor de métricas
            if self.config.settings.enable_metrics:
                self.metrics_collector = MetricsCollector()
                logger.info("Coletor de métricas inicializado")
            
            # Iniciar tasks de background
            await self._start_background_tasks()
            
            logger.info("Collector Service inicializado com sucesso")
            
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
            logger.warning("Erro ao conectar com Redis, continuando sem cache", error=str(e))
            self.redis_client = None
    
    async def _start_background_tasks(self):
        """Inicia tasks de background"""
        
        # Task de processamento de input
        input_task = asyncio.create_task(self._process_input_queue())
        self.background_tasks.append(input_task)
        
        # Task de processamento de output
        output_task = asyncio.create_task(self._process_output_queue())
        self.background_tasks.append(output_task)
        
        # Task de limpeza periódica
        cleanup_task = asyncio.create_task(self._periodic_cleanup())
        self.background_tasks.append(cleanup_task)
        
        # Task de métricas
        if self.metrics_collector:
            metrics_task = asyncio.create_task(self._update_metrics())
            self.background_tasks.append(metrics_task)
        
        logger.info("Tasks de background iniciadas", count=len(self.background_tasks))
    
    async def _process_input_queue(self):
        """Processa eventos da fila de input"""
        logger.info("Iniciando processamento da fila de input")
        
        while not self.shutdown_event.is_set():
            try:
                # Aguardar evento com timeout
                event = await asyncio.wait_for(
                    self.input_queue.get(),
                    timeout=1.0
                )
                
                REQUESTS_RECEIVED.inc()
                QUEUE_SIZE.set(self.input_queue.qsize())
                
                # Processar com batch processor
                with PROCESSING_TIME.time():
                    results = await self.batch_processor.add_event(event)
                
                # Atualizar métricas
                for result in results:
                    if result:
                        REQUESTS_PROCESSED.inc()
                
                self.input_queue.task_done()
                
            except asyncio.TimeoutError:
                # Timeout normal, continuar
                continue
            except Exception as e:
                logger.error("Erro no processamento de input", error=str(e))
                REQUESTS_ERRORS.inc()
    
    async def _process_output_queue(self):
        """Processa eventos da fila de output"""
        logger.info("Iniciando processamento da fila de output")
        
        while not self.shutdown_event.is_set():
            try:
                # Aguardar evento com timeout
                event = await asyncio.wait_for(
                    self.output_queue.get(),
                    timeout=1.0
                )
                
                # Processar evento de output (enviar para WireMock, etc.)
                await self._handle_output_event(event)
                
                self.output_queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("Erro no processamento de output", error=str(e))
    
    async def _handle_output_event(self, event: dict):
        """Processa evento de output"""
        event_type = event.get('type')
        
        if event_type == 'wiremock_mapping':
            # Enviar mapping para WireMock (implementado no wiremock-loader)
            logger.debug("Mapping WireMock gerado", mapping_id=event.get('mapping', {}).get('id', 'unknown'))
        else:
            logger.warning("Tipo de evento de output desconhecido", type=event_type)
    
    async def _periodic_cleanup(self):
        """Executa limpeza periódica"""
        logger.info("Iniciando task de limpeza periódica")
        
        while not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(300)  # 5 minutos
                
                if self.deduplicator:
                    cleaned = await self.deduplicator.cleanup_expired()
                    if cleaned > 0:
                        logger.info("Limpeza periódica executada", entries_removed=cleaned)
                
            except Exception as e:
                logger.error("Erro na limpeza periódica", error=str(e))
    
    async def _update_metrics(self):
        """Atualiza métricas periodicamente"""
        while not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(30)  # 30 segundos
                
                # Atualizar métricas de fila
                QUEUE_SIZE.set(self.input_queue.qsize())
                
                # Outras métricas podem ser adicionadas aqui
                
            except Exception as e:
                logger.error("Erro na atualização de métricas", error=str(e))
    
    async def shutdown(self):
        """Shutdown graceful da aplicação"""
        logger.info("Iniciando shutdown do Collector Service")
        
        # Sinalizar shutdown
        self.shutdown_event.set()
        
        # Parar servidor gRPC
        if self.grpc_server:
            await self.grpc_server.stop()
        
        # Aguardar tasks de background
        if self.background_tasks:
            logger.info("Aguardando finalização das tasks de background")
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
        
        # Processar filas restantes
        await self._drain_queues()
        
        # Fechar conexão Redis
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("Collector Service finalizado")
    
    async def _drain_queues(self):
        """Processa eventos restantes nas filas"""
        logger.info("Processando eventos restantes nas filas")
        
        # Processar input queue restante
        while not self.input_queue.empty():
            try:
                event = self.input_queue.get_nowait()
                await self.batch_processor.add_event(event)
                self.input_queue.task_done()
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                logger.error("Erro ao processar evento restante", error=str(e))
        
        # Flush batch final
        if self.batch_processor:
            await self.batch_processor.flush_batch()


# Instância global da aplicação
collector_app = CollectorApp()


async def main():
    """Função principal"""
    
    # Configurar handlers de sinal
    def signal_handler(signum, frame):
        logger.info("Sinal recebido, iniciando shutdown", signal=signum)
        asyncio.create_task(collector_app.shutdown())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Inicializar aplicação
        await collector_app.initialize()
        
        # Iniciar servidor HTTP
        config = uvicorn.Config(
            collector_app.app,
            host=collector_app.config.settings.host,
            port=collector_app.config.settings.port,
            log_level=collector_app.config.settings.log_level.lower(),
            access_log=True
        )
        
        server = uvicorn.Server(config)
        
        logger.info(
            "Iniciando servidor HTTP",
            host=collector_app.config.settings.host,
            port=collector_app.config.settings.port
        )
        
        await server.serve()
        
    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuário")
    except Exception as e:
        logger.error("Erro crítico na aplicação", error=str(e))
        sys.exit(1)
    finally:
        await collector_app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())