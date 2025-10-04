"""
Configurações do WireMock Loader Service
Gerencia configurações para integração com WireMock e filas de mensagens
"""
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseSettings, validator, Field
import yaml


class WireMockLoaderSettings(BaseSettings):
    """Configurações principais do WireMock Loader"""
    
    # Configurações do servidor
    host: str = Field(default="0.0.0.0", description="Host do servidor HTTP")
    port: int = Field(default=8090, description="Porta do servidor HTTP")
    
    # Configurações de logging
    log_level: str = Field(default="INFO", description="Nível de log")
    log_format: str = Field(default="json", description="Formato do log")
    
    # Configurações do WireMock
    wiremock_url: str = Field(default="http://localhost:8080", description="URL do WireMock")
    wiremock_admin_path: str = Field(default="/__admin", description="Path da API admin do WireMock")
    wiremock_timeout: int = Field(default=30, description="Timeout para WireMock em segundos")
    wiremock_retry_attempts: int = Field(default=3, description="Tentativas de retry para WireMock")
    wiremock_retry_delay: float = Field(default=1.0, description="Delay entre retries em segundos")
    
    # Configurações do Redis
    redis_url: str = Field(default="redis://localhost:6379", description="URL do Redis")
    redis_db: int = Field(default=1, description="Database do Redis para loader")
    redis_password: Optional[str] = Field(default=None, description="Senha do Redis")
    
    # Configurações de processamento
    batch_size: int = Field(default=5, description="Tamanho do batch para envio ao WireMock")
    batch_timeout: int = Field(default=10, description="Timeout do batch em segundos")
    max_concurrent_requests: int = Field(default=10, description="Máximo de requests concorrentes ao WireMock")
    
    # Configurações de fila
    queue_name: str = Field(default="wiremock_mappings", description="Nome da fila de mappings")
    queue_consumer_group: str = Field(default="wiremock_loader", description="Grupo de consumidores")
    queue_max_retries: int = Field(default=3, description="Máximo de retries para mensagens da fila")
    
    # Configurações de validação
    validate_mappings: bool = Field(default=True, description="Validar mappings antes de enviar")
    skip_invalid_mappings: bool = Field(default=True, description="Pular mappings inválidos")
    
    # Configurações de backup
    backup_mappings: bool = Field(default=True, description="Fazer backup dos mappings")
    backup_path: str = Field(default="/app/data/backups", description="Caminho para backups")
    backup_retention_days: int = Field(default=7, description="Dias para manter backups")
    
    # Configurações de monitoramento
    enable_metrics: bool = Field(default=True, description="Habilitar métricas Prometheus")
    metrics_port: int = Field(default=8091, description="Porta das métricas")
    
    # Configurações de segurança
    api_key: Optional[str] = Field(default=None, description="API key para autenticação")
    allowed_origins: List[str] = Field(default=["*"], description="Origins permitidas para CORS")
    
    @validator('log_level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'log_level deve ser um de: {valid_levels}')
        return v.upper()
    
    @validator('wiremock_retry_delay')
    def validate_retry_delay(cls, v):
        if v < 0.1 or v > 60.0:
            raise ValueError('wiremock_retry_delay deve estar entre 0.1 e 60.0 segundos')
        return v
    
    @validator('batch_size')
    def validate_batch_size(cls, v):
        if v < 1 or v > 100:
            raise ValueError('batch_size deve estar entre 1 e 100')
        return v
    
    class Config:
        env_prefix = "WIREMOCK_LOADER_"
        case_sensitive = False


class MappingValidationRule:
    """Regra de validação para mappings WireMock"""
    
    def __init__(self, name: str, rule_type: str, config: Dict[str, Any]):
        self.name = name
        self.rule_type = rule_type
        self.config = config
    
    def validate(self, mapping: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Valida um mapping e retorna (is_valid, error_message)"""
        try:
            if self.rule_type == "required_fields":
                return self._validate_required_fields(mapping)
            elif self.rule_type == "url_pattern":
                return self._validate_url_pattern(mapping)
            elif self.rule_type == "response_structure":
                return self._validate_response_structure(mapping)
            else:
                return True, None
                
        except Exception as e:
            return False, f"Erro na validação: {str(e)}"
    
    def _validate_required_fields(self, mapping: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Valida campos obrigatórios"""
        required_fields = self.config.get('fields', [])
        
        for field_path in required_fields:
            if not self._get_nested_field(mapping, field_path):
                return False, f"Campo obrigatório ausente: {field_path}"
        
        return True, None
    
    def _validate_url_pattern(self, mapping: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Valida padrões de URL"""
        import re
        
        request = mapping.get('request', {})
        url_path = request.get('urlPath') or request.get('url', '')
        
        if not url_path:
            return False, "URL path não encontrado"
        
        # Verificar padrões proibidos
        forbidden_patterns = self.config.get('forbidden_patterns', [])
        for pattern in forbidden_patterns:
            if re.search(pattern, url_path):
                return False, f"URL contém padrão proibido: {pattern}"
        
        # Verificar padrões obrigatórios
        required_patterns = self.config.get('required_patterns', [])
        for pattern in required_patterns:
            if not re.search(pattern, url_path):
                return False, f"URL não contém padrão obrigatório: {pattern}"
        
        return True, None
    
    def _validate_response_structure(self, mapping: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Valida estrutura da response"""
        response = mapping.get('response', {})
        
        # Verificar status code válido
        status = response.get('status', 200)
        if not isinstance(status, int) or status < 100 or status > 599:
            return False, f"Status code inválido: {status}"
        
        # Verificar se tem body ou jsonBody
        has_body = 'body' in response or 'jsonBody' in response
        if not has_body and self.config.get('require_body', False):
            return False, "Response deve ter body ou jsonBody"
        
        return True, None
    
    def _get_nested_field(self, data: Dict[str, Any], field_path: str) -> Any:
        """Obtém campo aninhado usando notação de ponto"""
        keys = field_path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current


class ConfigManager:
    """Gerenciador de configurações com suporte a validação"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.settings = WireMockLoaderSettings()
        self.validation_rules: List[MappingValidationRule] = []
        
        if config_path and os.path.exists(config_path):
            self._load_config_file(config_path)
        
        self._setup_default_validation_rules()
    
    def _load_config_file(self, config_path: str):
        """Carrega configurações de arquivo YAML"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            # Atualizar configurações principais
            if 'wiremock_loader' in config_data:
                for key, value in config_data['wiremock_loader'].items():
                    if hasattr(self.settings, key):
                        setattr(self.settings, key, value)
            
            # Carregar regras de validação
            if 'validation_rules' in config_data:
                self.validation_rules = []
                for rule_data in config_data['validation_rules']:
                    rule = MappingValidationRule(
                        name=rule_data['name'],
                        rule_type=rule_data['type'],
                        config=rule_data.get('config', {})
                    )
                    self.validation_rules.append(rule)
                    
        except Exception as e:
            print(f"Erro ao carregar arquivo de configuração {config_path}: {e}")
    
    def _setup_default_validation_rules(self):
        """Configura regras de validação padrão"""
        if not self.validation_rules:
            # Regra para campos obrigatórios
            required_fields_rule = MappingValidationRule(
                name="required_fields",
                rule_type="required_fields",
                config={
                    'fields': ['request.method', 'request.urlPath', 'response.status']
                }
            )
            self.validation_rules.append(required_fields_rule)
            
            # Regra para padrões de URL
            url_pattern_rule = MappingValidationRule(
                name="url_patterns",
                rule_type="url_pattern",
                config={
                    'forbidden_patterns': [
                        r'/__admin.*',  # Não permitir mock da API admin
                        r'/health.*',   # Não permitir mock de health checks
                        r'/metrics.*'   # Não permitir mock de métricas
                    ]
                }
            )
            self.validation_rules.append(url_pattern_rule)
    
    def validate_mapping(self, mapping: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Valida um mapping usando todas as regras configuradas"""
        if not self.settings.validate_mappings:
            return True, []
        
        errors = []
        
        for rule in self.validation_rules:
            is_valid, error_message = rule.validate(mapping)
            if not is_valid and error_message:
                errors.append(f"{rule.name}: {error_message}")
        
        return len(errors) == 0, errors
    
    def should_backup_mapping(self, mapping: Dict[str, Any]) -> bool:
        """Verifica se deve fazer backup do mapping"""
        return self.settings.backup_mappings
    
    def get_wiremock_admin_url(self, endpoint: str = "") -> str:
        """Constrói URL da API admin do WireMock"""
        base_url = self.settings.wiremock_url.rstrip('/')
        admin_path = self.settings.wiremock_admin_path.strip('/')
        endpoint = endpoint.lstrip('/')
        
        if endpoint:
            return f"{base_url}/{admin_path}/{endpoint}"
        else:
            return f"{base_url}/{admin_path}"


# Instância global do gerenciador de configurações
config_manager = ConfigManager(
    config_path=os.getenv('WIREMOCK_LOADER_CONFIG_PATH', '/app/config/wiremock-loader.yaml')
)