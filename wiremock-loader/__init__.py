"""
Backend Mockado Automático - WireMock Loader Service

Serviço responsável por consumir mappings da fila e registrá-los no WireMock.
Inclui funcionalidades de backup, validação e monitoramento.
"""

__version__ = "1.0.0"
__author__ = "Backend Mockado Automático Team"
__description__ = "WireMock loader service for automatic mock backend generation"

from .config import config_manager
from .wiremock_client import WireMockClient, BatchWireMockClient
from .queue_consumer import RedisQueueConsumer, MockQueueConsumer
from .backup_manager import BackupManager
from .main import WireMockLoaderApp

__all__ = [
    'config_manager',
    'WireMockClient',
    'BatchWireMockClient',
    'RedisQueueConsumer',
    'MockQueueConsumer',
    'BackupManager',
    'WireMockLoaderApp'
]