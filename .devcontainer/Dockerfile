FROM python:3.11-slim

# Evite interações com o pacman durante a instalação
ENV DEBIAN_FRONTEND=noninteractive

# Instale dependências e Chrome/ChromeDriver para Selenium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    git \
    curl \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Crie um usuário não-root para trabalhar no container
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Crie o usuário vscode
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Configure o ambiente Python
COPY requirements.txt /tmp/
RUN pip install --upgrade pip \
    && pip install -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Instale ferramentas de qualidade de código
RUN pip install black pylint pytest pytest-cov \
    && rm -rf /root/.cache/pip

# Configure o ambiente de trabalho
WORKDIR /workspace

# Mude para o usuário vscode
USER $USERNAME

# Configure o ambiente virtual Python (venv)
RUN python -m venv /home/$USERNAME/venv
ENV PATH="/home/$USERNAME/venv/bin:$PATH"