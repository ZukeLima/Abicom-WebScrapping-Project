# src/config.py

"""
Arquivo de Configuração Global para o Scraper e Analisador Abicom (Versão Sem DB).
Define constantes usadas em várias partes do projeto, como URLs,
caminhos de arquivo, parâmetros de scraping e análise.
"""
# --- Imports Padrão ---
import os
# 'datetime' só era usado nas funções comentadas abaixo, pode ser removido se elas forem deletadas.
from datetime import datetime
# Import 'sys' se for usar print para stderr no fallback de criação de diretório
import sys

# --- Configurações de URLs e Navegação ---
# URL base da categoria PPI no site da Abicom (para o scraper)
BASE_URL = "https://abicom.com.br/categoria/ppi/"
# Padrão de URL para paginação (não usado se AbicomScraper hardcoded)
PAGE_PATTERN = "/page/{page_num}/"
# User-Agent para simular um navegador nas requisições HTTP
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# --- Configurações de Requisição HTTP (para HttpClient) ---
REQUEST_TIMEOUT = 30  # Tempo máximo de espera pela resposta (segundos)
RETRY_COUNT = 3       # Número de tentativas em caso de erro de conexão/timeout
RETRY_DELAY = 2       # Tempo de espera inicial entre tentativas (segundos)
# DOWNLOAD_TIMEOUT = 60 # Timeout específico para downloads (não usado no HttpClient atual)

# --- Configurações de Navegação do Scraper ---
SLEEP_BETWEEN_REQUESTS = 1  # Pausa entre requisições HTTP (segundos)
SLEEP_BETWEEN_PAGES = 2     # Pausa entre processar páginas diferentes (segundos)
MAX_PAGES = 4             # Máximo de páginas a processar por padrão

# --- Configurações de Imagem ---
# Extensões de arquivo que o scraper deve considerar como imagens válidas
IMAGE_EXTENSIONS = ['.jpg', '.jpeg'] # Adicione '.png' aqui se as imagens no site forem PNG

# --- Configurações de Arquivos e Diretórios ---

# 1. Calcula o caminho absoluto para o diretório RAIZ do projeto
#    (a pasta que contém 'src' e 'data')
#    __file__ -> caminho para este arquivo (src/config.py)
#    os.path.dirname() -> pega o diretório (src)
#    os.path.dirname() novamente -> pega o diretório pai (raiz do projeto)
BASE_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 2. Define o diretório 'data' dentro da pasta raiz do projeto
#    *** CORREÇÃO: Esta variável estava faltando, causando o ImportError ***
DATA_DIR = os.path.join(BASE_PROJECT_DIR, "data")

# 3. Define o diretório 'images' dentro da pasta 'data'
#    Usa DATA_DIR definido acima para consistência.
OUTPUT_DIR = os.path.join(DATA_DIR, "images")

# 4. (Opcional) Define o nome do arquivo de banco de dados (se fosse usar)
#    Se você NÃO está usando DB, pode remover/comentar esta linha.
# DATABASE_FILE = os.path.join(DATA_DIR, "abicom_data.db")

# 5. Formatos de data (usados pelo ImageService e talvez outros)
DATE_FORMAT = "%d-%m-%Y"       # Formato Dia-Mês-Ano
DATE_FORMAT_FOLDER = "%m-%Y"   # Formato Mês-Ano (para pastas)

# 6. Flag para organização de imagens (usada pelo ImageService)
ORGANIZE_BY_MONTH = True       # True = salva imagens em subpastas MM-YYYY

# --- Criação de Diretórios Essenciais ---
# Garante que as pastas 'data' e 'data/images' existam quando este módulo for carregado.
# É importante que DATA_DIR e OUTPUT_DIR estejam definidos ANTES daqui.
try:
    # Cria a pasta 'data' se não existir
    os.makedirs(DATA_DIR, exist_ok=True)
    logger.debug(f"Diretório de dados verificado/criado: {DATA_DIR}") # Usa logger se já configurado
    # Cria a pasta 'data/images' se não existir
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    logger.debug(f"Diretório de imagens verificado/criado: {OUTPUT_DIR}")
except OSError as e:
    # Usa print para stderr caso o logger ainda não esteja configurado
    print(f"ALERTA config.py: Falha ao criar diretórios ({DATA_DIR}, {OUTPUT_DIR}): {e}", file=sys.stderr)
except NameError:
     # Caso logger não esteja definido ainda (acontece se config é importado muito cedo)
     print(f"ALERTA config.py: Falha ao criar diretórios. Logger não definido ainda.")
except Exception as e: # Captura outros erros inesperados
     print(f"ERRO INESPERADO config.py ao criar diretórios: {e}", file=sys.stderr)


# --- Funções Auxiliares (Comentadas - Provavelmente Não Utilizadas) ---
# Estas funções parecem ter sido substituídas pela lógica mais específica
# dentro do ImageService (que usa a data extraída do post, não a data atual).
# É recomendado removê-las ou mantê-las comentadas para evitar confusão.

# def get_image_filename(prefix="ppi", ext=".jpg"):
#     """ Gera nome de arquivo com data ATUAL. (NÃO USADO?) """
#     # today = datetime.now()
#     # return f"{prefix}-{today.strftime('%d-%m-%Y')}{ext}"
#     pass

# def get_dated_image_path(url, prefix="ppi", ext=".jpg"):
#     """ Gera caminho completo com data ATUAL. (NÃO USADO?) """
#     # today = datetime.now()
#     # filename = f"{prefix}-{today.strftime('%d-%m-%Y')}{ext}"
#     # return os.path.join(OUTPUT_DIR, filename)
#     pass

# ----- FIM do arquivo src/config.py -----