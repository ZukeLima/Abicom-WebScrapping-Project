"""
Configurações globais para o scraper.
"""
import os
from datetime import datetime

# URLs e configurações de navegação
BASE_URL = "https://abicom.com.br/categoria/ppi/"
PAGE_PATTERN = "/page/{page_num}/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Configurações de requisição HTTP
REQUEST_TIMEOUT = 30  # segundos
RETRY_COUNT = 3
RETRY_DELAY = 2  # segundos
DOWNLOAD_TIMEOUT = 60  # segundos

# Configurações de navegação
SLEEP_BETWEEN_REQUESTS = 1  # segundos
SLEEP_BETWEEN_PAGES = 2  # segundos
MAX_PAGES = 10
MAX_POST_DEPTH = 3

# Padrões para identificação de imagens
IMAGE_EXTENSIONS = ['.jpg', '.jpeg']

# Configurações de arquivos e diretórios
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "images")
DATE_FORMAT = "dd-MM-yyyy"  # Formato para nomes de arquivos

# Criar diretório de saída se não existir
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_image_filename(prefix="ppi", ext=".jpg"):
    """Gera um nome de arquivo baseado na data atual."""
    today = datetime.now()
    return f"{prefix}-{today.strftime('%d-%m-%Y')}{ext}"

def get_dated_image_path(url, prefix="ppi", ext=".jpg"):
    """
    Gera um caminho completo para uma imagem baseado na data atual.
    
    Args:
        url: URL da imagem (usado para gerar um hash único se necessário)
        prefix: Prefixo para o nome do arquivo
        ext: Extensão do arquivo
        
    Returns:
        str: Caminho completo para o arquivo de imagem
    """
    today = datetime.now()
    filename = f"{prefix}-{today.strftime('%d-%m-%Y')}{ext}"
    return os.path.join(OUTPUT_DIR, filename)