# src/main.py 
"""
Ponto de entrada principal para o scraper da Abicom (versão SEM DB).
Orquestra: Configuração, Scraping (download imagens), Análise de Imagens
(extrai tabelas e salva CSVs individuais por mês/ano).
"""
# --- Imports Padrão ---
import os
import sys
import logging
import argparse
from logging import FileHandler, StreamHandler # Import explícito

# --- Configuração de Logging (NO TOPO) ---
# Configura logging antes de importar módulos do projeto
try:
    import src.config # Importa config para pegar DATA_DIR
    DATA_DIR_FOR_LOG = src.config.DATA_DIR
    if not DATA_DIR_FOR_LOG or not os.path.isdir(DATA_DIR_FOR_LOG): raise ValueError("DATA_DIR inválido")
    os.makedirs(DATA_DIR_FOR_LOG, exist_ok=True)
    ERROR_LOG_PATH = os.path.join(DATA_DIR_FOR_LOG, 'error.log'); GENERAL_LOG_PATH = 'scraper.log'
except Exception as config_err:
    print(f"[CONFIG FALLBACK] Erro obter/criar DATA_DIR: {config_err}. Usando 'data' relativo.", file=sys.stderr)
    _fallback_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
    os.makedirs(_fallback_data_dir, exist_ok=True); DATA_DIR_FOR_LOG = _fallback_data_dir
    ERROR_LOG_PATH = os.path.join(DATA_DIR_FOR_LOG, 'error.log'); GENERAL_LOG_PATH = 'scraper.log'
# Configuração base
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
root_logger = logging.getLogger(); # Obtém logger raiz
for handler in root_logger.handlers[:]: root_logger.removeHandler(handler) # Limpa handlers default
# Handler Console (INFO+)
console_handler = StreamHandler(sys.stdout); console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'); console_handler.setFormatter(console_formatter)
root_logger.addHandler(console_handler)
# Handler Log Geral (DEBUG+)
try:
    general_log_handler = FileHandler(GENERAL_LOG_PATH, mode='w', encoding='utf-8'); general_log_handler.setLevel(logging.DEBUG)
    general_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'); general_log_handler.setFormatter(general_formatter)
    root_logger.addHandler(general_log_handler)
except Exception as log_gen_err: print(f"ERRO: Falha criar log geral '{GENERAL_LOG_PATH}': {log_gen_err}", file=sys.stderr)
# Handler Log de Erro (ERROR+)
try:
    error_log_handler = FileHandler(ERROR_LOG_PATH, mode='w', encoding='utf-8'); error_log_handler.setLevel(logging.ERROR)
    error_log_handler.setFormatter(general_formatter); root_logger.addHandler(error_log_handler)
    print(f"INFO: Log de erros será salvo em: {ERROR_LOG_PATH}")
except Exception as log_err: print(f"ERRO: Falha config log erro '{ERROR_LOG_PATH}': {log_err}", file=sys.stderr)
# Logger específico para main.py
logger = logging.getLogger(__name__)
# --- Fim Configuração de Logging ---


# --- Imports do Projeto ---
logger.debug("Iniciando imports do projeto...")
from .scrapers.abicom_scraper import AbicomScraper # Scraper Abicom
try: # Configurações
    from .config import MAX_PAGES, OUTPUT_DIR, ORGANIZE_BY_MONTH, BASE_URL, DATA_DIR
    logger.info("Configurações carregadas de .config.")
except ImportError as e: # Fallback
    logger.critical(f"Falha CRÍTICA importar config: {e}. Usando fallbacks.", exc_info=True); raise e
# Serviço de Imagem (Versão SEM DB)
from .services.image_service import ImageService
try: # Função de Análise (Versão SEM DB - Salva Tabelas Individuais)
    from .analise_imagens import executar_e_reportar_analise
    analysis_function_available = True
    logger.info("Função de análise 'executar_e_reportar_analise' importada.")
except ImportError as ie: # Erro ao importar análise
    logger.error(f"Falha ao importar '.analise_imagens': {ie}", exc_info=True)
    executar_e_reportar_analise = None; analysis_function_available = False
    logger.warning("--> Análise avançada indisponível.")

# REMOVIDO: Import da função de tratamento final do CSV
# try: from .tratamento_dados import executar_tratamento_csv ...
# --- Fim Imports ---


# --- Definição das Funções ---
def parse_arguments():
    """ Analisa os argumentos da linha de comando. """
    parser = argparse.ArgumentParser(
        description='Web Scraper Abicom PPI e Analisador de Imagens (Salva Tabelas Individuais)', # Descrição atualizada
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--start-page', type=int, default=1, help='Página inicial.')
    parser.add_argument('--max-pages', type=int, default=MAX_PAGES, help=f'Máx. páginas ({MAX_PAGES}).')
    parser.add_argument('--output-dir', type=str, default=OUTPUT_DIR, help=f'Dir. saída imagens ({OUTPUT_DIR}).')
    parser.add_argument('--verbose', '-v', action='store_true', help='Log DEBUG.')
    # Help ajustado para refletir a saída atual da análise
    parser.add_argument('--analyze', '-a', action='store_true', help='Executa análise (gera CSVs individuais por mês).')
    return parser.parse_args()

# --- Função Principal (main) ---
def main():
    """ Função principal (Versão Sem DB): Orquestra o processo. """
    exit_code = 0 # Código de saída
    try:
        # 1. Parse Args & Setup Logging Level
        args = parse_arguments()
        log_level = logging.DEBUG if args.verbose else logging.INFO
        logging.getLogger().setLevel(log_level) # Define nível global do log
        logger.info(f"Nível de log definido para: {logging.getLevelName(log_level)}")

        # 2. Verificando/Criando Diretórios
        logger.info("--- 1. Verificando Diretórios ---")
        logger.info(f"Dir. imagens: {args.output_dir}")
        logger.info(f"Dir. dados: {DATA_DIR}")
        # O diretório data/tabelas_por_mes será criado por analise_imagens.py se necessário
        data_dir_analysis = DATA_DIR # Usado para passar para análise

        # 3. Log Inicial da Execução
        logger.info(f"--- 2. Iniciando Execução (Versão Sem DB) ---")
        logger.info(f"Argumentos: {args}")
        logger.info(f"Configs: OrganizePorMês={ORGANIZE_BY_MONTH}, URL={BASE_URL}")
        analysis_status_log = "HABILITADA" if args.analyze else "DESABILITADA";
        if args.analyze and not analysis_function_available: analysis_status_log += " (FUNÇÃO INDISPONÍVEL!)"
        logger.info(f"Análise (--analyze): {analysis_status_log}") # Log não menciona mais tratamento

        # --- 4. Bloco Scraper ---
        total_downloads = 0; scraper_success = False; exception_during_scraping = None
        logger.info("--- 3. Iniciando Bloco do Scraper ---")
        try:
            image_service = ImageService(output_dir=args.output_dir) # Versão Sem DB
            logger.info("Pré-indexando imagens existentes no disco...")
            image_service.pre_check_monthly_images() # Necessário para ImageService Sem DB
            with AbicomScraper(image_service=image_service, base_url=BASE_URL) as scraper:
                 total_downloads = scraper.run(start_page=args.start_page, max_pages=args.max_pages)
            if total_downloads > 0: logger.info(f"Scraping OK. {total_downloads} novas imagens.")
            else: logger.info("Scraping OK. Nenhuma nova imagem.")
            scraper_success = True
        except KeyboardInterrupt as e: logger.warning("Scraping interrompido."); exception_during_scraping = e; scraper_success = False
        except Exception as e: logger.error(f"Erro scraping: {e}", exc_info=True); exception_during_scraping = e; scraper_success = False
        logger.info("--- Bloco do Scraper Finalizado ---")

        # --- 5. Bloco Análise (Salva CSVs Individuais por Mês) ---
        analysis_success = True # Assume sucesso
        # Roda se --analyze foi pedido E scraper OK (ou interrompido) E função existe
        if args.analyze and (scraper_success or isinstance(exception_during_scraping, KeyboardInterrupt)) and analysis_function_available:
            logger.info("--- 4. Iniciando Bloco da Análise (Salvando Tabelas Individuais) ---")
            try:
                # Chama a função que salva tabelas individuais e reporta contagem
                executar_e_reportar_analise(
                    diretorio_imagens=args.output_dir,
                    organizar_por_mes=ORGANIZE_BY_MONTH,
                    diretorio_csv=data_dir_analysis, # Passa 'data', mas não salva CSV principal aqui
                    num_workers=None # Usa default (os.cpu_count) - poderia ser argumento
                )
                # Assume sucesso se não houve exceção. A função reporta sucessos/falhas no console.
                # Para um controle mais fino do status final, poderíamos fazer
                # executar_e_reportar_analise retornar True/False baseado nas contagens.
                logger.info("Função de análise/salvamento de tabelas executada.")
            except Exception as e_analysis: logger.error(f"Erro análise: {e_analysis}", exc_info=True); analysis_success = False
            logger.info("--- Bloco da Análise Finalizado ---")
        elif args.analyze and not analysis_function_available: logger.error("Análise solicitada, mas função indisponível."); analysis_success = False
        elif args.analyze: logger.warning("Análise pulada por falha no scraper."); analysis_success = False
        else: logger.info("Análise não solicitada.")

        # REMOVIDO: Bloco de Tratamento do CSV Final

        # --- 6. Status Final ---
        logger.info("--- 5. Avaliando Status Final ---")
        # Sucesso final depende apenas do scraper E da análise principal (se feita)
        final_success = (scraper_success or isinstance(exception_during_scraping, KeyboardInterrupt)) and \
                        (not args.analyze or (analysis_function_available and analysis_success))
        if final_success: logger.info("Status final: Sucesso."); exit_code = 0
        else: logger.error("Status final: Falha (ver logs)."); exit_code = 1; # Loga causas como antes

    except Exception as main_err: logger.critical(f"Erro fatal main: {main_err}", exc_info=True); exit_code = 2
    finally: logger.info(f"Finalizando execução. Código saída: {exit_code}"); logging.shutdown(); return exit_code

# --- Ponto de Entrada Principal ---
if __name__ == "__main__":
    # Logger já configurado no topo
    logger.info(f"Executando script principal: {__file__}")
    exit_code_final = main() # Chama a função main
    print(f"Script finalizado. Código de saída: {exit_code_final}")
    sys.exit(exit_code_final) # Sai com o código