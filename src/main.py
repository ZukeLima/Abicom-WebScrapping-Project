# src/main.py

"""
Ponto de entrada principal para o scraper da Abicom.
"""
import os
import sys
import logging
import argparse
import re
import pandas as pd
from datetime import datetime

# Importações do projeto
from src.scrapers.abicom_scraper import AbicomScraper
# Importa configs necessárias, incluindo ORGANIZE_BY_MONTH
from src.config import MAX_PAGES, OUTPUT_DIR, ORGANIZE_BY_MONTH, DATE_FORMAT_FOLDER
# from src.utils.file_utils import file_exists # Removido se não usado

# --- ADICIONADO: Importa a função de análise externa ---
# (Mantido da versão anterior - assume que você quer a análise avançada)
try:
    from src.analise_imagens import executar_e_reportar_analise
    analysis_function_available = True
except ImportError as ie:
    executar_e_reportar_analise = None
    analysis_function_available = False
    logging.error(f"Não foi possível importar a função de análise avançada de src.analise_imagens: {ie}")
    logging.error("A análise avançada (com OCR) não estará disponível.")
# --- FIM DO IMPORT ADICIONADO ---


# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('scraper.log')
    ]
)
logger = logging.getLogger(__name__)

# Definições de Regex para análise interna (se for usada)
filename_date_pattern = re.compile(r"ppi-(\d{2}-\d{2}-\d{4})\.(jpg|jpeg)", re.IGNORECASE)
folder_date_pattern = re.compile(r"(\d{2})-(\d{4})")

# Função de Análise ANTIGA (Definição mantida, mas não chamada via --analyze na versão anterior)
def analisar_imagens_baixadas(diretorio_base: str, organizar_por_mes: bool) -> pd.DataFrame:
    """
    Analisa os arquivos de imagem no diretório de saída e retorna um DataFrame Pandas.
    *** ESTA É A VERSÃO ANTIGA - SÓ METADADOS DO ARQUIVO ***
    """
    dados_arquivos = []
    if not os.path.exists(diretorio_base):
        logger.error(f"[Análise Interna Antiga] Diretório não encontrado: {diretorio_base}")
        return pd.DataFrame(dados_arquivos)
    logger.info(f"[Análise Interna Antiga] Analisando diretório: {diretorio_base} ...")
    for root, dirs, files in os.walk(diretorio_base):
        for filename in files:
            file_lower = filename.lower()
            if file_lower.endswith('.jpg') or file_lower.endswith('.jpeg'):
                filepath = os.path.join(root, filename)
                folder_name = os.path.basename(root)
                extracted_date_from_filename = None
                folder_month = None
                folder_year = None
                file_size = 0
                match_filename = filename_date_pattern.search(filename)
                if match_filename:
                    extracted_date_from_filename = match_filename.group(1)
                    try:
                        datetime.strptime(extracted_date_from_filename, '%d-%m-%Y')
                    except ValueError:
                        logger.warning(f"[Análise Interna Antiga] Formato de data inválido: {filename}")
                        extracted_date_from_filename = None
                if organizar_por_mes and root != diretorio_base:
                    match_folder = folder_date_pattern.match(folder_name)
                    if match_folder:
                        folder_month, folder_year = match_folder.groups()
                    else:
                        # Comentado para evitar poluição no log normal
                        # logger.warning(f"[Análise Interna Antiga] Pasta não segue padrão MM-YYYY: {folder_name}")
                        pass
                try:
                    file_size = os.path.getsize(filepath)
                except OSError as e:
                    logger.error(f"[Análise Interna Antiga] Erro tamanho {filepath}: {e}")

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
        logger.warning("[Análise Interna Antiga] Nenhum arquivo de imagem encontrado.")
    return pd.DataFrame(dados_arquivos)

# Função parse_arguments
def parse_arguments():
    """
    Analisa os argumentos da linha de comando.
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
        default=OUTPUT_DIR,
        help=f'Diretório de saída para as imagens (padrão: {OUTPUT_DIR})'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Habilita logging detalhado'
    )
    parser.add_argument(
        '--analyze',
        action='store_true', # Se presente, roda a análise
        help='Executa a análise avançada (com OCR) dos arquivos baixados após o scraping.' # Help atualizado
    )
    return parser.parse_args()


def main():
    """
    Função principal.
    """
    args = parse_arguments()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Diretório de dados para o CSV da análise
    data_dir_analysis = os.path.dirname(args.output_dir)
    os.makedirs(data_dir_analysis, exist_ok=True) # Cria se não existir

    logger.info(f"Iniciando scraper da Abicom (páginas {args.start_page} a {args.start_page + args.max_pages - 1})")
    logger.info(f"Diretório de saída das imagens: {args.output_dir}")
    logger.info(f"Organizar imagens por mês: {ORGANIZE_BY_MONTH}")
    if args.analyze:
        if analysis_function_available:
            logger.info(f"Análise avançada pós-scraping habilitada. CSV será salvo em: {data_dir_analysis}")
        else:
            logger.warning("Flag --analyze fornecida, mas a função de análise avançada não pôde ser importada. Nenhuma análise será executada.")

    # Garante que o diretório de saída das imagens exista
    os.makedirs(args.output_dir, exist_ok=True)

    total_downloads = 0
    scraper_success = False
    exception_occurred = None

    # --- Bloco Try/Except do Scraper ---
    try:
        from src.services.image_service import ImageService
        image_service = ImageService(output_dir=args.output_dir)
        logger.info("Pré-indexando imagens existentes...")
        image_service.pre_check_monthly_images()

        with AbicomScraper(image_service=image_service) as scraper:
            total_downloads = scraper.run(
                start_page=args.start_page,
                max_pages=args.max_pages
            )

        if total_downloads > 0:
            logger.info(f"Scraping concluído. Total de {total_downloads} novas imagens baixadas.")
        else:
            logger.info("Scraping concluído. Nenhuma nova imagem baixada.")
        scraper_success = True

    except KeyboardInterrupt as e:
        logger.info("Scraping interrompido pelo usuário.")
        exception_occurred = e # Armazena a exceção para decidir o return code
    except ImportError as e:
        logger.exception(f"Erro de importação durante o scraping. Verifique as dependências: {e}")
        exception_occurred = e
    except Exception as e:
        logger.exception(f"Erro durante o scraping: {e}")
        exception_occurred = e
    # --- Fim do Bloco Try/Except do Scraper ---


    # --- Análise Pós-Scraping ---
    # Executa SE a flag --analyze foi passada E a função externa foi importada com sucesso
    if args.analyze and analysis_function_available:
        logger.info("Iniciando análise avançada (com OCR) dos arquivos baixados...")
        try:
            # Chama a função externa importada
            executar_e_reportar_analise(
                diretorio_imagens=args.output_dir,
                organizar_por_mes=ORGANIZE_BY_MONTH,
                diretorio_csv=data_dir_analysis
            )
            # O log/print de conclusão é feito dentro da função externa

        except ImportError as e:
             # Captura erro se faltar dependência DA ANÁLISE (ex: easyocr, Pillow, torch)
             logger.error(f"Erro de importação ao tentar executar a análise avançada: {e}.")
             print(f"\nERRO: Falta dependência para a análise avançada: {e}")
        except Exception as e_analysis:
            logger.exception(f"Erro durante a execução da análise avançada: {e_analysis}")

    elif args.analyze and not analysis_function_available:
        logger.error("A análise foi solicitada (--analyze), mas a função necessária não pôde ser carregada (ver logs anteriores).")
        print("\nERRO: Análise solicitada, mas função de análise avançada não disponível.")

    # Decide o status de saída final
    # Sucesso (0) se scraper ok ou interrupção, falha (1) caso contrário
    if isinstance(exception_occurred, ImportError) and "src.services" in str(exception_occurred):
        # Erro de importação do *scraper* é fatal
        return 1
    elif exception_occurred and not isinstance(exception_occurred, KeyboardInterrupt):
        # Outro erro do *scraper* também é fatal
        return 1
    else:
         # Scraper funcionou OU foi interrompido -> sucesso
        return 0


if __name__ == "__main__":
    # Verifica se Pandas está disponível se a análise for solicitada
    # A análise avançada também precisa de pandas, então este check é útil
    if '--analyze' in sys.argv:
        try:
            import pandas
        except ImportError:
            print("ERRO: A biblioteca Pandas é necessária para a análise (--analyze), mas não está instalada.", file=sys.stderr)
            print("Instale com: pip install pandas", file=sys.stderr)
            print("Verifique também se Pillow e EasyOCR (com torch) estão instalados para a análise avançada.", file=sys.stderr)
            # Não sai imediatamente, permite que o main() tente importar e falhe graciosamente

    sys.exit(main())