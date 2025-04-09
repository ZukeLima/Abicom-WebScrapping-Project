"""
Serviço para download de arquivos.
"""
import os
import logging
from typing import Dict, Optional, List, Set
from src.services.http_client import HttpClient
from src.utils.file_utils import ensure_directory_exists, file_exists
from src.utils.url_utils import is_image_url
from src.models.image import Image

logger = logging.getLogger(__name__)

class Downloader:
    """
    Serviço para gerenciar o download de arquivos.
    """
    
    def __init__(self, output_dir: str, http_client: Optional[HttpClient] = None):
        """
        Inicializa o serviço de download.
        
        Args:
            output_dir: Diretório onde os arquivos serão salvos
            http_client: Cliente HTTP opcional
        """
        self.output_dir = output_dir
        ensure_directory_exists(output_dir)
        
        # Usa o cliente HTTP fornecido ou cria um novo
        self.http_client = http_client if http_client else HttpClient()
        
        # Conjunto para controlar URLs já baixadas
        self.downloaded_urls: Set[str] = set()
        
    def download_file(self, url: str, filename: str) -> bool:
        """
        Baixa um arquivo para o disco.
        
        Args:
            url: URL do arquivo
            filename: Nome do arquivo de saída
            
        Returns:
            bool: True se o download for bem-sucedido, False caso contrário
        """
        # Constrói o caminho completo do arquivo
        output_path = os.path.join(self.output_dir, filename)
        
        # Verifica se o arquivo já existe
        if file_exists(output_path):
            logger.info(f"Arquivo já existe: {output_path}")
            self.downloaded_urls.add(url)
            return True
            
        # Baixa o arquivo
        download_success = self.http_client.download_file(url, output_path)
        
        if download_success:
            # Adiciona à lista de URLs baixadas
            self.downloaded_urls.add(url)
            logger.info(f"Arquivo baixado: {url} -> {output_path}")
            return True
        else:
            logger.error(f"Falha ao baixar arquivo: {url}")
            return False
            
    def is_already_downloaded(self, url: str) -> bool:
        """
        Verifica se um arquivo já foi baixado.
        
        Args:
            url: URL do arquivo
            
        Returns:
            bool: True se o arquivo já foi baixado, False caso contrário
        """
        return url in self.downloaded_urls
        
    def download_images(self, images: List[Image]) -> int:
        """
        Baixa uma lista de imagens.
        
        Args:
            images: Lista de objetos Image
            
        Returns:
            int: Número de imagens baixadas com sucesso
        """
        download_count = 0
        
        for image in images:
            # Pula imagens já baixadas
            if self.is_already_downloaded(image.url):
                logger.debug(f"Imagem já baixada: {image.url}")
                continue
                
            # Gera o nome do arquivo
            today_str = image.found_date.strftime('%d-%m-%Y')
            filename = f"ppi-{today_str}{image.file_extension}"
            
            # Baixa a imagem
            if self.download_file(image.url, filename):
                image.saved_path = os.path.join(self.output_dir, filename)
                download_count += 1
                
        return download_count
        
    def close(self):
        """
        Fecha recursos utilizados pelo serviço.
        """
        self.http_client.close()
        
    def __enter__(self):
        """
        Suporte para uso com 'with'.
        """
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Fecha os recursos ao sair do bloco 'with'.
        """
        self.close()