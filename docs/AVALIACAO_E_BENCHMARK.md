# BibliotecaPI — avaliação e benchmark

Avaliação em 24/10/2026. Objetivo: permitir que uma pequena biblioteca migre seu controle em Excel para uma ferramenta leve e utilizável.

## Diagnóstico do projeto original

A aplicação usa Django, templates renderizados no servidor, Bootstrap e modelos de livros, autores, gêneros, idiomas e exemplares. Essa arquitetura é adequada ao piloto: não exige um frontend separado, API adicional ou infraestrutura de serviços. O README identifica como origem o tutorial Local Library da MDN e o Projeto Integrador da Univesp.

| Área | Evidência encontrada | Consequência |
| --- | --- | --- |
| Entrada de dados | Não havia importação de planilhas | Cadastrar o acervo manualmente impediria a adoção |
| Operação | Empréstimo representado somente por campos no exemplar; renovação disponível | Ausência de histórico e de fluxo dedicado de devolução |
| Leitores | Tomador vinculado à conta de autenticação Django | Cada leitor exigiria conta de acesso para ser identificado nesse modelo |
| Busca | Listagens sem consulta e filtros | Dificuldade para encontrar uma obra em acervos maiores |
| Paginação | `paginate_by` nas views, sem navegação nos templates | Interface não permitia chegar aos itens seguintes |
| Renovação | Método `limpar_data_renovacao` | Django não executava a validação customizada, que exige `clean_data_renovacao` |
| Exclusão | Rota `autors` e fallbacks `autor-delete`/`livro-delete` inexistentes | Falha na exclusão ou no tratamento de vínculo protegido |
| Modelos | `mostra_genero` acessava `self.genero.nome` | Método incorreto para a relação de vários gêneros |
| Administração | `LivroAdmin` definido, mas livro registrado sem essa classe | Configuração de listagem e exemplares inline não aplicada |
| Interface | Listas simples, CSS mínimo, `lang="en"`, textos de tutorial | Pouca orientação para operação real |
| Configuração | PostgreSQL obrigatório, `DEBUG` ativo por padrão e hosts irrestritos | Instalação difícil e configuração inadequada para exposição pública |
| Dependências | Django 5.1 e requirements em UTF-16, ferramentas de ambiente no runtime | Manutenção e distribuição desnecessariamente complexas |
| Testes | Arquivo de testes vazio | Sem regressão automatizada para os fluxos críticos |
| Publicação | Configuração Vercel com rota geral antes dos estáticos e diretórios de saída divergentes | Precisa de revisão específica antes de publicar; não validada neste trabalho |

## Benchmark funcional

Comparação documental, baseada nas fontes oficiais abaixo. Não foram executados ensaios de desempenho, auditorias de acessibilidade ou testes de usabilidade com usuários desses produtos. As escolhas visuais do BibliotecaPI são uma proposta própria.

| Referência | Recursos documentados | Aprendizado para o piloto |
| --- | --- | --- |
| [Koha — manual oficial](https://koha-community.org/manual/latest/en/html/using-koha.html) | Módulos de catalogação, circulação, leitores, busca, catálogo público e relatórios | Separar descoberta de livros e tarefas da equipe; tornar circulação explícita |
| [Evergreen — documentação oficial](https://docs.evergreen-ils.org/docs/latest/shared/about_evergreen.html) | Interface da equipe para gestão, catalogação e circulação; interface pública de consulta | Exibir catálogo ao público e proteger dados de leitores e operações |
| [Biblivre — descrição oficial](https://www.biblivre.org.br/index.php/sobre-biblivre/o-programa) | Pesquisa, reservas, empréstimo, devolução, catalogação, aquisição, permissões, backups e relatórios | Priorizar ciclo de empréstimo e proteção dos dados antes de recursos avançados |

A inferência para o BibliotecaPI é manter um recorte pequeno desses fluxos: importar acervo, localizar exemplar, identificar leitor, emprestar, renovar e devolver. Aquisição, catalogação MARC, Z39.50, consórcios e multas automáticas não são necessários para validar a primeira adoção.

## Implementado nesta versão

- Interface própria sem dependência de recursos externos: navegação por tarefa, resumo do acervo, catálogo com representações gráficas de livros, formulários, tabelas e estados vazios. As representações não são capas editoriais reais.
- Pesquisa por título, autor, ISBN e código; filtro por gênero e disponibilidade; navegação paginada preservando filtros.
- Importação de XLSX e CSV: escolha de aba, associação de colunas, sugestões por nomes comuns, amostra e prévia. Até 5 MB, 5.000 linhas, 100 colunas e 20 abas.
- Validação por linha, rejeição de fórmulas e ISBN-13 incorreto, detecção de códigos repetidos e conflitos de título, confirmação e transação integral.
- ISBN opcional e código de exemplar independente do ISBN. Reenvio com o mesmo código preserva o registro existente, sem atualização destrutiva.
- Geração determinística de códigos quando ausentes. Se o conteúdo da linha mudar, o código pode mudar; por isso, usar tombamento fixo é a opção recomendada.
- Leitores separados das contas de acesso; cadastro e edição com permissão.
- Empréstimo com leitor e prazo, renovação validada, devolução por POST e histórico persistente. Atualização condicional de disponibilidade e restrição de um empréstimo aberto por exemplar.
- Exportação CSV do acervo, modelo CSV, criação interativa de conta da equipe e backup consistente do SQLite.
- SQLite local em arquivo novo; a etapa posterior de infraestrutura removeu a configuração PostgreSQL e adicionou Docker Desktop (ver `DOCKER.md`). Arquivo `db.sqlite3` original não alterado.
- Dependências reduzidas e Django 5.2 LTS. A [política oficial de versões](https://www.djangoproject.com/download/) fundamenta a escolha de uma linha LTS.

## Limites e próximos critérios para adoção

1. **Planilha real ainda não disponível.** A associação flexível cobre uma aba de acervo com uma linha por exemplar. Uma planilha de títulos com coluna de quantidade, múltiplas linhas de cabeçalho, células mescladas, autores em formatos variados ou várias abas relacionadas precisa de adaptação. A primeira linha preenchida deve ser o cabeçalho.
2. **Migração dos empréstimos ativos não está automatizada.** O importador bloqueia situações de empréstimo/reserva quando associadas, e exige confirmação explícita de que os itens estão disponíveis ou em manutenção. Leitores existentes são cadastrados pela interface; importação de leitores e histórico legado depende do formato real. Antes de substituir o Excel, reconciliar todos os empréstimos atuais.
3. **Sem sincronização bidirecional.** Reimportar preserva exemplares conhecidos; não atualiza metadados existentes. O Excel deixa de ser a fonte operacional após a conferência da migração.
4. **Execução sem Docker e publicação.** A etapa posterior adicionou Gunicorn e persistência via Docker (ver `DOCKER.md`). Os iniciadores usam o servidor de desenvolvimento Django, limitado a `127.0.0.1`. Não são uma solução de hospedagem pública. Uso em rede exige servidor de aplicação, HTTPS, configuração de produção e rotina de backup. Vercel serverless requer banco persistente externo; não usar SQLite efêmero nesse ambiente.
5. **Backups precisam sair do computador.** CSV é intercâmbio de acervo; não é cópia completa. O comando de backup inclui contas, leitores e histórico; armazenar cópias em local protegido e testar restauração.
6. **Políticas ainda simples.** Prazo inicial configurável (padrão de 14 dias), limite de exemplares por leitor e bloqueio opcional de novos empréstimos por atraso. Renovação entre hoje e 28 dias; sem multas, reservas funcionais, notificações e leitura de códigos de barras.
7. **Validação humana necessária.** Interface conferida em Chrome desktop; a CSS inclui adaptação a telas menores, mas não houve teste em aparelho móvel nem ensaio com a equipe da biblioteca.

## Roteiro de homologação com a biblioteca

- Fazer uma cópia do Excel original e identificar uma aba de acervo com situação atual dos exemplares.
- Importar uma amostra de 20–50 exemplares; conferir títulos, autores, códigos, totais e disponibilidade.
- Definir códigos fixos onde faltarem; corrigir dados antes de importar o restante.
- Conciliar empréstimos já ativos e cadastrar os leitores necessários antes de abandonar a planilha.
- Executar empréstimo, renovação e devolução acompanhados pela equipe.
- Criar backup, restaurar em uma cópia separada e verificar acervo, leitores e histórico.
- Somente após essa conferência, escolher a data de transição e deixar o Excel anterior como arquivo de consulta.
