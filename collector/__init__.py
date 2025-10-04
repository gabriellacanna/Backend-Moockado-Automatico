"""
Backend Mockado Automático - Collector Service

Serviço de coleta e processamento de tráfego HTTP/gRPC capturado pelo Envoy tap filter.
Responsável por sanitizar dados sensíveis, deduplificar requests e gerar mappings WireMock.
"""

__version__ = "1.0.0"
__author__ = "Backend Mockado Automático Team"
__description__ = "Automatic mock backend collector service for Istio/ASM environments"

from .config import config_manager
from .sanitizer import DataSanitizer, create_sanitizer
from .deduplicator import RequestDeduplicator, InMemoryDeduplicator
from .processor import RequestProcessor, BatchProcessor
from .metrics import MetricsCollector, PerformanceTimer
from .main import CollectorApp

__all__ = [
    'config_manager',
    'DataSanitizer',
    'create_sanitizer',
    'RequestDeduplicator',
    'InMemoryDeduplicator',
    'RequestProcessor',
    'BatchProcessor',
    'MetricsCollector',
    'PerformanceTimer',
    'CollectorApp'
]