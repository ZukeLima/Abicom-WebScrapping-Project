# Abicom Web Scraper

Este projeto realiza web scraping no site da Abicom para coletar dados da categoria PPI.

## Estrutura do Projeto

```
abicom-scraper/
├── .devcontainer/     # Configuração do VS Code + Docker
├── .vscode/           # Configurações do VS Code
├── src/               # Código-fonte do projeto
├── data/              # Dados extraídos (criado automaticamente)
├── requirements.txt   # Dependências do projeto
└── README.md          # Este arquivo
```

## Requisitos

- Docker
- VS Code com extensão Remote - Containers

## Configuração do Ambiente

### Usando VS Code + Docker (recomendado)

1. Instale o Docker na sua máquina.
2. Instale o VS Code.
3. Instale a extensão "Remote - Containers" no VS Code.
4. Clone este repositório.
5. Abra o projeto no VS Code.
6. Quando solicitado, clique em "Reabrir no Container" ou use o comando `Remote-Containers: Reopen in Container`.
7. Aguarde o ambiente ser configurado automaticamente.

### Usando venv (sem Docker)

Se preferir não usar Docker, você pode configurar um ambiente virtual Python:

```bash
# Criar o ambiente virtual
python -m venv venv

# Ativar o ambiente virtual (Windows)
venv\Scripts\activate

# Ativar o ambiente virtual (Linux/Mac)
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
```

## Uso

Para executar o scraper:

```bash
# Dentro do container Docker ou com venv ativo
python src/scraper.py
```

Por padrão, o script irá:
1. Acessar até 3 páginas da categoria PPI da Abicom
2. Extrair os links dos artigos encontrados
3. Acessar cada artigo para extrair seus dados
4. Salvar os resultados em um arquivo CSV na pasta `data/`

## Personalização

Você pode modificar o comportamento do scraper editando os parâmetros no arquivo `src/scraper.py`:

- Altere `max_pages` para processar mais ou menos páginas
- Modifique a classe `AbicomScraper` para extrair diferentes informações

## Notas

- O scraper inclui pausas (sleeps) entre requisições para evitar sobrecarga no servidor
- Os dados são salvos em formato CSV com timestamp para evitar sobrescrever arquivos anteriores
- Use este scraper de forma responsável e em conformidade com os termos de uso do site alvo