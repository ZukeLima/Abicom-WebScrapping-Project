# src/analise_imagens.py

"""
Módulo para análise de imagens (versão SEM DB, salva tabelas individuais por mês).
Este script:
1. Varre o diretório de imagens OU processa imagem única via arg.
2. Processa imagens em paralelo:
    a. Opcional: Redimensiona/Corta.
    b. Tenta extrair a primeira tabela com `img2table`/`EasyOCR`.
    c. Extrai a data (DD-MM-YYYY) do nome do arquivo original.
    d. **Pré-processa cabeçalhos mesclados** no DataFrame da tabela extraída.
    e. Salva a tabela tratada como CSV individual em 'data/tabelas_por_mes/MM-YYYY/'.
3. Reporta o número de tabelas salvas com sucesso/falha.
"""

# --- Imports ---
import os
import re
import pandas as pd
import logging
from datetime import datetime
from PIL import Image, UnidentifiedImageError
import easyocr
import numpy as np
import concurrent.futures
import time
import sys
import math
import argparse # Para teste standalone
from img2table.document import Image as Img2TableDoc
from img2table.ocr import EasyOCR as Img2TableEasyOCR
from typing import List, Optional, Dict, Tuple
# from io import StringIO # Não necessário

# --- Imports do Projeto ---
try:
    from .config import OUTPUT_DIR, ORGANIZE_BY_MONTH, IMAGE_EXTENSIONS, DATA_DIR
    os.makedirs(DATA_DIR, exist_ok=True); os.makedirs(OUTPUT_DIR, exist_ok=True)
    logger = logging.getLogger(__name__)
    logger.debug(f"Config carregada via .config.")
except Exception as e:
    logger = logging.getLogger(__name__) # Garante logger
    logger.warning(f"Falha importar/validar config ({e}). Usando padrões.")
    # Define fallbacks...
    _default_data_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
    DATA_DIR = _default_data_path; OUTPUT_DIR = os.path.join(DATA_DIR, "images"); ORGANIZE_BY_MONTH = True; IMAGE_EXTENSIONS = ['.jpg', '.jpeg']
    os.makedirs(DATA_DIR, exist_ok=True); os.makedirs(OUTPUT_DIR, exist_ok=True)
# --- Fim Imports ---

# --- Logger ---
logger = logging.getLogger(__name__)

# --- Constantes e Configs ---
MAX_IMAGE_DIM_FOR_OCR = 2000
CROP_BOX_MAIN_TABLE = (0.01, 0.12, 0.83, 0.53) # AJUSTE!
# CROP_BOX_MAIN_TABLE = None # Desabilita corte
OUTPUT_DIR_BASE_TABELAS = os.path.join(DATA_DIR, "tabelas_por_mes")

# --- Regex ---
filename_date_pattern = re.compile(r"ppi-(\d{2})-(\d{2})-(\d{4})\.(jpg|jpeg)", re.IGNORECASE)

# --- Verificação EasyOCR ---
_easyocr_checker_instance = None; easyocr_available = False; use_gpu = False
try: logger.info(f"Verificando EasyOCR..."); _easyocr_checker_instance = easyocr.Reader(['pt', 'en']); easyocr_available = True; logger.info(f"EasyOCR disponível."); del _easyocr_checker_instance
except Exception as e: logger.error(f"Falha init EasyOCR: {e}. OCR desativado."); easyocr_available = False
_worker_ocr_wrappers = {}


# --- Função Worker (com Header Fill) ---
def processar_e_salvar_tabela_individual(filepath: str, base_dir: str, organizar_por_mes: bool) -> bool:
    """
    Worker: Processa UMA imagem. Extrai data, pré-processa, extrai tabela,
    PREENCHE CABEÇALHOS, salva CSV individual em MM-YYYY. Retorna True/False.
    """
    global _worker_ocr_wrappers
    worker_pid = os.getpid(); worker_logger = logging.getLogger(f"{__name__}.worker{worker_pid}")
    filename = os.path.basename(filepath)
    worker_logger.debug(f"W {worker_pid}: Iniciando: {filename}")

    # --- Extração da Data (Corrigida) ---
    pasta_mes_ano = None; data_extraida_ok = False; day, month, year = None, None, None
    data_match = filename_date_pattern.search(filename)
    if data_match:
        try: day_str, month_str, year_str, _ = data_match.groups(); datetime.strptime(f"{day_str}-{month_str}-{year_str}", '%d-%m-%Y'); day, month, year = day_str, month_str, year_str; pasta_mes_ano = f"{month}-{year}"; data_extraida_ok = True; worker_logger.debug(f"W {worker_pid}: Data OK: {pasta_mes_ano}") # noqa: E501
        except ValueError as e: captured_groups = data_match.groups(); worker_logger.warning(f"W {worker_pid}: Data inválida/Erro grupos regex '{filename}': {e}. Grupos: {captured_groups}")
        except Exception as date_err: worker_logger.warning(f"W {worker_pid}: Erro data {filename}: {date_err}")
    else: worker_logger.warning(f"W {worker_pid}: Padrão data não encontrado nome '{filename}'.")
    if not data_extraida_ok: worker_logger.error(f"W {worker_pid}: Data inválida {filename}. Abortando."); return False
    # --- Fim Extração Data ---

    img_object_pil = None; temp_filepath = None; df_tabela_principal = None; success = False
    try: # Bloco Principal
        # 1. Abrir Imagem
        img_object_pil = Image.open(filepath)
        img_to_process = img_object_pil
        # 2. Pré-processamento (Opcional: Redimensionar/Cortar)
        # ...

        # 3. Salvar Temp e Extrair Tabela
        try: # Try interno para limpar temp file
            temp_filename = f"{os.path.splitext(filename)[0]}_pid{worker_pid}_proc.png"
            temp_filepath = os.path.join(DATA_DIR, temp_filename)
            img_to_process.save(temp_filepath, format='PNG')
            worker_logger.debug(f"W {worker_pid}: Img proc salva temp: {temp_filepath}")

            ocr_error_msg = None; extracted_tables = None; df_tabela_principal = None
            if easyocr_available:
                # ... (Lógica OCR wrapper como antes) ...
                 current_ocr_wrapper = _worker_ocr_wrappers.get(worker_pid)
                 if current_ocr_wrapper is None:
                    try: current_ocr_wrapper = Img2TableEasyOCR(lang=['pt', 'en']); _worker_ocr_wrappers[worker_pid] = current_ocr_wrapper; worker_logger.info(f"W {worker_pid}: Wrapper OCR init OK.")
                    except Exception as e: ocr_error_msg = f"ERRO_OCR_INIT: {e}"; _worker_ocr_wrappers[worker_pid] = False; worker_logger.error(f"W {worker_pid}: Falha init OCR: {e}")
                 if isinstance(current_ocr_wrapper, Img2TableEasyOCR):
                     try: # Try img2table
                         img_doc = Img2TableDoc(src=temp_filepath)
                         extracted_tables = img_doc.extract_tables(ocr=current_ocr_wrapper, implicit_rows=True, borderless_tables=True, min_confidence=50)
                         if extracted_tables: df_tabela_principal = extracted_tables[0].df; worker_logger.info(f"W {worker_pid}: Tabela extraída {filename}.")
                         else: ocr_error_msg = "Nenhuma tabela encontrada"; worker_logger.warning(f"W {worker_pid}: Nenhuma tabela {filename}.")
                     except Exception as table_err: ocr_error_msg = f"ERRO_TABELA: {str(table_err)[:150]}"; worker_logger.warning(f"W {worker_pid}: Erro extração {filename}: {table_err}", exc_info=False)
                 elif current_ocr_wrapper is False: ocr_error_msg = "ERRO_OCR_INIT_ANTERIOR"
            else: ocr_error_msg = "ERRO_EASYOCR_NAO_DISPONIVEL_GLOBAL"

            # 4. Salvar Tabela Individual (SE FOI EXTRAÍDA)
            if isinstance(df_tabela_principal, pd.DataFrame) and not df_tabela_principal.empty:
                worker_logger.debug(f"W {worker_pid}: Tabela válida ({df_tabela_principal.shape}). Pré-processando cabeçalho...")

                # --- *** ADICIONADO: Pré-processamento do Cabeçalho (ffill) *** ---
                try:
                    # Preenche valores vazios (NaN/None) nas linhas de cabeçalho (índice 0 e 1)
                    # usando o último valor válido encontrado à esquerda (axis=1).
                    if len(df_tabela_principal) > 0: # Garante que linha 0 existe
                        df_tabela_principal.iloc[0] = df_tabela_principal.iloc[0].ffill()
                        worker_logger.debug(f"W {worker_pid}: Cabeçalho linha 0 preenchido (ffill).")
                    if len(df_tabela_principal) > 1: # Garante que linha 1 existe
                        df_tabela_principal.iloc[1] = df_tabela_principal.iloc[1].ffill()
                        worker_logger.debug(f"W {worker_pid}: Cabeçalho linha 1 preenchido (ffill).")
                except Exception as header_err:
                     # Se der erro ao preencher, loga e continua para salvar a tabela original
                     worker_logger.warning(f"W {worker_pid}: Erro ao preencher cabeçalhos: {header_err}. Salvando tabela original.")
                # --- Fim do Pré-processamento do Cabeçalho ---

                # Define caminho da subpasta MM-YYYY
                caminho_subpasta = os.path.join(OUTPUT_DIR_BASE_TABELAS, pasta_mes_ano)
                os.makedirs(caminho_subpasta, exist_ok=True)

                # Define nome do arquivo CSV
                nome_base_sem_ext = os.path.splitext(filename)[0]
                nome_arquivo_saida = f"{nome_base_sem_ext}_tabela.csv"
                caminho_saida_individual = os.path.join(caminho_subpasta, nome_arquivo_saida)

                try: # Tenta salvar o CSV (agora com cabeçalhos preenchidos)
                    worker_logger.info(f"W {worker_pid}: Salvando tabela em: {caminho_saida_individual}")
                    df_tabela_principal.to_csv(caminho_saida_individual, index=False, encoding='utf-8-sig')
                    if os.path.isfile(caminho_saida_individual):
                         worker_logger.info(f"W {worker_pid}: Tabela salva SUCESSO: {nome_arquivo_saida}")
                         success = True # Marca sucesso FINAL
                    else: ocr_error_msg = (ocr_error_msg + "; " if ocr_error_msg else "") + "Falha conf salvamento CSV"; worker_logger.error(f"W {worker_pid}: ERRO PÓS-SALVAR CSV: {caminho_saida_individual}")
                except Exception as save_err: ocr_error_msg = (ocr_error_msg + "; " if ocr_error_msg else "") + f"Erro salvamento CSV: {save_err}"; worker_logger.error(f"W {worker_pid}: Erro salvar CSV {filename}: {save_err}", exc_info=True)
            else: worker_logger.warning(f"W {worker_pid}: Nenhuma tabela válida de {filename} para salvar. Erro OCR/Tabela: {ocr_error_msg}")

        # Captura erro no try interno
        except Exception as inner_e: logger.error(f"Erro INTERNO W {worker_pid} {filename}: {inner_e}", exc_info=True)
        finally: # Limpa temp file
            if temp_filepath and os.path.exists(temp_filepath):
                try: os.remove(temp_filepath); logger.debug(f"W {worker_pid}: Temp file interno removido.")
                except OSError as e: worker_logger.error(f"W {worker_pid}: Falha remover temp file: {e}")

    # Captura erros no try externo
    except FileNotFoundError: logger.error(f"Arquivo original não encontrado: {filepath}")
    except UnidentifiedImageError: logger.warning(f"Imagem inválida/corrompida: {filename}")
    except Exception as outer_e: logger.error(f"Erro GERAL EXTERNO W {worker_pid} {filename}: {outer_e}", exc_info=True)
    # Finally externo (Fecha imagem PIL)
    finally:
        if img_object_pil:
             try: img_object_pil.close()
             except Exception: pass

    # Log final e retorno
    log_func = worker_logger.info if success else worker_logger.warning
    log_func(f"W[{worker_pid}] --- Finalizado: {filename} -> {'OK (Tabela salva)' if success else 'FALHA (Tabela não salva)'} ---")
    return success

# --- Função Coordenadora Paralela ---
# (Mantida como antes - conta sucessos/falhas dos workers)
def analisar_e_salvar_paralelo(diretorio_base: str, organizar_por_mes: bool, max_workers: Optional[int] = None) -> Tuple[int, int]:
    """ Coordena análise/salvamento paralelo. Retorna (sucessos, falhas). """
    start_time = time.time(); logger.info(f"Iniciando análise/salvamento de tabelas individuais em: {diretorio_base}")
    try: all_files_paths = [os.path.join(r, f) for r, d, fs in os.walk(diretorio_base) for f in fs if f.lower().endswith(tuple(IMAGE_EXTENSIONS))]; total_files = len(all_files_paths); logger.info(f"Encontrados {total_files} arquivos para analisar/salvar."); # Removido Assert
    except Exception as walk_err: logger.error(f"Erro ao listar arquivos: {walk_err}"); return 0, 1
    if total_files == 0: logger.warning("Nenhum arquivo de imagem encontrado."); return 0, 0

    success_count = 0; failure_count = 0; workers = max_workers if isinstance(max_workers, int) and max_workers > 0 else os.cpu_count(); logger.info(f"Usando até {workers} processos.")
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(processar_e_salvar_tabela_individual, fp, diretorio_base, organizar_por_mes): fp for fp in all_files_paths}
        processed_count = 0
        for future in concurrent.futures.as_completed(futures):
            filepath = futures[future]; processed_count += 1
            try: worker_success = future.result();
            except Exception as exc: logger.error(f'Worker {os.path.basename(filepath)} CRASHOU: {exc}', exc_info=True); worker_success = False
            if worker_success: success_count += 1
            else: failure_count += 1
            if processed_count % 20 == 0 or processed_count == total_files: logger.info(f"Progresso Salvar Tabelas Indiv.: {processed_count}/{total_files} concluídos ({success_count} S, {failure_count} F).")
    end_time = time.time(); logger.info(f"Processamento concluído em {end_time - start_time:.2f} s.")
    logger.info(f"Resultado Final: {success_count} tabelas individuais salvas, {failure_count} falhas.")
    return success_count, failure_count


# --- Função Principal de Análise e Reporte ---
# (Mantida como antes - apenas reporta as contagens)
def executar_e_reportar_analise(diretorio_imagens: str, organizar_por_mes: bool, diretorio_csv: str, num_workers: Optional[int] = None):
    """ Chama a função paralela e reporta o resultado no console. """
    logger.info(f"Executando extração e salvamento de tabelas individuais para: {diretorio_imagens}")
    sucessos, falhas = analisar_e_salvar_paralelo(diretorio_imagens, organizar_por_mes, max_workers=num_workers)
    print("\n--- Resumo da Extração de Tabelas Individuais ---")
    print(f"Diretório base de saída das tabelas: {OUTPUT_DIR_BASE_TABELAS}")
    print(f"Total de imagens processadas: {sucessos + falhas}")
    print(f"Tabelas individuais salvas com sucesso: {sucessos}")
    print(f"Falhas ao processar/salvar: {falhas}")
    if falhas > 0: print("Verifique o arquivo 'scraper.log' e 'data/error.log' para detalhes.")


# --- Bloco Standalone (com Argumentos para Teste) ---
# (Mantido como antes - permite testar uma imagem ou com N workers)
if __name__ == "__main__":
    # Configura logging APENAS se executado diretamente
    if not logging.getLogger().hasHandlers():
         logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
         logging.getLogger().setLevel(logging.INFO)

    parser_test = argparse.ArgumentParser(description='Executor Standalone - Analisa Imagens e Salva Tabelas Individuais por Mês.')
    parser_test.add_argument('-i', '--image-path', type=str, default=None, help='(TESTE) Caminho para UMA imagem específica.')
    parser_test.add_argument('-w', '--workers', type=int, default=None, help='(TESTE) Número de workers (padrão: CPU count). Use 1 para sequencial.')
    parser_test.add_argument('-v', '--verbose', action='store_true', help='(TESTE) Ativa log nível DEBUG.')
    args_test = parser_test.parse_args()
    if args_test.verbose: logging.getLogger().setLevel(logging.DEBUG); logger.info("Log DEBUG ativado.")

    logger.info(f"Executando {__file__} standalone...")
    try:
        if args_test.image_path: # Teste de Imagem Única
            logger.info(f"--- Iniciando Teste de Imagem Única ---")
            image_path_test = os.path.abspath(args_test.image_path)
            logger.info(f"Arquivo: {image_path_test}")
            if os.path.isfile(image_path_test):
                success = processar_e_salvar_tabela_individual(filepath=image_path_test, base_dir=DATA_DIR, organizar_por_mes=ORGANIZE_BY_MONTH)
                print(f"\nTeste concluído. {'Tabela salva.' if success else 'FALHA (ver logs).'}")
            else: logger.error(f"Erro: Imagem teste não encontrada: {image_path_test}")
        else: # Execução Normal (todas as imagens)
            logger.info("Iniciando análise completa...")
            executar_e_reportar_analise(OUTPUT_DIR, ORGANIZE_BY_MONTH, DATA_DIR, num_workers=args_test.workers)
    except Exception as e: logger.critical(f"Erro fatal standalone: {e}", exc_info=True)

    logger.info(f"Execução standalone de {__file__} finalizada.")

# ----- FIM do arquivo src/analise_imagens.py -----