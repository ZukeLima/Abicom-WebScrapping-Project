# src/analise_imagens.py
import os
import re
import pandas as pd
import logging
from datetime import datetime
from PIL import Image, UnidentifiedImageError
from PIL.ExifTags import TAGS
import easyocr
import numpy as np
import json
import concurrent.futures
import time
import sys
from img2table.document import Image as Img2TableDoc
from img2table.ocr import EasyOCR # Nome correto

# --- Logger ---
logger = logging.getLogger(__name__)

# --- Configuração e Inicialização (com fallback) ---
# (Sem alterações aqui)
try:
    from src.config import OUTPUT_DIR, ORGANIZE_BY_MONTH
    DATA_DIR = os.path.dirname(OUTPUT_DIR)
    if not OUTPUT_DIR or not DATA_DIR or not os.path.isdir(DATA_DIR):
        raise ImportError("OUTPUT_DIR não definido ou inválido em config.py, ou DATA_DIR não encontrado.")
    os.makedirs(DATA_DIR, exist_ok=True)
    logger.debug(f"Configuração carregada: OUTPUT_DIR={OUTPUT_DIR}, DATA_DIR={DATA_DIR}")
except ImportError as e:
    logger.warning(f"Configuração via src.config falhou ({e}). Usando caminhos padrão.")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    DATA_DIR = os.path.join(project_root, "data")
    OUTPUT_DIR = os.path.join(DATA_DIR, "images")
    ORGANIZE_BY_MONTH = True
    logger.warning(f"Fallback: OUTPUT_DIR={OUTPUT_DIR}, DATA_DIR={DATA_DIR}")
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


# --- Regex ---
filename_date_pattern = re.compile(r"ppi-(\d{2}-\d{2}-\d{4})\.(jpg|jpeg)", re.IGNORECASE)
folder_date_pattern = re.compile(r"(\d{2})-(\d{4})")

# --- Verificação Inicial da Disponibilidade do EasyOCR ---
_easyocr_checker_instance = None
easyocr_available = False
try:
    logger.info("Verificando disponibilidade do EasyOCR...")
    # --- CORRIGIDO: Remove gpu=False também da verificação ---
    _easyocr_checker_instance = easyocr.Reader(['pt', 'en']) # Ajuste idiomas
    # ------------------------------------------------------
    easyocr_available = True
    logger.info("EasyOCR parece estar disponível.")
    del _easyocr_checker_instance
except Exception as e:
    logger.error(f"Falha ao inicializar EasyOCR na verificação global: {e}. Extração de tabela/OCR será desativada.")

# --- Dicionário para armazenar OCR Wrappers img2table por worker ---
_worker_ocr_wrappers = {}

# --- Função para processar UM ÚNICO arquivo (Executada em processo separado) ---
def processar_arquivo_imagem(filepath: str, base_dir: str, organizar_por_mes: bool):
    """
    Processa um único arquivo de imagem, extraindo metadados, propriedades,
    EXIF e TENTANDO extrair tabelas usando img2table com EasyOCR.
    Retorna um dicionário com os resultados.
    """
    global _worker_ocr_wrappers
    worker_pid = os.getpid()
    worker_logger = logging.getLogger(f"{__name__}.worker{worker_pid}")
    filename = os.path.basename(filepath)
    worker_logger.debug(f"Processando: {filename}")

    # (Inicialização do result_dict e metadados como antes)
    result_dict = {
        "caminho_completo": filepath, "nome_arquivo": filename, "pasta_pai": None,
        "data_extraida_arquivo": None, "mes_pasta": None, "ano_pasta": None,
        "tamanho_bytes": None, "largura_px": None, "altura_px": None,
        "modo_cor": None, "formato_imagem": None, "exif_data_json": None,
        "tabelas_extraidas_json": None, "erro_processamento": None
    }
    root = os.path.dirname(filepath); norm_base_path = os.path.normpath(base_dir)
    current_folder_is_base = (os.path.normpath(root) == norm_base_path)
    result_dict["pasta_pai"]= os.path.basename(root) if not current_folder_is_base else "[RAIZ]"


    try:
        # --- Metadados do Arquivo (Tamanho, Datas) ---
        result_dict["tamanho_bytes"] = os.path.getsize(filepath)
        match_filename = filename_date_pattern.search(filename)
        if match_filename:
             date_str = match_filename.group(1)
             try: datetime.strptime(date_str, '%d-%m-%Y'); result_dict["data_extraida_arquivo"] = date_str
             except ValueError: worker_logger.warning(f"Formato data inválido nome: {filename}")
        if organizar_por_mes and not current_folder_is_base:
             match_folder = folder_date_pattern.match(result_dict["pasta_pai"])
             if match_folder: result_dict["mes_pasta"], result_dict["ano_pasta"] = match_folder.groups()


        # --- Processamento da Imagem (Pillow, EXIF) ---
        exif_info = {}
        with Image.open(filepath) as img:
            result_dict["largura_px"], result_dict["altura_px"] = img.size
            result_dict["modo_cor"] = img.mode
            result_dict["formato_imagem"] = img.format
            try:
                 exif_raw = img._getexif();
                 if exif_raw:
                      for tag, value in exif_raw.items():
                          decoded_tag = TAGS.get(tag, tag)
                          if isinstance(value, bytes):
                              try: exif_info[decoded_tag] = value.decode(errors='replace')
                              except: exif_info[decoded_tag] = repr(value)
                          elif decoded_tag != 'MakerNote' and not isinstance(decoded_tag, int) and 'IFD' not in str(decoded_tag):
                               exif_info[decoded_tag] = value
                 result_dict["exif_data_json"] = json.dumps(exif_info, default=str) if exif_info else None
            except Exception as exif_err:
                 worker_logger.debug(f"Erro EXIF {filename}: {exif_err}")

        # --- Extração de Tabelas com img2table ---
        if easyocr_available: # Só tenta se EasyOCR estiver disponível globalmente
            current_ocr_wrapper = _worker_ocr_wrappers.get(worker_pid)

            # Inicializa o WRAPPER img2table se ainda não feito para este worker
            if current_ocr_wrapper is None:
                worker_logger.info(f"Inicializando wrapper img2table.ocr.EasyOCR...")
                try:
                    # --- CORRIGIDO: Remove gpu=False ---
                    current_ocr_wrapper = EasyOCR(lang=['pt', 'en']) # Ajuste idiomas
                    # ----------------------------------
                    _worker_ocr_wrappers[worker_pid] = current_ocr_wrapper
                    worker_logger.info(f"Wrapper img2table.ocr.EasyOCR inicializado.")
                except Exception as worker_init_err:
                    worker_logger.error(f"Falha ao inicializar wrapper EasyOCR no worker: {worker_init_err}")
                    result_dict["erro_processamento"] = f"ERRO_OCR_WRAPPER_INIT: {str(worker_init_err)[:100]}"
                    _worker_ocr_wrappers[worker_pid] = False # Marca como falho

            # Executa extração de tabela se o wrapper foi inicializado com sucesso
            if isinstance(current_ocr_wrapper, EasyOCR): # Verifica o tipo do wrapper
                try:
                    worker_logger.debug(f"Iniciando extração de tabela para {filename}...")
                    img_doc = Img2TableDoc(filepath)
                    extracted_tables = img_doc.extract_tables(ocr=current_ocr_wrapper,
                                                              implicit_rows=True,
                                                              borderless_tables=True,
                                                              min_confidence=50) # Ajuste parâmetros se necessário

                    if extracted_tables:
                        list_of_table_json = []
                        worker_logger.debug(f"Encontradas {len(extracted_tables)} tabelas em {filename}.")
                        for table_obj in extracted_tables:
                            df_table = table_obj.df
                            table_json = df_table.to_json(orient="split", index=False, default_handler=str)
                            list_of_table_json.append(table_json)
                        result_dict["tabelas_extraidas_json"] = json.dumps(list_of_table_json)
                    else:
                         worker_logger.debug(f"Nenhuma tabela encontrada em {filename}.")
                         result_dict["tabelas_extraidas_json"] = "[]" # Indica lista vazia

                except Exception as table_err:
                    worker_logger.warning(f"Erro durante extração de tabela em {filename}: {table_err}", exc_info=False)
                    prev_error = result_dict["erro_processamento"] + "; " if result_dict["erro_processamento"] else ""
                    result_dict["erro_processamento"] = f"{prev_error}ERRO_TABELA: {str(table_err)[:100]}"
            elif current_ocr_wrapper is False:
                 # Se a inicialização falhou, registra o erro correspondente
                 prev_error = result_dict["erro_processamento"] + "; " if result_dict["erro_processamento"] else ""
                 result_dict["erro_processamento"] = f"{prev_error}ERRO_OCR_INIT_ANTERIOR"
        # --- Fim da Extração de Tabelas ---

    # (Bloco except geral como antes)
    except FileNotFoundError:
        worker_logger.error(f"Arquivo não encontrado: {filepath}")
        result_dict["erro_processamento"] = "Arquivo não encontrado"
    except UnidentifiedImageError:
        worker_logger.warning(f"Não foi possível identificar/abrir imagem: {filename}")
        result_dict["erro_processamento"] = "Formato inválido/corrompido"
    except Exception as e:
        worker_logger.error(f"Erro inesperado processando {filename}: {e}", exc_info=False)
        prev_error = result_dict["erro_processamento"] + "; " if result_dict["erro_processamento"] else ""
        result_dict["erro_processamento"] = f"{prev_error}ERRO_GERAL: {str(e)[:100]}"


    return result_dict

# --- Função analisar_imagens_paralelo ---
# (Sem alterações)
def analisar_imagens_paralelo(diretorio_base: str, organizar_por_mes: bool, max_workers: int = None) -> pd.DataFrame:
    start_time = time.time(); logger.info(f"Iniciando análise paralela com img2table em: {diretorio_base}")
    if not os.path.exists(diretorio_base): logger.error(f"Diretório não encontrado: {diretorio_base}"); return pd.DataFrame([])
    try:
        all_files_paths = [os.path.join(r, f) for r, d, fs in os.walk(diretorio_base) for f in fs if f.lower().endswith(('.jpg', '.jpeg'))]
        total_files = len(all_files_paths); logger.info(f"Encontrados {total_files} arquivos para analisar.")
        if total_files == 0: return pd.DataFrame([])
    except Exception as walk_err: logger.error(f"Erro ao listar arquivos: {walk_err}"); return pd.DataFrame([])
    resultados = []; workers = max_workers if max_workers else os.cpu_count(); logger.info(f"Usando até {workers} processos.")
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(processar_arquivo_imagem, fp, diretorio_base, organizar_por_mes): fp for fp in all_files_paths}
        processed_count = 0
        for future in concurrent.futures.as_completed(futures):
            filepath = futures[future]; processed_count += 1
            try:
                result = future.result();
                if result: resultados.append(result)
            except Exception as exc:
                logger.error(f'Worker para {os.path.basename(filepath)} falhou: {exc}')
                resultados.append({"caminho_completo": filepath, "nome_arquivo": os.path.basename(filepath), "erro_processamento": f"Falha Worker: {str(exc)[:100]}"})
            if processed_count % 100 == 0 or processed_count == total_files: logger.info(f"Progresso: {processed_count}/{total_files} concluídos.")
    end_time = time.time(); logger.info(f"Análise paralela concluída em {end_time - start_time:.2f} segundos.")
    if not resultados: logger.warning("Nenhum resultado coletado."); return pd.DataFrame([])
    df_analise = pd.DataFrame(resultados)
    col_order = [ "nome_arquivo", "pasta_pai", "data_extraida_arquivo", "mes_pasta", "ano_pasta", "tamanho_bytes", "largura_px", "altura_px", "modo_cor", "formato_imagem", "tabelas_extraidas_json", "exif_data_json", "erro_processamento", "caminho_completo" ]
    existing_cols = [col for col in col_order if col in df_analise.columns]
    return df_analise[existing_cols]

# --- Função executar_e_reportar_analise ---
# (Sem alterações)
def executar_e_reportar_analise(diretorio_imagens: str, organizar_por_mes: bool, diretorio_csv: str):
    logger.info(f"Executando análise (img2table) e report para: {diretorio_imagens}")
    df_analise = analisar_imagens_paralelo(diretorio_imagens, organizar_por_mes)
    if df_analise is None or df_analise.empty:
        logger.warning("DataFrame de análise vazio. Nenhum relatório gerado.")
        print("\nNenhuma imagem processada ou encontrada para gerar análise/CSV.")
        return
    try:
        print("\n--- Tabela de Análise das Imagens (Prévia) ---")
        cols_preview = [ "nome_arquivo", "pasta_pai", "data_extraida_arquivo", "largura_px", "altura_px", "tamanho_bytes", "erro_processamento", "tabelas_extraidas_json"]
        cols_to_show = [col for col in cols_preview if col and col in df_analise.columns]
        df_preview = df_analise[cols_to_show].head().copy()
        if "tabelas_extraidas_json" in df_preview.columns: df_preview.loc[:, "tabelas_extraidas_json"] = df_preview["tabelas_extraidas_json"].apply(lambda x: "[Tabelas Extraídas]" if pd.notna(x) and x != '[]' else "[Nenhuma Tabela]" if x == '[]' else "[Erro/Vazio]")
        if "erro_processamento" in df_preview.columns: df_preview.loc[:, "erro_processamento"] = df_preview["erro_processamento"].fillna('')
        try: print(df_preview.to_markdown(index=False))
        except ImportError: print(df_preview.to_string(index=False))
    except Exception as print_err: logger.error(f"Erro ao gerar prévia: {print_err}", exc_info=True)
    print("\n--- Resumo da Análise (com img2table) ---")
    try:
        total_registros = len(df_analise); print(f"Total de registros: {total_registros}")
        erros_proc = df_analise['erro_processamento'].notna().sum(); print(f"Imagens com erro no processamento: {erros_proc}")
        if organizar_por_mes and 'pasta_pai' in df_analise.columns: contagem_pasta = df_analise[df_analise['pasta_pai'] != '[RAIZ]']['pasta_pai'].value_counts(); print("\nContagem por pasta:\n" + contagem_pasta.to_string())
        if 'data_extraida_arquivo' in df_analise.columns: datas_validas = df_analise['data_extraida_arquivo'].notna().sum(); print(f"Imagens com data do nome: {datas_validas}")
        if 'tamanho_bytes' in df_analise.columns and df_analise['tamanho_bytes'].notna().any(): tamanho_total_mb = df_analise['tamanho_bytes'].sum()/(1024*1024); tamanho_medio_kb = (df_analise['tamanho_bytes'].mean(skipna=True)/1024); print(f"Tamanho total: {tamanho_total_mb:.2f} MB"); print(f"Tamanho médio: {tamanho_medio_kb:.2f} KB")
        if 'largura_px' in df_analise.columns and 'altura_px' in df_analise.columns: largura_media = df_analise['largura_px'].mean(skipna=True); altura_media = df_analise['altura_px'].mean(skipna=True); print(f"Dimensões médias: {largura_media:.0f}x{altura_media:.0f} px")
        if 'exif_data_json' in df_analise.columns: exif_present_count = df_analise['exif_data_json'].notna().sum(); print(f"Imagens com dados EXIF: {exif_present_count}")
        if 'tabelas_extraidas_json' in df_analise.columns: tabelas_encontradas = df_analise[(df_analise['tabelas_extraidas_json'].notna()) & (df_analise['tabelas_extraidas_json'] != '[]')].shape[0]; print(f"Imagens com tabelas (img2table): {tabelas_encontradas}")
    except Exception as summary_err: logger.error(f"Erro ao gerar resumo: {summary_err}", exc_info=True)
    try:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S"); csv_filename = f"analise_img2table_{timestamp_str}.csv"; os.makedirs(diretorio_csv, exist_ok=True); csv_filepath = os.path.join(diretorio_csv, csv_filename)
        df_analise.to_csv(csv_filepath, index=False, encoding='utf-8-sig'); logger.info(f"Análise completa salva: {csv_filepath}"); print(f"\nAnálise detalhada salva em: {csv_filepath}")
    except Exception as e: logger.error(f"Erro crítico ao salvar CSV: {e}", exc_info=True); print(f"\nERRO CRÍTICO ao salvar CSV: {e}")


# Bloco principal para execução standalone
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
    logging.getLogger().setLevel(logging.INFO)
    logger.info("Executando analise_imagens.py como script principal...")
    executar_e_reportar_analise(OUTPUT_DIR, ORGANIZE_BY_MONTH, DATA_DIR)