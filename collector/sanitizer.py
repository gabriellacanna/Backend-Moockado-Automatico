"""
Módulo de sanitização de dados sensíveis
Remove informações confidenciais de headers, body e query parameters
"""
import re
import json
import hashlib
from typing import Dict, Any, List, Optional, Union
from urllib.parse import parse_qs, urlencode
import structlog

logger = structlog.get_logger(__name__)


class DataSanitizer:
    """Sanitizador de dados sensíveis com suporte a múltiplos formatos"""
    
    # Padrões regex para identificar dados sensíveis
    SENSITIVE_PATTERNS = {
        'credit_card': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
        'cpf': r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b',
        'cnpj': r'\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b',
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'phone': r'\b(?:\+55\s?)?(?:\(\d{2}\)\s?)?\d{4,5}-?\d{4}\b',
        'token': r'\b[A-Za-z0-9]{20,}\b',
        'uuid': r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b',
        'ip_address': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        'password_field': r'(password|senha|pwd|pass)\s*[:=]\s*["\']?([^"\'\\s]+)["\']?',
    }
    
    def __init__(self, sensitive_headers: List[str], sensitive_fields: List[str]):
        self.sensitive_headers = [h.lower() for h in sensitive_headers]
        self.sensitive_fields = [f.lower() for f in sensitive_fields]
        
        # Compilar padrões regex para melhor performance
        self.compiled_patterns = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.SENSITIVE_PATTERNS.items()
        }
    
    def sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Sanitiza headers sensíveis"""
        sanitized = {}
        
        for key, value in headers.items():
            key_lower = key.lower()
            
            if key_lower in self.sensitive_headers:
                # Manter apenas os primeiros e últimos caracteres para debug
                if len(value) > 8:
                    sanitized[key] = f"{value[:4]}***{value[-4:]}"
                else:
                    sanitized[key] = "***SANITIZED***"
            else:
                # Verificar se o valor contém dados sensíveis
                sanitized_value = self._sanitize_string_value(value)
                sanitized[key] = sanitized_value
        
        return sanitized
    
    def sanitize_body(self, body: Union[str, bytes, Dict, List], content_type: str = "") -> Any:
        """Sanitiza body baseado no content-type"""
        if not body:
            return body
        
        try:
            # Converter bytes para string se necessário
            if isinstance(body, bytes):
                body = body.decode('utf-8', errors='ignore')
            
            # Determinar tipo de conteúdo
            content_type_lower = content_type.lower()
            
            if 'application/json' in content_type_lower:
                return self._sanitize_json_body(body)
            elif 'application/x-www-form-urlencoded' in content_type_lower:
                return self._sanitize_form_body(body)
            elif 'multipart/form-data' in content_type_lower:
                return self._sanitize_multipart_body(body)
            elif 'text/' in content_type_lower or 'application/xml' in content_type_lower:
                return self._sanitize_text_body(body)
            else:
                # Para tipos desconhecidos, tentar sanitizar como texto
                return self._sanitize_string_value(str(body))
                
        except Exception as e:
            logger.warning("Erro ao sanitizar body", error=str(e), content_type=content_type)
            return "***SANITIZATION_ERROR***"
    
    def _sanitize_json_body(self, body: Union[str, Dict, List]) -> Any:
        """Sanitiza body JSON"""
        try:
            if isinstance(body, str):
                data = json.loads(body)
            else:
                data = body
            
            sanitized_data = self._sanitize_dict_recursive(data)
            return sanitized_data
            
        except json.JSONDecodeError:
            # Se não for JSON válido, tratar como texto
            return self._sanitize_string_value(str(body))
    
    def _sanitize_form_body(self, body: str) -> str:
        """Sanitiza body de formulário URL-encoded"""
        try:
            parsed = parse_qs(body, keep_blank_values=True)
            sanitized = {}
            
            for key, values in parsed.items():
                key_lower = key.lower()
                if key_lower in self.sensitive_fields:
                    sanitized[key] = ["***SANITIZED***"] * len(values)
                else:
                    sanitized[key] = [self._sanitize_string_value(v) for v in values]
            
            return urlencode(sanitized, doseq=True)
            
        except Exception:
            return self._sanitize_string_value(body)
    
    def _sanitize_multipart_body(self, body: str) -> str:
        """Sanitiza body multipart (simplificado)"""
        # Para multipart, fazer sanitização básica de string
        # Em produção, seria necessário um parser mais sofisticado
        return self._sanitize_string_value(body)
    
    def _sanitize_text_body(self, body: str) -> str:
        """Sanitiza body de texto/XML"""
        return self._sanitize_string_value(body)
    
    def _sanitize_dict_recursive(self, data: Any) -> Any:
        """Sanitiza dicionário recursivamente"""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                key_lower = str(key).lower()
                
                if key_lower in self.sensitive_fields:
                    sanitized[key] = "***SANITIZED***"
                else:
                    sanitized[key] = self._sanitize_dict_recursive(value)
            return sanitized
            
        elif isinstance(data, list):
            return [self._sanitize_dict_recursive(item) for item in data]
            
        elif isinstance(data, str):
            return self._sanitize_string_value(data)
            
        else:
            return data
    
    def _sanitize_string_value(self, value: str) -> str:
        """Sanitiza string usando padrões regex"""
        if not isinstance(value, str):
            return value
        
        sanitized_value = value
        
        # Aplicar padrões de sanitização
        for pattern_name, compiled_pattern in self.compiled_patterns.items():
            if compiled_pattern.search(sanitized_value):
                if pattern_name in ['credit_card', 'cpf', 'cnpj']:
                    # Para dados estruturados, manter formato mas ocultar dígitos
                    sanitized_value = compiled_pattern.sub(
                        lambda m: self._mask_structured_data(m.group(0)),
                        sanitized_value
                    )
                else:
                    # Para outros tipos, substituir completamente
                    sanitized_value = compiled_pattern.sub("***SANITIZED***", sanitized_value)
        
        return sanitized_value
    
    def _mask_structured_data(self, data: str) -> str:
        """Mascara dados estruturados mantendo formato"""
        # Remove caracteres especiais para contar dígitos
        digits_only = re.sub(r'\D', '', data)
        
        if len(digits_only) >= 8:
            # Manter primeiros 4 e últimos 4 dígitos
            masked_digits = digits_only[:2] + '*' * (len(digits_only) - 4) + digits_only[-2:]
        else:
            masked_digits = '*' * len(digits_only)
        
        # Reconstruir com formato original
        result = data
        digit_index = 0
        for i, char in enumerate(data):
            if char.isdigit():
                if digit_index < len(masked_digits):
                    result = result[:i] + masked_digits[digit_index] + result[i+1:]
                    digit_index += 1
        
        return result
    
    def sanitize_query_params(self, query_string: str) -> str:
        """Sanitiza query parameters"""
        if not query_string:
            return query_string
        
        try:
            parsed = parse_qs(query_string, keep_blank_values=True)
            sanitized = {}
            
            for key, values in parsed.items():
                key_lower = key.lower()
                if key_lower in self.sensitive_fields:
                    sanitized[key] = ["***SANITIZED***"] * len(values)
                else:
                    sanitized[key] = [self._sanitize_string_value(v) for v in values]
            
            return urlencode(sanitized, doseq=True)
            
        except Exception:
            return self._sanitize_string_value(query_string)
    
    def generate_body_hash(self, body: Any, max_length: int = 1000) -> str:
        """Gera hash do body para deduplicação"""
        try:
            # Converter para string se necessário
            if isinstance(body, (dict, list)):
                body_str = json.dumps(body, sort_keys=True, separators=(',', ':'))
            elif isinstance(body, bytes):
                body_str = body.decode('utf-8', errors='ignore')
            else:
                body_str = str(body)
            
            # Limitar tamanho para hash
            if len(body_str) > max_length:
                body_str = body_str[:max_length]
            
            # Gerar hash SHA-256
            return hashlib.sha256(body_str.encode('utf-8')).hexdigest()[:16]
            
        except Exception as e:
            logger.warning("Erro ao gerar hash do body", error=str(e))
            return "hash_error"
    
    def is_sensitive_content(self, content: str) -> bool:
        """Verifica se o conteúdo contém dados sensíveis"""
        if not content:
            return False
        
        for pattern in self.compiled_patterns.values():
            if pattern.search(content):
                return True
        
        return False


def create_sanitizer(sensitive_headers: List[str], sensitive_fields: List[str]) -> DataSanitizer:
    """Factory function para criar sanitizador"""
    return DataSanitizer(sensitive_headers, sensitive_fields)