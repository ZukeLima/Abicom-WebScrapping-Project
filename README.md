# Abicom Web Scraper

Este projeto realiza web scraping no site da Abicom para coletar imagens JPG da categoria PPI.

## Funcionalidades

- Varre páginas sequenciais do site usando o formato correto de paginação (`/categoria/ppi/page/N/`).
- Extrai links para posts individuais de cada página de listagem.
- **Organiza as imagens por pastas mensais (formato MM-YYYY)** para facilitar a gestão.
- Verifica de forma eficiente se uma imagem já foi baixada **antes** de acessar a página do post.
- Acessa cada post individualmente e extrai APENAS a primeira imagem JPG de cada post.
- Ignora imagens em páginas de listagem, focando apenas em imagens dentro de posts individuais.
- Filtra imagens que parecem ser elementos de UI (ícones, logos, etc.).
- Nomeia as imagens usando o padrão `ppi-DD-MM-YYYY.jpg` extraído do nome da página/post.
- Se o padrão de data não for encontrado no URL, usa o nome do post ou página como identificador.
- Evita o download de imagens repetidas.
- Rastreia URLs já visitadas para evitar processamento duplicado.
- Gera relatórios de downloads por mês.
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

## Configurações

O scraper possui algumas configurações que podem ser ajustadas no arquivo `src/config.py`:

- `ORGANIZE_BY_MONTH`: Se `True` (padrão), organiza as imagens em pastas mensais. Se `False`, salva todas as imagens no diretório raiz.
- `MAX_PAGES`: Número máximo de páginas a processar.
- `SLEEP_BETWEEN_REQUESTS`: Tempo de espera entre requisições (em segundos).
- `SLEEP_BETWEEN_PAGES`: Tempo de espera entre páginas (em segundos).
- `OUTPUT_DIR`: Diretório de saída para as imagens.

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

## Estrutura de Arquivos

O scraper salva as imagens em uma estrutura de diretórios organizada por mês:

```
data/images/
├── 04-2025/         # Pasta para abril de 2025
│   ├── ppi-01-04-2025.jpg
│   ├── ppi-02-04-2025.jpg
│   └── ...
├── 03-2025/         # Pasta para março de 2025
│   ├── ppi-28-03-2025.jpg
│   ├── ppi-30-03-2025.jpg
│   └── ...
└── ...              # Uma pasta para cada mês
```

Essa organização facilita o gerenciamento de grandes volumes de imagens ao longo do tempo.

## Otimizações de Desempenho

O scraper inclui várias otimizações para melhorar a velocidade e eficiência:

1. **Pré-verificação de downloads**: Verifica se uma imagem já foi baixada antes mesmo de acessar a página do post, economizando requisições HTTP.

2. **Indexação inicial**: Ao iniciar, o script faz uma varredura das pastas existentes para criar um índice das imagens já baixadas.

3. **Agrupamento por mês**: Organiza as imagens em pastas mensais, o que não só facilita a organização, mas também melhora a performance de verificação.

4. **Cache de informações**: Mantém um cache de URLs já processadas e resultados de extração de data para evitar operações redundantes.

5. **Relatórios por mês**: Gera relatórios agrupados por mês, facilitando o acompanhamento do progresso.

## Logs

O scraper registra informações detalhadas sobre sua operação em:

- Saída padrão (console)
- Arquivo `scraper.log` no diretório raiz

## Notas

- O scraper foi projetado para ser educado com o servidor, incluindo pausas entre requisições
- Ao executar novamente, o scraper evita baixar imagens que já foram obtidas
- As imagens são salvas com o formato de data do dia atual