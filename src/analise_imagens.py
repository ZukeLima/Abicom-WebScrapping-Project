# src/analise_imagens.py

"""
Módulo para análise de imagens (versão SEM DB, otimizada para CPU).
Este script:
1. Varre o diretório de imagens (`os.walk`).
2. Processa imagens em paralelo:
    a. Extrai metadados básicos (Pillow).
    b. Opcionalmente redimensiona/corta a imagem para performance/precisão.
    c. Tenta extrair tabelas usando `img2table` com `EasyOCR` (forçado para CPU).
    d. Tenta extrair VALORES NUMÉRICOS específicos da tabela detectada.
3. Agrega todos os resultados (metadados + valores extraídos) em um DataFrame.
4. Salva o DataFrame consolidado em um arquivo CSV.
"""

# --- Imports Padrão e de Bibliotecas Externas ---
import os
import re
import pandas as pd
import logging
from datetime import datetime
from PIL import Image, UnidentifiedImageError
# from PIL.ExifTags import TAGS # Comentado - Habilite se for usar EXIF
import easyocr
import numpy as np
import json
import concurrent.futures
import time
import sys
import math
from img2table.document import Image as Img2TableDoc
from img2table.ocr import EasyOCR as Img2TableEasyOCR
# --- CORREÇÃO: Import de Tipagem ---
# Adicionado para usar List, Optional, Dict nas dicas de tipo
from typing import List, Optional, Dict
from io import StringIO

# --- Imports do Projeto ---
# REMOVIDO: Import de database não é necessário nesta versão
# from . import database as db
try:
    # Usa import relativo '.' para config
    from .config import OUTPUT_DIR, ORGANIZE_BY_MONTH, IMAGE_EXTENSIONS, DATA_DIR
    os.makedirs(DATA_DIR, exist_ok=True); os.makedirs(OUTPUT_DIR, exist_ok=True)
    # Obtém logger APENAS após garantir que imports/paths básicos funcionaram
    logger = logging.getLogger(__name__) # Definido aqui para o caso de sucesso
    logger.debug(f"Config carregada via .config: OUTPUT_DIR={OUTPUT_DIR}")
except Exception as e:
    # Configura logger básico APENAS se o import falhar
    logging.basicConfig(level=logging.WARNING); logger = logging.getLogger(__name__)
    logger.warning(f"Falha importar/validar config ({e}). Usando padrões.")
    # Define fallbacks
    _default_data_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
    DATA_DIR = _default_data_path; OUTPUT_DIR = os.path.join(DATA_DIR, "images")
    ORGANIZE_BY_MONTH = True; IMAGE_EXTENSIONS = ['.jpg', '.jpeg']
    os.makedirs(DATA_DIR, exist_ok=True); os.makedirs(OUTPUT_DIR, exist_ok=True)
    logger.warning(f"Fallback Análise: Usando OUTPUT_DIR={OUTPUT_DIR}")
# --- Fim Imports ---

# --- Logger ---
# Garante que logger exista globalmente no módulo
logger = logging.getLogger(__name__)

# --- Constantes e Configs de Otimização ---
MAX_IMAGE_DIM_FOR_OCR = 2000 # Redimensiona se maior que isso (px)
# Caixa de corte relativa (esq, topo, dir, fundo) - AJUSTE CONFORME TESTES!
CROP_BOX_MAIN_TABLE = (0.01, 0.12, 0.83, 0.53) # Estimativa inicial
# CROP_BOX_MAIN_TABLE = None # Desabilita

# --- Regex ---
filename_date_pattern = re.compile(r"ppi-(\d{2}-\d{2}-\d{4})\.(jpg|jpeg)", re.IGNORECASE)
folder_date_pattern = re.compile(r"(\d{2})-(\d{4})")

# --- Verificação EasyOCR (Forçando CPU) ---
_easyocr_checker_instance = None
easyocr_available = False
use_gpu = False # Força CPU
logger.info(f"EasyOCR: Verificando disponibilidade (GPU Forçado: {use_gpu})...")
try:
    _easyocr_checker_instance = easyocr.Reader(['pt', 'en']) # Remove gpu= se causou erro
    easyocr_available = True; logger.info(f"EasyOCR disponível (GPU Forçado: {use_gpu}).")
    del _easyocr_checker_instance
except Exception as e: logger.error(f"Falha init EasyOCR: {e}. OCR desativado."); easyocr_available = False

# --- Cache OCR Wrappers ---
_worker_ocr_wrappers = {}

# --- Funções Auxiliares ---
def clean_numeric_value(value):
    """ Limpa e converte string para float. """
    if value is None: return np.nan;
    if isinstance(value, (int, float)): return float(value)
    if not isinstance(value, str): return np.nan
    try: cleaned = value.strip().replace('R$', '').replace('%', ''); cleaned = cleaned.replace('.', '').replace(',', '.'); return float(cleaned) if cleaned else np.nan
    except (ValueError, TypeError): return np.nan

def find_indices_in_table(df_table, location, fuel, metric):
    """ Encontra índices (linha, coluna) no DataFrame da tabela. """
    col_idx = None; row_idx = None; header_row_idx = 1;
    if df_table is None or df_table.empty or header_row_idx >= len(df_table.index): return None, None
    try: # Coluna
        header_row = df_table.iloc[header_row_idx]; loc_search = location.strip().lower();
        for idx, cell in enumerate(header_row):
            if isinstance(cell, str) and loc_search in cell.strip().lower(): col_idx = idx; break
        if col_idx is None: logger.debug(f"Coluna não encontrada para '{location}'"); return None, None
    except Exception as e: logger.warning(f"Erro busca col '{location}': {e}"); return None, None
    try: # Linha
        fuel_search=fuel.strip().lower(); met_search=metric.strip().lower(); is_price=(met_search == 'preço (r$/l)');
        for idx in range(header_row_idx + 1, len(df_table.index)):
            try: row = df_table.iloc[idx]; f_cell = row.iloc[0] if len(row) > 0 else None; m_cell = row.iloc[1] if len(row) > 1 else None;
            except IndexError: continue
            if not isinstance(f_cell, str) or fuel_search not in f_cell.strip().lower(): continue
            if is_price and pd.isna(m_cell): row_idx = idx; break
            elif isinstance(m_cell, str) and met_search in m_cell.strip().lower(): row_idx = idx; break
        if row_idx is None: logger.debug(f"Linha não encontrada para '{fuel}'/'{metric}'"); return None, None
    except Exception as e: logger.warning(f"Erro busca lin '{fuel}'/'{metric}': {e}"); return None, None
    return row_idx, col_idx


# --- Função Worker Otimizada para CPU (Sem DB) ---
def processar_arquivo_imagem(filepath: str, base_dir: str, organizar_por_mes: bool) -> Dict:
    """
    Worker (Sem DB): Processa UMA imagem.
    Retorna dicionário com metadados e VALORES NUMÉRICOS EXTRAÍDOS.
    Garante retorno de dicionário mesmo em erro (com 'erro_processamento').
    """
    global _worker_ocr_wrappers
    worker_pid = os.getpid(); worker_logger = logging.getLogger(f"{__name__}.worker{worker_pid}")
    filename = os.path.basename(filepath)
    worker_logger.debug(f"WORKER {worker_pid}: Iniciando: {filename}")

    # Dicionário de resultados base
    result_dict = {
        "caminho_completo": filepath, "nome_arquivo": filename, "pasta_pai": "[RAIZ]", # Default pasta_pai
        "data_extraida_arquivo": None, "mes_pasta": None, "ano_pasta": None,
        "tamanho_bytes": None, "largura_orig_px": None, "altura_orig_px": None,
        "modo_cor": None, "formato_imagem": None,
        # Valores extraídos inicializados
        'paulinia_diesel_preco': np.nan, 'paulinia_diesel_pct_def': np.nan, 'paulinia_gasolina_pct_def': np.nan,
        'itaqui_diesel_ppi': np.nan, 'itaqui_gasolina_def_rs': np.nan, 'aratu_diesel_preco': np.nan,
        'aratu_gasolina_ppi': np.nan,
        # Status/Erro
        "erro_processamento": None, "tabela_detectada": False
    }

    # Calcula metadados do path
    try:
        root = os.path.dirname(filepath); norm_base_path = os.path.normpath(base_dir)
        if norm_base_path != os.path.normpath(root): # Define pasta_pai se não for a base
             result_dict["pasta_pai"] = os.path.basename(root)
             if organizar_por_mes: # Tenta pegar mes/ano da pasta pai
                  match_folder = folder_date_pattern.match(result_dict["pasta_pai"])
                  if match_folder: result_dict["mes_pasta"], result_dict["ano_pasta"] = match_folder.groups()
        # Extrai data do nome do arquivo
        match_filename = filename_date_pattern.search(filename)
        if match_filename:
            date_str = match_filename.group(1)
            try: datetime.strptime(date_str, '%d-%m-%Y'); result_dict["data_extraida_arquivo"] = date_str # Valida e atribui
            except ValueError: worker_logger.warning(f"W {worker_pid}: Data inválida nome {filename}")
        # Pega tamanho do arquivo
        result_dict["tamanho_bytes"] = os.path.getsize(filepath)
    except Exception as meta_err: worker_logger.warning(f"W {worker_pid}: Erro meta path {filename}: {meta_err}")

    img_object_pil = None; temp_filepath = None; df_tabela_principal = None; processing_successful = False

    try: # Bloco principal: Abrir, Pré-processar, OCR/Tabela, Extrair Valores
        # 1. Abrir com Pillow
        worker_logger.debug(f"W {worker_pid}: Abrindo {filename}...")
        img_object_pil = Image.open(filepath)
        orig_width, orig_height = img_object_pil.size; result_dict["largura_orig_px"], result_dict["altura_orig_px"] = orig_width, orig_height

        img_to_process = img_object_pil # Imagem a ser processada (pode mudar)

        # 2. Pré-processamento (Redimensionar/Cortar)
        if MAX_IMAGE_DIM_FOR_OCR and (orig_width > MAX_IMAGE_DIM_FOR_OCR or orig_height > MAX_IMAGE_DIM_FOR_OCR):
            try: # Redimensiona
                 ratio = min(MAX_IMAGE_DIM_FOR_OCR/orig_width, MAX_IMAGE_DIM_FOR_OCR/orig_height)
                 new_size = (int(orig_width*ratio), int(orig_height*ratio))
                 img_to_process = img_object_pil.resize(new_size, Image.Resampling.LANCZOS)
                 worker_logger.info(f"W {worker_pid}: Redimensionada p/ {img_to_process.size}")
            except Exception as resize_err: worker_logger.error(f"W {worker_pid}: Erro redim {filename}: {resize_err}."); img_to_process = img_object_pil
        if CROP_BOX_MAIN_TABLE:
            try: # Corta (Crop)
                curr_w, curr_h = img_to_process.size; box = (int(curr_w*CROP_BOX_MAIN_TABLE[0]), int(curr_h*CROP_BOX_MAIN_TABLE[1]), int(curr_w*CROP_BOX_MAIN_TABLE[2]), int(curr_h*CROP_BOX_MAIN_TABLE[3]))
                if box[2] > box[0] and box[3] > box[1]: img_to_process = img_to_process.crop(box); worker_logger.info(f"W {worker_pid}: Corte {box}. Novo tam: {img_to_process.size}")
                else: worker_logger.warning(f"W {worker_pid}: Coords corte inválidas {box}.")
            except Exception as crop_err: worker_logger.error(f"W {worker_pid}: Erro cortar {filename}: {crop_err}.")
        # (Opcional: Escala de Cinza)
        # img_to_process = img_to_process.convert('L')

        # --- Bloco TRY INTERNO para garantir limpeza do temp file ---
        try:
            # 3. Salvar Temp e Extrair Tabela
            temp_filename = f"{os.path.splitext(filename)[0]}_pid{worker_pid}_proc.png"
            temp_filepath = os.path.join(DATA_DIR, temp_filename); img_to_process.save(temp_filepath, format='PNG')
            worker_logger.debug(f"W {worker_pid}: Img proc salva: {temp_filepath}")

            if easyocr_available:
                current_ocr_wrapper = _worker_ocr_wrappers.get(worker_pid)
                if current_ocr_wrapper is None: # Init OCR
                    try: current_ocr_wrapper = Img2TableEasyOCR(lang=['pt', 'en']); _worker_ocr_wrappers[worker_pid] = current_ocr_wrapper; worker_logger.info(f"W {worker_pid}: Wrapper OCR init OK.")
                    except Exception as e: result_dict["erro_processamento"] = f"ERRO_OCR_INIT: {e}"; _worker_ocr_wrappers[worker_pid] = False; worker_logger.error(f"W {worker_pid}: Falha init OCR: {e}")
                if isinstance(current_ocr_wrapper, Img2TableEasyOCR): # Se OCR OK
                     try: # Try img2table
                         img_doc = Img2TableDoc(src=temp_filepath)
                         extracted_tables = img_doc.extract_tables(ocr=current_ocr_wrapper, implicit_rows=True, borderless_tables=True, min_confidence=50)
                         if extracted_tables: df_tabela_principal = extracted_tables[0].df; result_dict["tabela_detectada"] = True
                     except Exception as table_err: result_dict["erro_processamento"] = f"ERRO_TABELA: {str(table_err)[:150]}"; worker_logger.warning(f"W {worker_pid}: Erro extração {filename}: {table_err}", exc_info=False)
                elif current_ocr_wrapper is False: result_dict["erro_processamento"] = "ERRO_OCR_INIT_ANTERIOR"
            else: result_dict["erro_processamento"] = "ERRO_EASYOCR_NAO_DISPONIVEL_GLOBAL"

            # 4. Extração de Valores Específicos (se tabela foi encontrada)
            if df_tabela_principal is not None and not df_tabela_principal.empty:
                targets = [('paulinia_diesel_preco', 'Paulínia', 'Óleo Diesel A', 'Preço (R$/L)'), ('paulinia_diesel_pct_def', 'Paulínia', 'Óleo Diesel A', '% Defasado'), ('paulinia_gasolina_pct_def', 'Paulínia', 'Gasolina A', '% Defasado'), ('itaqui_diesel_ppi', 'Itaqui', 'Óleo Diesel A', 'PPI (RS/L)'), ('itaqui_gasolina_def_rs', 'Itaqui', 'Gasolina A', 'Defasagem (RS/L)'), ('aratu_diesel_preco', 'Aratu', 'Óleo Diesel A', 'Preço (R$/L)'), ('aratu_gasolina_ppi', 'Aratu', 'Gasolina A', 'PPI (RS/L)'), ]
                extracted_values_count = 0
                for key, loc, fuel, metric in targets:
                    try: # Tenta extrair cada valor
                        row_idx, col_idx = find_indices_in_table(df_tabela_principal, loc, fuel, metric)
                        if row_idx is not None and col_idx is not None: raw_value = df_tabela_principal.iloc[row_idx, col_idx]; cleaned_value = clean_numeric_value(raw_value); result_dict[key] = cleaned_value
                        if not pd.isna(result_dict[key]): extracted_values_count += 1
                    except Exception as extract_err: worker_logger.warning(f"W {worker_pid}: Erro extrair '{key}' {filename}: {extract_err}")
                worker_logger.debug(f"W {worker_pid}: Extraídos {extracted_values_count} valores de {filename}.")
                if result_dict["tabela_detectada"] and extracted_values_count == 0: worker_logger.warning(f"W {worker_pid}: Tabela OK {filename}, mas 0 valores alvo extraídos.")

            # Marca sucesso interno se não houve erro DENTRO deste bloco
            if result_dict["erro_processamento"] is None:
                processing_successful = True

        except Exception as inner_e: # Captura erro no try interno
             error_msg_inner = f"ERRO INTERNO WORKER: {str(inner_e)[:150]}"
             result_dict["erro_processamento"] = (result_dict.get("erro_processamento","") + "; " + error_msg_inner).strip('; ')
             worker_logger.error(f"Erro INTERNO W {worker_pid} {filename}: {inner_e}", exc_info=True)
             processing_successful = False
        finally: # Finally do try interno -> Limpa temp file
            if temp_filepath and os.path.exists(temp_filepath):
                try: os.remove(temp_filepath); logger.debug(f"W {worker_pid}: Temp file interno removido.")
                except OSError as e: worker_logger.error(f"W {worker_pid}: Falha remover temp file interno: {e}")
        # --- Fim do Bloco Interno ---

    # Excepts do try externo (Abrir imagem, pré-processamento)
    except FileNotFoundError: result_dict["erro_processamento"] = "Arquivo original não encontrado"; worker_logger.error(f"FNF {filename}")
    except UnidentifiedImageError: result_dict["erro_processamento"] = "Imagem inválida/corrompida"; worker_logger.warning(f"Inválida {filename}")
    except Exception as outer_e: error_msg_outer = f"ERRO GERAL EXTERNO: {str(outer_e)[:150]}"; result_dict["erro_processamento"] = (result_dict.get("erro_processamento","") + "; " + error_msg_outer).strip('; '); worker_logger.error(f"Erro EXTERNO W {worker_pid} {filename}: {outer_e}", exc_info=True); processing_successful = False
    # Finally do try externo (Fecha imagem Pillow)
    finally:
        if img_object_pil:
             try: img_object_pil.close()
             except Exception as close_err: worker_logger.warning(f"W {worker_pid}: Erro fechar PIL {filename}: {close_err}")

    # Log final do worker
    log_func = worker_logger.info if processing_successful else worker_logger.warning
    log_func(f"W {worker_pid}: Processamento finalizado {'OK' if processing_successful else 'COM ERRO'}: {filename}. Erro: {result_dict.get('erro_processamento', 'Nenhum')}")

    # Retorna o dicionário (contém dados ou erro)
    return result_dict


# --- Função Coordenadora Paralela ---
def analisar_imagens_paralelo(diretorio_base: str, organizar_por_mes: bool, max_workers: int = None) -> pd.DataFrame:
    """ Coordena análise paralela, retorna DataFrame com resultados (inclui valores extraídos). """
    start_time = time.time(); logger.info(f"Iniciando análise paralela otimizada CPU em: {diretorio_base}")
    # 1. Lista arquivos .jpg/.jpeg no diretório e subdiretórios
    try:
        all_files_paths = [os.path.join(r, f) for r, d, fs in os.walk(diretorio_base) for f in fs if f.lower().endswith(tuple(IMAGE_EXTENSIONS))]
        total_files = len(all_files_paths); logger.info(f"Encontrados {total_files} arquivos para analisar.")
        if total_files == 0: return pd.DataFrame([]) # Retorna DF vazio se não achar arquivos
    except Exception as walk_err: logger.error(f"Erro ao listar arquivos: {walk_err}"); return pd.DataFrame([])

    # 2. Processamento Paralelo
    resultados_completos = []; workers = max_workers if max_workers else os.cpu_count(); logger.info(f"Usando até {workers} processos.")
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        # Submete cada arquivo para a função worker 'processar_arquivo_imagem'
        futures = {executor.submit(processar_arquivo_imagem, fp, diretorio_base, organizar_por_mes): fp for fp in all_files_paths}
        processed_count = 0
        for future in concurrent.futures.as_completed(futures): # Coleta resultados conforme terminam
            filepath = futures[future]; processed_count += 1
            try:
                result_dict = future.result() # Pega o dicionário retornado pelo worker
                if result_dict: resultados_completos.append(result_dict) # Adiciona à lista
            except Exception as exc: # Se o processo worker falhar completamente
                logger.error(f'Worker para {os.path.basename(filepath)} CRASHOU: {exc}', exc_info=True)
                # Adiciona um registro de erro mínimo
                resultados_completos.append({"caminho_completo": filepath, "nome_arquivo": os.path.basename(filepath), "erro_processamento": f"Falha Worker: {str(exc)[:100]}"})
            # Log de progresso
            if processed_count % 20 == 0 or processed_count == total_files: logger.info(f"Progresso Análise: {processed_count}/{total_files} concluídos.")

    # 3. Criação do DataFrame Final
    end_time = time.time(); logger.info(f"Análise paralela concluída em {end_time - start_time:.2f} s.")
    if not resultados_completos: logger.warning("Nenhum resultado coletado."); return pd.DataFrame([])

    logger.debug(f"Criando DataFrame final com {len(resultados_completos)} resultados.")
    df_analise = pd.DataFrame(resultados_completos) # Cria DataFrame a partir da lista de dicionários
    logger.info("DataFrame final criado.")

    # 4. Define a ordem das colunas para o CSV final
    #    Garante que as colunas com valores extraídos estejam presentes
    col_order = [
        "nome_arquivo", "pasta_pai", "data_extraida_arquivo", "largura_orig_px", "altura_orig_px", "tamanho_bytes",
        'paulinia_diesel_preco', 'paulinia_diesel_pct_def', 'paulinia_gasolina_pct_def', 'itaqui_diesel_ppi',
        'itaqui_gasolina_def_rs', 'aratu_diesel_preco', 'aratu_gasolina_ppi', "tabela_detectada",
        "erro_processamento", "caminho_completo" # Mantém erro e caminho no final
    ]
    # Reordena o DataFrame, colocando colunas extras (inesperadas) no final
    existing_cols = [col for col in col_order if col in df_analise.columns]
    extra_cols = [col for col in df_analise.columns if col not in existing_cols]
    df_analise = df_analise[existing_cols + extra_cols]

    return df_analise


# --- Função Principal de Análise e Reporte ---
def executar_e_reportar_analise(diretorio_imagens: str, organizar_por_mes: bool, diretorio_csv: str):
    """
    Ponto de entrada: Chama análise paralela, reporta no console
    e salva CSV final com valores extraídos ('tabela_tratada.csv').
    """
    logger.info(f"Executando análise otimizada CPU e report para: {diretorio_imagens}")
    # Chama a função que retorna o DataFrame com metadados e valores extraídos
    df_analise = analisar_imagens_paralelo(diretorio_imagens, organizar_por_mes)

    if df_analise is None or df_analise.empty: logger.warning("DataFrame vazio."); print("\nNenhuma imagem processada."); return

    # --- Ordenação por Data ---
    coluna_data = 'data_extraida_arquivo' # Coluna com DD-MM-YYYY
    if coluna_data in df_analise.columns:
        # Converte para datetime (erros viram NaT) e ordena
        df_analise[coluna_data] = pd.to_datetime(df_analise[coluna_data], format='%d-%m-%Y', errors='coerce')
        df_analise = df_analise.sort_values(by=coluna_data).reset_index(drop=True)
        logger.info(f"DataFrame final ordenado por '{coluna_data}'.")
        # Opcional: formatar data de volta para string no CSV final, se preferir
        # df_analise[coluna_data] = df_analise[coluna_data].dt.strftime('%d-%m-%Y')
    else: logger.warning(f"Coluna '{coluna_data}' não encontrada para ordenação.")

    # --- Relatório Console (Prévia) ---
    try:
        print("\n--- Tabela de Análise (Prévia com Valores Extraídos) ---")
        cols_preview = [ "nome_arquivo", "data_extraida_arquivo", "paulinia_diesel_preco", "paulinia_diesel_pct_def", "tabela_detectada", "erro_processamento" ]
        # ... (código da prévia como antes) ...
        cols_to_show = [col for col in cols_preview if col in df_analise.columns]; df_preview = df_analise[cols_to_show].head().copy()
        if "erro_processamento" in df_preview.columns: df_preview.loc[:, "erro_processamento"] = df_preview["erro_processamento"].fillna('')
        try: print(df_preview.to_markdown(index=False, floatfmt=".4f"))
        except ImportError: print(df_preview.to_string(index=False, float_format="%.4f"))
    except Exception as print_err: logger.error(f"Erro gerar prévia: {print_err}", exc_info=True)

    # --- Relatório Console (Resumo) ---
    print("\n--- Resumo da Análise Otimizada ---")
    try:
        # ... (código do resumo como antes, usando colunas do df_analise) ...
        total=len(df_analise); print(f"Total imagens: {total}"); erros=df_analise['erro_processamento'].notna().sum(); print(f"Com erro: {erros}");
        datas_validas=df_analise[coluna_data].notna().sum(); print(f"Com data válida: {datas_validas}");
        if 'tamanho_bytes' in df_analise.columns and df_analise['tamanho_bytes'].notna().any(): mb=df_analise['tamanho_bytes'].sum()/(1024*1024); kb=(df_analise['tamanho_bytes'].mean(skipna=True)/1024); print(f"Tam total: {mb:.2f} MB / Médio: {kb:.2f} KB")
        if 'largura_orig_px' in df_analise.columns and 'altura_orig_px' in df_analise.columns: w=df_analise['largura_orig_px'].mean(skipna=True); h=df_analise['altura_orig_px'].mean(skipna=True); print(f"Dimensões médias: {w:.0f}x{h:.0f} px")
        if 'tabela_detectada' in df_analise.columns: tab_ok=df_analise[df_analise['tabela_detectada'] == True].shape[0]; print(f"Com tabela detectada: {tab_ok}")
        if 'paulinia_diesel_pct_def' in df_analise.columns: media_def=df_analise['paulinia_diesel_pct_def'].mean(skipna=True); print(f"Média Def% Diesel Paulínia: {media_def:.2f}%")
    except Exception as summary_err: logger.error(f"Erro gerar resumo: {summary_err}", exc_info=True)

    # --- Salvamento do CSV Final Tratado ('tabela_tratada.csv') ---
    try:
        csv_filename = "tabela_tratada.csv" # Nome fixo
        # Salva no diretório passado por main.py (geralmente DATA_DIR)
        os.makedirs(diretorio_csv, exist_ok=True)
        csv_filepath = os.path.join(diretorio_csv, csv_filename)

        # Salva o DataFrame final (ordenado e com valores extraídos)
        df_analise.to_csv(csv_filepath, index=False, encoding='utf-8-sig', float_format='%.4f')
        logger.info(f"Análise final com valores extraídos salva em: {csv_filepath}")
        print(f"\nAnálise detalhada e tratada salva em: {csv_filepath}")
    except Exception as e: logger.error(f"Erro crítico ao salvar CSV final '{csv_filepath}': {e}", exc_info=True); print(f"\nERRO CRÍTICO ao salvar CSV final: {e}")


# --- Bloco Standalone ---
if __name__ == "__main__":
    # Configura logging para teste direto
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
    logging.getLogger().setLevel(logging.INFO)
    logger.info(f"Executando {__file__} standalone (teste otimizado)...")
    try: executar_e_reportar_analise(OUTPUT_DIR, ORGANIZE_BY_MONTH, DATA_DIR)
    except Exception as e: logger.critical(f"Erro fatal standalone: {e}", exc_info=True)

# ----- FIM do arquivo src/analise_imagens.py -----