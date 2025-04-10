# src/main.py

"""
Ponto de entrada principal para o scraper da Abicom.
"""
import os
import sys
import logging
import argparse
# Remova imports não usados diretamente em main.py se a análise for externa
# import re
# import pandas as pd
# from datetime import datetime

# Importações do projeto
from src.scrapers.abicom_scraper import AbicomScraper
from src.config import MAX_PAGES, OUTPUT_DIR, ORGANIZE_BY_MONTH
# Importa a função de análise externa
try:
    from src.analise_imagens import executar_e_reportar_analise
    analysis_function_available = True
except ImportError as ie:
    executar_e_reportar_analise = None
    analysis_function_available = False
    # Log configurado abaixo, mas imprime erro crítico imediatamente
    print(f"ERRO CRÍTICO: Não foi possível importar a função de análise avançada: {ie}", file=sys.stderr)
    print("Verifique se todas as dependências de 'analise_imagens.py' (pandas, Pillow, numpy, easyocr, torch, img2table) estão instaladas.", file=sys.stderr)

# Configuração de logging
logging.basicConfig(
    level=logging.INFO, # Nível inicial, pode ser alterado por --verbose
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('scraper.log', mode='w') # modo 'w' para sobrescrever log a cada execução
    ]
)
logger = logging.getLogger(__name__) # Logger principal para main.py

# Função parse_arguments (sem alterações)
def parse_arguments():
    parser = argparse.ArgumentParser(description='Web Scraper e Analisador Abicom PPI')
    parser.add_argument('--start-page', type=int, default=1, help='Página inicial (padrão: 1)')
    parser.add_argument('--max-pages', type=int, default=MAX_PAGES, help=f'Máximo de páginas (padrão: {MAX_PAGES})')
    parser.add_argument('--output-dir', type=str, default=OUTPUT_DIR, help=f'Diretório de saída para imagens (padrão: {OUTPUT_DIR})')
    parser.add_argument('--verbose', action='store_true', help='Habilita logging detalhado (DEBUG)')
    parser.add_argument('--analyze', action='store_true', help='Executa análise avançada (OCR/Tabela) após scraping.')
    return parser.parse_args()

def main():
    """
    Função principal: executa scraper e, opcionalmente, a análise.
    """
    args = parse_arguments()

    # Configura nível de log global baseado em --verbose
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.getLogger().setLevel(log_level) # Ajusta o nível do logger raiz

    # Diretório para salvar o CSV da análise (diretório pai do diretório das imagens)
    try:
        data_dir_analysis = os.path.dirname(args.output_dir)
        if not data_dir_analysis: # Caso output_dir seja a raiz (improvável)
             data_dir_analysis = "."
        os.makedirs(data_dir_analysis, exist_ok=True)
    except Exception as dir_err:
         logger.critical(f"Erro ao definir/criar diretório de análise '{data_dir_analysis}' a partir de '{args.output_dir}': {dir_err}")
         return 1 # Erro crítico de diretório

    logger.info(f"--- Iniciando Execução ---")
    logger.info(f"Scraper: Páginas {args.start_page} a {args.start_page + args.max_pages - 1}")
    logger.info(f"Diretório de Imagens: {args.output_dir}")
    logger.info(f"Organizar por Mês: {ORGANIZE_BY_MONTH}")
    logger.info(f"Análise Avançada (--analyze): {'Habilitada' if args.analyze else 'Desabilitada'}")
    if args.analyze and not analysis_function_available:
        logger.error("Análise avançada foi solicitada, mas não está disponível devido a erro de importação.")

    # Garante que o diretório de saída das imagens exista
    try:
        os.makedirs(args.output_dir, exist_ok=True)
    except Exception as dir_err:
        logger.critical(f"Erro ao criar diretório de saída de imagens '{args.output_dir}': {dir_err}")
        return 1

    total_downloads = 0
    scraper_success = False # Flag para indicar sucesso do scraper
    exception_during_scraping = None # Armazena exceção do scraper

    # --- Bloco de Execução do Scraper ---
    logger.info("--- Iniciando Scraper ---")
    try:
        # Importa o serviço SÓ quando necessário
        from src.services.image_service import ImageService
        image_service = ImageService(output_dir=args.output_dir)

        logger.info("Pré-indexando imagens existentes...")
        image_service.pre_check_monthly_images()

        # Usa 'with' para garantir que os recursos do scraper (ex: sessão http) sejam fechados
        with AbicomScraper(image_service=image_service) as scraper:
            total_downloads = scraper.run(
                start_page=args.start_page,
                max_pages=args.max_pages
            )

        if total_downloads > 0:
            logger.info(f"Scraping concluído. Total de {total_downloads} novas imagens baixadas.")
        else:
            logger.info("Scraping concluído. Nenhuma nova imagem foi baixada (ou todas já existiam).")
        scraper_success = True # Scraper terminou sem lançar exceção

    except KeyboardInterrupt as e:
        logger.warning("Scraping interrompido pelo usuário.")
        exception_during_scraping = e
        scraper_success = False # Interrupção não é sucesso completo
    except ImportError as e:
        # Erro crítico se não conseguir importar componentes do scraper
        logger.critical(f"Erro FATAL de importação durante o scraping: {e}. Verifique as dependências do scraper.", exc_info=True)
        # Não tenta análise se o próprio scraper não pôde ser importado/montado
        return 1
    except Exception as e:
        # Outros erros durante o scraping
        logger.error(f"Erro durante a execução do scraping: {e}", exc_info=True) # Log completo do erro
        exception_during_scraping = e
        scraper_success = False
    logger.info("--- Scraper Finalizado ---")
    # --- Fim do Bloco Scraper ---


    # --- Bloco de Execução da Análise ---
    analysis_success = True # Assume sucesso a menos que falhe
    if args.analyze:
        logger.info("--- Iniciando Análise Avançada ---")
        if analysis_function_available:
            try:
                # Chama a função externa que faz todo o trabalho de análise e reporte
                executar_e_reportar_analise(
                    diretorio_imagens=args.output_dir,
                    organizar_por_mes=ORGANIZE_BY_MONTH,
                    diretorio_csv=data_dir_analysis # Passa o diretório 'data'
                )
                # Log de sucesso já está dentro da função chamada
            except Exception as e_analysis:
                logger.error(f"Erro durante a execução da análise avançada: {e_analysis}", exc_info=True)
                analysis_success = False # Marca que a análise falhou
        else:
            logger.error("Análise avançada solicitada (--analyze), mas a função não estava disponível devido a erro de importação anterior.")
            analysis_success = False # Marca como falha se foi pedida mas não disponível
        logger.info("--- Análise Finalizada ---")
    else:
         logger.info("Análise avançada não solicitada (flag --analyze não utilizada).")
    # --- Fim do Bloco Análise ---


    # --- Status Final de Saída ---
    logger.info("--- Execução Concluída ---")
    # Retorna 0 (sucesso) apenas se:
    # - Scraper teve sucesso OU foi interrompido pelo usuário
    # - E (Análise não foi solicitada OU (Análise foi solicitada E teve sucesso))
    final_success = (scraper_success or isinstance(exception_during_scraping, KeyboardInterrupt)) and \
                    (not args.analyze or analysis_success)

    if final_success:
        logger.info("Status final: Sucesso.")
        return 0
    else:
        logger.error("Status final: Falha (verificar logs para detalhes).")
        return 1


if __name__ == "__main__":
    # Verifica se Pandas está disponível se a análise for solicitada
    # Este check é básico, erros em outras dependências da análise serão pegos no import
    if '--analyze' in sys.argv:
        try:
            import pandas
        except ImportError:
            # Loga o erro mas não sai imediatamente, deixa o try/except do import cuidar disso
            logging.critical("Pandas (dependência da análise) não encontrado. Instale com 'pip install pandas'.")
            # print("ERRO: Pandas é necessário...", file=sys.stderr) # Opcional
            # print("Instale com: pip install pandas", file=sys.stderr)

    # Chama a função principal e usa seu código de retorno para sair
    exit_code = main()
    sys.exit(exit_code)