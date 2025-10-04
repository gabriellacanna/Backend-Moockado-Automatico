"""
Configurações do Collector Service
Gerencia todas as configurações de ambiente e validações de segurança
"""
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseSettings, validator, Field
import yaml


class CollectorSettings(BaseSettings):
    """Configurações principais do collector"""
    
    # Configurações do servidor
    host: str = Field(default="0.0.0.0", description="Host do servidor HTTP")
    port: int = Field(default=9090, description="Porta do servidor HTTP")
    grpc_port: int = Field(default=50051, description="Porta do servidor gRPC")
    
    # Configurações de logging
    log_level: str = Field(default="INFO", description="Nível de log")
    log_format: str = Field(default="json", description="Formato do log")
    
    # Configurações do Redis
    redis_url: str = Field(default="redis://localhost:6379", description="URL do Redis")
    redis_db: int = Field(default=0, description="Database do Redis")
    redis_password: Optional[str] = Field(default=None, description="Senha do Redis")
    
    # Configurações do WireMock
    wiremock_url: str = Field(default="http://localhost:8080", description="URL do WireMock")
    wiremock_timeout: int = Field(default=30, description="Timeout para WireMock em segundos")
    
    # Configurações de processamento
    body_size_limit: int = Field(default=8192, description="Limite do body em bytes")
    enable_sampling: bool = Field(default=False, description="Habilitar sampling")
    default_sample_rate: float = Field(default=1.0, description="Taxa de sampling padrão")
    
    # Configurações de deduplicação
    dedup_ttl: int = Field(default=3600, description="TTL para deduplicação em segundos")
    dedup_hash_fields: List[str] = Field(
        default=["method", "path", "query", "body_hash"],
        description="Campos para hash de deduplicação"
    )
    
    # Configurações de segurança
    sensitive_headers: List[str] = Field(
        default=[
            "authorization", "cookie", "x-api-key", "x-auth-token",
            "x-access-token", "x-refresh-token", "x-session-id", "x-user-token"
        ],
        description="Headers sensíveis para sanitizar"
    )
    
    sensitive_fields: List[str] = Field(
        default=[
            "password", "senha", "token", "api_key", "apiKey",
            "access_token", "refresh_token", "credit_card", "creditCard",
            "cartao", "cpf", "cnpj", "ssn", "social_security",
            "phone", "telefone", "email", "birth_date", "data_nascimento"
        ],
        description="Campos sensíveis no body para sanitizar"
    )
    
    # Configurações de filtros
    ignored_hosts: List[str] = Field(
        default=[
            "kubernetes.default.svc.cluster.local",
            "*.istio-system.svc.cluster.local",
            "*.kube-system.svc.cluster.local",
            "prometheus.*", "grafana.*"
        ],
        description="Hosts para ignorar"
    )
    
    ignored_paths: List[str] = Field(
        default=[
            "/health", "/healthz", "/ready", "/live",
            "/metrics", "/favicon.ico", "/.well-known/*"
        ],
        description="Paths para ignorar"
    )
    
    # Configurações de performance
    max_concurrent_requests: int = Field(default=100, description="Máximo de requests concorrentes")
    request_timeout: int = Field(default=30, description="Timeout de request em segundos")
    batch_size: int = Field(default=10, description="Tamanho do batch para processamento")
    batch_timeout: int = Field(default=5, description="Timeout do batch em segundos")
    
    # Configurações de monitoramento
    enable_metrics: bool = Field(default=True, description="Habilitar métricas Prometheus")
    metrics_port: int = Field(default=9091, description="Porta das métricas")
    
    @validator('log_level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'log_level deve ser um de: {valid_levels}')
        return v.upper()
    
    @validator('default_sample_rate')
    def validate_sample_rate(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError('default_sample_rate deve estar entre 0.0 e 1.0')
        return v
    
    @validator('body_size_limit')
    def validate_body_size_limit(cls, v):
        if v < 1024 or v > 1024 * 1024:  # Entre 1KB e 1MB
            raise ValueError('body_size_limit deve estar entre 1024 e 1048576 bytes')
        return v
    
    class Config:
        env_prefix = "COLLECTOR_"
        case_sensitive = False


class SamplingRule:
    """Regra de sampling para endpoints específicos"""
    
    def __init__(self, path_regex: str, sample_rate: float, method: Optional[str] = None):
        self.path_regex = path_regex
        self.sample_rate = sample_rate
        self.method = method
        
        if not 0.0 <= sample_rate <= 1.0:
            raise ValueError('sample_rate deve estar entre 0.0 e 1.0')


class ConfigManager:
    """Gerenciador de configurações com suporte a arquivos YAML"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.settings = CollectorSettings()
        self.sampling_rules: List[SamplingRule] = []
        
        if config_path and os.path.exists(config_path):
            self._load_config_file(config_path)
    
    def _load_config_file(self, config_path: str):
        """Carrega configurações de arquivo YAML"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            # Atualizar configurações principais
            if 'collector' in config_data:
                for key, value in config_data['collector'].items():
                    if hasattr(self.settings, key):
                        setattr(self.settings, key, value)
            
            # Carregar regras de sampling
            if 'sampling_rules' in config_data:
                self.sampling_rules = []
                for rule_data in config_data['sampling_rules']:
                    rule = SamplingRule(
                        path_regex=rule_data['path_regex'],
                        sample_rate=rule_data['sample_rate'],
                        method=rule_data.get('method')
                    )
                    self.sampling_rules.append(rule)
                    
        except Exception as e:
            print(f"Erro ao carregar arquivo de configuração {config_path}: {e}")
            # Continua com configurações padrão
    
    def get_sample_rate(self, path: str, method: str) -> float:
        """Retorna a taxa de sampling para um endpoint específico"""
        import re
        
        for rule in self.sampling_rules:
            if re.match(rule.path_regex, path):
                if rule.method is None or rule.method.upper() == method.upper():
                    return rule.sample_rate
        
        return self.settings.default_sample_rate
    
    def should_ignore_request(self, host: str, path: str) -> bool:
        """Verifica se uma request deve ser ignorada"""
        import fnmatch
        
        # Verificar hosts ignorados
        for ignored_host in self.settings.ignored_hosts:
            if fnmatch.fnmatch(host, ignored_host):
                return True
        
        # Verificar paths ignorados
        for ignored_path in self.settings.ignored_paths:
            if fnmatch.fnmatch(path, ignored_path):
                return True
        
        return False


# Instância global do gerenciador de configurações
config_manager = ConfigManager(
    config_path=os.getenv('COLLECTOR_CONFIG_PATH', '/app/config/collector.yaml')
)