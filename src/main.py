"""
Ponto de entrada principal para o scraper da Abicom.
"""
import os
import sys
import logging
import argparse
from src.scrapers.abicom_scraper import AbicomScraper
from src.config import MAX_PAGES, OUTPUT_DIR

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
        default=OUTPUT_DIR,
        help=f'Diretório de saída para as imagens (padrão: {OUTPUT_DIR})'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Habilita logging detalhado'
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
    logger.info(f"As imagens serão organizadas em pastas mensais (MM-YYYY)")
    
    # Garante que o diretório de saída exista
    os.makedirs(args.output_dir, exist_ok=True)
    
    try:
        # Cria uma instância do serviço de imagens com o diretório de saída
        from src.services.image_service import ImageService
        image_service = ImageService(output_dir=args.output_dir)
        
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
        
    except Exception as e:
        logger.exception(f"Erro durante o scraping: {e}")
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())