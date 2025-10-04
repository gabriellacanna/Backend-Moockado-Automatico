#!/usr/bin/env python3
"""
Testes unitários para o módulo de deduplicação.
"""

import pytest
import json
from collector.deduplicator import RequestDeduplicator


class TestRequestDeduplicator:
    """Testes para a classe RequestDeduplicator."""
    
    def setup_method(self):
        """Configuração para cada teste."""
        self.deduplicator = RequestDeduplicator()
    
    def test_generate_hash_identical_requests(self):
        """Testa se requests idênticas geram o mesmo hash."""
        request1 = {
            "method": "GET",
            "path": "/api/v1/users",
            "query": {"page": "1", "limit": "10"},
            "body": {"filter": "active"}
        }
        
        request2 = {
            "method": "GET",
            "path": "/api/v1/users",
            "query": {"page": "1", "limit": "10"},
            "body": {"filter": "active"}
        }
        
        hash1 = self.deduplicator.generate_hash(request1)
        hash2 = self.deduplicator.generate_hash(request2)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest
    
    def test_generate_hash_different_methods(self):
        """Testa se requests com métodos diferentes geram hashes diferentes."""
        request1 = {
            "method": "GET",
            "path": "/api/v1/users",
            "query": {},
            "body": {}
        }
        
        request2 = {
            "method": "POST",
            "path": "/api/v1/users",
            "query": {},
            "body": {}
        }
        
        hash1 = self.deduplicator.generate_hash(request1)
        hash2 = self.deduplicator.generate_hash(request2)
        
        assert hash1 != hash2
    
    def test_generate_hash_different_paths(self):
        """Testa se requests com paths diferentes geram hashes diferentes."""
        request1 = {
            "method": "GET",
            "path": "/api/v1/users",
            "query": {},
            "body": {}
        }
        
        request2 = {
            "method": "GET",
            "path": "/api/v1/products",
            "query": {},
            "body": {}
        }
        
        hash1 = self.deduplicator.generate_hash(request1)
        hash2 = self.deduplicator.generate_hash(request2)
        
        assert hash1 != hash2
    
    def test_generate_hash_different_query_params(self):
        """Testa se requests com query params diferentes geram hashes diferentes."""
        request1 = {
            "method": "GET",
            "path": "/api/v1/users",
            "query": {"page": "1"},
            "body": {}
        }
        
        request2 = {
            "method": "GET",
            "path": "/api/v1/users",
            "query": {"page": "2"},
            "body": {}
        }
        
        hash1 = self.deduplicator.generate_hash(request1)
        hash2 = self.deduplicator.generate_hash(request2)
        
        assert hash1 != hash2
    
    def test_generate_hash_different_body(self):
        """Testa se requests com body diferentes geram hashes diferentes."""
        request1 = {
            "method": "POST",
            "path": "/api/v1/users",
            "query": {},
            "body": {"name": "João"}
        }
        
        request2 = {
            "method": "POST",
            "path": "/api/v1/users",
            "query": {},
            "body": {"name": "Maria"}
        }
        
        hash1 = self.deduplicator.generate_hash(request1)
        hash2 = self.deduplicator.generate_hash(request2)
        
        assert hash1 != hash2
    
    def test_generate_hash_query_param_order(self):
        """Testa se a ordem dos query params não afeta o hash."""
        request1 = {
            "method": "GET",
            "path": "/api/v1/users",
            "query": {"page": "1", "limit": "10", "sort": "name"},
            "body": {}
        }
        
        request2 = {
            "method": "GET",
            "path": "/api/v1/users",
            "query": {"sort": "name", "page": "1", "limit": "10"},
            "body": {}
        }
        
        hash1 = self.deduplicator.generate_hash(request1)
        hash2 = self.deduplicator.generate_hash(request2)
        
        assert hash1 == hash2
    
    def test_generate_hash_body_key_order(self):
        """Testa se a ordem das chaves no body não afeta o hash."""
        request1 = {
            "method": "POST",
            "path": "/api/v1/users",
            "query": {},
            "body": {"name": "João", "age": 30, "city": "SP"}
        }
        
        request2 = {
            "method": "POST",
            "path": "/api/v1/users",
            "query": {},
            "body": {"city": "SP", "name": "João", "age": 30}
        }
        
        hash1 = self.deduplicator.generate_hash(request1)
        hash2 = self.deduplicator.generate_hash(request2)
        
        assert hash1 == hash2
    
    def test_generate_hash_nested_objects(self):
        """Testa hash com objetos aninhados."""
        request1 = {
            "method": "POST",
            "path": "/api/v1/users",
            "query": {},
            "body": {
                "user": {
                    "name": "João",
                    "address": {
                        "street": "Rua A",
                        "city": "SP"
                    }
                }
            }
        }
        
        request2 = {
            "method": "POST",
            "path": "/api/v1/users",
            "query": {},
            "body": {
                "user": {
                    "address": {
                        "city": "SP",
                        "street": "Rua A"
                    },
                    "name": "João"
                }
            }
        }
        
        hash1 = self.deduplicator.generate_hash(request1)
        hash2 = self.deduplicator.generate_hash(request2)
        
        assert hash1 == hash2
    
    def test_generate_hash_arrays(self):
        """Testa hash com arrays."""
        request1 = {
            "method": "POST",
            "path": "/api/v1/users",
            "query": {},
            "body": {
                "tags": ["python", "api", "web"],
                "numbers": [1, 2, 3]
            }
        }
        
        request2 = {
            "method": "POST",
            "path": "/api/v1/users",
            "query": {},
            "body": {
                "numbers": [1, 2, 3],
                "tags": ["python", "api", "web"]
            }
        }
        
        hash1 = self.deduplicator.generate_hash(request1)
        hash2 = self.deduplicator.generate_hash(request2)
        
        assert hash1 == hash2
    
    def test_generate_hash_array_order_matters(self):
        """Testa se a ordem dos elementos no array afeta o hash."""
        request1 = {
            "method": "POST",
            "path": "/api/v1/users",
            "query": {},
            "body": {
                "tags": ["python", "api", "web"]
            }
        }
        
        request2 = {
            "method": "POST",
            "path": "/api/v1/users",
            "query": {},
            "body": {
                "tags": ["api", "python", "web"]
            }
        }
        
        hash1 = self.deduplicator.generate_hash(request1)
        hash2 = self.deduplicator.generate_hash(request2)
        
        # A ordem dos elementos no array deve afetar o hash
        assert hash1 != hash2
    
    def test_generate_hash_missing_fields(self):
        """Testa hash com campos opcionais ausentes."""
        request1 = {
            "method": "GET",
            "path": "/api/v1/users"
        }
        
        request2 = {
            "method": "GET",
            "path": "/api/v1/users",
            "query": {},
            "body": {}
        }
        
        request3 = {
            "method": "GET",
            "path": "/api/v1/users",
            "query": None,
            "body": None
        }
        
        hash1 = self.deduplicator.generate_hash(request1)
        hash2 = self.deduplicator.generate_hash(request2)
        hash3 = self.deduplicator.generate_hash(request3)
        
        # Todos devem gerar o mesmo hash
        assert hash1 == hash2 == hash3
    
    def test_generate_hash_large_body(self):
        """Testa hash com body grande (teste de truncamento)."""
        # Criar um body grande (maior que 1KB)
        large_body = {
            "data": "x" * 2000,  # 2KB de dados
            "items": [{"id": i, "name": f"item_{i}"} for i in range(100)]
        }
        
        request = {
            "method": "POST",
            "path": "/api/v1/data",
            "query": {},
            "body": large_body
        }
        
        hash_result = self.deduplicator.generate_hash(request)
        
        # Deve gerar um hash válido mesmo com body grande
        assert len(hash_result) == 64
        assert isinstance(hash_result, str)
    
    def test_is_duplicate_new_request(self):
        """Testa se uma nova request não é considerada duplicata."""
        request = {
            "method": "GET",
            "path": "/api/v1/users",
            "query": {"page": "1"},
            "body": {}
        }
        
        is_duplicate = self.deduplicator.is_duplicate(request)
        
        assert is_duplicate is False
    
    def test_is_duplicate_same_request_twice(self):
        """Testa se a mesma request é considerada duplicata na segunda vez."""
        request = {
            "method": "GET",
            "path": "/api/v1/users",
            "query": {"page": "1"},
            "body": {}
        }
        
        # Primeira vez - não é duplicata
        is_duplicate1 = self.deduplicator.is_duplicate(request)
        assert is_duplicate1 is False
        
        # Segunda vez - é duplicata
        is_duplicate2 = self.deduplicator.is_duplicate(request)
        assert is_duplicate2 is True
    
    def test_is_duplicate_similar_but_different_requests(self):
        """Testa se requests similares mas diferentes não são consideradas duplicatas."""
        request1 = {
            "method": "GET",
            "path": "/api/v1/users",
            "query": {"page": "1"},
            "body": {}
        }
        
        request2 = {
            "method": "GET",
            "path": "/api/v1/users",
            "query": {"page": "2"},  # Página diferente
            "body": {}
        }
        
        # Primeira request
        is_duplicate1 = self.deduplicator.is_duplicate(request1)
        assert is_duplicate1 is False
        
        # Segunda request (diferente)
        is_duplicate2 = self.deduplicator.is_duplicate(request2)
        assert is_duplicate2 is False
        
        # Primeira request novamente (duplicata)
        is_duplicate3 = self.deduplicator.is_duplicate(request1)
        assert is_duplicate3 is True
    
    def test_cache_size_limit(self):
        """Testa se o cache respeita o limite de tamanho."""
        # Configurar um deduplicator com cache pequeno
        small_deduplicator = RequestDeduplicator(cache_size=3)
        
        requests = []
        for i in range(5):
            request = {
                "method": "GET",
                "path": f"/api/v1/users/{i}",
                "query": {},
                "body": {}
            }
            requests.append(request)
        
        # Adicionar 5 requests diferentes
        for request in requests:
            is_duplicate = small_deduplicator.is_duplicate(request)
            assert is_duplicate is False
        
        # O cache deve ter apenas 3 itens (os mais recentes)
        assert len(small_deduplicator.seen_hashes) <= 3
        
        # As primeiras requests devem ter sido removidas do cache
        # então não serão mais consideradas duplicatas
        is_duplicate_first = small_deduplicator.is_duplicate(requests[0])
        assert is_duplicate_first is False  # Não está mais no cache
        
        # As últimas requests ainda devem estar no cache
        is_duplicate_last = small_deduplicator.is_duplicate(requests[-1])
        assert is_duplicate_last is True  # Ainda está no cache
    
    def test_hash_consistency(self):
        """Testa se o hash é consistente entre múltiplas execuções."""
        request = {
            "method": "POST",
            "path": "/api/v1/users",
            "query": {"sort": "name", "page": "1"},
            "body": {
                "user": {
                    "name": "João",
                    "age": 30,
                    "tags": ["python", "api"]
                }
            }
        }
        
        # Gerar hash múltiplas vezes
        hashes = []
        for _ in range(10):
            hash_result = self.deduplicator.generate_hash(request)
            hashes.append(hash_result)
        
        # Todos os hashes devem ser iguais
        assert len(set(hashes)) == 1
        assert all(h == hashes[0] for h in hashes)
    
    def test_special_characters_in_data(self):
        """Testa hash com caracteres especiais."""
        request = {
            "method": "POST",
            "path": "/api/v1/users",
            "query": {"search": "joão & maria"},
            "body": {
                "name": "José da Silva",
                "description": "Usuário com acentos: ção, ã, é, ü",
                "symbols": "!@#$%^&*()_+-=[]{}|;':\",./<>?",
                "unicode": "🚀 🎉 ✨"
            }
        }
        
        hash_result = self.deduplicator.generate_hash(request)
        
        # Deve gerar um hash válido
        assert len(hash_result) == 64
        assert isinstance(hash_result, str)
        
        # Hash deve ser consistente
        hash_result2 = self.deduplicator.generate_hash(request)
        assert hash_result == hash_result2
    
    def test_none_and_empty_values(self):
        """Testa hash com valores None e vazios."""
        request1 = {
            "method": "GET",
            "path": "/api/v1/users",
            "query": None,
            "body": None
        }
        
        request2 = {
            "method": "GET",
            "path": "/api/v1/users",
            "query": {},
            "body": {}
        }
        
        request3 = {
            "method": "GET",
            "path": "/api/v1/users",
            "query": "",
            "body": ""
        }
        
        hash1 = self.deduplicator.generate_hash(request1)
        hash2 = self.deduplicator.generate_hash(request2)
        hash3 = self.deduplicator.generate_hash(request3)
        
        # Todos devem gerar o mesmo hash
        assert hash1 == hash2 == hash3