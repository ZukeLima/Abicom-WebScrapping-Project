"""
Classe base para scrapers.
"""
import abc
import time
import logging
from typing import List, Optional, Set, Generator
from src.models.image import Image
from src.services.http_client import HttpClient
from src.services.image_service import ImageService
from src.config import SLEEP_BETWEEN_REQUESTS, SLEEP_BETWEEN_PAGES

logger = logging.getLogger(__name__)

class BaseScraper(abc.ABC):
    """
    Classe base abstrata para implementações de scrapers.
    """
    
    def __init__(self, base_url: str, http_client: Optional[HttpClient] = None, 
                image_service: Optional[ImageService] = None):
        """
        Inicializa o scraper base.
        
        Args:
            base_url: URL base para o scraping
            http_client: Cliente HTTP opcional
            image_service: Serviço de imagens opcional
        """
        self.base_url = base_url
        
        # Usa os serviços fornecidos ou cria novos
        self.http_client = http_client if http_client else HttpClient()
        self.image_service = image_service if image_service else ImageService()
        
        # Conjunto para controlar URLs já visitadas
        self.visited_urls: Set[str] = set()
        
    @abc.abstractmethod
    def build_page_url(self, page_num: int) -> str:
        """
        Constrói a URL para uma página específica.
        
        Args:
            page_num: Número da página
            
        Returns:
            str: URL completa da página
        """
        pass
        
    @abc.abstractmethod
    def extract_images_from_page(self, page_url: str) -> List[Image]:
        """
        Extrai imagens de uma página.
        
        Args:
            page_url: URL da página
            
        Returns:
            List[Image]: Lista de objetos Image encontrados
        """
        pass
        
    def scrape_page(self, page_url: str) -> List[Image]:
        """
        Realiza o scraping de uma página.
        
        Args:
            page_url: URL da página
            
        Returns:
            List[Image]: Lista de objetos Image encontrados
        """
        # Verifica se a URL já foi visitada
        if page_url in self.visited_urls:
            logger.debug(f"Página já visitada: {page_url}")
            return []
            
        # Marca a URL como visitada
        self.visited_urls.add(page_url)
        
        # Extrai imagens da página
        images = self.extract_images_from_page(page_url)
        
        # Pausa entre requisições
        if SLEEP_BETWEEN_REQUESTS > 0:
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            
        return images
        
    def scrape_pages(self, start_page: int = 1, max_pages: int = 10) -> Generator[List[Image], None, None]:
        """
        Realiza o scraping de múltiplas páginas.
        
        Args:
            start_page: Página inicial
            max_pages: Número máximo de páginas
            
        Yields:
            List[Image]: Lista de objetos Image encontrados em cada página
        """
        for page_num in range(start_page, start_page + max_pages):
            # Constrói a URL da página
            page_url = self.build_page_url(page_num)
            
            # Realiza o scraping da página
            logger.info(f"Realizando scraping da página {page_num}: {page_url}")
            images = self.scrape_page(page_url)
            
            # Verifica se alguma imagem foi encontrada
            if images:
                logger.info(f"Encontradas {len(images)} imagens na página {page_num}")
                yield images
            else:
                logger.warning(f"Nenhuma imagem encontrada na página {page_num}")
                
            # Pausa entre páginas
            if SLEEP_BETWEEN_PAGES > 0 and page_num < start_page + max_pages - 1:
                time.sleep(SLEEP_BETWEEN_PAGES)
                
    def run(self, start_page: int = 1, max_pages: int = 10) -> int:
        """
        Executa o scraper.
        
        Args:
            start_page: Página inicial
            max_pages: Número máximo de páginas
            
        Returns:
            int: Número total de imagens baixadas
        """
        total_downloads = 0
        
        try:
            # Realiza o scraping das páginas
            for images in self.scrape_pages(start_page, max_pages):
                # Processa as imagens
                downloads = self.image_service.process_images(images)
                total_downloads += downloads
                
            logger.info(f"Total de {total_downloads} imagens baixadas")
            return total_downloads
            
        finally:
            # Fecha os recursos
            self.close()
            
    def close(self):
        """
        Fecha recursos utilizados pelo scraper.
        """
        self.http_client.close()
        self.image_service.close()
        
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