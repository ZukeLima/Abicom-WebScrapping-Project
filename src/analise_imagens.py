# analise_imagens.py
import os
import re
import pandas as pd
import logging
from datetime import datetime

# --- Configuração ---
# Pega o diretório de saída da configuração do scraper ou define manualmente
# Se rodar da raiz do projeto:
try:
    # Tenta importar a configuração se executado com -m ou PYTHONPATH configurado
    from src.config import OUTPUT_DIR, ORGANIZE_BY_MONTH, DATE_FORMAT_FOLDER
except ImportError:
    # Define manualmente se a importação falhar (ajuste se necessário)
    OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "images")
    ORGANIZE_BY_MONTH = True # Assumindo o padrão do config.py
    DATE_FORMAT_FOLDER = "%m-%Y" # Assumindo o padrão do config.py
    print("Aviso: Não foi possível importar de src.config. Usando caminhos/configurações padrão.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Padrão regex para extrair data do nome do arquivo 'ppi-DD-MM-YYYY.jpg'
filename_date_pattern = re.compile(r"ppi-(\d{2}-\d{2}-\d{4})\.(jpg|jpeg)", re.IGNORECASE)
# Padrão regex para validar formato de pasta 'MM-YYYY'
folder_date_pattern = re.compile(r"(\d{2})-(\d{4})")

def analisar_imagens_baixadas(diretorio_base: str, organizar_por_mes: bool) -> pd.DataFrame:
    """
    Analisa os arquivos de imagem no diretório de saída e retorna um DataFrame Pandas.
    """
    dados_arquivos = []

    if not os.path.exists(diretorio_base):
        logger.error(f"Diretório de imagens não encontrado: {diretorio_base}")
        return pd.DataFrame(dados_arquivos)

    logger.info(f"Analisando diretório: {diretorio_base} (Organizar por mês: {organizar_por_mes})")

    for root, dirs, files in os.walk(diretorio_base):
        for filename in files:
            if filename.lower().endswith(('.jpg', '.jpeg')):
                filepath = os.path.join(root, filename)
                folder_name = os.path.basename(root) # Nome da pasta pai
                extracted_date_from_filename = None
                folder_month = None
                folder_year = None
                file_size = 0

                # Extrair data do nome do arquivo
                match_filename = filename_date_pattern.search(filename)
                if match_filename:
                    extracted_date_from_filename = match_filename.group(1)
                    # Tenta validar o formato da data extraída
                    try:
                        datetime.strptime(extracted_date_from_filename, '%d-%m-%Y')
                    except ValueError:
                        logger.warning(f"Formato de data inválido no nome do arquivo: {filename}")
                        extracted_date_from_filename = None # Invalida se formato errado

                # Extrair mês/ano da pasta se organizado por mês
                if organizar_por_mes and root != diretorio_base:
                    match_folder = folder_date_pattern.match(folder_name)
                    if match_folder:
                        folder_month = match_folder.group(1)
                        folder_year = match_folder.group(2)
                    else:
                         logger.warning(f"Nome da pasta não segue o padrão MM-YYYY: {folder_name}")

                # Obter tamanho do arquivo
                try:
                    file_size = os.path.getsize(filepath)
                except OSError as e:
                    logger.error(f"Erro ao obter tamanho do arquivo {filepath}: {e}")

                dados_arquivos.append({
                    "caminho_completo": filepath,
                    "nome_arquivo": filename,
                    "pasta_pai": folder_name if root != diretorio_base else "[RAIZ]",
                    "data_extraida_arquivo": extracted_date_from_filename,
                    "mes_pasta": folder_month,
                    "ano_pasta": folder_year,
                    "tamanho_bytes": file_size
                })

    if not dados_arquivos:
         logger.warning("Nenhum arquivo de imagem encontrado para análise.")

    return pd.DataFrame(dados_arquivos)

# --- Execução da Análise ---
if __name__ == "__main__":
    logger.info("Iniciando análise dos arquivos de imagem baixados...")
    df_analise = analisar_imagens_baixadas(OUTPUT_DIR, ORGANIZE_BY_MONTH)

    if not df_analise.empty:
        print("\n--- Tabela de Análise das Imagens ---")
        # Mostra as primeiras linhas da tabela
        print(df_analise.head().to_markdown(index=False)) # to_markdown para melhor visualização

        print("\n--- Resumo ---")
        print(f"Total de imagens analisadas: {len(df_analise)}")

        # Contagem por pasta (se organizado por mês)
        if ORGANIZE_BY_MONTH:
            contagem_pasta = df_analise[df_analise['pasta_pai'] != '[RAIZ]']['pasta_pai'].value_counts()
            if not contagem_pasta.empty:
                print("\nContagem de imagens por pasta (Mês-Ano):")
                print(contagem_pasta.to_string())

        # Contagem de datas extraídas com sucesso
        datas_validas = df_analise['data_extraida_arquivo'].notna().sum()
        print(f"\nImagens com data extraída do nome: {datas_validas}")

        # Tamanho total e médio
        tamanho_total_mb = df_analise['tamanho_bytes'].sum() / (1024 * 1024)
        tamanho_medio_kb = (df_analise['tamanho_bytes'].mean() / 1024) if len(df_analise) > 0 else 0
        print(f"\nTamanho total dos arquivos: {tamanho_total_mb:.2f} MB")
        print(f"Tamanho médio por arquivo: {tamanho_medio_kb:.2f} KB")

    else:
        print("\nNenhuma imagem encontrada no diretório especificado para gerar a análise.")