"""
Módulo para realizar web scraping no site da Abicom.
"""
import os
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

class AbicomScraper:
    """
    Scraper para extrair dados do site da Abicom.
    """
    BASE_URL = "https://abicom.com.br/categoria/ppi/"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    def __init__(self, output_folder="data"):
        """
        Inicializa o scraper.
        
        Args:
            output_folder (str): Pasta para salvar os dados extraídos.
        """
        self.output_folder = output_folder
        
        # Cria a pasta de saída se não existir
        os.makedirs(output_folder, exist_ok=True)
        
        # Inicializa a lista para armazenar os dados
        self.data = []

    def get_page(self, url):
        """
        Obtém o conteúdo de uma página.
        
        Args:
            url (str): URL da página a ser obtida.
            
        Returns:
            BeautifulSoup: Objeto BeautifulSoup com o conteúdo da página.
        """
        try:
            response = requests.get(url, headers=self.HEADERS, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.content, "html.parser")
        except requests.RequestException as e:
            print(f"Erro ao acessar a URL {url}: {e}")
            return None

    def scrape_article(self, url):
        """
        Extrai informações de um artigo específico.
        
        Args:
            url (str): URL do artigo.
            
        Returns:
            dict: Dicionário com informações do artigo.
        """
        soup = self.get_page(url)
        if not soup:
            return None
        
        # Implemente a lógica para extrair dados do artigo
        # Esta é uma implementação básica, ajuste conforme necessário
        try:
            title = soup.find("h1", class_="entry-title").text.strip()
            date = soup.find("time", class_="entry-date").get("datetime", "")
            content = soup.find("div", class_="entry-content").get_text(strip=True)
            
            return {
                "url": url,
                "title": title,
                "date": date,
                "content": content[:500] + "..." if len(content) > 500 else content
            }
        except (AttributeError, TypeError) as e:
            print(f"Erro ao extrair dados do artigo {url}: {e}")
            return None

    def scrape_listing_page(self, page_num=1):
        """
        Extrai URLs de artigos de uma página de listagem.
        
        Args:
            page_num (int): Número da página a ser processada.
            
        Returns:
            list: Lista de URLs de artigos.
        """
        url = f"{self.BASE_URL}page/{page_num}/" if page_num > 1 else self.BASE_URL
        soup = self.get_page(url)
        
        if not soup:
            return []
        
        article_links = []
        # Ajuste os seletores conforme a estrutura real do site
        articles = soup.find_all("article")
        
        for article in articles:
            link_element = article.find("a", href=True)
            if link_element:
                article_links.append(link_element["href"])
                
        return article_links

    def scrape(self, max_pages=5):
        """
        Executa o scraping principal.
        
        Args:
            max_pages (int): Número máximo de páginas a serem processadas.
        """
        all_article_links = []
        
        # Coleta todos os links de artigos
        for page_num in range(1, max_pages + 1):
            print(f"Coletando links da página {page_num}...")
            links = self.scrape_listing_page(page_num)
            
            if not links:
                print(f"Nenhum link encontrado na página {page_num} ou página não existe.")
                break
                
            all_article_links.extend(links)
            time.sleep(1)  # Pausa para evitar sobrecarga no servidor
        
        print(f"Total de {len(all_article_links)} artigos encontrados.")
        
        # Processa cada artigo
        for url in tqdm(all_article_links, desc="Processando artigos"):
            article_data = self.scrape_article(url)
            if article_data:
                self.data.append(article_data)
            time.sleep(1)  # Pausa entre requisições

    def save_to_csv(self, filename=None):
        """
        Salva os dados extraídos em um arquivo CSV.
        
        Args:
            filename (str, optional): Nome do arquivo de saída.
        """
        if not self.data:
            print("Nenhum dado para salvar.")
            return
            
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"abicom_data_{timestamp}.csv"
            
        filepath = os.path.join(self.output_folder, filename)
                
        print(f"Dados salvos em {filepath}")

if __name__ == "__main__":
    scraper = AbicomScraper()
    scraper.scrape(max_pages=3)  # Começa com um número pequeno para teste
    scraper.save_to_csv()