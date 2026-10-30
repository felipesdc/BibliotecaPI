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
