# Abicom Web Scraper & Image Analyzer

![Tenor GIF](https://c.tenor.com/OjVjDqcWaIoAAAAd/tenor.gif)

Este projeto combina duas funcionalidades principais:
1.  **Web Scraping:** Coleta imagens JPG da categoria PPI do site da Abicom de forma eficiente e organizada.
2.  **Análise de Imagens:** Processa as imagens baixadas para extrair metadados, propriedades da imagem, dados EXIF e **conteúdo textual usando OCR**, salvando os resultados em um arquivo CSV detalhado. A análise utiliza processamento paralelo para melhor performance.

**Desenvolvido por:** Lucas Lima <a href="https://www.linkedin.com/in/zukelima/" target="_blank" rel="noopener noreferrer"><img src="https://cdn-icons-png.flaticon.com/256/174/174857.png" alt="LinkedIn" width="24" height="24" style="vertical-align:middle;"></a>

---

## Funcionalidades

### Scraping (`src/main.py`)

* Varre páginas sequenciais da categoria PPI da Abicom (`/categoria/ppi/page/N/`).
* Extrai links para posts individuais de cada página de listagem.
* **Organiza as imagens por pastas mensais** (formato `MM-YYYY`) dentro de `data/images/` (configurável).
* Verifica de forma eficiente se uma imagem já foi baixada **antes** de acessar a página do post, evitando downloads repetidos e requisições desnecessárias.
* Acessa cada post relevante e extrai **apenas a primeira imagem JPG** encontrada no conteúdo principal.
* Ignora imagens em páginas de listagem e filtra elementos comuns de UI (ícones, logos, etc.).
* Nomeia as imagens usando o padrão `ppi-DD-MM-YYYY.jpg`, extraindo a data da URL do post sempre que possível.
* Implementa tratamento de erros HTTP e pausas (`time.sleep`) para não sobrecarregar o site.

### Análise de Imagens (`src/analise_imagens.py`, acionado por `main.py --analyze`)

* Analisa todos os arquivos `.jpg` e `.jpeg` no diretório de saída configurado.
* Utiliza **Processamento Paralelo** (`concurrent.futures`) para acelerar a análise, especialmente a etapa de OCR.
* Extrai um conjunto rico de informações para cada imagem:
    * **Metadados do Arquivo:** Caminho completo, nome do arquivo, pasta pai, tamanho em bytes.
    * **Datas Inferidas:** Data extraída do nome do arquivo, Mês/Ano extraídos da pasta pai (se aplicável).
    * **Propriedades da Imagem (via Pillow):** Largura (px), Altura (px), Modo de cor (ex: RGB), Formato (ex: JPEG).
    * **Dados EXIF:** Extrai **todos** os metadados EXIF disponíveis e os salva como uma string JSON na coluna `exif_data_json`.
    * **Conteúdo Textual (via EasyOCR):** Realiza OCR na imagem para extrair o texto visível. O texto bruto reconhecido é salvo na coluna `texto_easyocr`.
* Gera um **arquivo CSV detalhado** com todas as informações extraídas na pasta `data/`, nomeado com timestamp (ex: `analise_paralela_ocr_YYYYMMDD_HHMMSS.csv`).
* Exibe um resumo da análise no console após a conclusão.
* Pode ser executado de forma independente (`python src/analise_imagens.py`).

## Estrutura do Projeto

Abicom-WebScrapping-Project/
├── .devcontainer/     # (Opcional) Configuração VS Code + Docker
│   ├── devcontainer.json
│   └── Dockerfile
├── .vscode/           # (Opcional) Configurações VS Code
│   └── settings.json
├── src/               # Código fonte principal
│   ├── init.py
│   ├── config.py      # Configurações globais (URLs, pastas, etc.)
│   ├── main.py        # Ponto de entrada principal (Scraper + chamada da Análise)
│   ├── analise_imagens.py # Lógica de análise detalhada (Pillow, OCR, CSV)
│   ├── models/        # Modelos de dados (ex: Image)
│   ├── services/      # Serviços (HTTP Client, Image Service)
│   ├── scrapers/      # Scrapers (Base e AbicomScraper)
│   └── utils/         # Utilitários (URL, Arquivos)
├── data/              # Dados gerados
│   ├── images/        # Imagens baixadas (organizadas por mês, ex: 04-2025/)
│   └── *.csv          # CSVs gerados pela análise
├── requirements.txt   # Dependências Python do projeto
├── scraper.log        # Arquivo de log gerado pela execução
└── README.md          # Este arquivo


## Saída Gerada

* **Imagens:** Salvas em `data/images/MM-YYYY/ppi-DD-MM-YYYY.jpg`.
* **Relatório CSV:** Salvo em `data/analise_paralela_ocr_YYYYMMDD_HHMMSS.csv`. Contém colunas como:
    * `nome_arquivo`, `pasta_pai`, `data_extraida_arquivo`, `mes_pasta`, `ano_pasta`
    * `tamanho_bytes`, `largura_px`, `altura_px`, `modo_cor`, `formato_imagem`
    * `texto_easyocr` (texto completo extraído via OCR)
    * `exif_data_json` (string JSON com todos os dados EXIF encontrados)
    * `erro_processamento` (indica se houve erro ao processar a imagem específica)
    * `caminho_completo`

## Requisitos

* Python 3.8+
* Pip (gerenciador de pacotes Python)
* Bibliotecas Python listadas em `requirements.txt`. Chave incluem:
    * `requests`
    * `beautifulsoup4`
    * `pandas`
    * `Pillow` (para manipulação de imagem e EXIF)
    * `numpy`
    * `easyocr` (para OCR)
    * `torch`, `torchvision`, `torchaudio` (dependências do `easyocr`)
* **Importante (EasyOCR):** Na primeira vez que a análise com OCR for executada, a biblioteca `easyocr` pode precisar baixar modelos de linguagem da internet (ex: para português e inglês). Permita a conexão se solicitado.

*Opcional:*
* Docker
* VS Code com extensão Remote - Containers (para usar o ambiente pré-configurado em `.devcontainer/`)

## Configuração do Ambiente (venv)

1.  Clone este repositório:
    ```bash
    git clone <URL_DO_REPOSITORIO>
    cd Abicom-WebScrapping-Project
    ```
2.  Crie um ambiente virtual:
    ```bash
    python -m venv venv
    ```
3.  Ative o ambiente virtual:
    * Windows (cmd/powershell): `.\venv\Scripts\activate`
    * Linux / macOS: `source venv/bin/activate`
4.  Instale as dependências:
    ```bash
    pip install -r requirements.txt
    ```

*(Alternativa: Se usar VS Code com a extensão Remote-Containers, abra a pasta do projeto e selecione "Reabrir no Container" para configurar o ambiente automaticamente via Docker).*

## Uso

**Importante:** Execute os comandos a partir do diretório raiz do projeto (`Abicom-WebScrapping-Project`).

1.  **Executar Apenas o Scraper:**
    ```bash
    python -m src.main [opções]
    ```
    Isso baixará as imagens para `data/images/` conforme as configurações.

2.  **Executar o Scraper e DEPOIS a Análise Completa (com OCR):**
    ```bash
    python -m src.main --analyze [opções]
    ```
    Após o scraper terminar (ou ser interrompido), a análise será iniciada automaticamente. Um arquivo CSV será gerado em `data/`.

3.  **Executar Apenas a Análise Completa (com OCR) em imagens já baixadas:**
    ```bash
    python src/analise_imagens.py
    ```
    Isso analisará as imagens no diretório configurado em `src/config.py` (ou o padrão `data/images/`) e gerará o CSV em `data/`.

**Opções de Linha de Comando para `src/main.py`:**

* `--start-page N`: Define a página inicial do scraping (padrão: 1).
* `--max-pages N`: Define o número máximo de páginas a processar (padrão do `config.py`).
* `--output-dir /caminho/para/pasta`: Especifica o diretório de saída para as *imagens* (padrão do `config.py`). O CSV da análise será salvo no diretório *pai* deste.
* `--verbose`: Habilita logs mais detalhados no console e no `scraper.log`.
* `--analyze`: Ativa a execução da análise detalhada (com OCR) após o scraping.

## Configurações

Ajustes podem ser feitos no arquivo `src/config.py`:

* `BASE_URL`: URL da categoria a ser raspada.
* `OUTPUT_DIR`: Diretório base onde a pasta `images` será criada.
* `ORGANIZE_BY_MONTH`: `True` (padrão) para criar subpastas `MM-YYYY` dentro de `images`, `False` para salvar tudo direto em `images`.
* `MAX_PAGES`: Número padrão de páginas a processar se não especificado na linha de comando.
* `SLEEP_BETWEEN_REQUESTS`, `SLEEP_BETWEEN_PAGES`: Pausas para evitar sobrecarga no servidor.
* *(Avançado):* Idiomas do EasyOCR (`['pt', 'en']`) poderiam ser movidos para cá.

## Notas e Limitações

* **Performance do OCR:** A análise com OCR é intensiva em CPU e memória. O uso de paralelismo acelera o processo em máquinas multi-core, mas ainda pode levar tempo para analisar um grande número de imagens.
* **Precisão do OCR:** A qualidade do texto extraído depende da resolução e clareza da imagem original.
* **Parsing do Texto OCR:** O script salva o texto *bruto* extraído pelo OCR. Para extrair valores específicos das tabelas contidas nesse texto, é necessária lógica adicional de parsing (ex: usando Expressões Regulares ou bibliotecas de análise de tabelas mais avançadas) a ser aplicada sobre a coluna `texto_easyocr` do CSV gerado.
* **Ética e Termos de Uso:** Sempre verifique o arquivo `robots.txt