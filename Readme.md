# BibliotecaPI

Sistema leve de acervo e circulação para o piloto de uma biblioteca: importar o controle em Excel, encontrar livros, cadastrar leitores e registrar empréstimos e devoluções.

Projeto originalmente desenvolvido para o Projeto Integrador I da Univesp, DRP14, Turma 005, Grupo 009, baseado no [tutorial Local Library da MDN](https://github.com/mdn/django-locallibrary-tutorial).

## Iniciar no Docker Desktop (recomendado)

Com o Docker Desktop aberto, execute na pasta do projeto:

```sh
docker compose up -d --build --wait
docker compose exec app python manage.py preparar_biblioteca --se-vazio
```

O segundo comando solicita o nome e a senha do primeiro acesso, sem senha padrão. Abra **http://localhost:8000**. Não é necessário instalar Python na máquina. Nas próximas vezes, basta `docker compose up -d --wait`.

A aplicação usa **somente SQLite**, em volume persistente do Docker, com Gunicorn e arquivos estáticos incluídos na imagem. O banco da instalação local anterior não é importado automaticamente. O volume também guarda uma chave exclusiva de sessão, gerada na primeira inicialização.

```sh
docker compose ps                       # Estado e saúde
docker compose logs -f app              # Logs; Ctrl+C encerra apenas a visualização
docker compose stop                    # Parar sem remover o container
docker compose down                    # Remover o container, preservando o volume
```

Não use `docker compose down -v` para uma instalação com dados que deseja manter: `-v` remove o volume do banco. O Compose expõe a aplicação apenas no próprio computador, em `127.0.0.1`.

[Guia Docker: backup, restauração, atualização e importação do banco local](docs/DOCKER.md).

## Alternativa sem Docker para desenvolvimento

Requer Python 3.12 ou superior compatível com Django 5.2 e internet na primeira instalação. Não exige Node, Docker ou um servidor PostgreSQL.

- **Windows:** abra `iniciar.bat`.
- **macOS/Linux:** no terminal, dentro da pasta do projeto, execute `./iniciar.sh`.

Na primeira execução, informe o nome e a senha da equipe. A senha não aparece enquanto é digitada. Acesse **http://127.0.0.1:8000** e entre com esse usuário. O terminal precisa permanecer aberto; use `Ctrl+C` para parar.

Esses iniciadores são para um piloto local em um computador. Não exponha o servidor de desenvolvimento na internet. O iniciador Windows foi incluído para distribuição, mas não foi executado neste ambiente macOS.

### Alternativa manual

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r bibliotecapi/requirements.txt
.venv/bin/python bibliotecapi/manage.py migrate
.venv/bin/python bibliotecapi/manage.py preparar_biblioteca
.venv/bin/python bibliotecapi/manage.py runserver 127.0.0.1:8000
```

No Windows, use `.venv\Scripts\python.exe` no lugar de `.venv/bin/python`.

## Importar o Excel da biblioteca

1. Entre com a conta da equipe e escolha **Importar planilha**.
2. Envie `.xlsx` ou `.csv` com até 5 MB e 5.000 linhas. Para `.xls`, salve como `.xlsx` no Excel.
3. Escolha a aba. A primeira linha preenchida deve conter os nomes das colunas; cada linha seguinte representa **um exemplar físico**.
4. Associe as colunas. Somente o título é obrigatório; associe tombamento/código sempre que existir. ISBN é opcional e, se preenchido, deve ser ISBN-13 válido.
5. Confira a prévia e corrija os erros. A prévia não grava livros.
6. Confirme a importação. Se houver erro de gravação, o lote inteiro é cancelado.

Há um modelo CSV para download na própria tela, aberto pelo Excel. Exportações CSV usam UTF-8 e separador `;`; escolha essa codificação caso o Excel pergunte.

**Atenção à migração:** este importador traz o acervo disponível ou em manutenção. Leitores, reservas, histórico legado e empréstimos ativos não são importados automaticamente. Concilie esses dados antes de substituir o Excel. Não marque um exemplar emprestado como disponível para passar pela importação.

Códigos já cadastrados são preservados e ignorados no reenvio. Sem código, o sistema gera um identificador pelo conteúdo da linha; mudanças nesse conteúdo podem criar outro exemplar. O importador não sincroniza alterações nem deve ser usado para editar registros existentes.

## Operar a biblioteca

- **Leitores → Cadastrar leitor:** nome e, opcionalmente, contato. Leitores não precisam ter conta de acesso.
- **Catálogo ou Exemplares → Emprestar:** escolha o leitor e o prazo. O padrão inicial é 14 dias.
- **Leitores → Nome do leitor:** ficha com contato, totais, empréstimos em aberto, atrasos e histórico paginado. Filtre por situação e acesse o exemplar para atendimento. Disponível para gestor e atendente.
- **Regras de circulação (gestor):** configure prazo sugerido, limite por leitor (zero = sem limite) e bloqueio opcional de novos empréstimos por atraso. A regra é aplicada no servidor e não altera empréstimos existentes.
- **Empréstimos → Renovar:** escolha uma data entre hoje e 4 semanas.
- **Empréstimos → Devolver:** o exemplar volta à disponibilidade; o histórico permanece.
- **Histórico:** consulta das operações realizadas nesta ferramenta.
- **Catálogo → Exportar acervo:** download CSV dos exemplares. Não inclui contatos de leitores.

O primeiro gestor usa o comando `preparar_biblioteca`. Depois, as contas da equipe são criadas e administradas em **Usuários e perfis**, com perfis de gestor, atendente e consulta interna. Contas novas recebem senha temporária e devem trocá-la ao entrar. Para administração técnica, `manage.py createsuperuser` continua disponível; o gestor comum não é superusuário.

[Gestão de usuários, matriz de permissões e recuperação de acesso](docs/USUARIOS_E_PERFIS.md).

## Relatórios gerenciais e demonstração

O menu **Relatórios gerenciais** reúne situação do acervo, circulação mensal, atrasos, próximos vencimentos, títulos mais emprestados, atividade dos leitores e importações. Há filtro de período, exportações CSV e impressão. O acesso exige permissão específica; o perfil Gestor recebe essa permissão.

Para explorar dados fictícios sem misturar com a biblioteca, use a demonstração em **http://localhost:8001**:

```sh
docker compose -f compose.demo.yaml up -d --build --wait
docker compose -f compose.demo.yaml exec app python manage.py carregar_demonstracao
```

Acesse como `gestor_demo`, com a senha fictícia `BibliotecaDemo2026!`. A carga cria todas as estruturas de negócio, incluindo 24 títulos, 72 exemplares, 30 leitores, 210 empréstimos e quatro contas: `gestor_demo`, `atendente_demo`, `consulta_demo` e `inativo_demo`. Todas usam a senha fictícia acima; a conta inativa não permite login. A instalação principal permanece no seu volume e na porta 8000.

[Critérios dos relatórios, contas e dados da demonstração](docs/RELATORIOS_E_DEMONSTRACAO.md).

## Dados e backup

O banco local novo fica em `bibliotecapi/biblioteca.sqlite3`. O `db.sqlite3` original foi preservado e não é migrado automaticamente para o banco novo.

```sh
.venv/bin/python bibliotecapi/manage.py backup_biblioteca
```

A cópia completa é criada em `bibliotecapi/backups/`. Copie os backups para outro local protegido, com frequência compatível com a operação. Eles contêm contas e dados de leitores. Exportar CSV não substitui esse backup.

Para restaurar: encerre a aplicação, guarde o banco atual, copie o backup escolhido para `bibliotecapi/biblioteca.sqlite3` e inicie novamente. Faça primeiro um ensaio em uma cópia da pasta do projeto, com a aplicação parada. No Docker, siga os comandos de backup e restauração do guia específico.

## Configuração e publicação

Uma referência de variáveis para execução sem Docker está em `bibliotecapi/.env.example`. O projeto usa exclusivamente SQLite. No Compose, os caminhos persistentes e a chave são configurados automaticamente; não é preciso criar um `.env`.

Produção requer `DJANGO_DEBUG=False`, segredo próprio, hosts específicos, HTTPS, servidor WSGI/ASGI e armazenamento persistente. O Docker já usa Gunicorn e `DEBUG=False`; a publicação em rede ainda exige configuração de domínio e HTTPS. Os arquivos de publicação Vercel legados foram removidos. Nunca armazene o banco na camada descartável do container. A recuperação de senha por e-mail continua com backend de console; SMTP precisa ser configurado antes de oferecer esse recurso em produção.

O arquivo `requirements.txt` é a fonte de dependências desta versão; Pipfile e lock antigos foram removidos para evitar instalações divergentes.

## Verificação e diagnóstico

```sh
.venv/bin/python bibliotecapi/manage.py check
.venv/bin/python bibliotecapi/manage.py test acervo bibliotecapi
.venv/bin/python bibliotecapi/manage.py makemigrations --check --dry-run
```

[Leia a avaliação, o benchmark e os limites do piloto](docs/AVALIACAO_E_BENCHMARK.md). [Evidências da verificação](docs/VERIFICACAO.md).

O desenvolvimento atual é validado com dados fictícios; o acesso à planilha da biblioteca deixou de estar disponível. A carga de demonstração permite reproduzir os fluxos e os testes sem dados reais.
