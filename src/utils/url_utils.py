"""
Utilitários para manipulação de URLs.
"""
import os
import urllib.parse
from typing import Optional, Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

def is_valid_url(url: str) -> bool:
    """
    Verifica se uma URL é válida.
    
    Args:
        url: URL a ser verificada
        
    Returns:
        bool: True se for uma URL válida, False caso contrário
    """
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def normalize_url(url: str, base_url: Optional[str] = None) -> str:
    """
    Normaliza uma URL, adicionando o esquema se ausente e lidando com URLs relativas.
    
    Args:
        url: URL a ser normalizada
        base_url: URL base para resolver URLs relativas
        
    Returns:
        str: URL normalizada
    """
    # Remove espaços no início e fim
    url = url.strip()
    
    # Se a URL for relativa e uma base_url for fornecida
    if base_url and not is_valid_url(url):
        return urllib.parse.urljoin(base_url, url)
        
    # Adiciona o esquema se estiver ausente
    if "://" not in url:
        return f"https://{url}"
        
    return url

def join_url_path(base_url: str, path: str) -> str:
    """
    Junta uma URL base com um caminho, tratando corretamente as barras.
    
    Args:
        base_url: URL base
        path: Caminho a ser adicionado
        
    Returns:
        str: URL completa
    """
    # Garante que a URL base não termina com barra
    base_url = base_url.rstrip("/")
    
    # Garante que o caminho não começa com barra
    path = path.lstrip("/")
    
    # Junta a URL base com o caminho
    return f"{base_url}/{path}"

def get_url_extension(url: str) -> str:
    """
    Obtém a extensão de um arquivo a partir de sua URL.
    
    Args:
        url: URL do arquivo
        
    Returns:
        str: Extensão do arquivo (incluindo o ponto)
    """
    parsed = urllib.parse.urlparse(url)
    path = parsed.path
    
    # Extrai a extensão do caminho
    _, extension = os.path.splitext(path)
    
    return extension.lower()

def is_image_url(url: str, extensions: List[str] = ['.jpg', '.jpeg', '.png', '.gif']) -> bool:
    """
    Verifica se uma URL aponta para uma imagem com base na extensão.
    
    Args:
        url: URL a ser verificada
        extensions: Lista de extensões de imagem válidas
        
    Returns:
        bool: True se a URL aparenta ser uma imagem, False caso contrário
    """
    extension = get_url_extension(url)
    return extension in extensions

def build_page_url(base_url: str, page_num: int, page_pattern: str = "/page/{page_num}/") -> str:
    """
    Constrói a URL para uma página específica.
    
    Args:
        base_url: URL base do site
        page_num: Número da página
        page_pattern: Padrão de formatação para páginas
        
    Returns:
        str: URL completa da página
    """
    if page_num <= 1:
        return base_url
        
    # Aplica o número da página ao padrão
    page_path = page_pattern.format(page_num=page_num)
    
    # Constrói a URL final
    return join_url_path(base_url, page_path)

def extract_domain(url: str) -> str:
    """
    Extrai o domínio de uma URL.
    
    Args:
        url: URL completa
        
    Returns:
        str: Domínio da URL
    """
    parsed = urllib.parse.urlparse(url)
    return parsed.netloc

def get_url_without_query(url: str) -> str:
    """
    Remove os parâmetros de consulta de uma URL.
    
    Args:
        url: URL completa
        
    Returns:
        str: URL sem parâmetros de consulta
    """
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse((
        parsed.scheme, 
        parsed.netloc, 
        parsed.path, 
        parsed.params, 
        '', 
        parsed.fragment
    ))