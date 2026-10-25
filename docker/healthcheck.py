"""Usa a biblioteca padrão, sem instalar curl na imagem."""
from urllib.request import urlopen

with urlopen('http://127.0.0.1:8000/health/', timeout=3) as resposta:
    if resposta.status != 200:
        raise SystemExit(1)
