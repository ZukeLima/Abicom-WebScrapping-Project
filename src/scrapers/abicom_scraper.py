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
            
        # Aplica o número da página ao padrão
        page_path = self.page_pattern.format(page_num=page_num)
        
        # Constrói a URL final
        return urljoin(self.base_url, page_path)
    
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
        # Ajuste os seletores conforme a estrutura real do site
        post_links = []
        
        # A estrutura comum para posts é ter um container de artigo com links
        # Podemos tentar diversos seletores comuns
        
        # Tentativa 1: Procurar artigos ou posts
        articles = soup.find_all(['article', 'div'], class_=['post', 'article', 'entry'])
        
        if not articles:
            # Tentativa 2: Procurar qualquer div com título que contenha link
            articles = soup.find_all('div', class_=['entry', 'post-content', 'content'])
        
        # Se ainda não encontrou, tenta uma busca mais ampla
        if not articles:
            # Tentativa 3: Procurar cabeçalhos com links
            headers = soup.find_all(['h1', 'h2', 'h3'], class_=['entry-title', 'post-title'])
            for header in headers:
                link = header.find('a', href=True)
                if link and link['href']:
                    post_links.append(link['href'])
        else:
            # Extrai links dos artigos encontrados
            for article in articles:
                # Tenta encontrar o link no título primeiro
                title = article.find(['h1', 'h2', 'h3'], class_=['entry-title', 'post-title'])
                if title:
                    link = title.find('a', href=True)
                    if link and link['href']:
                        post_links.append(link['href'])
                else:
                    # Se não encontrou no título, procura qualquer link no artigo
                    links = article.find_all('a', href=True)
                    for link in links:
                        # Ignora links de menu, categorias, etc. (normalmente são curtos ou contêm palavras específicas)
                        href = link['href']
                        ignore_keywords = ['category', 'tag', 'author', 'page', 'comment', '#']
                        if not any(keyword in href.lower() for keyword in ignore_keywords) and len(href) > 15:
                            post_links.append(href)
        
        # Se ainda não encontrou, tenta um método mais genérico
        if not post_links:
            # Procura todos os links
            all_links = soup.find_all('a', href=True)
            
            # Filtra os links prováveis de serem posts (geralmente têm data ou ID no URL)
            for link in all_links:
                href = link['href']
                # Verifica se o link parece ser um post (tem a URL base e contém /yyyy/ ou ID numérico)
                base_host = self.base_url.split('//')[1].split('/')[0]  # Extrai o domínio base
                if base_host in href and ('20' in href or any(c.isdigit() for c in href.split('/')[-2])):
                    post_links.append(href)
        
        # Normaliza os links e remove duplicatas
        normalized_links = []
        seen_links = set()
        
        for link in post_links:
            # Normaliza a URL
            full_url = normalize_url(link, page_url)
            
            # Evita duplicatas
            if full_url not in seen_links:
                seen_links.add(full_url)
                normalized_links.append(full_url)
        
        logger.info(f"Encontrados {len(normalized_links)} links de posts na página {page_url}")
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
                
        logger.info(f"Total de {len(all_images)} imagens encontradas na página {page_url} e seus posts")
        return all_images