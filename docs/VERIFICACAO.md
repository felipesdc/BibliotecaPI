# Verificação do piloto

Data: 24/10/2026. Ambiente: macOS, Python 3.12, Django 5.2.18, SQLite. Dados de teste criados em banco separado em `/private/tmp`; o `db.sqlite3` original não foi modificado.

## História verificada

A equipe envia uma planilha → associa colunas → revisa a prévia → confirma → encontra o título no catálogo → empresta a um leitor → registra devolução → consulta o histórico preservado.

| Fronteira | Evidência |
| --- | --- |
| Interface | Visão geral, login, importação, associação, catálogo, detalhe, empréstimo, devolução e histórico abertos no Chrome |
| Envio e associação | CSV de teste com colunas `Tombo`, `Obra`, `Autor`, `Situacao`; nomes reconhecidos automaticamente |
| Prévia | Exibiu um exemplar novo sem gravar antecipadamente; confirmação explícita da situação exigida |
| Gravação e resposta | Mensagem `Importação concluída`; catálogo passou de 6 para 7 títulos; código `QA-100` visível |
| Empréstimo | Leitor de demonstração e prazo apresentados; resposta `Empréstimo registrado` e exemplar na lista de circulação |
| Devolução | Resposta `Devolução registrada. Exemplar disponível novamente.`; lista de empréstimos ficou vazia |
| Histórico | Registro `QA-100` preservado com leitor, data de registro, prazo e data de devolução |
| Backup | Cópia SQLite aberta separadamente; `PRAGMA integrity_check` retornou `ok`, com 7 exemplares e 1 empréstimo no histórico |

## Verificações automatizadas

`python manage.py test acervo --noinput`: **22 testes aprovados**.

Cobrem renderização das páginas, permissões e CSRF, upload e associação, prévia sem escrita, confirmação, repetição de lote, isolamento entre contas, rollback integral, códigos duplicados/conflitantes, fórmulas, situações não suportadas, ISBN inválido, XLSX com múltiplas abas, geração de códigos, criação mínima de livros e exemplares, criação da equipe, empréstimo duplicado, renovação, devolução, histórico, paginação e exportação CSV.

`python manage.py check`: sem problemas identificados.

`python manage.py makemigrations --check --dry-run`: nenhuma mudança pendente.

`git diff --check`: sem erros de whitespace.

## Alcance

O teste no Chrome usou CSV. A leitura de XLSX e seleção de múltiplas abas foram verificadas por teste automatizado. A interface foi inspecionada em desktop; não houve teste em celular físico. O iniciador Windows e a hospedagem Vercel não foram executados. A planilha real da biblioteca ainda não foi disponibilizada, portanto a migração real permanece sujeita à homologação descrita no diagnóstico.

## Etapa de infraestrutura — Docker Desktop

Também validada em 24/10/2026, em container Linux ARM64 no Docker Desktop:

- Imagem construída com Python 3.12, Django 5.2.18 e Gunicorn 26.2.0; sem serviço ou driver PostgreSQL.
- **24 testes aprovados dentro do container** (22 funcionais e 2 de saúde).
- Container saudável; HTTP 200 em `/health/`, catálogo, login e CSS, com `DEBUG=False`.
- Processo com UID 10001 e raiz somente leitura; banco e chave fora da imagem, em volume persistente.
- SQLite confirmado em modo WAL.
- Registro e chave de sessão preservados após recriar o container.
- Backup restaurado com serviço parado: registro anterior preservado e registro posterior ausente.
- Migration pendente simulada no ambiente isolado: backup automático criado antes da reaplicação.
- Ambiente de teste encerrado; instalação principal separada, sem os registros artificiais.

Procedimentos atuais: [guia Docker](DOCKER.md). Esta etapa substitui a opção anterior de PostgreSQL e a configuração Vercel legada. Não foi realizado build AMD64 nem teste de carga.
