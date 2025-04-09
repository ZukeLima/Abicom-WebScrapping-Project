"""
Serviço para manipulação de imagens.
"""
import os
import logging
from typing import Set, List, Optional
from datetime import datetime
from src.models.image import Image
from src.services.http_client import HttpClient
from src.utils.file_utils import file_exists, ensure_directory_exists
from src.utils.url_utils import get_url_extension
from src.config import OUTPUT_DIR

logger = logging.getLogger(__name__)

class ImageService:
    """
    Serviço para gerenciar o download e armazenamento de imagens.
    """
    
    def __init__(self, output_dir: str = OUTPUT_DIR):
        """
        Inicializa o serviço de imagens.
        
        Args:
            output_dir: Diretório onde as imagens serão salvas
        """
        self.output_dir = output_dir
        ensure_directory_exists(output_dir)
        self.downloaded_urls: Set[str] = set()
        self.http_client = HttpClient()
        
    def get_image_path(self, image: Image) -> str:
        """
        Gera o caminho para salvar a imagem baseado na data atual.
        
        Args:
            image: Objeto de imagem
            
        Returns:
            str: Caminho completo do arquivo
        """
        today = datetime.now()
        filename = f"ppi-{today.strftime('%d-%m-%Y')}{image.file_extension}"
        return os.path.join(self.output_dir, filename)
    
    def is_already_downloaded(self, url: str) -> bool:
        """
        Verifica se uma imagem já foi baixada.
        
        Args:
            url: URL da imagem
            
        Returns:
            bool: True se a imagem já foi baixada, False caso contrário
        """
        # Verifica na memória
        if url in self.downloaded_urls:
            return True
            
        # Verifica se existe no sistema de arquivos
        date_format = "%d-%m-%Y"
        today = datetime.now()
        today_str = today.strftime(date_format)
        
        # Gera o caminho esperado para a imagem
        expected_filename = f"ppi-{today_str}{get_url_extension(url)}"
        expected_path = os.path.join(self.output_dir, expected_filename)
        
        return file_exists(expected_path)
    
    def download_image(self, image: Image) -> bool:
        """
        Baixa uma imagem para o disco.
        
        Args:
            image: Objeto de imagem
            
        Returns:
            bool: True se o download for bem-sucedido, False caso contrário
        """
        # Verifica se a imagem já foi baixada
        if self.is_already_downloaded(image.url):
            logger.info(f"Imagem já baixada: {image.url}")
            return False
            
        # Gera o caminho de destino
        output_path = self.get_image_path(image)
        
        # Realiza o download
        download_success = self.http_client.download_file(image.url, output_path)
        
        if download_success:
            # Atualiza o caminho salvo na imagem
            image.saved_path = output_path
            # Adiciona à lista de URLs baixadas
            self.downloaded_urls.add(image.url)
            logger.info(f"Imagem baixada: {image.url} -> {output_path}")
            return True
        else:
            logger.error(f"Falha ao baixar imagem: {image.url}")
            return False
            
    def process_images(self, images: List[Image]) -> int:
        """
        Processa uma lista de imagens, baixando aquelas que ainda não foram baixadas.
        
        Args:
            images: Lista de objetos Image
            
        Returns:
            int: Número de imagens baixadas com sucesso
        """
        download_count = 0
        
        for image in images:
            if self.download_image(image):
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