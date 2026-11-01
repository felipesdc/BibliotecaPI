# Gestão de usuários e perfis

O desenvolvimento e os testes usam dados fictícios reproduzíveis. A ausência da planilha da biblioteca não bloqueia esta funcionalidade; o importador permanece genérico e a validação com dados reais fica fora desta entrega.

## Perfis

| Ação | Gestor | Atendente | Consulta interna |
| --- | --- | --- | --- |
| Consultar catálogo, autores, gêneros, idiomas e disponibilidade | Sim | Sim | Sim |
| Cadastrar e editar leitores | Sim | Sim | Não |
| Emprestar, renovar, devolver e consultar histórico | Sim | Sim | Não |
| Cadastrar, editar e excluir itens do acervo | Sim | Não | Não |
| Importar e exportar acervo | Sim | Não | Não |
| Relatórios e seus CSV | Sim | Não | Não |
| Gerenciar contas e perfis | Sim | Não | Não |
| Alterar a própria senha | Sim | Sim | Sim |
| Acesso técnico ao Django Admin | Não | Não | Não |

O catálogo continua público. Consulta interna acrescenta uma conta identificada e acesso à própria senha e aos eventuais empréstimos legados vinculados àquela conta; não libera dados pessoais de outros leitores.

Cada perfil usa um grupo reservado: `Biblioteca · Gestor`, `Biblioteca · Atendente` ou `Biblioteca · Consulta interna`. A interface utiliza permissões Django no servidor, além de controlar os links visíveis. A exportação do acervo tem permissão própria (`acervo.export_acervo`); consultar exemplares não concede direito a exportar.

## Primeiro gestor

```sh
docker compose exec app python manage.py preparar_biblioteca --se-vazio
```

O comando solicita nome de acesso e senha, cria um gestor comum, sem privilégios de superusuário, e não solicita outra conta se já houver um gestor ativo. A senha escolhida nesse comando já é pessoal; não há troca obrigatória inicial para esse acesso.

Depois, o gestor utiliza **Usuários e perfis → Criar usuário**. O nome de acesso deve ser único, inclusive considerando letras maiúsculas e minúsculas. Ele fica fixo após a criação para manter a identificação da conta. Nome, sobrenome, e-mail opcional e perfil podem ser editados.

## Cadastro, senha e recuperação

1. O gestor escolhe o perfil e informa uma senha temporária com confirmação.
2. A senha passa pelos validadores do Django e é armazenada somente como hash.
3. O gestor entrega a senha à pessoa por um canal reservado. A ferramenta não a exibe depois nem envia e-mails.
4. No primeiro acesso, a pessoa é encaminhada a **Alterar minha senha** e precisa informar a senha temporária antes de escolher outra.
5. Após a troca, a sessão atual continua aberta; outras sessões precisam entrar novamente.

Em caso de esquecimento, o gestor abre a conta e escolhe **Redefinir senha**, define outra senha temporária e a entrega ao usuário. A redefinição invalida os acessos anteriores e exige nova troca. Para sua própria senha, o gestor usa **Alterar minha senha**, com confirmação da senha atual.

A recuperação por e-mail não faz parte deste fluxo local. O backend de e-mail continua sendo o console; não há SMTP configurado. Se o único gestor perder sua senha, o responsável técnico pode usar `docker compose exec app python manage.py changepassword NOME-DE-ACESSO` no terminal confiável.

## Desativação e proteção de contas

- Desativar exige uma confirmação por POST e bloqueia a autenticação. Contas não são excluídas pela interface.
- Empréstimos, importações e demais registros mantêm o vínculo com o usuário anterior.
- Reativar libera novos logins, mas não recupera sessões antigas.
- Não é possível desativar a própria conta nem alterar o próprio perfil. Outro gestor precisa fazer isso.
- O último gestor ativo não pode ser desativado nem perder o perfil de gestor. Um superusuário técnico não conta como substituto desse gestor operacional.
- Superusuários, contas `staff`, contas com permissões diretas ou com grupos personalizados são protegidos contra alterações por esta interface. A administração técnica desses acessos permanece separada.
- Operações incluem uma versão da conta: uma tela antiga não pode sobrescrever uma alteração mais recente. Atualize a página se aparecer o aviso de conflito.

Mudanças de cadastro, perfil, situação ou senha incrementam a versão de acesso. Sessões antigas de uma conta gerenciada são encerradas na próxima requisição. A própria edição de nome pelo usuário preserva a sessão atual, encerrando as demais. Essa regra também impede que uma sessão anterior à desativação volte a funcionar após a reativação.

## Histórico de gestão de acessos

A tela da conta exibe as últimas 15 operações, incluindo criação, edição, mudança de perfil, ativação, desativação e alteração de senha, com responsável e data. Senhas não são registradas no histórico, nem em texto claro nem como hash de senha.

Este é um histórico de gestão de contas. Ele não substitui uma auditoria geral de todas as operações do acervo, nem uma trilha imutável contra administradores técnicos do banco.

## Atualização de instalações existentes

```sh
docker compose up -d --build --wait
```

As migrations preservam senhas e registros de negócio. Contas comuns nos grupos conhecidos `Bibliotecários` e `Gestores da demonstração` passam a gestor; `Atendentes da demonstração` passa a atendente. Contas comuns sem grupos nem permissões diretas recebem consulta interna. Contas técnicas ou com configurações de acesso personalizadas ficam para revisão separada.

Os acessos antigos das contas migradas pedem novo login uma vez, pois ainda não possuem a versão de sessão. Não é necessário trocar as senhas existentes. O grupo amplo `Bibliotecários` deixa de ser o perfil atribuído pelo comando inicial; ele não recebe automaticamente novas contas.

Os grupos dos três perfis têm definições fixas. Não altere suas permissões manualmente esperando mantê-las: a preparação inicial e a carga de demonstração reaplicam a matriz documentada. Use a interface para atribuir os perfis.

## Demonstração com quatro contas

```sh
docker compose -f compose.demo.yaml up -d --build --wait
docker compose -f compose.demo.yaml exec app python manage.py carregar_demonstracao
```

Em **http://localhost:8001**, use a senha fictícia `BibliotecaDemo2026!`:

| Conta | Comportamento |
| --- | --- |
| `gestor_demo` | Acessa usuários, relatórios e operação completa |
| `atendente_demo` | Opera leitores e circulação; gestão de usuários e relatórios são negados |
| `consulta_demo` | Consulta o catálogo; gestão e dados pessoais dos leitores são negados |
| `inativo_demo` | Login bloqueado até ser reativado por um gestor |

As contas de demonstração já têm senha de demonstração definitiva para permitir exploração imediata. Contas novas criadas pela tela exigem troca de senha normalmente. Na demonstração existente, executar a carga adiciona somente as novas contas que faltarem; mantém o acervo, os empréstimos, os perfis já alterados e as senhas existentes.

O volume da demonstração é separado da instalação principal. Não são necessárias planilhas ou informações reais para reproduzir os testes.

## Ficha individual do leitor

Em **Leitores**, o nome abre contato e histórico individual, com filtros de empréstimos em aberto, atrasados e devolvidos. Os indicadores sempre incluem todo o histórico do leitor; vencimento hoje não é atraso. A tabela exibe 20 registros por página e oferece acesso ao exemplar. Leitores inativos conservam seu histórico.

A página exige conjuntamente `acervo.view_leitor` e `acervo.marca_devolucao`, verificadas no servidor. Gestor e atendente possuem ambas; consulta interna e visitantes não acessam a ficha. Registros legados vinculados somente a uma conta de acesso não são associados por nome ou e-mail.

## Regras de circulação

O gestor acessa **Regras de circulação** (`acervo.change_politicacirculacao`). Atendentes e consulta interna não podem alterar as regras, nem enviando POST diretamente. A migração concede a permissão aos gestores já existentes.

- Prazo sugerido: 1 a 365 dias; padrão de 14 dias. A equipe pode selecionar outra data futura no empréstimo.
- Limite por leitor: 0 a 1000 exemplares em aberto; zero mantém a operação sem limite. Inclui exemplares legados vinculados ao leitor.
- Bloqueio por atraso: opcional e inicialmente desligado; impede somente novos empréstimos quando o leitor possui exemplar com prazo anterior a hoje.

As regras são globais, persistidas no SQLite e incluídas no backup completo. A alteração não modifica empréstimos existentes; renovação e devolução continuam disponíveis. Desativar o bloqueio ou aumentar o limite libera novas operações conforme a situação atual. Registros legados vinculados apenas a contas de acesso não são associados automaticamente a leitores.

A gravação do empréstimo valida leitor ativo, limite, atrasos e disponibilidade dentro da transação. No SQLite, a escrita inicial serializa operações concorrentes antes da contagem.

## Central de atendimento

O menu **Central de atendimento** exige as duas permissões `acervo.view_leitor` e `acervo.marca_devolucao`, verificadas no servidor. Gestor e atendente recebem ambas; visitantes e consulta interna não acessam a tela nem suas buscas.

1. Busque o leitor por nome ou número e selecione o resultado. Homônimos são diferenciados pelo número do cadastro.
2. Confira os totais de exemplares em aberto, atrasos e eventuais bloqueios. As regras são revalidadas na gravação.
3. Busque o exemplar por código, título ou ISBN; confira o código físico e o prazo antes de confirmar o empréstimo.
4. Para renovar ou devolver, use a linha correspondente na lista dos exemplares do leitor. O leitor permanece selecionado após a operação.

Buscas exibem até 20 resultados e pedem refinamento quando há mais. Não há gravações por GET. Formulários incluem CSRF, validação de datas e mensagens com exemplar, leitor e resultado. As devoluções e renovações usam os serviços transacionais compartilhados com as telas anteriores.

Uma confirmação assinada, com validade de uma hora, vincula renovação/devolução ao leitor e ao registro atual. Se o empréstimo mudar, for devolvido e reaberto ou a confirmação expirar, atualize o atendimento. Empréstimos legados associados a um leitor também podem ser atendidos; itens vinculados apenas a contas de acesso continuam nas telas anteriores.

## Painel inicial por perfil

A Visão geral usa permissões efetivas, incluindo contas técnicas e permissões personalizadas:

- Com `view_leitor` e `marca_devolucao`, mostra o painel de atendimento: atrasos, vencimentos hoje, empréstimos em aberto, exemplares disponíveis e até cinco prioridades, ordenadas pelo prazo mais antigo. O atalho leva ao leitor na central ou ao exemplar quando não há leitor cadastrado.
- Com `view_relatorios`, acrescenta a visão gerencial: empréstimos e devoluções do mês até hoje, situação do acervo e leitores ativos. Devoluções incluem empréstimos iniciados em meses anteriores. Sem as permissões de atendimento, nenhuma lista individual é consultada ou enviada ao template.
- Visitantes e consulta interna recebem a página de descoberta do catálogo, sem dados operacionais individuais.

Os números de situação atual usam os exemplares, incluindo empréstimos legados. O movimento mensal usa somente o histórico registrado na ferramenta. Vencimento hoje não é atraso; exemplares emprestados sem prazo aparecem em aviso separado. Os filtros de destino (atrasados, vencem hoje e sem prazo) continuam protegidos pela permissão de circulação.

## Busca e filtros de empréstimos

Em **Empréstimos**, combine busca por nome/número de leitor, título, código ou ISBN; contas legadas também podem ser encontradas por nome de acesso, nome ou sobrenome. Todos os resultados são exemplares atualmente emprestados e exigem `marca_devolucao`.

- Situações: todos em aberto, atraso, vence hoje, próximos sete dias (amanhã até hoje + 7, inclusive) e sem prazo.
- Período: uma ou ambas as datas de vencimento, inclusive. Data final anterior à inicial e combinação de datas com “sem prazo” exibem erro, sem resultados parciais.
- Ordenação: prazo mais próximo/distante, título ou nome do leitor. Na ordenação por prazo, registros sem data ficam no fim.
- Dez resultados por página; filtros e ordem permanecem durante a navegação. Quantidade total e intervalo visível aparecem antes da tabela.
- Renovar, cancelar renovação ou devolver retorna à seleção anterior. Se uma operação remover a última linha de uma página, a lista se ajusta para a última página existente. Somente o caminho interno da lista de empréstimos é aceito como retorno.

Filtros são consultas GET e não alteram o acervo. As confirmações continuam por POST com CSRF, usando os serviços de circulação existentes.

## Retorno visual das operações

Depois de confirmar um empréstimo, renovação ou devolução, a central e a lista de empréstimos exibem o mesmo cartão de sucesso: livro, código do exemplar, leitor, prazo, data/hora e operador. Na devolução, o prazo exibido é o anterior e a identificação do leitor permanece no resumo mesmo após a liberação do exemplar.

Os atalhos permitem continuar com o mesmo leitor, atender outro ou consultar os empréstimos em aberto. Acesso à central continua exigindo ambas as permissões de atendimento; contas com somente `marca_devolucao` recebem o resumo sem esses atalhos. Contas legadas sem cadastro de leitor não oferecem o atalho para o mesmo leitor.

O cartão é transitório, pertence à sessão e à conta que realizou a operação e aparece uma vez no destino do redirecionamento. Expira após dez minutos; atualizar a página não repete o cartão nem a operação. Apenas o resumo mais recente fica pendente por sessão, como os demais avisos transitórios. O histórico continua sendo o registro permanente. Erros de validação e operações recusadas não criam cartões de sucesso.
