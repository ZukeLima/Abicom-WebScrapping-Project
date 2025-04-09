# Baixador e Renomeador de Imagens JPG (Exemplo: Abicom PPI)

Este script Python baixa imagens `.jpg` de páginas sequenciais de um site (ótimo para categorias ou arquivos paginados). Depois de baixar, ele procura por arquivos que tenham `de-YYYY-MM-DD-as` no nome e os renomeia para o formato `YYYY-MM-DD[_N].jpg`. Ele usa um ambiente virtual (`venv`) para manter as dependências organizadas.

---

## ✨ O que ele faz?

* Varre páginas sequenciais de um site (configurado para o padrão `/page/N/`).
* Encontra imagens (`<img>`) com links (`src`) terminando em `.jpg`.
* Transforma URLs relativas de imagens em absolutas.
* Baixa as imagens `.jpg` para uma pasta local que você define.
* Não baixa imagens repetidas (verifica se o arquivo já existe).
* Busca por `de-YYYY-MM-DD-as` no nome dos arquivos baixados.
* Extrai e valida a data (`YYYY-MM-DD`) encontrada no nome.
* Renomeia o arquivo para `YYYY-MM-DD.jpg` (ou `YYYY-MM-DD_N.jpg` se o nome já existir).
* Tem tratamento básico de erros (HTTP, Timeout, Arquivo) e pausas educadas (`time.sleep`) para não sobrecarregar o site.
* Mostra o progresso no terminal enquanto roda.

---

## 💻 Tecnologias

* **Linguagem:** Python 3
* **Ambiente:** `venv`
* **Bibliotecas:**
    * `requests`
    * `beautifulsoup4`
    * `os`
    * `urllib.parse`
    * `time`
    * `re`
    * `datetime`

---

## 📋 Pré-requisitos

Você vai precisar de:

* Python 3 (v3.6 ou mais recente).
* Pip (normalmente já vem com o Python).
* Git (para baixar o código).
* Acesso à internet.

---

## ⚙️ Instalação

Para instalar e configurar:

```bash
# 1. Baixe o código do GitHub:
git clone [https://github.com/ZukeLima/abicom_webscraping.git](https://github.com/ZukeLima/abicom_webscraping.git)

# 2. Entre na pasta que foi criada:
cd abicom_webscraping

# 3. Crie o ambiente virtual:
python -m venv venv

# 4. Ative o ambiente virtual:
#    Windows (cmd):      .\venv\Scripts\activate.bat
#    Windows (PowerShell): .\venv\Scripts\Activate.ps1
#      (Talvez precise rodar: Set-ExecutionPolicy Unrestricted -Scope Process)
#    Linux / macOS:      source venv/bin/activate

# 5. Instale as bibliotecas necessárias (já com o ambiente ativado):
pip install requests beautifulsoup4

# Pronto!