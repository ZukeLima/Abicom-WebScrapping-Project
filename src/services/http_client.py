"""
Cliente HTTP com tratamento de erros e retentativas.
"""
import os
import time
import logging
from typing import Dict, Optional, Union, Any
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError
from src.config import REQUEST_TIMEOUT, RETRY_COUNT, RETRY_DELAY, USER_AGENT

logger = logging.getLogger(__name__)

class HttpClient:
    """
    Cliente HTTP com tratamento de erros e retentativas.
    """
    
    def __init__(self, 
                timeout: int = REQUEST_TIMEOUT, 
                retry_count: int = RETRY_COUNT, 
                retry_delay: int = RETRY_DELAY):
        """
        Inicializa o cliente HTTP.
        
        Args:
            timeout: Tempo limite para requisições em segundos
            retry_count: Número de tentativas em caso de falha
            retry_delay: Tempo de espera entre tentativas em segundos
        """
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        
        # Headers padrão para requisições
        self.default_headers = {
            "User-Agent": USER_AGENT,
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
        }
        
        # Sessão para reutilização de conexões
        self.session = requests.Session()
        
    def get(self, url: str, 
           headers: Optional[Dict[str, str]] = None, 
           params: Optional[Dict[str, str]] = None,
           stream: bool = False) -> Optional[requests.Response]:
        """
        Realiza uma requisição GET com tratamento de erros e retentativas.
        
        Args:
            url: URL para a requisição
            headers: Headers adicionais para a requisição
            params: Parâmetros para a URL
            stream: Se True, o conteúdo será baixado sob demanda
            
        Returns:
            Response: Objeto de resposta ou None em caso de falha
        """
        # Combina os headers padrão com os headers adicionais
        request_headers = {**self.default_headers}
        if headers:
            request_headers.update(headers)
            
        for attempt in range(1, self.retry_count + 1):
            try:
                logger.debug(f"GET {url} (tentativa {attempt}/{self.retry_count})")
                
                response = self.session.get(
                    url,
                    headers=request_headers,
                    params=params,
                    timeout=self.timeout,
                    stream=stream
                )
                
                # Verifica se a resposta foi bem-sucedida
                response.raise_for_status()
                
                return response
                
            except Timeout as e:
                logger.warning(f"Timeout ao acessar {url}: {e}")
            except ConnectionError as e:
                logger.warning(f"Erro de conexão ao acessar {url}: {e}")
            except RequestException as e:
                # Captura códigos de status HTTP de erro
                if hasattr(e, 'response') and e.response is not None:
                    status_code = e.response.status_code
                    logger.warning(f"Erro HTTP {status_code} ao acessar {url}")
                else:
                    logger.warning(f"Erro ao acessar {url}: {e}")
            
            # Se não for a última tentativa, aguarda antes de tentar novamente
            if attempt < self.retry_count:
                delay = self.retry_delay * attempt  # Aumento gradual do tempo de espera
                logger.debug(f"Aguardando {delay}s antes da próxima tentativa")
                time.sleep(delay)
            
        logger.error(f"Falha após {self.retry_count} tentativas: {url}")
        return None
        
    def download_file(self, url: str, 
                     output_path: str,
                     chunk_size: int = 8192,
                     headers: Optional[Dict[str, str]] = None) -> bool:
        """
        Baixa um arquivo de uma URL para um caminho local.
        
        Args:
            url: URL do arquivo
            output_path: Caminho local onde o arquivo será salvo
            chunk_size: Tamanho dos chunks para download
            headers: Headers adicionais para a requisição
            
        Returns:
            bool: True se o download for bem-sucedido, False caso contrário
        """
        response = self.get(url, headers=headers, stream=True)
        
        if response is None:
            return False
            
        try:
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:  # Filtra keep-alive chunks
                        f.write(chunk)
            
            logger.info(f"Arquivo baixado com sucesso: {output_path}")
            return True
            
        except IOError as e:
            logger.error(f"Erro ao salvar arquivo {output_path}: {e}")
            # Tenta remover o arquivo parcialmente baixado
            try:
                if os.path.exists(output_path):
                    os.remove(output_path)
            except IOError:
                pass
            return False
            
    def close(self):
        """
        Fecha a sessão HTTP.
        """
        self.session.close()
        
    def __enter__(self):
        """
        Suporte para uso com 'with'.
        """
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Fecha a sessão ao sair do bloco 'with'.
        """
        self.close()