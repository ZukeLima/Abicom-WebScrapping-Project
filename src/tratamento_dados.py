# src/tratamento_dados.py

"""
Módulo para EXTRAIR DADOS específicos das tabelas JSON contidas no CSV de análise
e consolidar esses dados em um único CSV tratado e organizado por data.
"""

# --- Imports ---
import os
import glob
import pandas as pd
import logging
import json
from datetime import datetime
import re
from typing import List, Optional, Dict # Import corrigido
from io import StringIO               # Para ler string JSON com pandas
import numpy as np                     # Para np.nan

# --- Imports do Projeto ---
try:
    from .config import DATA_DIR # Importa diretório 'data'
    if not DATA_DIR or not os.path.isdir(DATA_DIR): raise ValueError("DATA_DIR inválido")
    logger = logging.getLogger(__name__)
    logger.debug(f"Usando DATA_DIR de .config: {DATA_DIR}")
except Exception as e:
    logging.basicConfig(level=logging.WARNING); logger = logging.getLogger(__name__)
    logger.warning(f"Falha importar/validar DATA_DIR ({e}). Usando '../data'.")
    DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
    os.makedirs(DATA_DIR, exist_ok=True)
# --- Fim Imports ---

# --- Logger ---
logger = logging.getLogger(__name__)

# --- Regex e Constantes ---
# Padrão para extrair data DD-MM-YYYY do nome do arquivo de imagem
filename_date_pattern = re.compile(r"ppi-(\d{2}-\d{2}-\d{4})\.(jpg|jpeg)", re.IGNORECASE)

# Nomes ESPERADOS das colunas no CSV de entrada (AJUSTE SE NECESSÁRIO!)
COLUNA_NOME_ARQUIVO_IMG = "nome_arquivo"
COLUNA_JSON_TABELA = "tabelas_extraidas_json"

# Nome FIXO do arquivo de saída
NOME_ARQUIVO_SAIDA_TRATADO = "tabela_tratada.csv"
CAMINHO_SAIDA_TRATADO = os.path.join(DATA_DIR, NOME_ARQUIVO_SAIDA_TRATADO)


# --- Funções Auxiliares ---

def listar_csvs_analise(diretorio: str) -> List[str]:
    """ Lista arquivos 'analise_*.csv' ou 'relatorio_*.csv', recente primeiro. """
    # ** ATENÇÃO **: Confirme o padrão do arquivo gerado por analise_imagens.py!
    padrao_busca = os.path.join(diretorio, "analise_img2table_*.csv") # <--- AJUSTE SE NECESSÁRIO
    logger.debug(f"Procurando arquivos CSV com padrão: {padrao_busca}")
    # (Restante da função como antes)
    try:
        lista_arquivos = glob.glob(padrao_busca)
        if not lista_arquivos: logger.warning(f"Nenhum CSV encontrado: '{padrao_busca}'"); return []
        lista_arquivos.sort(key=os.path.getmtime, reverse=True)
        logger.info(f"Encontrados {len(lista_arquivos)} arquivos CSV de análise.")
        return lista_arquivos
    except Exception as e: logger.error(f"Erro listar CSVs: {e}", exc_info=True); return []


def clean_numeric_value(value):
    """ Limpa e converte string para float. """
    if value is None: return np.nan
    if isinstance(value, (int, float)): return float(value)
    if not isinstance(value, str): return np.nan
    try:
        cleaned = value.strip().replace('R$', '').replace('%', ''); cleaned = cleaned.replace('.', '').replace(',', '.')
        return float(cleaned) if cleaned else np.nan
    except (ValueError, TypeError): return np.nan

def find_indices_in_table(df_table, location, fuel, metric):
    """ Encontra índices (linha, coluna) no DataFrame da tabela. """
    # (Implementação mantida - assume cabeçalho na linha 1, comb na col 0, metr na col 1)
    col_idx = None; row_idx = None; header_row_idx = 1
    if df_table is None or df_table.empty or header_row_idx >= len(df_table.index): return None, None
    try: # Coluna
        header_row = df_table.iloc[header_row_idx]; loc_search = location.strip().lower()
        for idx, cell in enumerate(header_row):
            if isinstance(cell, str) and loc_search in cell.strip().lower(): col_idx = idx; break
        if col_idx is None: return None, None
    except Exception: return None, None
    try: # Linha
        fuel_search=fuel.strip().lower(); met_search=metric.strip().lower(); is_price=(met_search == 'preço (r$/l)')
        for idx in range(header_row_idx + 1, len(df_table.index)):
            try:
                row = df_table.iloc[idx]; f_cell = row.iloc[0] if len(row) > 0 else None; m_cell = row.iloc[1] if len(row) > 1 else None
                if not isinstance(f_cell, str) or fuel_search not in f_cell.strip().lower(): continue
                if is_price and pd.isna(m_cell): row_idx = idx; break
                elif isinstance(m_cell, str) and met_search in m_cell.strip().lower(): row_idx = idx; break
            except IndexError: continue
        if row_idx is None: return None, None
    except Exception: return None, None
    return row_idx, col_idx

def extrair_dados_tabela_individual(df_tabela: Optional[pd.DataFrame]) -> Dict:
    """
    Recebe o DataFrame de UMA tabela (parseada do JSON) e extrai os dados específicos.
    *** ESTA FUNÇÃO CONTÉM A LÓGICA DE EXTRAÇÃO QUE VOCÊ PRECISA AJUSTAR/CRIAR ***

    Args:
        df_tabela: DataFrame Pandas ou None se parse falhou.

    Returns:
        Dicionário com os dados extraídos (ex: {'preco_diesel_paulinia': 3.75, ...}).
        Inclui 'erro_extracao_tabela' se algo der errado na extração *desta* tabela.
    """
    # Define as chaves que queremos extrair e inicializa com NaN
    resultados_tabela = {
        'Paulínia_Diesel_Preço': np.nan, 'Paulínia_Diesel_%Defasado': np.nan, 'Paulínia_Gasolina_%Defasado': np.nan,
        'Itaqui_Diesel_PPI': np.nan, 'Itaqui_Gasolina_Defasagem(RS/L)': np.nan, 'Aratu_Diesel_Preço': np.nan,
        'Aratu_Gasolina_PPI': np.nan, 'erro_extracao_tabela': None
    }
    # Renomeei as chaves para facilitar a leitura no CSV final

    if df_tabela is None or df_tabela.empty:
        resultados_tabela['erro_extracao_tabela'] = "Tabela vazia ou erro no parse JSON"
        return resultados_tabela

    # Lista de alvos para extrair: (chave_dict, local_col, comb_lin, metr_lin)
    # As chaves do dicionário acima devem corresponder às chaves aqui!
    targets = [
        ('Paulínia_Diesel_Preço', 'Paulínia', 'Óleo Diesel A', 'Preço (R$/L)'),
        ('Paulínia_Diesel_%Defasado', 'Paulínia', 'Óleo Diesel A', '% Defasado'),
        ('Paulínia_Gasolina_%Defasado', 'Paulínia', 'Gasolina A', '% Defasado'),
        ('Itaqui_Diesel_PPI', 'Itaqui', 'Óleo Diesel A', 'PPI (RS/L)'),
        ('Itaqui_Gasolina_Defasagem(RS/L)', 'Itaqui', 'Gasolina A', 'Defasagem (RS/L)'),
        ('Aratu_Diesel_Preço', 'Aratu', 'Óleo Diesel A', 'Preço (R$/L)'),
        ('Aratu_Gasolina_PPI', 'Aratu', 'Gasolina A', 'PPI (RS/L)'),
    ]

    extracted_count = 0
    try:
        for key, loc, fuel, metric in targets:
            row_idx, col_idx = find_indices_in_table(df_tabela, loc, fuel, metric)
            if row_idx is not None and col_idx is not None:
                raw_value = df_tabela.iloc[row_idx, col_idx]
                cleaned_value = clean_numeric_value(raw_value)
                resultados_tabela[key] = cleaned_value # Guarda o valor limpo
                if not pd.isna(cleaned_value): extracted_count += 1
        logger.debug(f"Extraídos {extracted_count} valores da tabela individual.")
        if extracted_count == 0:
             logger.warning("Nenhum valor alvo extraído desta tabela individual.")
             # resultados_tabela['erro_extracao_tabela'] = "Nenhum valor alvo encontrado" # Opcional
    except Exception as e:
        logger.error(f"Erro ao extrair dados da tabela individual: {e}", exc_info=True)
        resultados_tabela['erro_extracao_tabela'] = f"Erro na extração: {str(e)[:100]}"

    return resultados_tabela


# --- Função Principal de Tratamento ---
def executar_tratamento_csv():
    """
    Ponto de entrada principal. Encontra o CSV mais recente, lê linha a linha,
    parseia o JSON de cada linha, extrai dados da tabela resultante,
    agrega os dados extraídos e salva um único CSV final ('tabela_tratada.csv').
    """
    logger.info("--- Iniciando Tratamento do CSV com Extração por Linha ---")

    # 1. Encontra o CSV de análise mais recente
    lista_csvs = listar_csvs_analise(DATA_DIR)
    if not lista_csvs: logger.error("Tratamento abortado: Nenhum CSV de análise encontrado."); return
    caminho_csv_entrada = lista_csvs[0] # Pega o mais recente
    logger.info(f"Arquivo CSV de análise selecionado para tratamento: {caminho_csv_entrada}")

    # 2. Carrega o CSV principal
    try:
        df_principal = pd.read_csv(caminho_csv_entrada)
        logger.info(f"CSV principal carregado com {len(df_principal)} linhas.")
        if df_principal.empty: logger.warning("CSV principal vazio. Abortando."); return
    except Exception as e: logger.error(f"Erro ao carregar CSV '{caminho_csv_entrada}': {e}", exc_info=True); return

    # Verifica colunas essenciais
    if COLUNA_NOME_ARQUIVO_IMG not in df_principal.columns or COLUNA_JSON_TABELA not in df_principal.columns:
        logger.error(f"Erro: Colunas '{COLUNA_NOME_ARQUIVO_IMG}' ou '{COLUNA_JSON_TABELA}' não encontradas no CSV."); return

    # 3. Processa cada linha para extrair dados das tabelas JSON
    lista_resultados_finais = [] # Guarda os resultados processados de cada linha
    logger.info("Iniciando processamento linha a linha do CSV principal...")
    for indice, linha in df_principal.iterrows():
        nome_arquivo_original = linha.get(COLUNA_NOME_ARQUIVO_IMG)
        json_str_lista = linha.get(COLUNA_JSON_TABELA)
        logger.debug(f"Processando linha {indice}: {nome_arquivo_original}")

        # Extrai a data do nome do arquivo original
        data_imagem_dt = None # datetime object
        data_imagem_str = None # string DD-MM-YYYY
        if isinstance(nome_arquivo_original, str):
             match = filename_date_pattern.search(nome_arquivo_original)
             if match:
                  data_imagem_str = match.group(1)
                  try: data_imagem_dt = pd.to_datetime(data_imagem_str, format='%d-%m-%Y')
                  except ValueError: logger.warning(f"Linha {indice}: Formato de data inválido no nome '{nome_arquivo_original}'")

        # Tenta parsear o JSON e extrair dados da tabela individual
        df_tabela_individual = None
        erro_parse_json = None
        if pd.notna(json_str_lista) and json_str_lista != '[]':
            try:
                lista_tabelas_json = json.loads(json_str_lista)
                if lista_tabelas_json:
                    primeira_tabela_json_str = lista_tabelas_json[0]
                    df_tabela_individual = pd.read_json(StringIO(primeira_tabela_json_str), orient="split")
            except Exception as e: erro_parse_json = f"Erro parse JSON: {str(e)[:100]}"
        else: erro_parse_json = "JSON ausente ou vazio"

        if erro_parse_json: logger.warning(f"Linha {indice} ({nome_arquivo_original}): {erro_parse_json}")

        # Chama a função para extrair os dados desta tabela (mesmo que seja None)
        dados_extraidos = extrair_dados_tabela_individual(df_tabela_individual)

        # Monta o dicionário de resultados para esta linha
        resultado_final_linha = {
            'Data': data_imagem_dt, # Coluna de Data (tipo datetime)
            'Nome_Arquivo_Origem': nome_arquivo_original,
            # Adiciona os dados extraídos (desempacota o dicionário)
            **dados_extraidos,
            # Adiciona outras informações úteis do CSV original, se desejar
            'Erro_Processamento_Inicial': linha.get('erro_processamento'), # Erro da etapa anterior
            'Erro_Parse_JSON_Tabela': erro_parse_json # Erro específico do parse JSON nesta etapa
        }
        lista_resultados_finais.append(resultado_final_linha)

    # 4. Cria o DataFrame final consolidado
    logger.info("Agregando resultados de todas as linhas...")
    if not lista_resultados_finais:
        logger.warning("Nenhum resultado processado. DataFrame final estará vazio.")
        df_final = pd.DataFrame()
    else:
        df_final = pd.DataFrame(lista_resultados_finais)
        # Garante que a coluna 'Data' seja do tipo datetime (pode ter sido perdida se todas as datas falharam)
        if 'Data' in df_final.columns:
            df_final['Data'] = pd.to_datetime(df_final['Data'], errors='coerce')
            # Ordena pela data
            df_final = df_final.sort_values(by='Data').reset_index(drop=True)
            logger.info(f"DataFrame final criado e ordenado por data com {len(df_final)} linhas.")
        else:
             logger.warning("Coluna 'Data' não encontrada no DataFrame final.")

    # 5. Salva o DataFrame final no arquivo 'tabela_tratada.csv'
    if not df_final.empty:
        try:
            logger.info(f"Salvando DataFrame final tratado em: {CAMINHO_SAIDA_TRATADO}")
            # Salva, sobrescrevendo se o arquivo já existir
            df_final.to_csv(CAMINHO_SAIDA_TRATADO, index=False, encoding='utf-8-sig', float_format='%.4f')
            if os.path.exists(CAMINHO_SAIDA_TRATADO): logger.info(f"Salvo com sucesso: {CAMINHO_SAIDA_TRATADO}"); print(f"\nArquivo final tratado salvo: {CAMINHO_SAIDA_TRATADO}")
            else: logger.error(f"ERRO: CSV final NÃO FOI CRIADO: {CAMINHO_SAIDA_TRATADO}"); print(f"\nERRO salvar CSV final.")
        except Exception as e: logger.error(f"Erro ao salvar CSV final: {e}", exc_info=True); print(f"\nERRO salvar CSV final: {e}")
    else:
        logger.warning("DataFrame final está vazio. Nenhum arquivo '{NOME_ARQUIVO_SAIDA_TRATADO}' foi salvo.")
        print(f"\nDataFrame final vazio. '{NOME_ARQUIVO_SAIDA_TRATADO}' não foi gerado.")

    logger.info("--- Tratamento (Extração por Linha) Concluído ---")


# --- Ponto de Entrada Principal (__name__ == "__main__") ---
if __name__ == "__main__":
    # Configura logging SE EXECUTADO DIRETAMENTE
    if not logging.getLogger().hasHandlers():
         logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
         logging.getLogger().setLevel(logging.INFO)

    logger.info(f"Executando {__file__} como script principal (processa CSV mais recente)...")
    # Chama a função principal que busca o mais recente e processa
    executar_tratamento_csv()
    logger.info("Script de tratamento de CSV finalizado.")

# ----- FIM do arquivo src/tratamento_dados.py -----