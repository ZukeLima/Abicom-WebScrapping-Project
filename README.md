# Abicom PPI - Scraper e Extrator de Tabela de Imagens

[![Versão Python](https://img.shields.io/badge/python-3.8+-blue)](https://www.python.org/) [![Licença](https://img.shields.io/badge/License-MIT-yellow.svg)](#)

## 1. Sumário

Coleta imagens de relatórios PPI do site Abicom e extrai a primeira tabela detectada via OCR/análise de layout, salvando-a como um arquivo CSV individual em `data/tabelas_por_mes/MM-YYYY/`.

**Desenvolvido por:** Lucas Lima <a href="https://www.linkedin.com/in/zukelima/" target="_blank" rel="noopener noreferrer"><img src="https://cdn-icons-png.flaticon.com/256/174/174857.png" alt="LinkedIn" width="24" height="24" style="vertical-align:middle;"></a>

## 2. Workflow Básico

1.  **Execução (`src/main.py`):** Orquestra as etapas via `python -m src.main`.
2.  **Scraping (`src/scrapers/abicom_scraper.py`):** Identifica URLs de posts/imagens.
3.  **Download/Verificação (`src/services/image_service.py`):** Baixa imagens novas, evita duplicatas (verificação de arquivos), organiza em `data/images/MM-YYYY/`.
4.  **Análise de Imagem (`src/analise_imagens.py`):** Processa imagens em `data/images/` (paralelamente): pré-processamento (opcional), extração da 1ª tabela (`img2table`/`easyocr`), tratamento de cabeçalho (`ffill`), salvamento do CSV individual em `data/tabelas_por_mes/MM-YYYY/`.
5.  **Relatório:** Exibe contagem de sucessos/falhas da análise no console.

## 3. Componentes Principais

* **`src/main.py`:** Orquestrador do fluxo, `argparse`, config. logging.
* **`src/config.py`:** Constantes globais (URLs, Paths, Limites).
* **`src/scrapers/abicom_scraper.py`:** Lógica de scraping Abicom (`requests`, `bs4`).
* **`src/services/image_service.py`:** Gerencia download/verificação de imagens (sem DB).
* **`src/analise_imagens.py`:** Lógica de análise (paralelismo, `Pillow`, `img2table`, `easyocr`, `pandas`, salvamento CSVs individuais).
* **`src/services/http_client.py`:** Cliente HTTP com re-tentativas (`requests.Session`).

## 4. Dependências Principais

* **Linguagem:** Python (>= 3.8)
* **Bibliotecas:** `requests`, `beautifulsoup4`, `Pillow`, `easyocr`, `img2table`, `pandas`, `numpy`, `torch`/`torchvision` (CPU), `concurrent.futures`, `logging`, `argparse`, `re`.

*(Consulte `requirements.txt`)*


## 🏗️ 4. Estrutura do Projeto

```text
Abicom-WebScrapping-Project/
|
+-- .venv/                     # Ambiente Virtual Python (ex: python -m venv venv)
|
+-- .devcontainer/             # (Opcional) Configuração VS Code + Docker
|   +-- devcontainer.json
|   +-- Dockerfile
+-- .vscode/                   # (Opcional) Configurações VS Code
|   +-- settings.json
|
+-- src/                       # Código Fonte (Package 'src')
|   |-- __init__.py            # Inicializador do pacote
|   |-- config.py              # Configurações globais (URLs, Paths, etc.)
|   |-- main.py                # Ponto de entrada principal (orquestra Scraper e Análise)
|   |-- analise_imagens.py     # Lógica de análise (OCR, Extração, Salvar CSVs Indiv.) <-- Descrição Atualizada
|   |-- models/                # Modelos de dados (dataclasses)
|   |   |-- __init__.py
|   |   |-- image.py           # Dataclass 'Image'
|   |-- services/              # Serviços reutilizáveis
|   |   |-- __init__.py
|   |   |-- http_client.py     # Cliente HTTP com retentativas
|   |   |-- image_service.py   # Gerenciador de imagens (versão sem DB)
|   |-- scrapers/              # Scrapers específicos do site
|   |   |-- __init__.py
|   |   |-- base_scraper.py    # Classe base abstrata
|   |   |-- abicom_scraper.py  # Implementação para Abicom
|   |-- utils/                 # Funções utilitárias
|   |   |-- __init__.py
|   |   |-- file_utils.py      # Utilitários de arquivo
|   |   |-- url_utils.py       # Utilitários de URL
|
+-- data/                      # Diretório de Dados Gerados (Criado automaticamente)
|   |-- images/                # Imagens baixadas pelo scraper
|   |   |-- MM-YYYY/           # Organizadas por mês/ano (se habilitado)
|   |       |-- ppi-DD-MM-YYYY.jpg
|   |-- tabelas_por_mes/       # CSVs das tabelas individuais extraídas <-- ATUALIZADO
|   |   |-- MM-YYYY/           # Organizadas por mês/ano <-- ATUALIZADO
|   |       |-- ppi-DD-MM-YYYY_tabela.csv <-- ATUALIZADO
|   |-- error.log              # Log específico de erros (ERROR/CRITICAL) <-- ADICIONADO/Confirmado
|
+-- requirements.txt           # Dependências Python
+-- scraper.log                # Log geral da execução (INFO/DEBUG)
+-- README.md                  # Documentação (Este arquivo)

```


## 5. ⚙️ Instalação

1.  **Pré-requisitos:** Python >= 3.8, `pip`, `git`.
2.  **Clone:** `git clone <URL_DO_SEU_REPOSITORIO> Abicom-WebScrapping-Project && cd Abicom-WebScrapping-Project`
3.  **Ambiente Virtual:** `python -m venv venv && source venv/bin/activate` (ou `.\venv\Scripts\activate` no Windows)
4.  **PyTorch (CPU):** É crucial instalar a versão correta **antes** do `easyocr`. Visite [pytorch.org](https://pytorch.org/), selecione: Stable, seu OS, Pip, Python, **CPU**. Copie e execute o comando `pip install` fornecido pelo site.
5.  **Dependências:** `pip install -r requirements.txt`.
    *(Nota: Verifique se `requirements.txt` está atualizado. `easyocr` baixará modelos na primeira execução. `img2table` pode requerer `opencv-python-headless` - `pip install opencv-python-headless`).*

## 6. Configuração

* **Geral (`src/config.py`):** Ajuste constantes como `BASE_URL`, `MAX_PAGES`, `OUTPUT_DIR` (para imagens), `DATA_DIR` (para logs e tabelas), `SLEEP_*`, `IMAGE_EXTENSIONS`.
* **Análise (`src/analise_imagens.py`):** Ajuste constantes no topo do arquivo para otimização:
    * `MAX_IMAGE_DIM_FOR_OCR`: Limite para redimensionamento pré-OCR (use `None` para desabilitar).
    * `CROP_BOX_MAIN_TABLE`: Coordenadas relativas `(esq, topo, dir, fundo)` para corte pré-OCR (use `None` para desabilitar). Requer testes.
    * Parâmetros internos de `img2table.extract_tables()` (ex: `min_confidence`) podem ser ajustados dentro da função `processar_e_salvar_tabela_individual`.

## 7. Utilização

Execute os comandos a partir do **diretório raiz do projeto** com o `venv` ativado. Utilize `python -m` para garantir a correta resolução de pacotes.

* **Modo 1: Apenas Scraping** (Baixa/atualiza imagens em `data/images/`)
    ```bash
    python -m src.main
    ```

* **Modo 2: Scraping + Análise Completa** (Baixa/atualiza imagens, depois analisa todas e salva CSVs individuais em `data/tabelas_por_mes/`)
    ```bash
    python -m src.main --analyze
    # ou alias:
    python -m src.main -a
    ```

* **Modo 3: Apenas Análise** (Processa imagens existentes em `data/images/`, salva CSVs individuais em `data/tabelas_por_mes/`)
    * Análise paralela (padrão):
        ```bash
        python -m src.analise_imagens
        ```
    * Análise sequencial (1 worker, útil para debug):
        ```bash
        python -m src.analise_imagens -w 1
        ```
    * Análise de UMA imagem específica (ótimo para debug):
        ```bash
        python -m src.analise_imagens -i data/images/MM-YYYY/nome_da_imagem.jpg
        ```
        *(Substitua pelo caminho real)*
    * **Log Detalhado (DEBUG):** Adicione `-v` ou `--verbose` a qualquer comando `analise_imagens` ou `main`.

**Opções de Linha de Comando (`python -m src.main`):**

* `--start-page N`: Página inicial do scraping.
* `--max-pages N`: Número máximo de páginas a raspar.
* `--output-dir /path/`: Diretório de saída das **imagens**.
* `-v`, `--verbose`: Ativa log nível DEBUG.
* `-a`, `--analyze`: Executa a etapa de análise após o scraping (salva tabelas individuais).

## 8. Saída Gerada

* **Imagens:** `data/images/MM-YYYY/ppi-DD-MM-YYYY.jpg`
* **Tabelas Extraídas (CSV):** `data/tabelas_por_mes/MM-YYYY/ppi-DD-MM-YYYY_tabela.csv` (Cada arquivo contém a primeira tabela extraída da imagem correspondente, com cabeçalho tratado e usando `-` como separador).
* **Logs:**
    * `scraper.log`: Log geral (INFO ou DEBUG).
    * `data/error.log`: Log específico de erros (ERROR/CRITICAL).

## 9. Limitações e Pontos de Atenção

* **Dependência do Website:** A estrutura HTML do site da Abicom pode mudar, exigindo ajustes no scraper (`src/scrapers/abicom_scraper.py`). A lógica de detecção de imagens pode precisar de revisão.
* **Precisão OCR/Extração:** A qualidade da extração depende das imagens e das bibliotecas (`easyocr`/`img2table`). Requer experimentação com os parâmetros de pré-processamento e extração em `src/analise_imagens.py`.
* **Foco na Primeira Tabela:** Apenas a primeira tabela detectada por `img2table` é processada e salva.
* **Performance CPU:** OCR é intensivo. O tempo de análise pode ser considerável.
