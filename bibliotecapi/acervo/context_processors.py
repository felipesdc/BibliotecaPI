from django.conf import settings


def ambiente(request):
    return {'ambiente_demo': settings.DEMO_MODE}


SECOES = {
    'index': ('Visão geral', []),
    'livros': ('Catálogo de livros', ['detalhe-livro', 'adicionar-livro', 'alterar-livro', 'excluir-livro']),
    'copias': ('Exemplares', ['detalhe-copia', 'adicionar-copia', 'alterar-copia', 'excluir-copia']),
    'autores': ('Autores', ['detalhe-autor', 'adicionar-autor', 'alterar-autor', 'excluir-autor']),
    'generos': ('Gêneros', ['detalhe-genero', 'adicionar-genero', 'alterar-genero', 'excluir-genero']),
    'linguas': ('Idiomas', ['detalhe-lingua', 'adicionar-lingua', 'alterar-lingua', 'excluir-lingua']),
    'atendimento': ('Central de atendimento', []),
    'todos-emprestimos': ('Empréstimos', ['emprestar', 'devolver', 'renovacao-emprestimo-bibliotecario']),
    'historico': ('Histórico', []),
    'relatorios': ('Relatórios gerenciais', []),
    'leitores': ('Leitores', ['detalhe-leitor', 'adicionar-leitor', 'alterar-leitor']),
    'importar-acervo': ('Importar planilha', ['mapear-importacao']),
    'usuarios': ('Usuários e perfis', ['criar-usuario', 'editar-usuario', 'desativar-usuario', 'reativar-usuario', 'redefinir-senha-usuario']),
    'politica-circulacao': ('Regras de circulação', []),
    'password_change': ('Alterar minha senha', ['password_change_done']),
    'meus-emprestimos': ('Meus empréstimos', []),
}


def navegacao(request):
    rota = getattr(request.resolver_match, 'url_name', None)
    for secao, (titulo, filhas) in SECOES.items():
        if rota == secao or rota in filhas:
            return {'nav_secao': secao, 'nav_titulo': titulo,
                    'nav_estado': 'page' if rota == secao else 'location'}
    return {'nav_secao': '', 'nav_titulo': 'Acesso à biblioteca', 'nav_estado': ''}
