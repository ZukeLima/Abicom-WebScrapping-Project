"""
Serviço para manipulação de imagens.
"""
import os
import logging
from typing import Set, List, Optional, Dict
from datetime import datetime
from src.models.image import Image
from src.services.http_client import HttpClient
from src.utils.file_utils import file_exists, ensure_directory_exists
from src.utils.url_utils import get_url_extension
from src.config import DATE_FORMAT_FOLDER, IMAGE_EXTENSIONS, OUTPUT_DIR, ORGANIZE_BY_MONTH

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
        
        # Dicionário para mapear URLs de posts com as datas extraídas
        self.post_dates: Dict[str, str] = {}
        
        # Conjunto para rastrear imagens já verificadas em cada pasta mensal
        self.checked_monthly_folders: Set[str] = set()
        self.existing_images_by_month: Dict[str, Set[str]] = {}


    def extract_date_from_url(self, url: str) -> Optional[tuple]:
        """
        Extrai a data de uma URL.
        
        Args:
            url: URL para extrair a data
            
        Returns:
            Optional[tuple]: Tupla (dia, mês, ano) ou None se não encontrar
        """
        # Procura pelo padrão "ppi-DD-MM-YYYY" na URL
        import re
        pattern = r"ppi-(\d{2})-(\d{2})-(\d{4})"
        match = re.search(pattern, url)
        
        if match:
            day, month, year = match.groups()
            return (day, month, year)
            
        return None

    def get_image_path(self, image: Image) -> str:
        """
        Gera o caminho para salvar a imagem baseado no nome da página de origem,
        organizando por pastas mensais se configurado.
        
        Args:
            image: Objeto de imagem
            
        Returns:
            str: Caminho completo do arquivo
        """
        # Extrai o padrão "ppi-DD-MM-YYYY" da URL, se presente
        source_url = image.source_url
        filename = None
        monthly_path = None
        
        # Tenta encontrar o padrão "ppi-DD-MM-YYYY" na URL
        import re
        pattern = r"ppi-(\d{2})-(\d{2})-(\d{4})"
        match = re.search(pattern, source_url)
        
        if match:
            # Se encontrou o padrão, usa-o para o nome do arquivo e pasta mensal
            day, month, year = match.groups()
            
            # Guarda a data para referência futura
            self.post_dates[source_url] = (day, month, year)
            
            # Define a pasta mensal (MM-YYYY) se a organização por mês estiver ativada
            if ORGANIZE_BY_MONTH:
                monthly_folder = f"{month}-{year}"
                monthly_path = os.path.join(self.output_dir, monthly_folder)
                ensure_directory_exists(monthly_path)
            else:
                monthly_path = self.output_dir
            
            # Nome do arquivo
            filename = f"ppi-{day}-{month}-{year}{image.file_extension}"
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
            
            # Usa a pasta do mês atual se a organização por mês estiver ativada
            if ORGANIZE_BY_MONTH:
                today = datetime.now()
                monthly_folder = today.strftime(DATE_FORMAT_FOLDER)
                monthly_path = os.path.join(self.output_dir, monthly_folder)
                ensure_directory_exists(monthly_path)
            else:
                monthly_path = self.output_dir
        
        # Se não conseguiu extrair um nome da URL, usa a data atual
        if not filename:
            today = datetime.now()
            day = today.strftime("%d")
            month = today.strftime("%m")
            year = today.strftime("%Y")
            
            filename = f"ppi-{day}-{month}-{year}{image.file_extension}"
            
            # Define a pasta mensal padrão se a organização por mês estiver ativada
            if ORGANIZE_BY_MONTH:
                monthly_folder = today.strftime(DATE_FORMAT_FOLDER)
                monthly_path = os.path.join(self.output_dir, monthly_folder)
                ensure_directory_exists(monthly_path)
            else:
                monthly_path = self.output_dir
        
        # Retorna o caminho completo
        return os.path.join(monthly_path, filename)
    
    def pre_check_monthly_images(self) -> None:
        """
        Pré-verifica todas as imagens existentes em pastas mensais ou no diretório base,
        dependendo da configuração.
        Esta função indexa as imagens existentes para acelerar as verificações futuras.
        """
        if ORGANIZE_BY_MONTH:
            logger.info("Indexando imagens existentes por mês...")
            
            # Lista todas as subpastas no diretório de saída
            try:
                monthly_folders = [f for f in os.listdir(self.output_dir) 
                                if os.path.isdir(os.path.join(self.output_dir, f))]
            except Exception as e:
                logger.error(f"Erro ao listar pastas mensais: {e}")
                return
                
            # Para cada pasta, indexa os arquivos
            for folder in monthly_folders:
                folder_path = os.path.join(self.output_dir, folder)
                
                # Registra a pasta como verificada
                self.checked_monthly_folders.add(folder)
                
                # Inicializa o conjunto para esta pasta
                self.existing_images_by_month[folder] = set()
                
                try:
                    # Lista todas as imagens na pasta
                    files = [f for f in os.listdir(folder_path) 
                          if os.path.isfile(os.path.join(folder_path, f))]
                    
                    # Adiciona ao conjunto para esta pasta
                    for file in files:
                        self.existing_images_by_month[folder].add(file)
                        
                    logger.debug(f"Indexados {len(files)} arquivos na pasta {folder}")
                except Exception as e:
                    logger.error(f"Erro ao indexar arquivos na pasta {folder}: {e}")
                    
            logger.info(f"Indexação concluída. {len(monthly_folders)} pastas mensais verificadas.")
        else:
            # Se não estiver organizando por mês, indexa os arquivos no diretório base
            logger.info("Indexando imagens existentes no diretório base...")
            
            try:
                # Lista todos os arquivos no diretório base
                files = [f for f in os.listdir(self.output_dir) 
                      if os.path.isfile(os.path.join(self.output_dir, f))]
                
                # Cria um registro especial para o diretório base
                self.existing_images_by_month["base"] = set(files)
                
                logger.info(f"Indexação concluída. {len(files)} arquivos indexados no diretório base.")
            except Exception as e:
                logger.error(f"Erro ao indexar arquivos no diretório base: {e}")
                return

    def get_monthly_folder(self, url: str) -> str:
        """
        Obtém o caminho da pasta mensal para uma URL.
        
        Args:
            url: URL da imagem ou post
            
        Returns:
            str: Caminho da pasta mensal ou diretório base se organização mensal estiver desativada
        """
        # Se a organização por mês estiver desativada, retorna o diretório base
        if not ORGANIZE_BY_MONTH:
            return self.output_dir
            
        # Verifica se já extraímos a data desta URL antes
        if url in self.post_dates:
            day, month, year = self.post_dates[url]
            monthly_folder = f"{month}-{year}"
        else:
            # Tenta extrair a data da URL
            date_parts = self.extract_date_from_url(url)
            
            if date_parts:
                day, month, year = date_parts
                self.post_dates[url] = (day, month, year)
                monthly_folder = f"{month}-{year}"
            else:
                # Se não conseguir extrair a data, usa o mês atual
                today = datetime.now()
                monthly_folder = today.strftime(DATE_FORMAT_FOLDER)
        
        # Caminho completo da pasta mensal
        monthly_path = os.path.join(self.output_dir, monthly_folder)
        ensure_directory_exists(monthly_path)
        
        return monthly_path
    
    def is_already_downloaded(self, image: Image) -> bool:
        """
        Verifica se uma imagem já foi baixada, consultando as pastas mensais.
        
        Args:
            image: Objeto de imagem
            
        Returns:
            bool: True se a imagem já foi baixada, False caso contrário
        """
        # Verifica se a URL já foi baixada nesta sessão
        if image.url in self.downloaded_urls:
            return True
            
        # Extrai a data da URL da origem
        date_parts = self.extract_date_from_url(image.source_url)
        
        if date_parts:
            day, month, year = date_parts
            
            if ORGANIZE_BY_MONTH:
                monthly_folder = f"{month}-{year}"
                
                # Verifica se já indexamos esta pasta
                if monthly_folder not in self.checked_monthly_folders:
                    self.check_monthly_folder(monthly_folder)
                    
                # Gera o nome do arquivo esperado
                expected_filename = f"ppi-{day}-{month}-{year}{image.file_extension}"
                
                # Verifica se o arquivo existe no índice
                return expected_filename in self.existing_images_by_month.get(monthly_folder, set())
            else:
                # Se não estiver usando organização mensal, verifica diretamente no diretório base
                expected_filename = f"ppi-{day}-{month}-{year}{image.file_extension}"
                expected_path = os.path.join(self.output_dir, expected_filename)
                return file_exists(expected_path)
        
        # Se não conseguiu extrair a data, assume que não foi baixada
        return False
    
    def check_monthly_folder(self, month_year: str) -> None:
        """
        Verifica os arquivos em uma pasta mensal específica.
        
        Args:
            month_year: Pasta mensal no formato "MM-YYYY"
        """
        # Se já verificamos esta pasta, não precisa verificar novamente
        if month_year in self.checked_monthly_folders:
            return
            
        # Marca a pasta como verificada
        self.checked_monthly_folders.add(month_year)
        
        # Se a organização por mês estiver desativada, verifica o diretório base
        if not ORGANIZE_BY_MONTH:
            folder_path = self.output_dir
        else:
            # Caminho da pasta mensal
            folder_path = os.path.join(self.output_dir, month_year)
        
        # Verifica se a pasta existe
        if not os.path.exists(folder_path):
            # Se não existe e estamos organizando por mês, cria a pasta
            if ORGANIZE_BY_MONTH:
                ensure_directory_exists(folder_path)
            self.existing_images_by_month[month_year] = set()
            return
            
        # Inicializa o conjunto para esta pasta
        self.existing_images_by_month[month_year] = set()
        
        try:
            # Lista todas as imagens na pasta
            files = [f for f in os.listdir(folder_path) 
                   if os.path.isfile(os.path.join(folder_path, f))]
            
            # Adiciona ao conjunto para esta pasta
            for file in files:
                self.existing_images_by_month[month_year].add(file)
                
            logger.debug(f"Indexados {len(files)} arquivos na pasta/diretório {month_year}")
        except Exception as e:
            logger.error(f"Erro ao indexar arquivos na pasta/diretório {month_year}: {e}")

    def download_image(self, image: Image) -> bool:
        """
        Baixa uma imagem para o disco na pasta mensal apropriada ou no diretório base.
        
        Args:
            image: Objeto de imagem
            
        Returns:
            bool: True se o download for bem-sucedido, False caso contrário
        """
        # Verifica se a imagem já foi baixada
        if self.is_already_downloaded(image):
            logger.info(f"Imagem já baixada: {image.url}")
            return False
            
        # Verifica se a URL da fonte é uma página de listagem
        ignore_patterns = ['/categoria/', '/category/', '/tag/', '/author/', '/page/']
        if any(pattern in image.source_url for pattern in ignore_patterns) and 'abicom.com.br/categoria/ppi' in image.source_url:
            logger.info(f"Ignorando imagem de página de listagem: {image.url} de {image.source_url}")
            return False
            
        # Gera o caminho de destino (já organizado por pasta mensal se configurado)
        output_path = self.get_image_path(image)
        
        # Extrai a pasta e o nome do arquivo
        if ORGANIZE_BY_MONTH:
            # Extrai a pasta mensal do caminho
            monthly_folder = os.path.basename(os.path.dirname(output_path))
        else:
            # Use "base" como identificador para o diretório base
            monthly_folder = "base"
            
        # Extrai o nome do arquivo
        filename = os.path.basename(output_path)
        
        # Realiza o download
        download_success = self.http_client.download_file(image.url, output_path)
        
        if download_success:
            # Atualiza o caminho salvo na imagem
            image.saved_path = output_path
            
            # Adiciona à lista de URLs baixadas
            self.downloaded_urls.add(image.url)
            
            # Adiciona ao índice de imagens existentes
            if monthly_folder in self.existing_images_by_month:
                self.existing_images_by_month[monthly_folder].add(filename)
            else:
                self.existing_images_by_month[monthly_folder] = {filename}
                
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
        
        # Agrupa as imagens por mês/ano para relatório
        downloads_by_month = {}
        
        for image in images:
            # Extrai o mês/ano do post
            date_parts = self.extract_date_from_url(image.source_url)
            
            if date_parts:
                day, month, year = date_parts
                month_year = f"{month}-{year}"
            else:
                # Se não conseguir extrair a data, usa o mês atual
                today = datetime.now()
                month_year = today.strftime(DATE_FORMAT_FOLDER)
            
            # Baixa a imagem
            if self.download_image(image):
                download_count += 1
                
                # Registra o download por mês
                if month_year in downloads_by_month:
                    downloads_by_month[month_year] += 1
                else:
                    downloads_by_month[month_year] = 1
        
        # Log com resumo por mês
        if download_count > 0:
            logger.info("Resumo de downloads por mês:")
            for month_year, count in downloads_by_month.items():
                logger.info(f"  {month_year}: {count} imagens baixadas")
                
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