"""
Utilitários para manipulação de arquivos.
"""
import os
import hashlib
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

def ensure_directory_exists(directory_path: str) -> None:
    """
    Garante que um diretório exista, criando-o se necessário.
    
    Args:
        directory_path: Caminho do diretório a ser verificado/criado
    """
    if not os.path.exists(directory_path):
        try:
            os.makedirs(directory_path)
            logger.info(f"Diretório criado: {directory_path}")
        except OSError as e:
            logger.error(f"Erro ao criar diretório {directory_path}: {e}")
            raise

def file_exists(file_path: str) -> bool:
    """
    Verifica se um arquivo existe.
    
    Args:
        file_path: Caminho do arquivo a ser verificado
        
    Returns:
        bool: True se o arquivo existir, False caso contrário
    """
    return os.path.isfile(file_path)

def get_file_extension(file_path: str) -> str:
    """
    Obtém a extensão de um arquivo.
    
    Args:
        file_path: Caminho do arquivo
        
    Returns:
        str: Extensão do arquivo (incluindo o ponto)
    """
    _, extension = os.path.splitext(file_path)
    return extension.lower()

def generate_unique_filename(base_path: str, url: str, prefix: str = "file", 
                            extension: str = "") -> str:
    """
    Gera um nome de arquivo único baseado na URL.
    
    Args:
        base_path: Diretório base onde o arquivo será salvo
        url: URL de origem do arquivo
        prefix: Prefixo para o nome do arquivo
        extension: Extensão do arquivo (se estiver vazio, tentará extrair da URL)
        
    Returns:
        str: Caminho completo para o arquivo
    """
    # Se não for fornecida uma extensão, tenta extrair da URL
    if not extension:
        extension = get_file_extension(url)
        
    # Gera um hash da URL para garantir unicidade
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    
    # Cria o nome do arquivo
    filename = f"{prefix}-{url_hash}{extension}"
    
    # Retorna o caminho completo
    return os.path.join(base_path, filename)

def list_files_in_directory(directory_path: str, 
                          extensions: Optional[List[str]] = None) -> List[str]:
    """
    Lista todos os arquivos em um diretório, opcionalmente filtrando por extensão.
    
    Args:
        directory_path: Caminho do diretório a ser listado
        extensions: Lista de extensões para filtrar (ex: ['.jpg', '.png'])
        
    Returns:
        List[str]: Lista de caminhos completos dos arquivos
    """
    if not os.path.exists(directory_path):
        logger.warning(f"Diretório não encontrado: {directory_path}")
        return []
        
    files = []
    
    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)
        
        if os.path.isfile(file_path):
            if extensions:
                # Filtra por extensão
                if get_file_extension(filename) in extensions:
                    files.append(file_path)
            else:
                # Sem filtro de extensão
                files.append(file_path)
                
    return files

def get_file_size(file_path: str) -> int:
    """
    Obtém o tamanho de um arquivo em bytes.
    
    Args:
        file_path: Caminho do arquivo
        
    Returns:
        int: Tamanho do arquivo em bytes
    """
    try:
        return os.path.getsize(file_path)
    except OSError as e:
        logger.error(f"Erro ao obter tamanho do arquivo {file_path}: {e}")
        return 0