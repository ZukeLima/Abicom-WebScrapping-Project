"""
Implementação específica de scraper para o site da Abicom.
"""
import logging
import os
import time
from typing import List, Optional, Set
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
        
        # Procura por links para posts
        post_links = []
        
        # Adaptação específica para o site da Abicom
        # Tenta localizar o container principal de posts
        main_container = soup.find('main', id='main') or soup.find('div', class_='content-area') or soup
        
        # Localizando possivelmente artigos ou posts
        articles = main_container.find_all(['article', 'div'], class_=['post', 'article', 'entry'])
        
        if articles:
            for article in articles:
                # Procura o link no cabeçalho ou em elementos com classe relacionada a título
                header = article.find(['h1', 'h2', 'h3', 'h4'], class_=['entry-title', 'post-title'])
                if header:
                    link = header.find('a', href=True)
                    if link and link['href']:
                        post_links.append(link['href'])
                else:
                    # Se não encontrou no cabeçalho, procura em qualquer link que pareça ser o principal
                    links = article.find_all('a', href=True)
                    for link in links:
                        href = link['href']
                        # Filtra links que parecem ser de categorias, tags, etc.
                        if not any(x in href for x in ['/categoria/', '/category/', '/tag/', '/author/', '/page/']):
                            post_links.append(href)
                            break  # Pega apenas o primeiro link relevante por artigo
        
        # Se não encontrou nada usando a abordagem acima, tenta uma abordagem mais genérica
        if not post_links:
            # Procura todos os links que sejam títulos ou que estão em elementos com classe de título
            title_links = soup.find_all('a', class_=['entry-title', 'post-title']) or soup.find_all('a', {'rel': 'bookmark'})
            
            for link in title_links:
                if link.get('href'):
                    post_links.append(link['href'])
        
        # Se ainda não encontrou nada, tenta encontrar quaisquer links que pareçam ser de posts
        if not post_links:
            all_links = soup.find_all('a', href=True)
            base_url = page_url.split('/categoria/')[0] if '/categoria/' in page_url else page_url.split('/page/')[0]
            
            for link in all_links:
                href = link['href']
                
                # Ignora links de navegação, categorias, etc.
                if any(x in href for x in ['/categoria/', '/category/', '/tag/', '/author/', '#']):
                    continue
                    
                # Verifica se o link parece ser um post (começa com a base URL do site)
                if href.startswith(base_url) and href != page_url and '/page/' not in href:
                    # Verifica se tem texto que sugere ser um título de post
                    if link.text and len(link.text.strip()) > 10:
                        post_links.append(href)
        
        # Normaliza os links e remove duplicatas
        normalized_links = []
        seen_links = set()
        
        for link in post_links:
            # Normaliza a URL
            full_url = normalize_url(link, page_url)
            
            # Evita duplicatas e links para páginas de listagem
            if full_url not in seen_links and not any(x in full_url for x in ['/page/', '/categoria/', '/category/']):
                seen_links.add(full_url)
                normalized_links.append(full_url)
        
        logger.info(f"Encontrados {len(normalized_links)} links de posts na página {page_url}")
        
        # Imprime os links encontrados para debugging
        for i, link in enumerate(normalized_links):
            logger.debug(f"  Post {i+1}: {link}")
            
        return normalized_links
    
    def extract_images_from_post(self, post_url: str) -> List[Image]:
        """
        Extrai imagens de um post individual.
        
        Args:
            post_url: URL do post
            
        Returns:
            List[Image]: Lista de objetos Image encontrados
        """
        # Verifica se o post já foi visitado
        if post_url in self.visited_posts:
            logger.debug(f"Post já visitado: {post_url}")
            return []
            
        # Verifica se a URL parece ser de uma página de listagem e não de um post individual
        # Ignoramos páginas de listagem para evitar baixar imagens incorretas
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
        # Geralmente o conteúdo está em uma div com classe específica
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
        
        images = []
        
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
                logger.debug(f"Ignorando imagem que parece ser um elemento de UI: {img_url}")
                continue
                
            # Cria o objeto Image
            image = Image(
                url=img_url,
                source_url=post_url,
                file_extension=extension
            )
            
            images.append(image)
            
        logger.info(f"Encontradas {len(images)} imagens no post {post_url}")
        return images
        
    def extract_images_from_page(self, page_url: str) -> List[Image]:
        """
        Extrai imagens de uma página de listagem e seus posts.
        
        Args:
            page_url: URL da página de listagem
            
        Returns:
            List[Image]: Lista de objetos Image encontrados
        """
        all_images = []
        
        # 1. Extrai links para posts da página de listagem
        post_links = self.extract_post_links(page_url)
        
        # 2. Para cada post, extrai as imagens
        for post_url in post_links:
            # Extrai imagens do post
            post_images = self.extract_images_from_post(post_url)
            all_images.extend(post_images)
            
            # Pausa entre requisições
            if SLEEP_BETWEEN_REQUESTS > 0:
                time.sleep(SLEEP_BETWEEN_REQUESTS)
                
        logger.info(f"Total de {len(all_images)} imagens encontradas nos posts da página {page_url}")
        return all_images