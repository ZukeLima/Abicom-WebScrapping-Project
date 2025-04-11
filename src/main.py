# src/main.py (CORRIGIDO com Logging Aprimorado)

"""
Ponto de entrada principal para o scraper da Abicom (versão SEM DB).
Orquestra: Configuração, Scraping, Análise de Imagens (gera CSVs individuais por mês),
e Tratamento Adicional do CSV gerado (se habilitado).
"""
# --- Imports Padrão ---
import os
import sys
import logging
import argparse
# Adiciona logging.FileHandler
from logging import FileHandler, StreamHandler

# --- Configuração de Logging (MOVIDA PARA O TOPO e MELHORADA) ---
# Define o diretório de dados ANTES de configurar o log de erro
try:
    # Tenta obter DATA_DIR de config primeiro
    import src.config # Importa o módulo config para pegar DATA_DIR
    DATA_DIR_FOR_LOG = src.config.DATA_DIR
    if not DATA_DIR_FOR_LOG or not os.path.isdir(DATA_DIR_FOR_LOG):
        raise ValueError("DATA_DIR inválido em config.py")
    os.makedirs(DATA_DIR_FOR_LOG, exist_ok=True) # Garante que exista
    ERROR_LOG_PATH = os.path.join(DATA_DIR_FOR_LOG, 'error.log')
    GENERAL_LOG_PATH = 'scraper.log' # Na raiz do projeto
except Exception as config_err:
    # Fallback se config ou DATA_DIR falharem
    print(f"[CONFIG FALLBACK] Erro ao obter DATA_DIR de config: {config_err}. Usando pasta 'data' relativa.", file=sys.stderr)
    _fallback_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
    os.makedirs(_fallback_data_dir, exist_ok=True)
    DATA_DIR_FOR_LOG = _fallback_data_dir
    ERROR_LOG_PATH = os.path.join(DATA_DIR_FOR_LOG, 'error.log')
    GENERAL_LOG_PATH = 'scraper.log'
    print(f"[CONFIG FALLBACK] Caminho do log de erro: {ERROR_LOG_PATH}", file=sys.stderr)

# Configuração base - Nível DEBUG captura tudo inicialmente
logging.basicConfig(
    level=logging.DEBUG, # Começa com DEBUG para capturar tudo
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    # REMOVIDO handlers daqui, serão adicionados abaixo
    # handlers=[ StreamHandler(sys.stdout), FileHandler(GENERAL_LOG_PATH, mode='w') ]
)
# Obtém o logger raiz
root_logger = logging.getLogger()
# Limpa handlers pré-existentes (caso basicConfig tenha adicionado algum default)
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# Cria handler para console (INFO e acima por padrão)
console_handler = StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO) # Nível padrão para console
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s') # Formato mais simples para console
console_handler.setFormatter(console_formatter)
root_logger.addHandler(console_handler)

# Cria handler para log geral (DEBUG e acima por padrão)
general_log_handler = FileHandler(GENERAL_LOG_PATH, mode='w', encoding='utf-8')
general_log_handler.setLevel(logging.DEBUG) # Nível padrão para arquivo geral
general_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
general_log_handler.setFormatter(general_formatter)
root_logger.addHandler(general_log_handler)

# Cria handler APENAS para erros (nível ERROR e CRITICAL)
try:
    error_log_handler = FileHandler(ERROR_LOG_PATH, mode='w', encoding='utf-8')
    error_log_handler.setLevel(logging.ERROR) # Só captura ERROR e CRITICAL
    error_log_handler.setFormatter(general_formatter) # Usa mesmo formato detalhado
    root_logger.addHandler(error_log_handler)
    print(f"INFO: Log de erros será salvo em: {ERROR_LOG_PATH}") # Confirmação para o usuário
except Exception as log_err:
    print(f"ERRO CRÍTICO: Não foi possível configurar o log de erro em '{ERROR_LOG_PATH}': {log_err}", file=sys.stderr)
    # Continua sem o log de erro separado se falhar

# Obtém logger específico para este módulo após configuração
logger = logging.getLogger(__name__)
# --- Fim Configuração de Logging ---


# --- Imports do Projeto ---
# (Imports relativos como na resposta anterior)
logger.debug("Iniciando imports do projeto...")
from .scrapers.abicom_scraper import AbicomScraper
try: from .config import MAX_PAGES, OUTPUT_DIR, ORGANIZE_BY_MONTH, BASE_URL, DATA_DIR
except ImportError as e: logger.critical(f"Falha CRÍTICA ao importar config: {e}. Usando fallbacks.", exc_info=True); raise e # Re-lança erro crítico de config
from .services.image_service import ImageService
try: from .analise_imagens import executar_e_reportar_analise; analysis_function_available = True; logger.info("Função de análise importada.")
except ImportError as ie: logger.error(f"Falha ao importar '.analise_imagens': {ie}", exc_info=True); executar_e_reportar_analise = None; analysis_function_available = False; logger.warning("--> Análise avançada indisponível.")
try: from .tratamento_dados import executar_tratamento_csv; treatment_function_available = True; logger.info("Função de tratamento CSV importada.")
except ImportError as ie: logger.warning(f"Falha ao importar '.tratamento_dados': {ie}"); logger.warning("--> Tratamento final CSV indisponível."); executar_tratamento_csv = None; treatment_function_available = False
# --- Fim Imports ---


# --- Definição das Funções ---
def parse_arguments():
    """ Analisa os argumentos da linha de comando. """
    # (Mantido como na última versão)
    parser = argparse.ArgumentParser(description='Web Scraper e Analisador Abicom PPI (Sem DB)', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--start-page', type=int, default=1, help='Página inicial.')
    parser.add_argument('--max-pages', type=int, default=MAX_PAGES, help=f'Máx. páginas ({MAX_PAGES}).')
    parser.add_argument('--output-dir', type=str, default=OUTPUT_DIR, help=f'Dir. saída imagens ({OUTPUT_DIR}).')
    parser.add_argument('--verbose', '-v', action='store_true', help='Log DEBUG.')
    parser.add_argument('--analyze', '-a', action='store_true', help='Executa análise (gera CSVs por mês).') # Help ajustado
    return parser.parse_args()

# --- Função Principal (main) ---
def main():
    """ Função principal (Versão Sem DB): Orquestra o processo. """
    exit_code = 0
    try:
        # 1. Parse Args & Setup Logging Level
        args = parse_arguments()
        log_level = logging.DEBUG if args.verbose else logging.INFO
        # Define o nível para TODOS os handlers configurados no logger raiz
        logging.getLogger().setLevel(log_level)
        # Log inicial já usando o nível definido
        logger.info(f"Nível de log definido para: {logging.getLevelName(log_level)}")

        # 2. Verificando/Criando Diretórios
        # (Logica mantida, mas criação principal acontece em config.py ou fallback)
        logger.info("--- 1. Verificando Diretórios (já devem existir) ---")
        logger.info(f"Dir. imagens: {args.output_dir}")
        logger.info(f"Dir. dados/relatórios: {DATA_DIR}")
        data_dir_analysis = DATA_DIR # Usado para passar para análise

        # 3. Log Inicial da Execução
        logger.info(f"--- 2. Iniciando Execução (Versão Sem DB) ---")
        # ... (logs de argumentos e configs como antes) ...

        # --- 4. Bloco Scraper ---
        # ... (lógica do scraper como antes, com pre_check_monthly_images) ...
        total_downloads = 0; scraper_success = False; exception_during_scraping = None
        logger.info("--- 3. Iniciando Bloco do Scraper ---")
        try:
            image_service = ImageService(output_dir=args.output_dir)
            logger.info("Pré-indexando imagens existentes no disco...")
            image_service.pre_check_monthly_images() # MANTIDO para Sem DB
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
        if args.analyze and (scraper_success or isinstance(exception_during_scraping, KeyboardInterrupt)) and analysis_function_available:
            logger.info("--- 4. Iniciando Bloco da Análise (Salvando Tabelas Individuais) ---")
            try:
                # Chama a função que salva tabelas individuais e reporta contagem
                executar_e_reportar_analise(
                    diretorio_imagens=args.output_dir,
                    organizar_por_mes=ORGANIZE_BY_MONTH,
                    diretorio_csv=data_dir_analysis # Passa diretório 'data', mas não salva CSV principal aqui
                )
                # Assume sucesso se não houve exceção. Para maior precisão,
                # executar_e_reportar_analise poderia retornar um status.
                logger.info("Função de análise/salvamento de tabelas executada.")
            except Exception as e_analysis: logger.error(f"Erro análise: {e_analysis}", exc_info=True); analysis_success = False
            logger.info("--- Bloco da Análise Finalizado ---")
        elif args.analyze and not analysis_function_available: logger.error("Análise solicitada, mas função indisponível."); analysis_success = False
        elif args.analyze: logger.warning("Análise pulada por falha no scraper."); analysis_success = False
        else: logger.info("Análise não solicitada.")

        # REMOVIDO: Bloco de Tratamento do CSV Final (não aplicável a este fluxo)

        # --- 6. Status Final ---
        logger.info("--- 5. Avaliando Status Final ---")
        final_success = (scraper_success or isinstance(exception_during_scraping, KeyboardInterrupt)) and \
                        (not args.analyze or (analysis_function_available and analysis_success))
        if final_success: logger.info("Status final: Sucesso."); exit_code = 0
        else: logger.error("Status final: Falha (ver logs)."); exit_code = 1; # Loga causas...

    except Exception as main_err: logger.critical(f"Erro fatal main: {main_err}", exc_info=True); exit_code = 2
    finally: logger.info(f"Finalizando execução. Código saída: {exit_code}"); logging.shutdown(); return exit_code


# --- Ponto de Entrada Principal ---
if __name__ == "__main__":
    # O logger já está configurado no topo do arquivo
    logger.info(f"Executando script principal: {__file__}")
    exit_code_final = main()
    print(f"Script finalizado. Código de saída: {exit_code_final}")
    sys.exit(exit_code_final)