"""
Módulo de métricas e monitoramento
Coleta métricas de performance, latência e uso de recursos
"""
import time
import psutil
import asyncio
from typing import Dict, Any, List
from datetime import datetime, timedelta
import structlog
from prometheus_client import Counter, Histogram, Gauge, Info

logger = structlog.get_logger(__name__)

# Métricas Prometheus
SYSTEM_CPU_USAGE = Gauge('collector_system_cpu_percent', 'System CPU usage percentage')
SYSTEM_MEMORY_USAGE = Gauge('collector_system_memory_percent', 'System memory usage percentage')
SYSTEM_MEMORY_BYTES = Gauge('collector_system_memory_bytes', 'System memory usage in bytes', ['type'])
NETWORK_BYTES = Counter('collector_network_bytes_total', 'Network bytes transferred', ['direction'])
PROCESS_CPU_USAGE = Gauge('collector_process_cpu_percent', 'Process CPU usage percentage')
PROCESS_MEMORY_USAGE = Gauge('collector_process_memory_bytes', 'Process memory usage in bytes')
PROCESS_THREADS = Gauge('collector_process_threads', 'Number of process threads')
PROCESS_FDS = Gauge('collector_process_file_descriptors', 'Number of open file descriptors')

# Métricas de aplicação
REQUEST_LATENCY = Histogram('collector_request_latency_seconds', 'Request processing latency')
SANITIZATION_TIME = Histogram('collector_sanitization_seconds', 'Time spent sanitizing data')
DEDUPLICATION_TIME = Histogram('collector_deduplication_seconds', 'Time spent on deduplication')
WIREMOCK_GENERATION_TIME = Histogram('collector_wiremock_generation_seconds', 'Time spent generating WireMock mappings')

# Métricas de negócio
SENSITIVE_DATA_DETECTED = Counter('collector_sensitive_data_detected_total', 'Sensitive data patterns detected', ['pattern_type'])
BODY_SIZE_DISTRIBUTION = Histogram('collector_body_size_bytes', 'Distribution of request/response body sizes')
STATUS_CODE_DISTRIBUTION = Counter('collector_status_codes_total', 'HTTP status code distribution', ['status_code'])
METHOD_DISTRIBUTION = Counter('collector_http_methods_total', 'HTTP method distribution', ['method'])
ENDPOINT_POPULARITY = Counter('collector_endpoints_total', 'Endpoint access frequency', ['method', 'path_pattern'])

# Info metrics
COLLECTOR_INFO = Info('collector_info', 'Collector service information')


class MetricsCollector:
    """Coletor de métricas do sistema e aplicação"""
    
    def __init__(self):
        self.process = psutil.Process()
        self.start_time = time.time()
        self.last_network_stats = None
        
        # Histórico de métricas para análise
        self.metrics_history: List[Dict[str, Any]] = []
        self.max_history_size = 1000
        
        # Configurar info metrics
        COLLECTOR_INFO.info({
            'version': '1.0.0',
            'python_version': f"{psutil.PYTHON_VERSION}",
            'start_time': datetime.utcnow().isoformat()
        })
    
    def collect_system_metrics(self):
        """Coleta métricas do sistema"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=None)
            SYSTEM_CPU_USAGE.set(cpu_percent)
            
            # Memória
            memory = psutil.virtual_memory()
            SYSTEM_MEMORY_USAGE.set(memory.percent)
            SYSTEM_MEMORY_BYTES.labels(type='total').set(memory.total)
            SYSTEM_MEMORY_BYTES.labels(type='available').set(memory.available)
            SYSTEM_MEMORY_BYTES.labels(type='used').set(memory.used)
            
            # Rede
            network = psutil.net_io_counters()
            if self.last_network_stats:
                bytes_sent_delta = network.bytes_sent - self.last_network_stats.bytes_sent
                bytes_recv_delta = network.bytes_recv - self.last_network_stats.bytes_recv
                
                NETWORK_BYTES.labels(direction='sent').inc(bytes_sent_delta)
                NETWORK_BYTES.labels(direction='received').inc(bytes_recv_delta)
            
            self.last_network_stats = network
            
        except Exception as e:
            logger.warning("Erro ao coletar métricas do sistema", error=str(e))
    
    def collect_process_metrics(self):
        """Coleta métricas do processo"""
        try:
            # CPU do processo
            cpu_percent = self.process.cpu_percent()
            PROCESS_CPU_USAGE.set(cpu_percent)
            
            # Memória do processo
            memory_info = self.process.memory_info()
            PROCESS_MEMORY_USAGE.set(memory_info.rss)
            
            # Threads
            num_threads = self.process.num_threads()
            PROCESS_THREADS.set(num_threads)
            
            # File descriptors (apenas em sistemas Unix)
            try:
                num_fds = self.process.num_fds()
                PROCESS_FDS.set(num_fds)
            except AttributeError:
                # Windows não suporta num_fds
                pass
            
        except Exception as e:
            logger.warning("Erro ao coletar métricas do processo", error=str(e))
    
    def record_request_metrics(self, method: str, path: str, status_code: int, 
                             processing_time: float, body_size: int = 0):
        """Registra métricas de uma request processada"""
        try:
            # Latência
            REQUEST_LATENCY.observe(processing_time)
            
            # Status code
            STATUS_CODE_DISTRIBUTION.labels(status_code=str(status_code)).inc()
            
            # Método HTTP
            METHOD_DISTRIBUTION.labels(method=method.upper()).inc()
            
            # Tamanho do body
            if body_size > 0:
                BODY_SIZE_DISTRIBUTION.observe(body_size)
            
            # Popularidade do endpoint (generalizar path para evitar cardinalidade alta)
            path_pattern = self._generalize_path(path)
            ENDPOINT_POPULARITY.labels(method=method.upper(), path_pattern=path_pattern).inc()
            
        except Exception as e:
            logger.warning("Erro ao registrar métricas da request", error=str(e))
    
    def record_sanitization_metrics(self, sanitization_time: float, patterns_detected: Dict[str, int]):
        """Registra métricas de sanitização"""
        try:
            SANITIZATION_TIME.observe(sanitization_time)
            
            for pattern_type, count in patterns_detected.items():
                SENSITIVE_DATA_DETECTED.labels(pattern_type=pattern_type).inc(count)
                
        except Exception as e:
            logger.warning("Erro ao registrar métricas de sanitização", error=str(e))
    
    def record_deduplication_metrics(self, dedup_time: float):
        """Registra métricas de deduplicação"""
        try:
            DEDUPLICATION_TIME.observe(dedup_time)
        except Exception as e:
            logger.warning("Erro ao registrar métricas de deduplicação", error=str(e))
    
    def record_wiremock_generation_metrics(self, generation_time: float):
        """Registra métricas de geração de mappings WireMock"""
        try:
            WIREMOCK_GENERATION_TIME.observe(generation_time)
        except Exception as e:
            logger.warning("Erro ao registrar métricas de geração WireMock", error=str(e))
    
    def _generalize_path(self, path: str) -> str:
        """Generaliza paths para reduzir cardinalidade das métricas"""
        import re
        
        # Remover query parameters
        path = path.split('?')[0]
        
        # Substituir IDs numéricos por placeholder
        path = re.sub(r'/\d+', '/{id}', path)
        
        # Substituir UUIDs por placeholder
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{uuid}', path, flags=re.IGNORECASE)
        
        # Substituir outros padrões comuns
        path = re.sub(r'/[a-zA-Z0-9]{20,}', '/{token}', path)  # Tokens longos
        
        # Limitar tamanho do path
        if len(path) > 100:
            path = path[:97] + '...'
        
        return path
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas atuais"""
        try:
            uptime = time.time() - self.start_time
            
            # Métricas do sistema
            memory = psutil.virtual_memory()
            
            # Métricas do processo
            process_memory = self.process.memory_info()
            
            stats = {
                'uptime_seconds': uptime,
                'system': {
                    'cpu_percent': psutil.cpu_percent(interval=None),
                    'memory_percent': memory.percent,
                    'memory_total_bytes': memory.total,
                    'memory_available_bytes': memory.available,
                    'memory_used_bytes': memory.used
                },
                'process': {
                    'cpu_percent': self.process.cpu_percent(),
                    'memory_rss_bytes': process_memory.rss,
                    'memory_vms_bytes': process_memory.vms,
                    'num_threads': self.process.num_threads(),
                    'create_time': self.process.create_time()
                }
            }
            
            # Adicionar file descriptors se disponível
            try:
                stats['process']['num_fds'] = self.process.num_fds()
            except AttributeError:
                pass
            
            return stats
            
        except Exception as e:
            logger.error("Erro ao obter estatísticas", error=str(e))
            return {'error': str(e)}
    
    def add_to_history(self, metrics: Dict[str, Any]):
        """Adiciona métricas ao histórico"""
        metrics['timestamp'] = datetime.utcnow().isoformat()
        self.metrics_history.append(metrics)
        
        # Limitar tamanho do histórico
        if len(self.metrics_history) > self.max_history_size:
            self.metrics_history = self.metrics_history[-self.max_history_size:]
    
    def get_history_summary(self, minutes: int = 60) -> Dict[str, Any]:
        """Retorna resumo do histórico de métricas"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
            
            recent_metrics = [
                m for m in self.metrics_history
                if datetime.fromisoformat(m['timestamp']) > cutoff_time
            ]
            
            if not recent_metrics:
                return {'message': 'No recent metrics available'}
            
            # Calcular estatísticas
            cpu_values = [m.get('system', {}).get('cpu_percent', 0) for m in recent_metrics]
            memory_values = [m.get('system', {}).get('memory_percent', 0) for m in recent_metrics]
            
            summary = {
                'period_minutes': minutes,
                'sample_count': len(recent_metrics),
                'cpu_stats': {
                    'min': min(cpu_values) if cpu_values else 0,
                    'max': max(cpu_values) if cpu_values else 0,
                    'avg': sum(cpu_values) / len(cpu_values) if cpu_values else 0
                },
                'memory_stats': {
                    'min': min(memory_values) if memory_values else 0,
                    'max': max(memory_values) if memory_values else 0,
                    'avg': sum(memory_values) / len(memory_values) if memory_values else 0
                }
            }
            
            return summary
            
        except Exception as e:
            logger.error("Erro ao gerar resumo do histórico", error=str(e))
            return {'error': str(e)}


class PerformanceTimer:
    """Context manager para medir tempo de execução"""
    
    def __init__(self, metric_name: str = None):
        self.metric_name = metric_name
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        
        if self.metric_name:
            duration = self.end_time - self.start_time
            
            # Registrar na métrica apropriada
            if self.metric_name == 'sanitization':
                SANITIZATION_TIME.observe(duration)
            elif self.metric_name == 'deduplication':
                DEDUPLICATION_TIME.observe(duration)
            elif self.metric_name == 'wiremock_generation':
                WIREMOCK_GENERATION_TIME.observe(duration)
            else:
                REQUEST_LATENCY.observe(duration)
    
    @property
    def duration(self) -> float:
        """Retorna a duração em segundos"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0


async def periodic_metrics_collection(metrics_collector: MetricsCollector, interval: int = 30):
    """Task para coleta periódica de métricas"""
    logger.info("Iniciando coleta periódica de métricas", interval=interval)
    
    while True:
        try:
            # Coletar métricas
            metrics_collector.collect_system_metrics()
            metrics_collector.collect_process_metrics()
            
            # Adicionar ao histórico
            current_stats = metrics_collector.get_stats()
            metrics_collector.add_to_history(current_stats)
            
            await asyncio.sleep(interval)
            
        except Exception as e:
            logger.error("Erro na coleta periódica de métricas", error=str(e))
            await asyncio.sleep(interval)