# Abicom Web Scraper

Este projeto realiza web scraping no site da Abicom para coletar imagens JPG da categoria PPI.

## Funcionalidades

- Varre páginas sequenciais do site usando o formato correto de paginação (`/categoria/ppi/page/N/`).
- Extrai links para posts individuais de cada página de listagem.
- **Acessa cada post individualmente e extrai APENAS a primeira imagem JPG de cada post**.
- Ignora imagens em páginas de listagem, focando apenas em imagens dentro de posts individuais.
- Filtra imagens que parecem ser elementos de UI (ícones, logos, etc.).
- Nomeia as imagens usando o padrão `ppi-DD-MM-YYYY.jpg` extraído do nome da página/post.
- Se o padrão de data não for encontrado no URL, usa o nome do post ou página como identificador.
- Evita o download de imagens repetidas.
- Rastreia URLs já visitadas para evitar processamento duplicado.
- Implementa tratamento de erros para falhas de HTTP, timeout e problemas de arquivo.
- Utiliza pausas (`time.sleep`) para não sobrecarregar o site.

## Estrutura do Projeto

```
abicom-scraper/
├── .devcontainer/     # Configuração do VS Code + Docker
│   ├── devcontainer.json
│   └── Dockerfile
├── .vscode/           # Configurações do VS Code
│   └── settings.json
├── src/
│   ├── config.py      # Configurações globais
│   ├── main.py        # Ponto de entrada
│   ├── models/        # Modelos de dados
│   ├── services/      # Serviços (HTTP, download, etc.)
│   ├── utils/         # Utilitários
│   └── scrapers/      # Implementações de scrapers
├── data/images/       # Pasta para imagens baixadas (criada automaticamente)
├── requirements.txt   # Dependências do projeto
└── README.md          # Este arquivo
```

## Requisitos

- Docker
- VS Code com extensão Remote - Containers
- ou Python 3.8+ com pip

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

Para executar o scraper com configurações padrão:

```bash
python src/main.py
```

### Opções de linha de comando

```bash
python src/main.py --start-page 1 --max-pages 10 --output-dir ./data/images --verbose
```

- `--start-page`: Página inicial para o scraping (padrão: 1)
- `--max-pages`: Número máximo de páginas para processar (padrão: 10)
- `--output-dir`: Diretório de saída para as imagens (padrão: ./data/images)
- `--verbose`: Habilita logging detalhado

## Arquitetura do Projeto

O projeto segue os princípios SOLID:

1. **Single Responsibility Principle**: Cada classe tem uma única responsabilidade.
   - `HttpClient`: Gerencia requisições HTTP
   - `ImageService`: Gerencia operações relacionadas a imagens
   - `BaseScraper`: Define o fluxo genérico de scraping

2. **Open/Closed Principle**: As classes são abertas para extensão, fechadas para modificação.
   - `BaseScraper` é uma classe abstrata que pode ser estendida para diferentes sites
   - `AbicomScraper` estende `BaseScraper` para o site específico

3. **Liskov Substitution Principle**: Objetos de uma superclasse podem ser substituídos por objetos de subclasses.
   - `AbicomScraper` pode ser usado onde `BaseScraper` é esperado

4. **Interface Segregation Principle**: Interfaces específicas para diferentes necessidades.
   - Cada serviço expõe apenas os métodos necessários para sua função

5. **Dependency Inversion Principle**: Dependências de alto nível não dependem de implementações de baixo nível.
   - Injeção de dependência é usada extensivamente (ex: `HttpClient`, `ImageService`)

## Logs

O scraper registra informações detalhadas sobre sua operação em:

- Saída padrão (console)
- Arquivo `scraper.log` no diretório raiz

## Notas

- O scraper foi projetado para ser educado com o servidor, incluindo pausas entre requisições
- Ao executar novamente, o scraper evita baixar imagens que já foram obtidas
- As imagens são salvas com o formato de data do dia atual