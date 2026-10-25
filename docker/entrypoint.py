"""Inicializa o volume, aplica migrations versionadas e entrega o processo ao servidor."""
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys


def main():
    banco = Path(os.environ.get('SQLITE_PATH', '/data/biblioteca.sqlite3'))
    banco.parent.mkdir(parents=True, exist_ok=True)
    banco_existente = banco.exists() and banco.stat().st_size > 0
    os.umask(0o077)
    if not os.environ.get('DJANGO_SECRET_KEY'):
        caminho = Path(os.environ.get('DJANGO_SECRET_KEY_FILE', '/data/secret_key'))
        caminho.parent.mkdir(parents=True, exist_ok=True)
        if not caminho.exists():
            # O segredo é exclusivo desta instalação e persiste junto ao banco.
            with caminho.open('x', encoding='utf-8') as arquivo:
                arquivo.write(secrets.token_urlsafe(64))
        if len(caminho.read_text().strip()) < 50:
            raise RuntimeError('Arquivo de chave inválido. Restaure a chave da instalação.')
    Path(os.environ.get('BACKUP_DIR', '/data/backups')).mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(banco, timeout=30) as conexao:
        conexao.execute('PRAGMA journal_mode=WAL')
    if banco_existente:
        pendentes = subprocess.run([sys.executable, 'manage.py', 'migrate', '--check'], check=False)
        if pendentes.returncode == 1:
            subprocess.run([sys.executable, 'manage.py', 'backup_biblioteca'], check=True)
        elif pendentes.returncode:
            raise RuntimeError('Não foi possível verificar as migrations do banco.')
    subprocess.run([sys.executable, 'manage.py', 'migrate', '--noinput'], check=True)
    if len(sys.argv) < 2:
        raise RuntimeError('Informe o comando do servidor.')
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == '__main__':
    main()
