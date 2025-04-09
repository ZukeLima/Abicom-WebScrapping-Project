"""
Implementação específica de scraper para o site da Abicom.
"""
import logging
import os
import time
import re
from typing import List, Optional, Set, Dict
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from src.scrapers.base_scraper import BaseScraper
from src.models.image import Image
from src.services.http_client import HttpClient
from src.services.image_service import ImageService
from src.utils.url_utils import normalize_url, is_image_url
from src.config import BASE_URL, PAGE_PATTERN, IMAGE_EXTENSIONS, SLEEP_BETWEEN_REQUESTS

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
        self.visited_posts: Set[str] = set()  # Para rastrear posts já visitados
        self.post_info_cache: Dict[str, Dict] = {}  # Cache de informações de posts
        
        # Pré-indexar as imagens existentes para otimizar a verificação
        self.image_service.pre_check_monthly_images()
        
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
            
        # Corrigindo para usar o formato correto de URL
        # Formato correto: https://abicom.com.br/categoria/ppi/page/2/
        if self.base_url.endswith('/'):
            return f"{self.base_url}page/{page_num}/"
        else:
            return f"{self.base_url}/page/{page_num}/"

    def extract_date_from_post_url(self, post_url: str) -> Optional[tuple]:
        """
        Extrai a data de uma URL de post.
        
        Args:
            post_url: URL do post
            
        Returns:
            Optional[tuple]: Tupla (dia, mês, ano) ou None se não encontrar
        """
        # Procura pelo padrão "ppi-DD-MM-YYYY" na URL
        import re
        pattern = r"ppi-(\d{2})-(\d{2})-(\d{4})"
        match = re.search(pattern, post_url)
        
        if match:
            day, month, year = match.groups()
            return (day, month, year)
            
        return None
        
    def should_download_post(self, post_url: str) -> bool:
        """
        Verifica se um post deve ser baixado ou pode ser pulado.
        
        Args:
            post_url: URL do post
            
        Returns:
            bool: True se o post deve ser baixado, False caso contrário
        """
        # Verifica se o post já foi visitado
        if post_url in self.visited_posts:
            logger.debug(f"Post já visitado: {post_url}")
            return False
            
        # Extrai a data do post para verificar se a imagem já existe
        date_parts = self.extract_date_from_post_url(post_url)
        
        if date_parts:
            # Cria uma imagem temporária para verificação
            day, month, year = date_parts
            dummy_image = Image(
                url="",
                source_url=post_url,
                file_extension=".jpg"  # Extensão padrão para verificação
            )
            
            # Verifica se a imagem já existe
            if self.image_service.is_already_downloaded(dummy_image):
                logger.info(f"Imagem do post {post_url} já existe. Pulando...")
                self.visited_posts.add(post_url)
                return False
                
        # Se chegou aqui, o post deve ser baixado
        return True
        
    def extract_post_links(self, page_url: str) -> List[str]:
        """
        Extrai links para posts individuais de uma página de listagem.
        
        Args:
            page_url: URL da página de listagem
            
        Returns:
            List[str]: Lista de URLs de posts individuais
        """
        # Obtém o conteúdo da página
        response = self.http_client.get(page_url)
        
        if not response:
            logger.error(f"Falha ao obter a página de listagem: {page_url}")
            return []
            
        # Analisa o HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Abordagem simplificada e direta para encontrar links da página
        post_links = []
        
        # Encontrar todos os links na página
        all_links = soup.find_all('a', href=True)
        
        # Filtrar links que parecem ser posts no site Abicom
        for link in all_links:
            href = link.get('href', '')
            
            # Verificar se o link é um post PPI específico
            # O formato típico é https://abicom.com.br/ppi/ppi-DD-MM-YYYY/
            if 'abicom.com.br/ppi/ppi-' in href and href not in post_links:
                post_links.append(href)
        
        # Se não encontrou nenhum link específico com o formato esperado,
        # tenta uma abordagem mais genérica
        if not post_links:
            # Buscar por links dentro de elementos com classe 'entry-title' ou similares
            title_links = soup.select('.entry-title a, .post-title a')
            for link in title_links:
                href = link.get('href', '')
                if href and '/categoria/' not in href and '/page/' not in href:
                    post_links.append(href)
        
        # Se ainda não encontrou, procurar links que parecem ser posts
        if not post_links:
            for link in all_links:
                href = link.get('href', '')
                # Filtrar links que parecem ser posts e não são navegação
                if (href.startswith(page_url.split('/categoria/')[0]) and 
                    '/categoria/' not in href and 
                    '/page/' not in href and
                    '/tag/' not in href and
                    len(href) > len(page_url) and
                    href != page_url):
                    post_links.append(href)
        
        # Normaliza e remove duplicados
        post_links = list(dict.fromkeys(post_links))
        
        logger.info(f"Encontrados {len(post_links)} links de posts na página {page_url}")
        
        # Log detalhado dos links encontrados
        for i, link in enumerate(post_links):
            logger.debug(f"Link {i+1}: {link}")
            
        return post_links
        
    def extract_images_from_post(self, post_url: str) -> List[Image]:
        """
        Extrai apenas a primeira imagem de um post individual.
        
        Args:
            post_url: URL do post
            
        Returns:
            List[Image]: Lista contendo apenas a primeira imagem encontrada, ou lista vazia se nenhuma for encontrada
        """
        # Verifica se o post já foi visitado
        if post_url in self.visited_posts:
            logger.debug(f"Post já visitado: {post_url}")
            return []
            
        # Verifica se a URL parece ser de uma página de listagem e não de um post individual
        ignore_patterns = ['/categoria/', '/category/', '/tag/', '/author/', '/page/']
        if any(pattern in post_url for pattern in ignore_patterns) and post_url != self.base_url:
            logger.debug(f"Ignorando URL que parece ser uma página de listagem: {post_url}")
            return []
            
        # Marca o post como visitado
        self.visited_posts.add(post_url)
        
        logger.info(f"Acessando post: {post_url}")
        
        # Obtém o conteúdo do post
        response = self.http_client.get(post_url)
        
        if not response:
            logger.error(f"Falha ao obter o post: {post_url}")
            return []
            
        # Analisa o HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Encontra o conteúdo principal do post
        content_selectors = [
            ('div', 'entry-content'),
            ('div', 'post-content'),
            ('div', 'content'),
            ('div', 'article-content'),
            ('article', None)
        ]
        
        content = None
        for tag, class_name in content_selectors:
            if class_name:
                content = soup.find(tag, class_=class_name)
            else:
                content = soup.find(tag)
                
            if content:
                break
                
        # Se não encontrou o conteúdo específico, usa o documento inteiro
        if not content:
            content = soup
            
        # Encontra todas as tags de imagem no conteúdo
        img_tags = content.find_all('img')
        
        # Procura pela primeira imagem JPG válida
        for img in img_tags:
            # Obtém a URL da imagem
            img_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            
            if not img_url:
                continue
                
            # Normaliza a URL
            img_url = normalize_url(img_url, post_url)
            
            # Verifica se é uma imagem com a extensão desejada
            extension = os.path.splitext(img_url.lower())[1]
            if extension not in IMAGE_EXTENSIONS:
                continue
                
            # Ignora imagens que parecem ser ícones, logos ou elementos de UI
            ignore_patterns = ['icon', 'logo', 'avatar', 'banner', 'header', 'footer', 'sidebar', 'thumbnail', 'placeholder']
            if any(pattern in img_url.lower() for pattern in ignore_patterns):
                continue
                
            # Encontramos a primeira imagem válida, criamos o objeto e retornamos
            image = Image(
                url=img_url,
                source_url=post_url,
                file_extension=extension
            )
            
            logger.info(f"Encontrada 1 imagem no post {post_url}")
            return [image]  # Retorna apenas a primeira imagem
            
        # Se não encontrou nenhuma imagem válida
        logger.info(f"Nenhuma imagem válida encontrada no post {post_url}")
        return []

    def extract_images_from_page(self, page_url: str) -> List[Image]:
        """
        Extrai imagens dos posts de uma página de listagem.
        
        Args:
            page_url: URL da página de listagem
            
        Returns:
            List[Image]: Lista de objetos Image encontrados (apenas a primeira imagem de cada post)
        """
        all_images = []
        
        # 1. Extrai links para posts da página de listagem
        post_links = self.extract_post_links(page_url)
        
        if not post_links:
            logger.warning(f"Nenhum link de post encontrado na página {page_url}")
            return []
            
        logger.info(f"Encontrados {len(post_links)} posts na página {page_url}")
        
        # 2. Filtra apenas os posts que precisam ser processados
        posts_to_process = []
        for post_url in post_links:
            if self.should_download_post(post_url):
                posts_to_process.append(post_url)
            else:
                logger.debug(f"Post já processado anteriormente: {post_url}")
                
        logger.info(f"De {len(post_links)} posts, {len(posts_to_process)} precisam ser processados")
        
        # 3. Para cada post não processado, extrai a primeira imagem
        for i, post_url in enumerate(posts_to_process):
            # Extrai imagens do post (apenas a primeira)
            post_images = self.extract_images_from_post(post_url)
            
            if post_images:
                all_images.extend(post_images)
                logger.debug(f"Adicionada imagem do post {i+1}/{len(posts_to_process)}: {post_url}")
            else:
                logger.debug(f"Nenhuma imagem encontrada no post {i+1}/{len(posts_to_process)}: {post_url}")
            
            # Pausa entre requisições
            if SLEEP_BETWEEN_REQUESTS > 0:
                time.sleep(SLEEP_BETWEEN_REQUESTS)
                
        # Agora o log será mais preciso - inclui apenas a primeira imagem de cada post
        total_imagens = len(all_images)
        if total_imagens > 0:
            logger.info(f"Coletadas {total_imagens} imagens dos {len(posts_to_process)} posts processados da página {page_url}")
        else:
            logger.warning(f"Nenhuma imagem coletada dos {len(posts_to_process)} posts processados da página {page_url}")
            
        return all_images