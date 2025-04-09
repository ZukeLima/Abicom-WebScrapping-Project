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
        Gera o caminho para salvar a imagem baseado no nome da página de origem.
        
        Args:
            image: Objeto de imagem
            
        Returns:
            str: Caminho completo do arquivo
        """
        # Extrai o padrão "ppi-DD-MM-YYYY" da URL, se presente
        source_url = image.source_url
        filename = None
        
        # Tenta encontrar o padrão "ppi-DD-MM-YYYY" na URL
        import re
        pattern = r"ppi-(\d{2}-\d{2}-\d{4})"
        match = re.search(pattern, source_url)
        
        if match:
            # Se encontrou o padrão, usa-o para o nome do arquivo
            date_str = match.group(1)
            filename = f"ppi-{date_str}{image.file_extension}"
        else:
            # Se não encontrou, tenta extrair a última parte significativa da URL
            path_parts = source_url.rstrip('/').split('/')
            
            # Encontra a parte mais específica que parece ser o nome do post
            for part in reversed(path_parts):
                if part and part not in ['www', 'ppi', 'categoria', 'category']:
                    # Remove extensões comuns de páginas web
                    part = re.sub(r'\.(html|php|asp|jsp)$', '', part)
                    # Se a parte começa com "ppi-", usa-a diretamente
                    if part.startswith('ppi-'):
                        filename = f"{part}{image.file_extension}"
                        break
                    # Caso contrário, adiciona o prefixo "ppi-"
                    else:
                        # Limita o tamanho da parte para evitar nomes muito longos
                        part = part[:50]
                        filename = f"ppi-{part}{image.file_extension}"
                        break
        
        # Se não conseguiu extrair um nome da URL, usa a data atual
        if not filename:
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
            
        # Como o nome do arquivo agora é baseado na URL da página e não na data atual,
        # não é mais possível verificar diretamente pelo nome esperado.
        # Verificamos apenas pelo registro em memória.
        return False
    
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