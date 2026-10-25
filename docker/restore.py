"""Restauração offline. Execute somente depois de `docker compose stop app`."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import sqlite3
import tempfile


def conectar_leitura(caminho):
    return sqlite3.connect(caminho.resolve().as_uri() + '?mode=ro', uri=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backup', type=Path, help='Caminho do backup dentro do container')
    args = parser.parse_args()
    origem = args.backup.resolve()
    destino = Path(os.environ.get('SQLITE_PATH', '/data/biblioteca.sqlite3')).resolve()
    if not origem.is_file() or origem == destino:
        parser.error('Selecione um arquivo de backup existente, diferente do banco ativo.')
    # Um backup online bem-sucedido produz um arquivo autocontido, sem WAL pendente.
    if Path(str(destino) + '-wal').exists() or Path(str(destino) + '-shm').exists():
        parser.error('Há arquivos WAL/SHM do banco ativo. Inicie e pare a aplicação normalmente antes de restaurar; não apague esses arquivos manualmente.')
    with conectar_leitura(origem) as fonte:
        if fonte.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            parser.error('O backup não passou na verificação de integridade.')
        tabelas = {r[0] for r in fonte.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'django_migrations', 'acervo_livro', 'auth_user'} <= tabelas:
            parser.error('O arquivo não é um backup compatível do BibliotecaPI.')
        pasta = Path(os.environ.get('BACKUP_DIR', '/data/backups'))
        pasta.mkdir(parents=True, exist_ok=True)
        if destino.exists():
            anterior = pasta / f'antes-restauracao-{datetime.now():%Y%m%d-%H%M%S-%f}.sqlite3'
            with conectar_leitura(destino) as atual, sqlite3.connect(anterior) as copia:
                atual.backup(copia)
            anterior.chmod(0o600)
            print(f'Cópia de segurança do banco anterior: {anterior}')
        with tempfile.NamedTemporaryFile(dir=destino.parent, suffix='.sqlite3', delete=False) as arquivo:
            temporario = Path(arquivo.name)
        try:
            with sqlite3.connect(temporario) as novo:
                fonte.backup(novo)
                novo.execute('PRAGMA journal_mode=DELETE')
            os.replace(temporario, destino)
            destino.chmod(0o600)
        finally:
            temporario.unlink(missing_ok=True)
    print('Backup restaurado. Inicie a aplicação com docker compose up -d.')


if __name__ == '__main__':
    main()
