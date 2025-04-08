import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urljoin, urlparse
import time
import re
from datetime import datetime # Importar datetime para validação

# --- Função de Download ---
def baixar_imagens_jpg_site(url_base, num_paginas, pasta_destino="imagens_jpg_baixadas"):
    """
    Localiza e baixa imagens que terminam com .jpg nas páginas de um site base
    para uma pasta local, usando o nome original do arquivo.
    Retorna True se o download ocorreu, False caso contrário.
    """
    if not os.path.exists(pasta_destino):
        os.makedirs(pasta_destino)
        print(f"Pasta '{pasta_destino}' criada.")

    all_jpg_image_links = set()
    urls_processadas = set()

    paginas_a_visitar = []
    for page_number in range(1, num_paginas + 1):
        # Assumindo estrutura /page/N para paginação após a primeira página
        url_pagina = f"{url_base}page/{page_number}/" if page_number > 1 else url_base
        paginas_a_visitar.append(url_pagina)

    page_count = 0
    download_ocorreu = False

    while paginas_a_visitar and page_count < num_paginas:
        url = paginas_a_visitar.pop(0)
        if url in urls_processadas:
            continue

        page_count += 1
        print(f"\n[{page_count}/{num_paginas}] Acessando a página: {url}")
        urls_processadas.add(url)

        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            # Encontra todas as tags <img> onde o src existe e termina com '.jpg' (case-insensitive)
            img_tags = soup.find_all('img', src=lambda s: s and s.lower().endswith('.jpg'))
            print(f"Encontradas {len(img_tags)} tags <img> com src terminando em .jpg nesta página.")

            for img in img_tags:
                if 'src' in img.attrs:
                    image_url = img['src']
                    # Constrói URL absoluta se for relativa
                    if not image_url.startswith('http'):
                        image_url = urljoin(url, image_url)

                    parsed_check = urlparse(image_url)
                    if parsed_check.path.lower().endswith('.jpg'):
                           all_jpg_image_links.add(image_url)
            time.sleep(1) # Pausa pequena para não sobrecarregar o servidor
        except requests.exceptions.Timeout:
             print(f"Erro de Timeout ao acessar {url}")
        except requests.exceptions.RequestException as e:
            print(f"Erro ao acessar {url}: {e}")
        except Exception as e:
             print(f"Ocorreu um erro inesperado ao processar {url}: {e}")

    print(f"\n--- Varredura de páginas concluída ---")
    print(f"Encontrados {len(all_jpg_image_links)} links únicos de imagem .jpg.")

    if not all_jpg_image_links:
         print("Nenhuma imagem .jpg encontrada para baixar.")
         return False

    print("\n--- Iniciando download das imagens ---")
    download_count = 0
    for i, image_url in enumerate(all_jpg_image_links):
        try:
            print(f"Baixando imagem {i+1}/{len(all_jpg_image_links)}: {image_url}")
            # Usa urlparse e os.path.basename para extrair nome do arquivo da URL
            parsed_url = urlparse(image_url)
            filename_from_url = os.path.basename(parsed_url.path)

            # Validação básica do nome do arquivo
            if not filename_from_url or len(filename_from_url) > 200:
                print(f"Nome de arquivo inválido ou muito longo extraído de {image_url}. Pulando.")
                continue

            filepath = os.path.join(pasta_destino, filename_from_url)
            # Verifica se o arquivo já existe para evitar baixar novamente
            if os.path.exists(filepath):
                print(f"Arquivo já existe: {filepath}. Pulando.")
                continue

            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            img_response = requests.get(image_url, stream=True, headers=headers, timeout=20) # Timeout maior para download
            img_response.raise_for_status()

            # Salva a imagem em modo binário
            with open(filepath, 'wb') as f:
                for chunk in img_response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"Imagem salva em: {filepath}")
            download_count += 1
            download_ocorreu = True
            time.sleep(0.5) # Pequena pausa entre downloads
        except requests.exceptions.Timeout:
             print(f"Erro de Timeout ao baixar a imagem {image_url}")
        except requests.exceptions.RequestException as e:
            print(f"Erro ao baixar a imagem {image_url}: {e}")
        except Exception as e:
            # Captura outros erros possíveis (ex: escrita no disco)
            print(f"Erro inesperado ao processar/salvar a imagem {image_url}: {e}")

    print(f"\n--- Download concluído ---")
    print(f"Total de {download_count} novas imagens .jpg baixadas com sucesso.")
    return download_ocorreu


# --- Função de Renomeação ---
def renomear_arquivos_por_data(pasta_alvo):
    """
    Renomeia arquivos .jpg na pasta_alvo que contêm 'de-YYYY-MM-DD-as' no nome.
    O novo nome será 'YYYY-MM-DD.jpg' ou 'YYYY-MM-DD_N.jpg' em caso de colisão.
    Arquivos que não correspondem ao padrão são ignorados.
    """
    print(f"\n--- Iniciando renomeação específica ('de-DATA-as') em '{pasta_alvo}' ---")
    renamed_count = 0
    pattern_not_found_count = 0 # Inclui arquivos sem padrão ou já nomeados
    error_count = 0

    # Regex para encontrar especificamente 'de-' seguido porAreaDataIndex-MM-DD e depois '-as'
    specific_pattern = re.compile(r'de-(?P<date>\d{4}-\d{2}-\d{2})-as')

    try:
        filenames = sorted(os.listdir(pasta_alvo))
    except FileNotFoundError:
        print(f"Erro: Pasta de destino '{pasta_alvo}' não encontrada para renomeação.")
        return

    for filename in filenames:
        original_filepath = os.path.join(pasta_alvo, filename)

        if not filename.lower().endswith('.jpg') or not os.path.isfile(original_filepath):
            continue

        match = specific_pattern.search(filename)

        if match:
            date_str = match.group('date')

            try:
                # Validação usando datetime
                datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError as e:
                print(f"Data inválida '{date_str}' encontrada no arquivo '{filename}': {e}. Pulando.")
                error_count += 1
                continue

            # ---- Lógica de Renomeação Revisada ----
            new_base_filename = f"{date_str}.jpg"
            target_filepath = os.path.join(pasta_alvo, new_base_filename)
            final_filepath_to_rename_to = None
            needs_rename = True

            counter = 1
            if os.path.exists(target_filepath):
                try:
                    if os.path.samefile(original_filepath, target_filepath):
                        needs_rename = False
                    else:
                        while True:
                            collided_filename = f"{date_str}_{counter}.jpg"
                            target_filepath = os.path.join(pasta_alvo, collided_filename)
                            if not os.path.exists(target_filepath):
                                final_filepath_to_rename_to = target_filepath
                                break
                            else:
                                if os.path.samefile(original_filepath, target_filepath):
                                    needs_rename = False
                                    break
                                counter += 1
                                if counter > 1000:
                                    print(f"Erro: Atingido limite de tentativas de colisão para data '{date_str}' com base em '{filename}'. Pulando.")
                                    error_count += 1
                                    needs_rename = False
                                    break
                except FileNotFoundError:
                    print(f"Aviso: Erro FileNotFoundError ao verificar samefile para '{target_filepath}' ou '{original_filepath}'. Pulando renomeação.")
                    error_count += 1
                    needs_rename = False
            else:
                if original_filepath == target_filepath:
                    needs_rename = False
                else:
                    final_filepath_to_rename_to = target_filepath

            if needs_rename and final_filepath_to_rename_to:
                try:
                    os.rename(original_filepath, final_filepath_to_rename_to)
                    print(f"Renomeado: '{filename}' -> '{os.path.basename(final_filepath_to_rename_to)}'")
                    renamed_count += 1
                except OSError as e:
                    print(f"Erro ao renomear '{filename}' para '{os.path.basename(final_filepath_to_rename_to)}': {e}")
                    error_count += 1
            elif not needs_rename:
                 pattern_not_found_count += 1

        else:
            pattern_not_found_count += 1

    print(f"\n--- Renomeação específica ('de-DATA-as') concluída ---")
    print(f"Arquivos renomeados para 'YYYY-MM-DD[_N].jpg': {renamed_count}")
    print(f"Arquivos que não continham o padrão ou já estavam nomeados corretamente: {pattern_not_found_count}")
    print(f"Erros durante a validação ou renomeação: {error_count}")


# --- Configuração e Execução ---
base_url_alvo = "https://abicom.com.br/categoria/ppi/"
numero_de_paginas_para_analisar = 5
pasta_para_salvar_jpg = "imagens_jpg_abicom"

# Chama a função de download
houve_download = baixar_imagens_jpg_site(base_url_alvo, numero_de_paginas_para_analisar, pasta_para_salvar_jpg)

# Chama a função de renomeação APÓS o download, se a pasta existir
if os.path.exists(pasta_para_salvar_jpg):
     renomear_arquivos_por_data(pasta_para_salvar_jpg)
else:
     print(f"\nPasta '{pasta_para_salvar_jpg}' não encontrada, pulando etapa de renomeação.")

print("\nProcesso de busca, download e organização concluído.")