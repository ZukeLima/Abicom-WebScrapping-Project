# src/config.py

"""
Arquivo de Configuração Global para o Scraper e Analisador Abicom (Versão Sem DB).
Define constantes usadas em várias partes do projeto, como URLs,
caminhos de arquivo, parâmetros de scraping e análise.
"""
# --- Imports Padrão ---
import os
# 'datetime' pode ser removido se as funções auxiliares forem deletadas permanentemente.
from datetime import datetime
import sys # Usado para print em stderr no except

# --- Configurações de URLs e Navegação ---
# (Mantidas como antes)
BASE_URL = "https://abicom.com.br/categoria/ppi/"
PAGE_PATTERN = "/page/{page_num}/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# --- Configurações de Requisição HTTP ---
# (Mantidas como antes)
REQUEST_TIMEOUT = 30
RETRY_COUNT = 3
RETRY_DELAY = 2
# DOWNLOAD_TIMEOUT = 60

# --- Configurações de Navegação do Scraper ---
# (Mantidas como antes)
SLEEP_BETWEEN_REQUESTS = 1
SLEEP_BETWEEN_PAGES = 2
MAX_PAGES = 4

# --- Configurações de Imagem ---
# (Mantidas como antes)
IMAGE_EXTENSIONS = ['.jpg', '.jpeg']

# --- Configurações de Arquivos e Diretórios ---
# 1. Calcula diretório raiz do projeto
BASE_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 2. Define diretório 'data' (OK)
DATA_DIR = os.path.join(BASE_PROJECT_DIR, "data")
# 3. Define diretório 'images' dentro de 'data' (OK)
OUTPUT_DIR = os.path.join(DATA_DIR, "images")
# 4. REMOVIDO/COMENTADO: DATABASE_FILE (OK para versão sem DB)
# DATABASE_FILE = os.path.join(DATA_DIR, "abicom_data.db")
# 5. Formatos de data (OK)
DATE_FORMAT = "%d-%m-%Y"
DATE_FORMAT_FOLDER = "%m-%Y"
# 6. Flag organização (OK)
ORGANIZE_BY_MONTH = True

# --- Criação de Diretórios Essenciais ---
# Garante que as pastas 'data' e 'data/images' existam.
# CORREÇÃO: Removidas as chamadas logger.debug daqui para evitar erro de logger não inicializado.
# A criação ainda acontece, mas sem log de debug neste ponto específico.
# Erros de criação (ex: permissão) ainda serão impressos via 'print' no except.
try:
    os.makedirs(DATA_DIR, exist_ok=True)
    # logger.debug(f"Diretório de dados verificado/criado: {DATA_DIR}") # <-- REMOVIDO logger.debug
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # logger.debug(f"Diretório de imagens verificado/criado: {OUTPUT_DIR}") # <-- REMOVIDO logger.debug
except OSError as e:
    # Mantém o print para erros de criação, que são importantes
    print(f"ALERTA config.py: Falha ao criar diretórios ({DATA_DIR}, {OUTPUT_DIR}): {e}", file=sys.stderr)
# REMOVIDO: except NameError, pois não usamos mais o logger aqui dentro do try.
except Exception as e: # Captura outros erros inesperados
     print(f"ERRO INESPERADO config.py ao criar diretórios: {e}", file=sys.stderr)


# --- Funções Auxiliares (Comentadas - Provavelmente Não Utilizadas) ---
# (Mantidas comentadas como antes)
# def get_image_filename(prefix="ppi", ext=".jpg"):
#    pass
# def get_dated_image_path(url, prefix="ppi", ext=".jpg"):
#    pass

# ----- FIM do arquivo src/config.py -----