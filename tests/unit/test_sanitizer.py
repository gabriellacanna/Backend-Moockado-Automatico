#!/usr/bin/env python3
"""
Testes unitários para o módulo de sanitização.
"""

import pytest
import json
from collector.sanitizer import DataSanitizer


class TestDataSanitizer:
    """Testes para a classe DataSanitizer."""
    
    def setup_method(self):
        """Configuração para cada teste."""
        self.sanitizer = DataSanitizer()
    
    def test_sanitize_headers_authorization(self):
        """Testa sanitização de headers de autorização."""
        headers = {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "X-API-Key": "secret-api-key-123",
            "Content-Type": "application/json"
        }
        
        sanitized = self.sanitizer.sanitize_headers(headers)
        
        assert sanitized["Authorization"] == "SANITIZED_JWT"
        assert sanitized["X-API-Key"] == "SANITIZED_HEADER"
        assert sanitized["Content-Type"] == "application/json"
    
    def test_sanitize_headers_cookies(self):
        """Testa sanitização de cookies."""
        headers = {
            "Cookie": "session_id=abc123; user_token=xyz789; theme=dark",
            "Accept": "application/json"
        }
        
        sanitized = self.sanitizer.sanitize_headers(headers)
        
        assert sanitized["Cookie"] == "SANITIZED_HEADER"
        assert sanitized["Accept"] == "application/json"
    
    def test_sanitize_body_credit_card(self):
        """Testa sanitização de cartões de crédito."""
        body = {
            "user": "João Silva",
            "credit_card": "4111111111111111",
            "card_number": "5555555555554444",
            "amount": 100.50
        }
        
        sanitized = self.sanitizer.sanitize_body(body)
        
        assert sanitized["credit_card"] == "SANITIZED_CARD"
        assert sanitized["card_number"] == "SANITIZED_CARD"
        assert sanitized["user"] == "João Silva"
        assert sanitized["amount"] == 100.50
    
    def test_sanitize_body_documents(self):
        """Testa sanitização de documentos (CPF, CNPJ)."""
        body = {
            "name": "João Silva",
            "cpf": "123.456.789-01",
            "cnpj": "12.345.678/0001-90",
            "document": "98765432101",
            "age": 30
        }
        
        sanitized = self.sanitizer.sanitize_body(body)
        
        assert sanitized["cpf"] == "SANITIZED_DOCUMENT"
        assert sanitized["cnpj"] == "SANITIZED_DOCUMENT"
        assert sanitized["document"] == "SANITIZED_DOCUMENT"
        assert sanitized["name"] == "João Silva"
        assert sanitized["age"] == 30
    
    def test_sanitize_body_email_phone(self):
        """Testa sanitização de email e telefone."""
        body = {
            "name": "João Silva",
            "email": "joao.silva@example.com",
            "phone": "+55 11 99999-9999",
            "mobile": "11987654321",
            "city": "São Paulo"
        }
        
        sanitized = self.sanitizer.sanitize_body(body)
        
        assert sanitized["email"] == "SANITIZED_EMAIL"
        assert sanitized["phone"] == "SANITIZED_PHONE"
        assert sanitized["mobile"] == "SANITIZED_PHONE"
        assert sanitized["name"] == "João Silva"
        assert sanitized["city"] == "São Paulo"
    
    def test_sanitize_body_passwords(self):
        """Testa sanitização de senhas."""
        body = {
            "username": "joao",
            "password": "super-secret-password",
            "confirm_password": "super-secret-password",
            "old_password": "old-secret",
            "role": "user"
        }
        
        sanitized = self.sanitizer.sanitize_body(body)
        
        assert sanitized["password"] == "SANITIZED_PASSWORD"
        assert sanitized["confirm_password"] == "SANITIZED_PASSWORD"
        assert sanitized["old_password"] == "SANITIZED_PASSWORD"
        assert sanitized["username"] == "joao"
        assert sanitized["role"] == "user"
    
    def test_sanitize_body_nested_objects(self):
        """Testa sanitização de objetos aninhados."""
        body = {
            "user": {
                "name": "João Silva",
                "email": "joao@example.com",
                "credentials": {
                    "password": "secret123",
                    "api_key": "key-123"
                }
            },
            "payment": {
                "card_number": "4111111111111111",
                "amount": 100.0
            }
        }
        
        sanitized = self.sanitizer.sanitize_body(body)
        
        assert sanitized["user"]["name"] == "João Silva"
        assert sanitized["user"]["email"] == "SANITIZED_EMAIL"
        assert sanitized["user"]["credentials"]["password"] == "SANITIZED_PASSWORD"
        assert sanitized["user"]["credentials"]["api_key"] == "SANITIZED_HEADER"
        assert sanitized["payment"]["card_number"] == "SANITIZED_CARD"
        assert sanitized["payment"]["amount"] == 100.0
    
    def test_sanitize_body_arrays(self):
        """Testa sanitização de arrays."""
        body = {
            "users": [
                {
                    "name": "João",
                    "email": "joao@example.com",
                    "password": "secret1"
                },
                {
                    "name": "Maria",
                    "email": "maria@example.com",
                    "password": "secret2"
                }
            ],
            "cards": ["4111111111111111", "5555555555554444"]
        }
        
        sanitized = self.sanitizer.sanitize_body(body)
        
        assert sanitized["users"][0]["name"] == "João"
        assert sanitized["users"][0]["email"] == "SANITIZED_EMAIL"
        assert sanitized["users"][0]["password"] == "SANITIZED_PASSWORD"
        assert sanitized["users"][1]["name"] == "Maria"
        assert sanitized["users"][1]["email"] == "SANITIZED_EMAIL"
        assert sanitized["users"][1]["password"] == "SANITIZED_PASSWORD"
        assert sanitized["cards"][0] == "SANITIZED_CARD"
        assert sanitized["cards"][1] == "SANITIZED_CARD"
    
    def test_sanitize_body_string_content(self):
        """Testa sanitização de conteúdo em strings."""
        body = {
            "description": "User email is joao@example.com and phone +55 11 99999-9999",
            "notes": "Credit card 4111111111111111 was used",
            "title": "Regular title without sensitive data"
        }
        
        sanitized = self.sanitizer.sanitize_body(body)
        
        # Strings com dados sensíveis devem ser sanitizadas
        assert "joao@example.com" not in sanitized["description"]
        assert "SANITIZED_EMAIL" in sanitized["description"]
        assert "+55 11 99999-9999" not in sanitized["description"]
        assert "SANITIZED_PHONE" in sanitized["description"]
        
        assert "4111111111111111" not in sanitized["notes"]
        assert "SANITIZED_CARD" in sanitized["notes"]
        
        # String sem dados sensíveis deve permanecer igual
        assert sanitized["title"] == "Regular title without sensitive data"
    
    def test_sanitize_request_complete(self):
        """Testa sanitização completa de uma request."""
        request_data = {
            "method": "POST",
            "path": "/api/v1/users",
            "headers": {
                "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "Content-Type": "application/json",
                "Cookie": "session_id=abc123"
            },
            "body": {
                "name": "João Silva",
                "email": "joao@example.com",
                "password": "secret123",
                "credit_card": "4111111111111111"
            }
        }
        
        sanitized = self.sanitizer.sanitize_request(request_data)
        
        # Verificar que método e path não foram alterados
        assert sanitized["method"] == "POST"
        assert sanitized["path"] == "/api/v1/users"
        
        # Verificar sanitização de headers
        assert sanitized["headers"]["Authorization"] == "SANITIZED_JWT"
        assert sanitized["headers"]["Content-Type"] == "application/json"
        assert sanitized["headers"]["Cookie"] == "SANITIZED_HEADER"
        
        # Verificar sanitização de body
        assert sanitized["body"]["name"] == "João Silva"
        assert sanitized["body"]["email"] == "SANITIZED_EMAIL"
        assert sanitized["body"]["password"] == "SANITIZED_PASSWORD"
        assert sanitized["body"]["credit_card"] == "SANITIZED_CARD"
    
    def test_sanitize_response_complete(self):
        """Testa sanitização completa de uma response."""
        response_data = {
            "status": 201,
            "headers": {
                "Content-Type": "application/json",
                "Set-Cookie": "session_id=new123; HttpOnly"
            },
            "body": {
                "id": "user-123",
                "name": "João Silva",
                "email": "joao@example.com",
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }
        
        sanitized = self.sanitizer.sanitize_response(response_data)
        
        # Verificar que status não foi alterado
        assert sanitized["status"] == 201
        
        # Verificar sanitização de headers
        assert sanitized["headers"]["Content-Type"] == "application/json"
        assert sanitized["headers"]["Set-Cookie"] == "SANITIZED_HEADER"
        
        # Verificar sanitização de body
        assert sanitized["body"]["id"] == "user-123"
        assert sanitized["body"]["name"] == "João Silva"
        assert sanitized["body"]["email"] == "SANITIZED_EMAIL"
        assert sanitized["body"]["token"] == "SANITIZED_JWT"
    
    def test_sanitize_empty_data(self):
        """Testa sanitização de dados vazios."""
        # Headers vazios
        assert self.sanitizer.sanitize_headers({}) == {}
        assert self.sanitizer.sanitize_headers(None) == {}
        
        # Body vazio
        assert self.sanitizer.sanitize_body({}) == {}
        assert self.sanitizer.sanitize_body(None) == {}
        assert self.sanitizer.sanitize_body("") == ""
        assert self.sanitizer.sanitize_body([]) == []
    
    def test_sanitize_non_dict_body(self):
        """Testa sanitização de body que não é dict."""
        # String simples
        body_str = "Simple string without sensitive data"
        sanitized = self.sanitizer.sanitize_body(body_str)
        assert sanitized == body_str
        
        # String com dados sensíveis
        body_str_sensitive = "Email: joao@example.com, Card: 4111111111111111"
        sanitized = self.sanitizer.sanitize_body(body_str_sensitive)
        assert "joao@example.com" not in sanitized
        assert "4111111111111111" not in sanitized
        assert "SANITIZED_EMAIL" in sanitized
        assert "SANITIZED_CARD" in sanitized
        
        # Lista
        body_list = ["item1", "joao@example.com", "item3"]
        sanitized = self.sanitizer.sanitize_body(body_list)
        assert sanitized[0] == "item1"
        assert sanitized[1] == "SANITIZED_EMAIL"
        assert sanitized[2] == "item3"
    
    def test_performance_large_data(self):
        """Testa performance com dados grandes."""
        import time
        
        # Criar um body grande com dados sensíveis
        large_body = {
            "users": []
        }
        
        for i in range(1000):
            large_body["users"].append({
                "id": i,
                "name": f"User {i}",
                "email": f"user{i}@example.com",
                "password": f"password{i}",
                "credit_card": "4111111111111111"
            })
        
        start_time = time.time()
        sanitized = self.sanitizer.sanitize_body(large_body)
        end_time = time.time()
        
        # Verificar que a sanitização foi executada
        assert len(sanitized["users"]) == 1000
        assert sanitized["users"][0]["email"] == "SANITIZED_EMAIL"
        assert sanitized["users"][0]["password"] == "SANITIZED_PASSWORD"
        assert sanitized["users"][0]["credit_card"] == "SANITIZED_CARD"
        
        # Verificar que não demorou muito (menos de 1 segundo)
        processing_time = end_time - start_time
        assert processing_time < 1.0, f"Sanitização demorou {processing_time:.2f}s"
    
    def test_regex_patterns(self):
        """Testa os padrões regex específicos."""
        # Testar diferentes formatos de cartão de crédito
        cards = [
            "4111111111111111",  # Visa
            "5555555555554444",  # Mastercard
            "378282246310005",   # Amex
            "4111-1111-1111-1111",  # Com hífens
            "4111 1111 1111 1111"   # Com espaços
        ]
        
        for card in cards:
            body = {"card": card}
            sanitized = self.sanitizer.sanitize_body(body)
            assert sanitized["card"] == "SANITIZED_CARD"
        
        # Testar diferentes formatos de CPF
        cpfs = [
            "123.456.789-01",
            "12345678901",
            "123 456 789 01"
        ]
        
        for cpf in cpfs:
            body = {"cpf": cpf}
            sanitized = self.sanitizer.sanitize_body(body)
            assert sanitized["cpf"] == "SANITIZED_DOCUMENT"
        
        # Testar diferentes formatos de telefone
        phones = [
            "+55 11 99999-9999",
            "(11) 99999-9999",
            "11999999999",
            "+5511999999999"
        ]
        
        for phone in phones:
            body = {"phone": phone}
            sanitized = self.sanitizer.sanitize_body(body)
            assert sanitized["phone"] == "SANITIZED_PHONE"