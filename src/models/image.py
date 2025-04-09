"""
Modelo de dados para imagens.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Image:
    """
    Representa uma imagem obtida do scraping.
    """
    url: str
    source_url: str  # URL da página onde a imagem foi encontrada
    file_extension: str
    found_date: datetime = datetime.now()
    saved_path: Optional[str] = None
    
    @property
    def is_saved(self) -> bool:
        """Verifica se a imagem foi salva localmente."""
        return self.saved_path is not None
    
    @property
    def filename(self) -> str:
        """Extrai o nome do arquivo da URL."""
        parts = self.url.split('/')
        return parts[-1] if parts else ""
    
    def __str__(self) -> str:
        """Representação em string da imagem."""
        return f"Image(url={self.url}, source={self.source_url})"
    
    def __hash__(self) -> int:
        """Implementação de hash para permitir uso em conjuntos."""
        return hash(self.url)
    
    def __eq__(self, other) -> bool:
        """Implementação de comparação para permitir uso em conjuntos."""
        if not isinstance(other, Image):
            return False
        return self.url == other.url