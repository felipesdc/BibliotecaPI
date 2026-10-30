# Relatórios gerenciais e demonstração

Acesse **Relatórios gerenciais** no menu da equipe, ou `/acervo/relatorios/`. A tela permite escolher um período de até dois anos, exportar CSV e imprimir o relatório pelo navegador.

## O que os relatórios mostram

| Visão | Critério |
| --- | --- |
| Acervo atual | Títulos, exemplares, disponibilidade, manutenção, reservas e empréstimos em aberto no momento da consulta |
| Atrasos atuais | Exemplares emprestados com prazo anterior à data de hoje; inclui registros antigos vinculados somente a contas de acesso |
| Próximos vencimentos | De hoje até hoje + 7 dias, inclusive |
| Circulação no período | Empréstimos iniciados e devoluções realizadas entre as datas selecionadas, inclusive, no fuso de São Paulo |
| Circulação mensal | As mesmas contagens, agrupadas por mês; meses sem movimento aparecem com zero |
| Pontualidade | Devoluções feitas até a data de prazo, divididas pelas devoluções realizadas no período |
| Duração média | Tempo entre a retirada e a devolução, somente para devoluções realizadas no período |
| Títulos mais emprestados | Número de retiradas iniciadas no período por título |
| Atividade dos leitores | Retiradas iniciadas no período por leitor; exportação inclui leitores sem movimento |
| Gêneros do acervo | Títulos e exemplares atualmente relacionados a cada gênero |
| Importações | Envios concluídos e pendentes no período, com os últimos cinco arquivos e responsáveis |

O filtro de datas **não reconstrói um estoque passado**: acervo, atrasos, situação dos leitores e próximos vencimentos sempre representam o presente. Uma devolução pode entrar no período mesmo quando a retirada aconteceu antes dele; por isso, as contagens de entradas e devoluções são independentes.

Renovações não criam outra retirada. A pontualidade considera o prazo registrado no histórico, já atualizado pelas renovações. Sem devoluções, pontualidade e duração são exibidas como “—”, sem atribuir um percentual artificial.

Um título pode pertencer a mais de um gênero; somar as linhas de gêneros duplica esses títulos. Registros antigos ligados apenas à conta de acesso participam da circulação, mas não do ranking de leitores cadastrados.

A tela mostra até 10 títulos, leitores, atrasos e próximos vencimentos. Os CSV de títulos e atrasos incluem todos os resultados; o CSV de leitores inclui todos os leitores, até os sem empréstimos. As exportações usam UTF-8 com BOM e separador `;`, e neutralizam fórmulas em campos textuais. O acervo por gênero possui exportação própria; a exportação detalhada de exemplares continua disponível no catálogo.

## Permissões

A tela e todas as exportações exigem `acervo.view_relatorios`. Esconder o menu não é a única proteção: a permissão também é conferida na requisição ao servidor.

O perfil **Gestor** possui a permissão dos relatórios. Atendente e consulta interna não a recebem. A migração dos grupos antigos preserva senhas e converte contas comuns conhecidas para os perfis atuais; contas técnicas ficam protegidas. Veja a [matriz de acesso](USUARIOS_E_PERFIS.md).

## Ambiente de demonstração separado

Na raiz do projeto, com Docker Desktop aberto:

```sh
docker compose -f compose.demo.yaml up -d --build --wait
docker compose -f compose.demo.yaml exec app python manage.py carregar_demonstracao
```

Abra **http://localhost:8001/acervo/relatorios/** e entre com:

| Conta fictícia | Usuário | Senha exclusiva da demonstração |
| --- | --- | --- |
| Gestor | `gestor_demo` | `BibliotecaDemo2026!` |
| Atendente | `atendente_demo` | `BibliotecaDemo2026!` |
| Consulta interna | `consulta_demo` | `BibliotecaDemo2026!` |
| Inativa | `inativo_demo` | `BibliotecaDemo2026!` |

O gestor acessa os relatórios; o atendente opera a circulação e os leitores, mas não acessa os relatórios. Não use essas credenciais na instalação real. Um aviso visível identifica o ambiente fictício em todas as telas.

O ambiente tem projeto `bibliotecapi-demo`, porta 8001 e volume `bibliotecapi-demo_demonstracao_dados`. A instalação principal continua na porta 8000, com seu próprio volume. A imagem de código é a mesma; as configurações e os dados são independentes.

### Dados gerados na primeira carga

- 8 autores fictícios, com datas de nascimento e um exemplo de falecimento.
- 6 gêneros e 3 idiomas.
- 24 títulos fictícios, com descrições, ISBN-13 matematicamente válidos e alguns títulos com múltiplos gêneros. ISBNs são exemplos técnicos, sem alegação de registro editorial.
- 72 exemplares: 36 disponíveis, 18 emprestados, 12 em manutenção e 6 reservados.
- 30 leitores fictícios: 27 ativos e 3 inativos, com e-mails `example.invalid` e telefones propositalmente inválidos.
- 210 registros de empréstimo: 192 devolvidos e 18 abertos, distribuídos por aproximadamente seis meses. Na data da carga, 9 empréstimos estão atrasados.
- Um empréstimo aberto usa o vínculo legado com a conta do atendente, permitindo demonstrar “Meus empréstimos”.
- Uma importação concluída e outra pendente, com dados de exemplo para associação de colunas.
- Quatro contas de acesso, seus perfis, grupos de permissões e eventos de gestão. A conta inativa não autentica.

A data de referência acompanha o dia da primeira carga, no fuso de São Paulo. Os atrasos evoluem conforme os dias passam. O filtro padrão de 180 dias pode excluir alguns registros mais antigos; para reconciliar os 210 empréstimos, escolha um período que cubra toda a carga, como os últimos 365 dias.

O comando exige `BIBLIOTECA_DEMO=True` e recusa bancos com dados existentes. Executá-lo novamente após uma carga concluída mantém os dados e as senhas existentes; adiciona as contas de consulta e inativa caso ainda não existam. Ele não apaga a demonstração nem serve para restaurar alterações manuais.

Reservados representam somente o estado do exemplar já suportado pelo modelo; a carga não implementa fila ou processo de reservas. As sessões e os registros internos do Django são criados pelo uso normal da aplicação, sem simular históricos de autenticação.

## Comandos úteis

```sh
docker compose -f compose.demo.yaml ps
docker compose -f compose.demo.yaml logs --tail=100 app
docker compose -f compose.demo.yaml exec app python manage.py test acervo bibliotecapi --noinput
docker compose -f compose.demo.yaml down
```

`down` preserva o volume da demonstração. Evite confundir os arquivos Compose: a instalação principal usa `compose.yaml`, e a demonstração usa `compose.demo.yaml` explicitamente.
