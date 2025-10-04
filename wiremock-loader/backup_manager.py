"""
Gerenciador de backup para mappings WireMock
Faz backup dos mappings para recuperação e auditoria
"""
import os
import json
import asyncio
import aiofiles
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import structlog
from pathlib import Path
import gzip
import hashlib

logger = structlog.get_logger(__name__)


class BackupManager:
    """Gerenciador de backup para mappings WireMock"""
    
    def __init__(
        self,
        backup_path: str = "/app/data/backups",
        retention_days: int = 7,
        compress_backups: bool = True,
        max_backup_size_mb: int = 100
    ):
        self.backup_path = Path(backup_path)
        self.retention_days = retention_days
        self.compress_backups = compress_backups
        self.max_backup_size_mb = max_backup_size_mb
        
        # Estatísticas
        self.stats = {
            'backups_created': 0,
            'backups_failed': 0,
            'backups_cleaned': 0,
            'total_size_bytes': 0,
            'last_backup': None,
            'last_cleanup': None
        }
        
        # Criar diretório de backup se não existir
        self.backup_path.mkdir(parents=True, exist_ok=True)
    
    async def backup_mapping(self, mapping: Dict[str, Any]) -> bool:
        """Faz backup de um mapping individual"""
        try:
            mapping_id = mapping.get('id', 'unknown')
            timestamp = datetime.utcnow()
            
            # Criar estrutura de diretórios por data
            date_dir = self.backup_path / timestamp.strftime('%Y/%m/%d')
            date_dir.mkdir(parents=True, exist_ok=True)
            
            # Nome do arquivo com timestamp
            filename = f"{mapping_id}_{timestamp.strftime('%H%M%S_%f')}.json"
            if self.compress_backups:
                filename += ".gz"
            
            file_path = date_dir / filename
            
            # Preparar dados para backup
            backup_data = {
                'mapping': mapping,
                'backup_metadata': {
                    'backup_timestamp': timestamp.isoformat(),
                    'mapping_id': mapping_id,
                    'backup_version': '1.0'
                }
            }
            
            # Escrever arquivo
            if self.compress_backups:
                await self._write_compressed_backup(file_path, backup_data)
            else:
                await self._write_backup(file_path, backup_data)
            
            # Atualizar estatísticas
            file_size = file_path.stat().st_size
            self.stats['backups_created'] += 1
            self.stats['total_size_bytes'] += file_size
            self.stats['last_backup'] = timestamp.isoformat()
            
            logger.debug("Backup de mapping criado", 
                        mapping_id=mapping_id, 
                        file_path=str(file_path),
                        size_bytes=file_size)
            
            return True
            
        except Exception as e:
            self.stats['backups_failed'] += 1
            logger.error("Erro ao fazer backup de mapping", 
                        mapping_id=mapping.get('id', 'unknown'), 
                        error=str(e))
            return False
    
    async def backup_batch(self, mappings: List[Dict[str, Any]]) -> int:
        """Faz backup de múltiplos mappings em lote"""
        if not mappings:
            return 0
        
        timestamp = datetime.utcnow()
        
        try:
            # Criar estrutura de diretórios
            date_dir = self.backup_path / timestamp.strftime('%Y/%m/%d')
            date_dir.mkdir(parents=True, exist_ok=True)
            
            # Nome do arquivo batch
            batch_filename = f"batch_{timestamp.strftime('%H%M%S_%f')}.json"
            if self.compress_backups:
                batch_filename += ".gz"
            
            file_path = date_dir / batch_filename
            
            # Preparar dados do batch
            batch_data = {
                'mappings': mappings,
                'batch_metadata': {
                    'backup_timestamp': timestamp.isoformat(),
                    'mapping_count': len(mappings),
                    'backup_version': '1.0',
                    'backup_type': 'batch'
                }
            }
            
            # Escrever arquivo
            if self.compress_backups:
                await self._write_compressed_backup(file_path, batch_data)
            else:
                await self._write_backup(file_path, batch_data)
            
            # Atualizar estatísticas
            file_size = file_path.stat().st_size
            self.stats['backups_created'] += 1
            self.stats['total_size_bytes'] += file_size
            self.stats['last_backup'] = timestamp.isoformat()
            
            logger.info("Backup em lote criado", 
                       mapping_count=len(mappings),
                       file_path=str(file_path),
                       size_bytes=file_size)
            
            return len(mappings)
            
        except Exception as e:
            self.stats['backups_failed'] += 1
            logger.error("Erro ao fazer backup em lote", 
                        mapping_count=len(mappings), 
                        error=str(e))
            return 0
    
    async def _write_backup(self, file_path: Path, data: Dict[str, Any]):
        """Escreve backup não comprimido"""
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2, ensure_ascii=False))
    
    async def _write_compressed_backup(self, file_path: Path, data: Dict[str, Any]):
        """Escreve backup comprimido"""
        json_data = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        compressed_data = gzip.compress(json_data.encode('utf-8'))
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(compressed_data)
    
    async def restore_mapping(self, backup_file: str) -> Optional[Dict[str, Any]]:
        """Restaura um mapping de um arquivo de backup"""
        try:
            file_path = Path(backup_file)
            if not file_path.exists():
                logger.error("Arquivo de backup não encontrado", file_path=backup_file)
                return None
            
            # Ler arquivo
            if file_path.suffix == '.gz':
                data = await self._read_compressed_backup(file_path)
            else:
                data = await self._read_backup(file_path)
            
            # Extrair mapping
            if 'mapping' in data:
                return data['mapping']
            elif 'mappings' in data and data['mappings']:
                # Se for um batch, retornar o primeiro mapping
                return data['mappings'][0]
            else:
                logger.error("Formato de backup inválido", file_path=backup_file)
                return None
                
        except Exception as e:
            logger.error("Erro ao restaurar mapping", 
                        file_path=backup_file, error=str(e))
            return None
    
    async def restore_batch(self, backup_file: str) -> List[Dict[str, Any]]:
        """Restaura múltiplos mappings de um arquivo de backup"""
        try:
            file_path = Path(backup_file)
            if not file_path.exists():
                logger.error("Arquivo de backup não encontrado", file_path=backup_file)
                return []
            
            # Ler arquivo
            if file_path.suffix == '.gz':
                data = await self._read_compressed_backup(file_path)
            else:
                data = await self._read_backup(file_path)
            
            # Extrair mappings
            if 'mappings' in data:
                return data['mappings']
            elif 'mapping' in data:
                # Se for um mapping individual, retornar como lista
                return [data['mapping']]
            else:
                logger.error("Formato de backup inválido", file_path=backup_file)
                return []
                
        except Exception as e:
            logger.error("Erro ao restaurar batch", 
                        file_path=backup_file, error=str(e))
            return []
    
    async def _read_backup(self, file_path: Path) -> Dict[str, Any]:
        """Lê backup não comprimido"""
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            return json.loads(content)
    
    async def _read_compressed_backup(self, file_path: Path) -> Dict[str, Any]:
        """Lê backup comprimido"""
        async with aiofiles.open(file_path, 'rb') as f:
            compressed_data = await f.read()
            json_data = gzip.decompress(compressed_data).decode('utf-8')
            return json.loads(json_data)
    
    async def list_backups(self, mapping_id: Optional[str] = None, 
                          days: int = 7) -> List[Dict[str, Any]]:
        """Lista backups disponíveis"""
        backups = []
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            # Percorrer estrutura de diretórios
            for year_dir in self.backup_path.iterdir():
                if not year_dir.is_dir() or not year_dir.name.isdigit():
                    continue
                
                for month_dir in year_dir.iterdir():
                    if not month_dir.is_dir() or not month_dir.name.isdigit():
                        continue
                    
                    for day_dir in month_dir.iterdir():
                        if not day_dir.is_dir() or not day_dir.name.isdigit():
                            continue
                        
                        # Verificar se está dentro do período
                        try:
                            dir_date = datetime.strptime(
                                f"{year_dir.name}-{month_dir.name}-{day_dir.name}",
                                "%Y-%m-%d"
                            )
                            if dir_date < cutoff_date:
                                continue
                        except ValueError:
                            continue
                        
                        # Listar arquivos no diretório
                        for backup_file in day_dir.iterdir():
                            if not backup_file.is_file():
                                continue
                            
                            # Filtrar por mapping_id se especificado
                            if mapping_id and not backup_file.name.startswith(mapping_id):
                                continue
                            
                            # Obter informações do arquivo
                            stat = backup_file.stat()
                            backup_info = {
                                'file_path': str(backup_file),
                                'file_name': backup_file.name,
                                'size_bytes': stat.st_size,
                                'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                                'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                'is_compressed': backup_file.suffix == '.gz',
                                'is_batch': 'batch_' in backup_file.name
                            }
                            
                            # Tentar extrair mapping_id do nome do arquivo
                            if not backup_info['is_batch']:
                                parts = backup_file.stem.split('_')
                                if len(parts) >= 2:
                                    backup_info['mapping_id'] = parts[0]
                            
                            backups.append(backup_info)
            
            # Ordenar por data de criação (mais recente primeiro)
            backups.sort(key=lambda x: x['created_at'], reverse=True)
            
            return backups
            
        except Exception as e:
            logger.error("Erro ao listar backups", error=str(e))
            return []
    
    async def cleanup_old_backups(self) -> int:
        """Remove backups antigos baseado na política de retenção"""
        if self.retention_days <= 0:
            return 0
        
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
        removed_count = 0
        
        try:
            # Percorrer estrutura de diretórios
            for year_dir in self.backup_path.iterdir():
                if not year_dir.is_dir() or not year_dir.name.isdigit():
                    continue
                
                for month_dir in year_dir.iterdir():
                    if not month_dir.is_dir() or not month_dir.name.isdigit():
                        continue
                    
                    for day_dir in month_dir.iterdir():
                        if not day_dir.is_dir() or not day_dir.name.isdigit():
                            continue
                        
                        # Verificar se o diretório é antigo
                        try:
                            dir_date = datetime.strptime(
                                f"{year_dir.name}-{month_dir.name}-{day_dir.name}",
                                "%Y-%m-%d"
                            )
                            
                            if dir_date < cutoff_date:
                                # Remover todos os arquivos no diretório
                                for backup_file in day_dir.iterdir():
                                    if backup_file.is_file():
                                        file_size = backup_file.stat().st_size
                                        backup_file.unlink()
                                        removed_count += 1
                                        self.stats['total_size_bytes'] -= file_size
                                
                                # Remover diretório vazio
                                try:
                                    day_dir.rmdir()
                                except OSError:
                                    pass  # Diretório não vazio
                                
                        except ValueError:
                            continue
                
                # Tentar remover diretórios de mês vazios
                try:
                    for month_dir in year_dir.iterdir():
                        if month_dir.is_dir():
                            try:
                                month_dir.rmdir()
                            except OSError:
                                pass
                except:
                    pass
                
                # Tentar remover diretório de ano vazio
                try:
                    year_dir.rmdir()
                except OSError:
                    pass
            
            if removed_count > 0:
                self.stats['backups_cleaned'] += removed_count
                self.stats['last_cleanup'] = datetime.utcnow().isoformat()
                logger.info("Limpeza de backups executada", 
                           removed_count=removed_count,
                           retention_days=self.retention_days)
            
            return removed_count
            
        except Exception as e:
            logger.error("Erro na limpeza de backups", error=str(e))
            return 0
    
    async def get_backup_summary(self) -> Dict[str, Any]:
        """Retorna resumo dos backups"""
        try:
            total_files = 0
            total_size = 0
            oldest_backup = None
            newest_backup = None
            
            # Percorrer todos os arquivos de backup
            for backup_file in self.backup_path.rglob("*.json*"):
                if backup_file.is_file():
                    total_files += 1
                    stat = backup_file.stat()
                    total_size += stat.st_size
                    
                    file_time = datetime.fromtimestamp(stat.st_ctime)
                    if oldest_backup is None or file_time < oldest_backup:
                        oldest_backup = file_time
                    if newest_backup is None or file_time > newest_backup:
                        newest_backup = file_time
            
            return {
                'total_files': total_files,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'oldest_backup': oldest_backup.isoformat() if oldest_backup else None,
                'newest_backup': newest_backup.isoformat() if newest_backup else None,
                'retention_days': self.retention_days,
                'compress_backups': self.compress_backups
            }
            
        except Exception as e:
            logger.error("Erro ao obter resumo de backups", error=str(e))
            return {'error': str(e)}
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do backup manager"""
        return {
            **self.stats,
            'backup_path': str(self.backup_path),
            'retention_days': self.retention_days,
            'compress_backups': self.compress_backups,
            'max_backup_size_mb': self.max_backup_size_mb
        }