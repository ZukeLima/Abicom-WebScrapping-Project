# src/main.py

"""
Ponto de entrada principal para o scraper da Abicom.
"""
import os
import sys
import logging
import argparse
import re                               ### ADICIONADO ###
import pandas as pd                     ### ADICIONADO ###
from datetime import datetime           ### ADICIONADO ### (se não estiver já importado)

# Importações do projeto
from src.scrapers.abicom_scraper import AbicomScraper
# Importa configs necessárias, incluindo ORGANIZE_BY_MONTH
from src.config import MAX_PAGES, OUTPUT_DIR, ORGANIZE_BY_MONTH, DATE_FORMAT_FOLDER ### MODIFICADO ###
from src.utils.file_utils import file_exists # Importar se necessário para análise

# Configuração de logging (mantida como está)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('scraper.log')
    ]
)
logger = logging.getLogger(__name__)

### ADICIONADO: Definições de Regex para análise (movidas para cá) ###
filename_date_pattern = re.compile(r"ppi-(\d{2}-\d{2}-\d{4})\.(jpg|jpeg)", re.IGNORECASE)
folder_date_pattern = re.compile(r"(\d{2})-(\d{4})")

### ADICIONADO: Função de Análise (copiada e adaptada) ###
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
            # Simplificado para verificar extensão aqui
            file_lower = filename.lower()
            if file_lower.endswith('.jpg') or file_lower.endswith('.jpeg'):
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
                    try:
                        datetime.strptime(extracted_date_from_filename, '%d-%m-%Y')
                    except ValueError:
                        logger.warning(f"Formato de data inválido no nome do arquivo: {filename}")
                        extracted_date_from_filename = None

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

# Função parse_arguments (mantida como está)
def parse_arguments():
    """
    Analisa os argumentos da linha de comando.

    Returns:
        argparse.Namespace: Argumentos analisados
    """
    parser = argparse.ArgumentParser(
        description='Web Scraper para o site da Abicom - categoria PPI'
    )

    parser.add_argument(
        '--start-page',
        type=int,
        default=1,
        help='Página inicial para o scraping (padrão: 1)'
    )

    parser.add_argument(
        '--max-pages',
        type=int,
        default=MAX_PAGES,
        help=f'Número máximo de páginas para processar (padrão: {MAX_PAGES})'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        # Usa o OUTPUT_DIR importado como padrão
        default=OUTPUT_DIR, ### MODIFICADO ###
        help=f'Diretório de saída para as imagens (padrão: {OUTPUT_DIR})'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Habilita logging detalhado'
    )
    
    # ### ADICIONADO: Argumento opcional para rodar ou não a análise ###
    parser.add_argument(
        '--analyze',
        action='store_true', # Se presente, roda a análise
        help='Executa a análise dos arquivos baixados após o scraping.'
    )

    return parser.parse_args()


def main():
    """
    Função principal.
    """
    # Analisa os argumentos
    args = parse_arguments()

    # Configura o nível de logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info(f"Iniciando scraper da Abicom (páginas {args.start_page} a {args.start_page + args.max_pages - 1})")
    logger.info(f"O scraper irá acessar cada post encontrado e baixar a primeira imagem JPG")
    logger.info(f"As imagens serão organizadas em pastas mensais (MM-YYYY): {ORGANIZE_BY_MONTH}")

    # Garante que o diretório de saída exista (usando o argumento, que tem default do config)
    os.makedirs(args.output_dir, exist_ok=True) ### MODIFICADO ###

    total_downloads = 0 # Inicializa fora do try para garantir que existe
    try:
        # Cria uma instância do serviço de imagens com o diretório de saída dos argumentos
        from src.services.image_service import ImageService
        # Passa o diretório de saída definido nos argumentos
        image_service = ImageService(output_dir=args.output_dir) ### MODIFICADO ###

        # Pré-indexa as imagens existentes para otimizar a verificação
        logger.info("Pré-indexando imagens existentes...")
        image_service.pre_check_monthly_images()

        # Inicializa e executa o scraper
        with AbicomScraper(image_service=image_service) as scraper:
            total_downloads = scraper.run(
                start_page=args.start_page,
                max_pages=args.max_pages
            )

        if total_downloads > 0:
            logger.info(f"Scraping concluído. Total de {total_downloads} novas imagens baixadas.")
        else:
            logger.info("Scraping concluído. Nenhuma nova imagem baixada.")

    except KeyboardInterrupt:
        logger.info("Scraping interrompido pelo usuário.")
        # ### MODIFICADO: Decide se roda análise mesmo com interrupção ###
        # Poderia optar por não rodar a análise aqui, ou rodar com o que foi baixado
        if args.analyze:
             logger.info("Executando análise com os arquivos baixados até a interrupção...")
        else:
             return 1 # Sai sem analisar

    except ImportError as e:
        # Captura erro específico se faltar alguma dependência do scraper
        logger.exception(f"Erro de importação durante o scraping. Verifique as dependências: {e}")
        return 1 # Sai sem analisar

    except Exception as e:
        logger.exception(f"Erro durante o scraping: {e}")
        # ### MODIFICADO: Decide se roda análise mesmo com erro ###
        # Geralmente não se roda análise se o scraping falhou, mas é uma opção
        if args.analyze:
             logger.warning("Scraping encontrou um erro, mas a análise será tentada...")
        else:
            return 1 # Sai sem analisar

    # --- Análise Pós-Scraping (Executada APÓS o bloco try do scraper, se não saiu antes) --- ### ADICIONADO ###
    if args.analyze:
        logger.info("Iniciando análise dos arquivos baixados...")
        try:
            # Usa o diretório de saída dos argumentos e a config de organização
            df_analise = analisar_imagens_baixadas(args.output_dir, ORGANIZE_BY_MONTH)

            if not df_analise.empty:
                print("\n--- Tabela de Análise das Imagens (Primeiras 5 linhas) ---")
                try:
                    print(df_analise.head().to_markdown(index=False))
                except ImportError:
                    print(df_analise.head().to_string(index=False)) # Fallback

                print("\n--- Resumo da Análise ---")
                print(f"Total de imagens analisadas: {len(df_analise)}")

                if ORGANIZE_BY_MONTH:
                    contagem_pasta = df_analise[df_analise['pasta_pai'] != '[RAIZ]']['pasta_pai'].value_counts()
                    if not contagem_pasta.empty:
                        print("\nContagem de imagens por pasta (Mês-Ano):")
                        print(contagem_pasta.to_string())

                datas_validas = df_analise['data_extraida_arquivo'].notna().sum()
                print(f"\nImagens com data extraída do nome: {datas_validas}")

                tamanho_total_mb = df_analise['tamanho_bytes'].sum() / (1024 * 1024)
                tamanho_medio_kb = (df_analise['tamanho_bytes'].mean() / 1024) if len(df_analise) > 0 else 0
                print(f"\nTamanho total dos arquivos: {tamanho_total_mb:.2f} MB")
                print(f"Tamanho médio por arquivo: {tamanho_medio_kb:.2f} KB")
                logger.info("Análise dos arquivos concluída.")
            else:
                logger.warning("Nenhuma imagem encontrada no diretório para análise.")

        except ImportError:
             logger.error("Pandas não está instalado. Execute 'pip install pandas' e adicione aos requirements para habilitar a análise.")
        except Exception as e_analysis:
            logger.exception(f"Erro durante a análise dos arquivos: {e_analysis}")

    return 0 # Retorno de sucesso geral


if __name__ == "__main__":
    # Verifica se Pandas está disponível se a análise for solicitada
    if '--analyze' in sys.argv:
        try:
            import pandas
        except ImportError:
            print("ERRO: A biblioteca Pandas é necessária para a análise (--analyze), mas não está instalada.", file=sys.stderr)
            print("Instale com: pip install pandas", file=sys.stderr)
            sys.exit(1) # Sai antes de tentar rodar main()

    sys.exit(main())