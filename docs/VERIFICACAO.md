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

## Relatórios e demonstração — 25/10/2026

- **39 testes aprovados localmente e dentro do container**: inclui filtros inválidos, limites inclusivos de datas no fuso de São Paulo, meses sem movimento, divisão por zero, devoluções de retiradas anteriores ao período, gêneros sem duplicar rankings, acesso por permissão e exportações sem truncar resultados.
- Carga fictícia executada em `bibliotecapi-demo`, no volume independente `bibliotecapi-demo_demonstracao_dados`: 8 autores, 6 gêneros, 3 idiomas, 24 títulos, 72 exemplares, 30 leitores, 210 empréstimos, 2 importações e 2 contas de acesso.
- Reexecução da carga confirmou que não houve duplicação nem sobrescrita.
- HTTP real, com autenticação e CSRF: as oito exportações retornaram 200. CSV de empréstimos com 210 linhas; devoluções, 192; atrasos, 9; títulos, 24; leitores, 30; circulação mensal, 7; composição do acervo, 7; resumo, 22.
- Conta de atendente recebeu 403 tanto na tela quanto no CSV de resumo. Conta de gestor acessou os relatórios.
- No Chrome desktop, conferidos os cards, gráficos mensais e tabelas; a prévia de impressão ocultou navegação e controles e manteve os dados legíveis. Nenhum arquivo ou impressão física foi gerado nessa conferência.
- Intervalo de outubro conferido no navegador: 15 retiradas, nenhuma devolução e “—” para pontualidade e duração média, mantendo os 72 exemplares e 9 atrasos atuais.
- Instalação principal atualizada em `localhost:8000`; não contém contas ou registros da demonstração. Demonstração em `localhost:8001`; ambas saudáveis.
- Nenhuma migration pendente de geração, e `git diff --check` sem problemas.

Critérios, acessos fictícios e reprodução: [relatórios e demonstração](RELATORIOS_E_DEMONSTRACAO.md). A conferência visual foi feita no desktop; não houve teste em celular físico nem teste de carga.

## Gestão de usuários e perfis — 28/10/2026

- **61 testes locais aprovados**, incluindo os 39 anteriores e 22 testes de gestão de acessos. A suíte também é executada na imagem Docker final.
- Matriz de gestor, atendente e consulta validada no servidor, incluindo bloqueios de gestão, relatórios, dados de leitores e exportação do acervo.
- Cadastro com senha temporária, validação de senha, hash, troca obrigatória e preservação da sessão atual após a troca.
- Desativação/reativação sem recuperar sessões antigas; mudanças de perfil encerram os acessos anteriores na próxima requisição.
- Proteção de contas técnicas, do próprio perfil e do último gestor ativo; versão de conta evita sobrescritas por formulários antigos.
- Simulada alteração de cadastro ou desativação durante uma troca de senha: a operação rejeitou os dados antigos, sem reativar a conta nem sobrescrever o cadastro.
- Histórico de contas conferido sem senhas em seus dados; não há exclusão de usuários na interface.
- Migração dos grupos conhecidos preserva o hash de senha, registros de negócio e contas técnicas. As contagens do banco principal foram comparadas antes e depois da atualização, sem diferenças em livros, exemplares, leitores, empréstimos, importações e usuários.
- Demonstração complementada com `consulta_demo` e `inativo_demo`, mantendo os dados e senhas fictícios anteriores.
- HTTP real com autenticação e CSRF: gestor acessa a lista e o formulário de contas; atendente e consulta são bloqueados com 403; a conta inativa não autentica. A alteração da própria senha está acessível aos três perfis ativos.
- No Chrome desktop, conferidos o novo menu, os perfis, a lista de quatro contas e o formulário de cadastro. Criações, redefinições e alterações de acesso foram verificadas pela suíte automatizada; não foram cadastradas contas reais na conferência visual.
- Ambos os ambientes usam SQLite em volumes distintos. A disponibilidade da planilha real não é pré-requisito desta entrega.

Guia: [usuários e perfis](USUARIOS_E_PERFIS.md). As contas fictícias continuam restritas à demonstração local. Não houve teste em aparelho móvel nem ensaio de carga concorrente.

## Ficha individual do leitor — 29/10/2026

- Adicionada ficha em `/acervo/leitores/<id>/`, com contato, indicadores e histórico filtrado e paginado (20 registros).
- Quatro novos testes com dados fictícios cobrem isolamento entre leitores, totais independentes do filtro, vencimento hoje, filtros, permissões, leitor inativo, ausência de registros, ID inexistente e paginação.
- Suíte local completa: **65 testes aprovados** (`manage.py test acervo bibliotecapi`).
- `manage.py check`, `makemigrations --check --dry-run` e `git diff --check` aprovados. Sem alteração de esquema ou novas dependências.
- Esta etapa não incluiu nova verificação visual em navegador nem reconstrução da imagem Docker.

## Regras de circulação — 29/10/2026

- Configuração global persistida: prazo sugerido, limite por leitor e bloqueio opcional por atraso. Padrões preservam a operação anterior (14 dias, sem limite, sem bloqueio).
- Migração `0010` adiciona configuração e concede permissão aos gestores existentes; novos gestores recebem a mesma permissão pelo configurador de grupos.
- Serviço transacional valida leitor ativo, limite, atrasos (incluindo exemplares legados vinculados ao leitor) e disponibilidade antes de criar o histórico. A escrita inicial serializa operações SQLite antes da contagem.
- Seis novos testes cobrem padrões, prazo sugerido, limite, ausência de gravação em rejeições, liberação após devolução, vencimento hoje, atraso legado, inatividade, manutenção, isolamento entre leitores, permissões e validação/persistência da configuração. Não foi executado teste de estresse concorrente.
- **71 testes aprovados localmente e na imagem Docker**. `check`, `makemigrations --check --dry-run` e `git diff --check` aprovados.
- Demonstração reconstruída e saudável em `http://localhost:8001`. Verificação pelo cliente Django no container: gestor acessa regras e ficha (200), atendente acessa ficha (200) e recebe 403 nas regras. Não houve nova inspeção visual em navegador.
