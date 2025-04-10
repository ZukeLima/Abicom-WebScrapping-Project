# Abicom Web Scraper & Advanced Image Analyzer

![Demonstração](https://c.tenor.com/OjVjDqcWaIoAAAAd/tenor.gif)

## Visão Geral

Este projeto automatiza completamente o processo de coleta e extração de dados de relatórios diários de Preço de Paridade de Importação (PPI) de combustíveis, publicados como imagens pela Abicom em seu site (`https://abicom.com.br/categoria/ppi/`). Ele supera os desafios da extração manual, transformando dados visuais complexos em informações estruturadas e prontas para análise.

O pipeline consiste em duas etapas principais:
1.  **Web Scraping:** Coleta eficiente das imagens de relatório do site.
2.  **Análise de Imagem Avançada:** Processamento paralelo das imagens para extrair metadados, propriedades e, crucialmente, dados tabulares específicos usando OCR e análise de layout.

**Desenvolvido por:** Zuke Lima <a href="https://www.linkedin.com/in/zukelima/" target="_blank" rel="noopener noreferrer"><img src="https://cdn-icons-png.flaticon.com/256/174/174857.png" alt="LinkedIn" width="24" height="24" style="vertical-align:middle;"></a>

---

## ✨ Funcionalidades Principais

### Web Scraping (`src/main.py` & Módulos)

* **Coleta Focada:** Navega pela paginação da categoria PPI da Abicom, identificando e baixando apenas a imagem de relatório principal (`.jpg`/`.jpeg`) de cada post diário.
* **Eficiência:** Utiliza um `ImageService` que pré-indexa arquivos já baixados para **evitar downloads duplicados**, economizando tempo e banda.
* **Organização:** Salva as imagens em uma estrutura lógica de pastas por mês e ano (`data/images/MM-YYYY`) com nomes padronizados (`ppi-DD-MM-YYYY.jpg`).
* **Robustez:** Emprega um `HttpClient` customizado com `requests.Session`, retentativas automáticas para erros de rede/timeout e headers apropriados.
* **Cortesia:** Inclui pausas configuráveis (`time.sleep`) entre requisições para não sobrecarregar o servidor da Abicom.

### Análise Avançada de Imagens (`src/analise_imagens.py`)

* **Processamento Paralelo:** Usa `concurrent.futures.ProcessPoolExecutor` para analisar múltiplas imagens simultaneamente, otimizando drasticamente o tempo de execução em máquinas multi-core.
* **Extração de Metadados e Propriedades:** Utiliza `Pillow` para obter dimensões, modo de cor, formato da imagem e extrair dados EXIF (salvos como JSON na coluna `exif_data_json`).
* **Extração de Tabelas com IA (OCR + Layout):** Integra a biblioteca `img2table` com o motor OCR `easyocr` (configurado para pt/en) para **detectar e reconstruir as tabelas** presentes nas imagens, mesmo aquelas sem bordas explícitas.
* **Extração de Valores Específicos:** **Ponto chave do projeto:** Após o `img2table` gerar um DataFrame para cada tabela encontrada, uma lógica customizada (`find_indices_in_table`) analisa o *conteúdo* desse DataFrame para localizar células específicas (cruzando localidade, tipo de combustível e métrica) e extrai os **valores numéricos correspondentes** (preços, defasagens R$, defasagens %).
* **Limpeza de Dados:** Inclui uma função (`clean_numeric_value`) para tratar os valores extraídos, removendo caracteres não numéricos (R$, %), convertendo vírgulas decimais para pontos e garantindo um formato numérico consistente (float).
* **Relatório CSV Estruturado:** Consolida todos os dados (metadados do arquivo, propriedades da imagem, EXIF JSON e **os valores numéricos específicos extraídos**) em um DataFrame `pandas` e o salva em um arquivo CSV timestamped (ex: `data/analise_valores_extraidos_YYYYMMDD_HHMMSS.csv`), pronto para análise direta.

## 🛠️ Tecnologias Utilizadas

* **Linguagem:** Python 3.8+
* **Web Scraping:** `requests`, `beautifulsoup4`
* **Processamento de Imagem:** `Pillow`
* **OCR:** `easyocr`
* **Extração de Tabelas:** `img2table`
* **Manipulação de Dados:** `pandas`, `numpy`
* **Paralelismo:** `concurrent.futures`
* **Dependências AI:** `torch`, `torchvision`, `torchaudio` (para EasyOCR)
* **Utilitários:** `logging`, `argparse`, `json`, `re`, `datetime`
* **Ambiente:** `venv` (recomendado), Docker (opcional)
* **Dependências Adicionais (prováveis):** `opencv-python-headless` (usado por `img2table`)

## 🏗️ Estrutura do Projeto

```text
Abicom-WebScrapping-Project/
+-- .devcontainer/          # (Opcional) Configuração VS Code + Docker
|   +-- devcontainer.json
|   +-- Dockerfile
+-- .vscode/                # (Opcional) Configurações VS Code
|   +-- settings.json
+-- src/                    # Código fonte principal
|   +-- __init__.py
|   +-- config.py           # Configurações globais
|   +-- main.py             # Ponto de entrada (Scraper + chamada da Análise)
|   +-- analise_imagens.py  # Lógica de análise (Pillow, OCR, Tabela, Valores, CSV)
|   +-- models/             # Modelos de dados
|   |   +-- __init__.py
|   |   +-- image.py
|   +-- services/           # Serviços
|   |   +-- __init__.py
|   |   +-- http_client.py
|   |   +-- image_service.py
|   +-- scrapers/           # Scrapers
|   |   +-- __init__.py
|   |   +-- base_scraper.py
|   |   +-- abicom_scraper.py
|   +-- utils/              # Utilitários
|       +-- __init__.py
|       +-- file_utils.py
|       +-- url_utils.py
+-- data/                   # Dados gerados
|   +-- images/             # Imagens baixadas (ex: 04-2025/...)
|   +-- *.csv               # CSVs da análise
+-- requirements.txt        # Dependências Python
+-- scraper.log             # Log da execução
+-- README.md               # Este arquivo

```

## ⚙️ Instalação e Configuração

1.  **Clone o Repositório:**
    ```bash
    git clone <URL_DO_SEU_REPOSITORIO>
    cd Abicom-WebScrapping-Project
    ```
2.  **Crie e Ative um Ambiente Virtual:**
    ```bash
    python -m venv venv
    # Windows: .\venv\Scripts\activate
    # Linux/macOS: source venv/bin/activate
    ```
3.  **Instale as Dependências:**
    ```bash
    pip install -r requirements.txt
    ```
    *Nota:* `easyocr` pode precisar baixar modelos de linguagem na primeira execução da análise. Certifique-se de ter conexão com a internet. `img2table` pode requerer `opencv-python-headless`.

4.  **(Opcional) Configure `src/config.py`:** Ajuste `OUTPUT_DIR`, `MAX_PAGES`, etc., se necessário.

## 🚀 Como Usar

**Execute os comandos a partir da pasta raiz do projeto (`Abicom-WebScrapping-Project`).**

1.  **Apenas Baixar/Atualizar Imagens:**
    ```bash
    python -m src.main
    ```
    As imagens serão salvas em `data/images/`.

2.  **Baixar/Atualizar Imagens E Executar Análise Completa:**
    ```bash
    python -m src.main --analyze
    ```
    Após o scraping, a análise será executada. O CSV final (`analise_valores_extraidos_...csv`) será salvo em `data/`.

3.  **Executar Apenas a Análise (em imagens já baixadas):**
    ```bash
    python src/analise_imagens.py
    ```
    Analisará as imagens em `data/images/` (ou conforme `config.py`) e gerará o CSV em `data/`.

**Opções de Linha de Comando (`src/main.py`):**

* `--start-page N`: Define a página inicial do scraping.
* `--max-pages N`: Define o número máximo de páginas a processar.
* `--output-dir /path/to/images`: Especifica o diretório para salvar imagens (o CSV vai para o diretório pai).
* `--verbose`: Ativa logs mais detalhados (nível DEBUG).
* `--analyze`: Executa a análise completa (com OCR/extração de valores) após o scraping.

## ⚠️ Notas Importantes e Limitações

* **Dependência da Estrutura do Site:** O scraper depende da estrutura HTML atual da Abicom. Mudanças no site podem quebrá-lo.
* **Qualidade do OCR/Tabela:** A precisão da extração de tabelas (`img2table`) e do OCR (`easyocr`) depende da qualidade e consistência das imagens originais.
* **Lógica de Extração de Valores (`find_indices_in_table`):** Esta função em `analise_imagens.py` é **crucial** e **altamente dependente** do layout da tabela retornado pelo `img2table`. **É muito provável que você precise inspecionar o DataFrame extraído (adicionando prints temporários) e ajustar essa lógica** para garantir que os valores corretos sejam localizados e extraídos de forma confiável para todas as variações de imagem.
* **Performance:** A análise com OCR é intensiva. O paralelismo acelera, mas processar milhares de imagens ainda levará tempo considerável.
* **Ética:** Use com responsabilidade. Respeite os Termos de Serviço do site e evite sobrecarregá-lo (mantenha as pausas configuradas).