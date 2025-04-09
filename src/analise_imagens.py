# src/analise_imagens.py
import os
import re
import pandas as pd
import logging
from datetime import datetime
from PIL import Image, UnidentifiedImageError # Importa erro específico
from PIL.ExifTags import TAGS
import easyocr
import numpy as np # Importa numpy para array de imagem
import json # Para salvar EXIF como JSON
import concurrent.futures # Para processamento paralelo
import time # Para medir tempo
import sys # Para standalone logging config

# --- Logger ---
# Cria um logger específico para este módulo. A configuração (nível, formato, handlers)
# geralmente é herdada do root logger configurado em main.py quando importado,
# mas definimos uma config básica no final para execução standalone.
logger = logging.getLogger(__name__)
# ---------------------------------------

# --- Configuração e Inicialização (com fallback) ---
# Tenta carregar as configurações do projeto. Se falhar, usa padrões.
try:
    # Assume que OUTPUT_DIR em config.py aponta para a pasta 'images'
    from src.config import OUTPUT_DIR, ORGANIZE_BY_MONTH
    # Deriva DATA_DIR como o diretório pai de OUTPUT_DIR (pasta 'data')
    DATA_DIR = os.path.dirname(OUTPUT_DIR)
    # Validação básica
    if not OUTPUT_DIR or not DATA_DIR or not os.path.isdir(DATA_DIR):
        raise ImportError("OUTPUT_DIR não definido ou inválido em config.py, ou DATA_DIR não encontrado.")
    # Garante que o diretório DATA_DIR exista (onde o CSV será salvo)
    os.makedirs(DATA_DIR, exist_ok=True)
    logger.debug(f"Configuração carregada: OUTPUT_DIR={OUTPUT_DIR}, DATA_DIR={DATA_DIR}")
except ImportError as e:
    logger.warning(f"Configuração via src.config falhou ({e}). Usando caminhos padrão.")
    # Define caminhos padrão relativos à localização deste script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    DATA_DIR = os.path.join(project_root, "data")
    OUTPUT_DIR = os.path.join(DATA_DIR, "images")
    ORGANIZE_BY_MONTH = True
    logger.warning(f"Fallback: OUTPUT_DIR={OUTPUT_DIR}, DATA_DIR={DATA_DIR}")
    # Garante que os diretórios de fallback existam
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
# --- Fim Configuração ---

# --- Regex ---
filename_date_pattern = re.compile(r"ppi-(\d{2}-\d{2}-\d{4})\.(jpg|jpeg)", re.IGNORECASE)
folder_date_pattern = re.compile(r"(\d{2})-(\d{4})")
# --- Fim Regex ---

# --- Verificação Inicial da Disponibilidade do EasyOCR ---
# Tenta inicializar uma vez aqui APENAS para definir a flag global 'easyocr_available'.
# A(s) instância(s) real(is) usada(s) pelos workers será(ão) criada(s) dentro deles.
_easyocr_checker_instance = None
easyocr_available = False
try:
    logger.info("Verificando disponibilidade do EasyOCR (pode baixar modelos)...")
    # Instancia temporariamente só para ver se funciona e baixa modelos se necessário
    _easyocr_checker_instance = easyocr.Reader(['pt', 'en'], gpu=False) # Ajuste idiomas conforme necessidade
    easyocr_available = True
    logger.info("EasyOCR parece estar disponível.")
    # Libera a instância de verificação da memória imediatamente
    del _easyocr_checker_instance
except Exception as e:
    logger.error(f"Falha ao inicializar EasyOCR na verificação global: {e}. OCR será desativado.")
    # easyocr_available já é False por padrão
# --- Fim Verificação EasyOCR ---


# --- Dicionário para armazenar leitores EasyOCR por processo worker ---
# Chave: PID do processo worker, Valor: instância do Reader ou False se falhou
# Isso evita reinicializar em cada chamada de função *dentro do mesmo worker*
_worker_readers = {}

# --- Função para processar UM ÚNICO arquivo (Executada em processo separado) ---
def processar_arquivo_imagem(filepath: str, base_dir: str, organizar_por_mes: bool):
    """
    Processa um único arquivo de imagem, extraindo metadados, propriedades
    e texto OCR. Retorna um dicionário com os resultados.
    Esta função é projetada para ser chamada por ProcessPoolExecutor.
    """
    global _worker_readers # Permite modificar o dicionário compartilhado *neste contexto de worker*
    worker_pid = os.getpid() # Identifica o processo worker atual

    filename = os.path.basename(filepath)
    # Usa um logger específico para o worker para facilitar debug se necessário
    worker_logger = logging.getLogger(f"{__name__}.worker{worker_pid}")
    worker_logger.debug(f"Processando: {filename}")

    root = os.path.dirname(filepath)
    norm_base_path = os.path.normpath(base_dir)
    current_folder_is_base = (os.path.normpath(root) == norm_base_path)
    folder_name = os.path.basename(root)

    # Inicializa dicionário de resultados para este arquivo
    result_dict = {
        "caminho_completo": filepath, "nome_arquivo": filename,
        "pasta_pai": folder_name if not current_folder_is_base else "[RAIZ]",
        "data_extraida_arquivo": None, "mes_pasta": None, "ano_pasta": None,
        "tamanho_bytes": None, "largura_px": None, "altura_px": None,
        "modo_cor": None, "formato_imagem": None,
        "exif_data_json": None, # Salvar EXIF como JSON
        "texto_easyocr": None,
        "erro_processamento": None
    }

    try:
        # --- Metadados do Arquivo ---
        result_dict["tamanho_bytes"] = os.path.getsize(filepath)

        # Extração de data/mês/ano do nome/pasta
        match_filename = filename_date_pattern.search(filename)
        if match_filename:
             date_str = match_filename.group(1)
             try:
                 datetime.strptime(date_str, '%d-%m-%Y')
                 result_dict["data_extraida_arquivo"] = date_str
             except ValueError: worker_logger.warning(f"Formato data inválido nome: {filename}") # Log com logger do worker
        if organizar_por_mes and not current_folder_is_base:
             match_folder = folder_date_pattern.match(folder_name)
             if match_folder: result_dict["mes_pasta"], result_dict["ano_pasta"] = match_folder.groups()

        # --- Processamento da Imagem (Pillow, EXIF, OCR) ---
        exif_info = {}
        img_array = None # Para passar ao OCR
        with Image.open(filepath) as img:
            result_dict["largura_px"], result_dict["altura_px"] = img.size
            result_dict["modo_cor"] = img.mode
            result_dict["formato_imagem"] = img.format

            # Extrair EXIF
            try:
                exif_raw = img._getexif()
                if exif_raw:
                     for tag, value in exif_raw.items():
                         decoded_tag = TAGS.get(tag, tag)
                         if isinstance(value, bytes):
                             try: exif_info[decoded_tag] = value.decode(errors='replace')
                             except: exif_info[decoded_tag] = repr(value)
                         # Ignora tags IFD (Internal File Directory pointers) que não são serializáveis
                         elif decoded_tag != 'MakerNote' and not isinstance(decoded_tag, int) and 'IFD' not in str(decoded_tag):
                              exif_info[decoded_tag] = value
                # Salva como JSON (lida com tipos não serializáveis como datas ou tuplas)
                result_dict["exif_data_json"] = json.dumps(exif_info, default=str) if exif_info else None
            except Exception as exif_err:
                 worker_logger.debug(f"Erro ao ler EXIF de {filename}: {exif_err}")

            # Prepara para OCR se OCR estiver disponível globalmente
            if easyocr_available:
                 # Converte imagem Pillow para Numpy array (necessário para easyocr)
                 img_array = np.array(img)

        # --- OCR (fora do 'with' da Pillow para liberar o arquivo da imagem) ---
        if easyocr_available and img_array is not None:
            # Verifica se este worker já inicializou seu leitor EasyOCR
            current_worker_reader = _worker_readers.get(worker_pid)

            if current_worker_reader is None: # Primeira vez para este worker
                worker_logger.info(f"Inicializando EasyOCR reader...")
                try:
                    # Cria a instância do reader para este worker
                    current_worker_reader = easyocr.Reader(['pt', 'en'], gpu=False) # Ajuste idiomas e GPU
                    _worker_readers[worker_pid] = current_worker_reader # Armazena para reutilização
                    worker_logger.info(f"EasyOCR reader inicializado.")
                except Exception as worker_ocr_init_err:
                    worker_logger.error(f"Falha ao inicializar EasyOCR no worker: {worker_ocr_init_err}")
                    result_dict["texto_easyocr"] = f"ERRO_OCR_INIT: {str(worker_ocr_init_err)[:100]}"
                    _worker_readers[worker_pid] = False # Marca como falho para este worker

            # Executa OCR se o leitor deste worker foi inicializado com sucesso
            if isinstance(current_worker_reader, easyocr.Reader):
                try:
                    # detail=0 retorna apenas a lista de strings detectadas
                    results = current_worker_reader.readtext(img_array, detail=0)
                    result_dict["texto_easyocr"] = ' '.join(results) if results else "" # Retorna string vazia se não detectar nada
                    if result_dict["texto_easyocr"]:
                        worker_logger.debug(f"Texto OCR de {filename} (trecho): {result_dict['texto_easyocr'][:50]}...")
                except Exception as ocr_err:
                    worker_logger.warning(f"Erro durante EasyOCR em {filename}: {ocr_err}")
                    result_dict["texto_easyocr"] = f"ERRO_OCR_EXEC: {str(ocr_err)[:100]}" # Guarda erro limitado
            elif current_worker_reader is False: # Se a inicialização falhou anteriormente neste worker
                 result_dict["texto_easyocr"] = "ERRO_OCR_INIT_ANTERIOR"

    except FileNotFoundError:
        worker_logger.error(f"Arquivo não encontrado: {filepath}")
        result_dict["erro_processamento"] = "Arquivo não encontrado"
    except UnidentifiedImageError:
        worker_logger.warning(f"Não foi possível identificar/abrir imagem: {filename}")
        result_dict["erro_processamento"] = "Formato inválido/corrompido"
    except Exception as e:
        worker_logger.error(f"Erro inesperado processando {filename}: {e}", exc_info=False) # Log traceback reduzido
        result_dict["erro_processamento"] = str(e)[:150] # Guarda mensagem de erro limitada

    return result_dict


def analisar_imagens_paralelo(diretorio_base: str, organizar_por_mes: bool, max_workers: int = None) -> pd.DataFrame:
    """
    Analisa imagens em paralelo usando ProcessPoolExecutor.
    """
    start_time = time.time()
    logger.info(f"Iniciando análise paralela em: {diretorio_base}")

    if not os.path.exists(diretorio_base):
        logger.error(f"Diretório de imagens não encontrado: {diretorio_base}")
        return pd.DataFrame([])

    # Lista todos os arquivos .jpg/.jpeg primeiro
    try:
        all_files_paths = [os.path.join(r, f) for r, d, fs in os.walk(diretorio_base) for f in fs if f.lower().endswith(('.jpg', '.jpeg'))]
        total_files = len(all_files_paths)
        logger.info(f"Encontrados {total_files} arquivos .jpg/.jpeg para analisar.")
        if total_files == 0:
            logger.warning("Nenhum arquivo de imagem encontrado para análise.")
            return pd.DataFrame([])
    except Exception as walk_err:
        logger.error(f"Erro ao listar arquivos para análise: {walk_err}")
        return pd.DataFrame([])

    resultados = []
    # Define o número de workers (processos paralelos)
    if max_workers is None:
         max_workers = os.cpu_count() # Default para número de CPUs
    logger.info(f"Usando até {max_workers} processos paralelos.")

    # Usa ProcessPoolExecutor para paralelismo real (melhor para CPU-bound OCR)
    # O inicializador pode ser usado para configurar logging em workers, mas
    # o logger global já deve funcionar se configurado corretamente no main.
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submete todas as tarefas para execução
        # Passa os argumentos fixos para processar_arquivo_imagem
        futures = {executor.submit(processar_arquivo_imagem, filepath, diretorio_base, organizar_por_mes): filepath for filepath in all_files_paths}

        processed_count = 0
        # Coleta resultados conforme eles ficam prontos
        for future in concurrent.futures.as_completed(futures):
            filepath = futures[future]
            processed_count += 1
            try:
                result = future.result() # Pega o dicionário retornado pela função worker
                if result:
                    resultados.append(result)
            except Exception as exc:
                # Captura exceções que podem ter ocorrido no worker e não foram tratadas lá
                logger.error(f'Arquivo {os.path.basename(filepath)} gerou exceção fatal no worker: {exc}')
                # Adiciona um registro de erro se o worker falhou completamente
                resultados.append({
                    "caminho_completo": filepath,
                    "nome_arquivo": os.path.basename(filepath),
                    "erro_processamento": f"Falha Worker: {str(exc)[:100]}" # Guarda erro limitado
                 })

            # Log de progresso periódico
            if processed_count % 100 == 0 or processed_count == total_files:
                 logger.info(f"Progresso da análise paralela: {processed_count}/{total_files} arquivos concluídos.")

    end_time = time.time()
    logger.info(f"Análise paralela concluída em {end_time - start_time:.2f} segundos.")

    if not resultados:
         logger.warning("Nenhum resultado válido coletado da análise paralela.")
         return pd.DataFrame([])

    # Converte a lista de dicionários em DataFrame do Pandas
    df_analise = pd.DataFrame(resultados)

    # Reordena colunas para uma melhor visualização no CSV (opcional)
    col_order = [
        "nome_arquivo", "pasta_pai", "data_extraida_arquivo", "mes_pasta", "ano_pasta",
        "tamanho_bytes", "largura_px", "altura_px", "modo_cor", "formato_imagem",
        "texto_easyocr", "exif_data_json", "erro_processamento", "caminho_completo"
    ]
    # Garante que só usa colunas que realmente existem no DataFrame final
    existing_cols = [col for col in col_order if col in df_analise.columns]
    df_analise = df_analise[existing_cols]

    return df_analise


def executar_e_reportar_analise(diretorio_imagens: str, organizar_por_mes: bool, diretorio_csv: str):
    """
    Executa a análise paralela das imagens, imprime um resumo no console
    e salva um arquivo CSV detalhado com os resultados.
    """
    logger.info(f"Executando análise completa e geração de relatório para: {diretorio_imagens}")
    # Chama a função de análise paralela
    df_analise = analisar_imagens_paralelo(diretorio_imagens, organizar_por_mes)

    # Verifica se o DataFrame resultante está vazio ou None
    if df_analise is None or df_analise.empty:
        logger.warning("DataFrame de análise vazio ou None após processamento paralelo. Nenhum relatório ou CSV será gerado.")
        print("\nNenhuma imagem processada com sucesso ou encontrada para gerar análise/CSV.")
        return # Termina a função aqui

    # --- Exibição no Console (Resumo e Prévia) ---
    try:
        print("\n--- Tabela de Análise das Imagens (Prévia) ---")
        cols_preview = [
            "nome_arquivo", "pasta_pai", "data_extraida_arquivo",
            "largura_px", "altura_px", "tamanho_bytes", "erro_processamento",
            "texto_easyocr" # Mostrar o início do texto OCR na prévia
        ]
        # Garante que só seleciona colunas que existem
        cols_to_show = [col for col in cols_preview if col in df_analise.columns]
        df_preview = df_analise[cols_to_show].head().copy() # Usa .copy() para evitar SettingWithCopyWarning

        # Formata colunas para exibição
        if "texto_easyocr" in df_preview.columns:
            # Limita o tamanho e trata None/NaN antes de aplicar .str
            df_preview.loc[:, "texto_easyocr"] = df_preview["texto_easyocr"].fillna('').astype(str).str[:70] + '...'
        if "erro_processamento" in df_preview.columns:
             df_preview.loc[:, "erro_processamento"] = df_preview["erro_processamento"].fillna('')

        # Tenta usar markdown para melhor formatação no terminal
        try:
            print(df_preview.to_markdown(index=False))
        except ImportError:
            # Fallback para to_string se tabulate não estiver instalado
            print(df_preview.to_string(index=False))

    except Exception as print_err:
        logger.error(f"Erro ao gerar prévia para console: {print_err}", exc_info=True)
        print("Erro ao gerar prévia da tabela.")

    # --- Resumo Estatístico ---
    print("\n--- Resumo da Análise ---")
    try:
        total_registros = len(df_analise)
        print(f"Total de registros (imagens processadas): {total_registros}")

        # Conta erros de processamento (coluna adicionada)
        erros_proc = df_analise['erro_processamento'].notna().sum()
        if erros_proc > 0:
             print(f"Imagens com erro durante processamento: {erros_proc}")

        # Contagem por pasta
        if organizar_por_mes and 'pasta_pai' in df_analise.columns:
            contagem_pasta = df_analise[df_analise['pasta_pai'] != '[RAIZ]']['pasta_pai'].value_counts()
            if not contagem_pasta.empty:
                print("\nContagem de imagens por pasta (Mês-Ano):")
                print(contagem_pasta.to_string())

        # Outras estatísticas (verificando se coluna existe)
        if 'data_extraida_arquivo' in df_analise.columns:
             datas_validas = df_analise['data_extraida_arquivo'].notna().sum()
             print(f"\nImagens com data válida extraída do nome: {datas_validas}")

        if 'tamanho_bytes' in df_analise.columns and df_analise['tamanho_bytes'].notna().any():
             tamanho_total_mb = df_analise['tamanho_bytes'].sum() / (1024 * 1024)
             tamanho_medio_kb = (df_analise['tamanho_bytes'].mean(skipna=True) / 1024)
             print(f"\nTamanho total dos arquivos: {tamanho_total_mb:.2f} MB")
             print(f"Tamanho médio por arquivo: {tamanho_medio_kb:.2f} KB")

        if 'largura_px' in df_analise.columns and 'altura_px' in df_analise.columns:
             largura_media = df_analise['largura_px'].mean(skipna=True)
             altura_media = df_analise['altura_px'].mean(skipna=True)
             if pd.notna(largura_media) and pd.notna(altura_media):
                  print(f"Dimensões médias: {largura_media:.0f} x {altura_media:.0f} px")

        # EXIF não é mais uma coluna específica, mas JSON
        if 'exif_data_json' in df_analise.columns:
             exif_present_count = df_analise['exif_data_json'].notna().sum()
             print(f"Imagens com dados EXIF extraídos: {exif_present_count}")

        # Contagem OCR
        if easyocr_available and 'texto_easyocr' in df_analise.columns:
            # Conta textos não nulos e não vazios como sucesso
            ocr_success_count = df_analise[df_analise['texto_easyocr'].fillna('').astype(str).str.strip() != ''].shape[0]
            # Conta erros explicitamente
            ocr_error_count = df_analise[df_analise['texto_easyocr'].astype(str).str.startswith("ERRO_OCR", na=False)].shape[0]
            # Ajusta a contagem de sucesso para não incluir os erros explícitos
            ocr_success_count -= ocr_error_count
            print(f"Imagens com texto extraído via EasyOCR: {ocr_success_count}")
            if ocr_error_count > 0:
                print(f"Imagens com erro durante EasyOCR (init ou exec): {ocr_error_count}")

    except Exception as summary_err:
        logger.error(f"Erro ao gerar resumo estatístico: {summary_err}", exc_info=True)
        print("Erro ao gerar resumo estatístico.")

    # --- Geração do CSV ---
    try:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"analise_paralela_ocr_{timestamp_str}.csv"
        # Garante que o diretório para salvar o CSV exista
        os.makedirs(diretorio_csv, exist_ok=True)
        csv_filepath = os.path.join(diretorio_csv, csv_filename)

        # Salva o DataFrame COMPLETO em CSV
        df_analise.to_csv(csv_filepath, index=False, encoding='utf-8-sig')
        logger.info(f"Análise completa salva com sucesso em: {csv_filepath}")
        print(f"\nAnálise detalhada (paralela com OCR) salva em: {csv_filepath}")

    except ImportError: # Erro se Pandas não estiver disponível aqui
         logger.critical("Pandas não instalado. Não foi possível salvar o resultado em CSV.")
         print("\nERRO CRÍTICO: Pandas não instalado, impossível salvar CSV.")
    except Exception as e:
        logger.error(f"Erro crítico ao salvar a análise em CSV: {e}", exc_info=True)
        print(f"\nERRO CRÍTICO ao salvar a análise em CSV: {e}")

# Bloco principal para permitir execução standalone do script de análise
if __name__ == "__main__":
    # Configura o logging AQUI TAMBÉM para quando rodar standalone
    # Define um nível mais detalhado para standalone se necessário
    log_level = logging.DEBUG # ou logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s', # Adiciona linha
        handlers=[logging.StreamHandler(sys.stdout)] # Saída só no console
    )
    # Define o nível para o logger raiz (afeta também os workers se usarem getLogger)
    logging.getLogger().setLevel(log_level)

    logger.info("Executando analise_imagens.py como script principal (standalone)...")
    # Chama a função principal de execução/reporte
    # Usa as variáveis OUTPUT_DIR e DATA_DIR definidas no início do script
    executar_e_reportar_analise(OUTPUT_DIR, ORGANIZE_BY_MONTH, DATA_DIR)