# src/main.py

"""
Ponto de entrada principal para o scraper da Abicom (versão SEM DB).
Orquestra: Configuração, Scraping, Análise de Imagens (gera CSV final tratado).
"""
# --- Imports Padrão ---
import os
import sys
import logging
import argparse

# --- Configuração de Logging (MOVIDA PARA O TOPO) ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler('scraper.log', mode='w')]
)
logger = logging.getLogger(__name__)
# --- Fim Configuração de Logging ---

# --- Imports do Projeto ---
logger.debug("Iniciando imports do projeto...")
from .scrapers.abicom_scraper import AbicomScraper
try:
    from .config import MAX_PAGES, OUTPUT_DIR, ORGANIZE_BY_MONTH, BASE_URL, DATA_DIR
    os.makedirs(DATA_DIR, exist_ok=True); os.makedirs(OUTPUT_DIR, exist_ok=True)
    logger.info("Configurações carregadas de .config.")
except ImportError as e:
    logger.error(f"Falha ao importar config: {e}. Usando padrões.", exc_info=True)
    # ... (Fallback como antes) ...
    MAX_PAGES=4; BASE_URL="https://abicom.com.br/categoria/ppi/"; ORGANIZE_BY_MONTH=True; _default_data_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data')); DATA_DIR = _default_data_path; OUTPUT_DIR = os.path.join(DATA_DIR, 'images'); os.makedirs(DATA_DIR, exist_ok=True); os.makedirs(OUTPUT_DIR, exist_ok=True); logger.warning(f"--> Usando Defaults: OUTPUT_DIR={OUTPUT_DIR}")

# ATENÇÃO: Garanta que 'src/services/image_service.py' seja a versão SEM DB!
from .services.image_service import ImageService
try:
    # Espera-se que esta versão GERE o CSV FINAL 'tabela_tratada.csv'
    from .analise_imagens import executar_e_reportar_analise
    analysis_function_available = True
    logger.info("Função 'executar_e_reportar_analise' importada.")
except ImportError as ie:
    logger.error(f"Falha ao importar '.analise_imagens': {ie}", exc_info=True)
    executar_e_reportar_analise = None; analysis_function_available = False
    logger.warning("--> Análise avançada indisponível.")

# REMOVIDO: Import da função de tratamento final do CSV, pois foi incorporada à análise.
# try:
#     from .tratamento_dados import executar_tratamento_csv
#     treatment_function_available = True
# except ImportError as ie:
#     logger.warning(f"Import '.tratamento_dados' falhou: {ie}")
#     executar_tratamento_csv = None; treatment_function_available = False
# --- Fim dos Imports ---


# --- Definição das Funções ---
def parse_arguments():
    """ Analisa os argumentos da linha de comando. """
    parser = argparse.ArgumentParser(description='Web Scraper e Analisador Abicom PPI (Gera CSV Final Tratado)', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--start-page', type=int, default=1, help='Página inicial.')
    parser.add_argument('--max-pages', type=int, default=MAX_PAGES, help=f'Máx. páginas ({MAX_PAGES}).')
    parser.add_argument('--output-dir', type=str, default=OUTPUT_DIR, help=f'Dir. saída imagens ({OUTPUT_DIR}).')
    parser.add_argument('--verbose', '-v', action='store_true', help='Log DEBUG.')
    parser.add_argument('--analyze', '-a', action='store_true', help='Executa análise final (gera tabela_tratada.csv).') # Help ajustado
    return parser.parse_args()

# --- Função Principal (main) ---
def main():
    """ Função principal (Versão Sem DB): Orquestra o processo. """
    exit_code = 0
    try:
        # 1. Args e Logging
        args = parse_arguments()
        log_level = logging.DEBUG if args.verbose else logging.INFO
        logging.getLogger().setLevel(log_level) # Define no raiz
        logger.info(f"Log level: {logging.getLevelName(log_level)}")

        # 2. Diretórios
        logger.info("--- 1. Verificando/Criando Diretórios ---")
        # Criação movida para o import de config, apenas loga aqui
        logger.info(f"Dir. imagens: {args.output_dir}")
        logger.info(f"Dir. dados/relatórios: {DATA_DIR}")
        data_dir_analysis = DATA_DIR # Usado para passar para análise

        # 3. Log Inicial
        logger.info(f"--- 2. Iniciando Execução (Versão Sem DB) ---")
        logger.info(f"Argumentos: {args}")
        logger.info(f"Configs: OrganizePorMês={ORGANIZE_BY_MONTH}, URL={BASE_URL}")
        analysis_status_log = "HABILITADA" if args.analyze else "DESABILITADA"
        if args.analyze and not analysis_function_available: analysis_status_log += " (FUNÇÃO INDISPONÍVEL!)"
        # REMOVIDO: Verificação de treatment_function_available
        logger.info(f"Análise Final (--analyze): {analysis_status_log}")

        # --- 4. Bloco Scraper ---
        # (Mantido como antes)
        total_downloads = 0; scraper_success = False; exception_during_scraping = None
        logger.info("--- 3. Iniciando Bloco do Scraper ---")
        try:
            image_service = ImageService(output_dir=args.output_dir)
            logger.info("Pré-indexando imagens (lógica sem DB)...")
            image_service.pre_check_monthly_images() # Mantido
            with AbicomScraper(image_service=image_service, base_url=BASE_URL) as scraper:
                 total_downloads = scraper.run(start_page=args.start_page, max_pages=args.max_pages)
            if total_downloads > 0: logger.info(f"Scraping OK. {total_downloads} novas imagens.")
            else: logger.info("Scraping OK. Nenhuma nova imagem.")
            scraper_success = True
        except KeyboardInterrupt as e: logger.warning("Scraping interrompido."); exception_during_scraping = e; scraper_success = False
        except Exception as e: logger.error(f"Erro scraping: {e}", exc_info=True); exception_during_scraping = e; scraper_success = False
        logger.info("--- Bloco do Scraper Finalizado ---")

        # --- 5. Bloco Análise (Gera CSV Final Tratado) ---
        analysis_success = True
        if args.analyze and (scraper_success or isinstance(exception_during_scraping, KeyboardInterrupt)) and analysis_function_available:
            logger.info("--- 4. Iniciando Bloco da Análise (Gerando CSV Final Tratado) ---")
            try:
                # Chama a função que agora salva o CSV final 'tabela_tratada.csv'
                executar_e_reportar_analise(
                    diretorio_imagens=args.output_dir,
                    organizar_por_mes=ORGANIZE_BY_MONTH,
                    diretorio_csv=data_dir_analysis # Passa pasta 'data'
                )
                logger.info("Função de análise (gerar CSV final) executada.")
            except Exception as e_analysis: logger.error(f"Erro análise: {e_analysis}", exc_info=True); analysis_success = False
            logger.info("--- Bloco da Análise Finalizado ---")
        elif args.analyze and not analysis_function_available: logger.error("Análise solicitada, mas função indisponível."); analysis_success = False
        elif args.analyze: logger.warning("Análise pulada por falha no scraper."); analysis_success = False
        else: logger.info("Análise não solicitada.")

        # REMOVIDO: Bloco de Tratamento do CSV Final, pois foi incorporado à análise.

        # --- 6. Status Final ---
        logger.info("--- 5. Avaliando Status Final ---")
        final_success = (scraper_success or isinstance(exception_during_scraping, KeyboardInterrupt)) and \
                        (not args.analyze or (analysis_function_available and analysis_success))
        if final_success: logger.info("Status final: Sucesso."); exit_code = 0
        else: logger.error("Status final: Falha (ver logs)."); exit_code = 1; # Loga causas como antes

    except Exception as main_err: logger.critical(f"Erro fatal main: {main_err}", exc_info=True); exit_code = 2
    finally: logger.info(f"Finalizando execução. Código saída: {exit_code}"); logging.shutdown(); return exit_code

# --- Ponto de Entrada ---
if __name__ == "__main__":
    logger.info(f"Executando script principal: {__file__}")
    exit_code_final = main()
    print(f"Script finalizado. Código de saída: {exit_code_final}")
    sys.exit(exit_code_final)