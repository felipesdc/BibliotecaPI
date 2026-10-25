# Docker Desktop e SQLite

A aplicação roda em um único container Linux, sem serviço externo de banco. Docker Desktop é o único requisito da máquina; o primeiro build precisa de internet.

## Arquitetura

| Componente | Configuração |
| --- | --- |
| Aplicação | Python 3.12 + Django 5.2 + Gunicorn, um worker e duas threads |
| Banco | SQLite em `/data/biblioteca.sqlite3`, modo WAL e timeout de 30 segundos |
| Persistência | Volume `bibliotecapi_biblioteca_dados`, montado em `/data` |
| Sessões | Chave exclusiva em `/data/secret_key`, gerada automaticamente, nunca incluída na imagem |
| Estáticos | Coletados durante o build, servidos pelo WhiteNoise |
| Usuário | Processo sem root, UID/GID 10001 |
| Escrita | Raiz do container somente leitura; `/data` persistente e `/tmp` temporário |
| Saúde | `GET /health/`, com verificação da conexão com o banco |
| Exposição | `127.0.0.1:8000`; somente o próprio computador |
| Logs | Saída padrão com rotação: até três arquivos de 10 MB |

O arquivo inteiro do banco, o WAL e o SHM ficam no mesmo volume local. Essa organização segue o [ciclo de vida de volumes do Docker](https://docs.docker.com/engine/storage/volumes/). Não coloque esse banco em pasta compartilhada de rede: o [SQLite WAL exige acesso local ao mesmo host](https://sqlite.org/wal.html).

Esta configuração é para uma única instância da aplicação. SQLite serializa escritas; o timeout e o modo IMMEDIATE reduzem disputas, mas não tornam as gravações paralelas ilimitadas. Não aumente réplicas para escalar este piloto.

## Primeira execução

Na raiz do projeto:

```sh
docker compose up -d --build --wait
docker compose exec app python manage.py preparar_biblioteca --se-vazio
```

Escolha nome e senha; depois acesse http://localhost:8000. Não há conta nem senha padrão. Os comandos não importam o banco SQLite antigo e não migram dados de PostgreSQL.

O início do container gera a chave se necessário, habilita WAL, aplica apenas migrations versionadas e inicia Gunicorn. Em atualizações com migrations pendentes sobre um banco existente, cria antes um backup em `/data/backups`. Não executa `makemigrations` automaticamente.

Para outra porta, crie um `.env` **na raiz**, ao lado do Compose, com `BIBLIOTECA_PORT=8080`, e recrie com `docker compose up -d --wait`. Acesse então http://localhost:8080. Esse `.env` é de interpolação do Compose; `bibliotecapi/.env` é a alternativa de desenvolvimento sem Docker e não entra na imagem.

## Operação e atualização

```sh
docker compose ps
docker compose logs --tail=100 app
docker compose stop
docker compose up -d --wait
```

Para aplicar uma versão nova do código:

```sh
docker compose exec app python manage.py backup_biblioteca
docker compose up -d --build --wait
```

Reinícios e recriações preservam banco e chave. Apagar volumes no Docker Desktop, executar `down -v` ou remover os dados do Docker Desktop apaga essa persistência. Mantenha uma cópia dos backups fora do Docker.

## Backup

```sh
docker compose exec app python manage.py backup_biblioteca
docker compose cp app:/data/backups ./backups
```

O primeiro comando informa o nome do arquivo criado e usa a API de backup do SQLite, que produz uma cópia consistente mesmo com a aplicação em uso. O segundo copia os backups para a máquina. Se `./backups` já existir, o Docker pode criar uma subpasta `backups` dentro dela; para evitar ambiguidade, copie um arquivo específico:

```sh
docker compose cp app:/data/backups/NOME-DO-ARQUIVO.sqlite3 ./NOME-DO-ARQUIVO.sqlite3
```

Substitua `NOME-DO-ARQUIVO.sqlite3` pelo nome informado pelo comando. O backup inclui acervo, leitores, usuários e histórico, portanto deve ficar em local protegido. O arquivo `secret_key` continua no volume; restaurar o banco em uma instalação com uma chave nova encerra sessões anteriores, mas preserva as contas e os dados.

## Restauração

Pare a aplicação antes de restaurar. Um arquivo já em `/data/backups` pode ser restaurado assim:

```sh
docker compose stop app
docker compose run --rm --no-deps --entrypoint python app /app/docker/restore.py /data/backups/NOME-DO-ARQUIVO.sqlite3
docker compose up -d --wait
```

A ferramenta verifica integridade e tabelas do BibliotecaPI, salva uma cópia do banco anterior e substitui o banco de forma atômica. Recusa a operação se encontrar WAL/SHM pendente; nesse caso, inicie e pare normalmente a aplicação antes de repetir. Não apague WAL/SHM manualmente.

Para um backup salvo na máquina, inicie a aplicação e envie o arquivo pela entrada padrão, gravando-o no volume com as permissões do usuário da aplicação:

```sh
docker compose exec -T app python -c "import os, sys; from pathlib import Path; os.umask(0o077); Path('/data/backups/entrada.sqlite3').write_bytes(sys.stdin.buffer.read())" < ./meu-backup.sqlite3
```

O comando acima funciona no terminal macOS/Linux e no Prompt de Comando do Windows. No PowerShell, abra o Prompt de Comando para esse passo de redirecionamento binário. Não use `docker compose cp` para enviar o arquivo: o filesystem somente leitura pode impedir a cópia de entrada, mesmo em áreas montadas. A cópia de saída dos backups continua funcionando normalmente.

Depois pare a aplicação e restaure `/data/backups/entrada.sqlite3` conforme os comandos anteriores. O envio apenas disponibiliza o backup; não substitui o banco ativo.

## Aproveitar o banco local anterior

O arquivo de uma execução sem Docker fica em `bibliotecapi/biblioteca.sqlite3`. Com essa execução local parada, gere uma cópia consistente usando `backup_biblioteca` pelo ambiente local. Envie esse backup ao container e restaure conforme a seção anterior.

O `bibliotecapi/db.sqlite3` original do projeto não entra na imagem e pode ter um esquema antigo. Preserve-o antes de qualquer migração. Não misture arquivos de duas instalações durante a operação.

## Verificações

```sh
docker compose exec app python manage.py check
docker compose exec app python manage.py makemigrations --check --dry-run
docker compose exec app python manage.py test acervo bibliotecapi --noinput
```

Os testes usam banco temporário em memória e não alteram o banco operacional. `/health/` retorna apenas `ok` ou `unavailable`, sem dados de leitores nem detalhes internos. O Docker marca o estado como `healthy` ou `unhealthy`; o healthcheck sozinho não reinicia o container, embora a política `unless-stopped` o reinicie se o processo encerrar.

A imagem usa a arquitetura nativa do build, compatível com Docker Desktop em Apple Silicon e com imagens base disponíveis para Intel/AMD. A validação desta entrega foi feita em Linux ARM64 dentro do Docker Desktop no macOS; não foi executado build AMD64.

O pacote ZIP do piloto anterior não inclui esta etapa de infraestrutura; use os arquivos atuais deste repositório.
