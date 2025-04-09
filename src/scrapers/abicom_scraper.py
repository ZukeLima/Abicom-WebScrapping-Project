"""
Implementação específica de scraper para o site da Abicom.
"""
import logging
import os
from typing import List, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from src.scrapers.base_scraper import BaseScraper
from src.models.image import Image
from src.services.http_client import HttpClient
from src.services.image_service import ImageService
from src.utils.url_utils import normalize_url, is_image_url
from src.config import BASE_URL, PAGE_PATTERN, IMAGE_EXTENSIONS

logger = logging.getLogger(__name__)

class AbicomScraper(BaseScraper):
    """
    Scraper específico para o site da Abicom, categoria PPI.
    """
    
    def __init__(self, 
                base_url: str = BASE_URL, 
                page_pattern: str = PAGE_PATTERN,
                http_client: Optional[HttpClient] = None,
                image_service: Optional[ImageService] = None):
        """
        Inicializa o scraper da Abicom.
        
        Args:
            base_url: URL base para o scraping
            page_pattern: Padrão para formação de URLs de páginas
            http_client: Cliente HTTP opcional
            image_service: Serviço de imagens opcional
        """
        super().__init__(base_url, http_client, image_service)
        self.page_pattern = page_pattern
        
    def build_page_url(self, page_num: int) -> str:
        """
        Constrói a URL para uma página específica.
        
        Args:
            page_num: Número da página
            
        Returns:
            str: URL completa da página
        """
        if page_num <= 1:
            return self.base_url
            
        # Aplica o número da página ao padrão
        page_path = self.page_pattern.format(page_num=page_num)
        
        # Constrói a URL final
        return urljoin(self.base_url, page_path)
        
    def extract_images_from_page(self, page_url: str) -> List[Image]:
        """
        Extrai imagens de uma página.
        
        Args:
            page_url: URL da página
            
        Returns:
            List[Image]: Lista de objetos Image encontrados
        """
        # Obtém o conteúdo da página
        response = self.http_client.get(page_url)
        
        if not response:
            logger.error(f"Falha ao obter a página: {page_url}")
            return []
            
        # Analisa o HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Encontra todas as tags de imagem
        img_tags = soup.find_all('img')
        
        images = []
        
        for img in img_tags:
            # Obtém a URL da imagem
            img_url = img.get('src')
            
            if not img_url:
                continue
                
            # Normaliza a URL
            img_url = normalize_url(img_url, page_url)
            
            # Verifica se é uma imagem JPG
            extension = os.path.splitext(img_url.lower())[1]
            if extension not in IMAGE_EXTENSIONS:
                continue
                
            # Cria o objeto Image
            image = Image(
                url=img_url,
                source_url=page_url,
                file_extension=extension
            )
            
            images.append(image)
            
        return images