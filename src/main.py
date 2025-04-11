# src/main.py

"""
Ponto de entrada principal para o scraper da Abicom (versão SEM DB).
Orquestra: Configuração, Scraping (download de imagens), Análise de Imagens (gera CSV),
e Tratamento Adicional do CSV gerado.
"""
# --- Imports Padrão ---
import os
import sys
import logging
import argparse

# --- Imports do Projeto (Corrigidos para 'python -m src.main') ---
# Usa '.' para imports relativos dentro do pacote 'src'.

# REMOVIDO: Import do módulo de banco de dados, pois não será usado.
# from . import database as db # <- REMOVIDO

# Importa a classe Scraper específica
from .scrapers.abicom_scraper import AbicomScraper

# Tenta importar constantes do arquivo config.py
try:
    from .config import MAX_PAGES, OUTPUT_DIR, ORGANIZE_BY_MONTH, BASE_URL, DATA_DIR
    # Garante que diretórios existam (redundante se config.py já faz, mas seguro)
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
except ImportError as e:
    # Fallback se config.py falhar
    print(f"ALERTA: Falha ao importar config: {e}. Usando valores padrão.", file=sys.stderr)
    MAX_PAGES=4; BASE_URL="https://abicom.com.br/categoria/ppi/"; ORGANIZE_BY_MONTH=True
    _default_data_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
    DATA_DIR = _default_data_path; OUTPUT_DIR = os.path.join(DATA_DIR, 'images')
    os.makedirs(DATA_DIR, exist_ok=True); os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"--> Defaults: Usando OUTPUT_DIR={OUTPUT_DIR}", file=sys.stderr)

# Importa o serviço de imagem (versão sem DB)
# ATENÇÃO: Garanta que 'src/services/image_service.py' seja a versão que
#          NÃO usa banco de dados e talvez precise de 'pre_check_monthly_images'.
from .services.image_service import ImageService

# Tenta importar a função de análise (versão sem DB, que gera CSV)
try:
    # Espera-se que esta função leia imagens do disco e salve um CSV
    from .analise_imagens import executar_e_reportar_analise
    analysis_function_available = True
except ImportError as ie:
    executar_e_reportar_analise = None; analysis_function_available = False
    print(f"ALERTA: Import '.analise_imagens' falhou: {ie}", file=sys.stderr)
    print("--> Análise avançada indisponível.", file=sys.stderr)

# Import da função de tratamento final do CSV
try:
    # Importa a função principal do módulo que trata o CSV gerado pela análise
    from .tratamento_dados import executar_tratamento_csv # <- Nome do módulo conforme sua informação
    treatment_function_available = True
except ImportError as ie:
    print(f"ALERTA: Import '.tratamento_dados' falhou: {ie}", file=sys.stderr) # <- Nome do módulo atualizado
    print("--> O tratamento final do CSV não será executado.", file=sys.stderr)
    executar_tratamento_csv = None
    treatment_function_available = False
# --- Fim dos Imports ---


# --- Configuração de Logging ---
# (Mantido como antes)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler('scraper.log', mode='w')])
logger = logging.getLogger(__name__)

# --- Definição das Funções ---

def parse_arguments():
    """ Analisa os argumentos da linha de comando. """
    # (Mantido como antes)
    parser = argparse.ArgumentParser(description='Web Scraper e Analisador Abicom PPI (Sem DB)')
    parser.add_argument('--start-page', type=int, default=1, help='Página inicial (padrão: 1)')
    parser.add_argument('--max-pages', type=int, default=MAX_PAGES, help=f'Máx. páginas (padrão: {MAX_PAGES})')
    parser.add_argument('--output-dir', type=str, default=OUTPUT_DIR, help=f'Dir. saída imagens (padrão: {OUTPUT_DIR})')
    parser.add_argument('--verbose', action='store_true', help='Log detalhado (DEBUG)')
    parser.add_argument('--analyze', action='store_true', help='Executa análise (gera CSV) e tratamento final.')
    return parser.parse_args()

# --- Função Principal (main) ---
def main():
    """
    Função principal (Versão Sem DB): Orquestra o processo.
    """
    # 1. Parse Args
    args = parse_arguments()

    # 2. Setup Logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.getLogger().setLevel(log_level)
    logger.info(f"Log level: {logging.getLevelName(log_level)}")

    # REMOVIDO: Inicialização do Banco de Dados
    # logger.info("--- Inicializando Banco de Dados ---") # REMOVIDO
    # try: # REMOVIDO
    #     db.initialize_database() # REMOVIDO
    #     logger.info("Banco de dados inicializado com sucesso.") # REMOVIDO
    # except Exception as db_init_err: # REMOVIDO
    #      logger.critical(f"ERRO CRÍTICO inicializando DB: {db_init_err}", exc_info=True) # REMOVIDO
    #      return 1 # REMOVIDO

    # 3. Create Dirs (Numerado corretamente agora)
    logger.info("--- 1. Verificando/Criando Diretórios ---") # Numerado como passo 1
    try:
        os.makedirs(args.output_dir, exist_ok=True); logger.info(f"Dir. imagens: {args.output_dir}")
        data_dir_analysis = DATA_DIR; os.makedirs(data_dir_analysis, exist_ok=True); logger.info(f"Dir. dados/relatórios: {data_dir_analysis}")
    except Exception as dir_err: logger.critical(f"Erro criar diretórios: {dir_err}", exc_info=True); return 1

    # 4. Log Inicial (Numerado corretamente agora)
    logger.info(f"--- 2. Iniciando Execução (Versão Sem DB) ---"); logger.info(f"Argumentos: {args}") # Numerado como passo 2
    logger.info(f"Configs: OrganizePorMês={ORGANIZE_BY_MONTH}, URL={BASE_URL}")
    analysis_status_log = "HABILITADA" if args.analyze else "DESABILITADA";
    if args.analyze and not analysis_function_available: analysis_status_log += " (ANÁLISE INDISPONÍVEL!)"
    if args.analyze and analysis_function_available and not treatment_function_available: analysis_status_log += " (TRATAMENTO CSV INDISPONÍVEL!)"
    logger.info(f"Análise e Tratamento (--analyze): {analysis_status_log}")

    # --- Bloco de Execução do Scraper ---
    # (Mantido como na versão Sem DB anterior)
    total_downloads = 0; scraper_success = False; exception_during_scraping = None
    logger.info("--- 3. Iniciando Bloco do Scraper ---") # Numerado como passo 3
    try:
        image_service = ImageService(output_dir=args.output_dir)
        # A versão sem DB do ImageService PODE precisar desta linha:
        logger.info("Pré-indexando imagens existentes no disco (lógica sem DB)...")
        image_service.pre_check_monthly_images() # MANTIDO
        # Instancia scraper com URL correta
        with AbicomScraper(image_service=image_service, base_url=BASE_URL) as scraper:
            logger.info(f"Executando scraper.run: Páginas {args.start_page} a {args.start_page + args.max_pages - 1}")
            total_downloads = scraper.run(start_page=args.start_page, max_pages=args.max_pages)
        if total_downloads > 0: logger.info(f"Scraping concluído. {total_downloads} novas imagens baixadas.")
        else: logger.info("Scraping concluído. Nenhuma nova imagem baixada.")
        scraper_success = True
    except KeyboardInterrupt as e: logger.warning("Scraping interrompido."); exception_during_scraping = e; scraper_success = False
    except Exception as e: logger.error(f"Erro inesperado scraping: {e}", exc_info=True); exception_during_scraping = e; scraper_success = False
    logger.info("--- Bloco do Scraper Finalizado ---")
    # --- Fim do Bloco Scraper ---


    # --- Bloco de Execução da Análise (Gera CSV) ---
    analysis_success = True
    # Roda se --analyze foi pedido E scraper OK (ou interrompido) E função existe
    if args.analyze and (scraper_success or isinstance(exception_during_scraping, KeyboardInterrupt)) and analysis_function_available:
        logger.info("--- 4. Iniciando Bloco da Análise de Imagens (Gerando CSV) ---") # Numerado como passo 4
        try:
            # Chama a função de analise_imagens.py (versão SEM DB)
            executar_e_reportar_analise(
                diretorio_imagens=args.output_dir,
                organizar_por_mes=ORGANIZE_BY_MONTH,
                diretorio_csv=data_dir_analysis # Passa diretório 'data' para salvar CSV
            )
            logger.info("Função de análise (gerar CSV) executada.")
        except Exception as e_analysis: logger.error(f"Erro inesperado análise: {e_analysis}", exc_info=True); analysis_success = False
        logger.info("--- Bloco da Análise de Imagens Finalizado ---")
    elif args.analyze and not analysis_function_available: logger.error("Análise solicitada, mas função indisponível."); analysis_success = False
    elif args.analyze: logger.warning("Análise pulada devido à falha no scraper."); analysis_success = False
    else: logger.info("Análise de imagens não solicitada (--analyze).")
    # --- Fim do Bloco Análise ---


    # --- Bloco de Tratamento do CSV Final ---
    treatment_success = True # Assume sucesso
    # Roda se: Análise foi pedida E Análise principal OK E Função de tratamento existe
    if args.analyze and analysis_success and treatment_function_available:
        logger.info("--- 5. Iniciando Bloco de Tratamento do CSV Final ---") # Numerado como passo 5
        try:
            # Chama a função importada de tratamento_dados.py
            executar_tratamento_csv()
            logger.info("Tratamento do CSV final concluído.")
        except Exception as treat_err: logger.error(f"Erro tratamento CSV: {treat_err}", exc_info=True); treatment_success = False
        logger.info("--- Bloco de Tratamento do CSV Finalizado ---")
    elif args.analyze and analysis_success and not treatment_function_available:
         logger.warning("Análise OK, mas tratamento CSV indisponível.")
         treatment_success = False
    # --- Fim do Bloco Tratamento CSV ---


    # --- Status Final de Saída ---
    logger.info("--- 6. Avaliando Status Final ---") # Numerado como passo 6
    # Sucesso final considera scraper OK (ou interrompido) E análise principal OK (se feita)
    # O tratamento do CSV é um passo extra e seu sucesso/falha não altera o código de saída.
    final_success = (scraper_success or isinstance(exception_during_scraping, KeyboardInterrupt)) and \
                    (not args.analyze or (analysis_function_available and analysis_success))
    if final_success: logger.info("Status final: Sucesso."); return 0
    else:
        logger.error("Status final: Falha (ver logs).")
        if not scraper_success and not isinstance(exception_during_scraping, KeyboardInterrupt): logger.error(f"--> Causa: Falha scraping: {exception_during_scraping}")
        if args.analyze and not analysis_success: logger.error("--> Causa: Falha análise ou função indisponível.")
        return 1

# --- Ponto de Entrada Principal (__name__ == "__main__") ---
if __name__ == "__main__":
    logger.info(f"Executando script principal: {__file__}")
    exit_code = main() # Chama a função main
    logging.shutdown() # Fecha handlers de log
    print(f"Script finalizado. Código de saída: {exit_code}")
    sys.exit(exit_code) # Sai com o código