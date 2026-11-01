"""Conteúdo inicial derivado das permissões efetivas da conta."""
from django.db.models import Count, Q
from django.utils import timezone

from .models import Emprestimo, Leitor, LivroCopia


def contexto_painel(usuario):
    gestao = usuario.has_perm('acervo.view_relatorios')
    atendimento = usuario.has_perms(('acervo.view_leitor', 'acervo.marca_devolucao'))
    if not (gestao or atendimento):
        return {}
    hoje = timezone.localdate()
    estoque = LivroCopia.objects.aggregate(
        abertos=Count('pk', filter=Q(estado='e')),
        atrasados=Count('pk', filter=Q(estado='e', data_devolucao__lt=hoje)),
        vencem_hoje=Count('pk', filter=Q(estado='e', data_devolucao=hoje)),
        sem_prazo=Count('pk', filter=Q(estado='e', data_devolucao__isnull=True)),
        manutencao=Count('pk', filter=Q(estado='m')),
    )
    contexto = {'painel_gestao': gestao, 'painel_atendimento': atendimento, 'hoje': hoje, 'estoque': estoque}
    if atendimento:
        contexto['prioridades'] = LivroCopia.objects.filter(
            estado='e', data_devolucao__lte=hoje,
        ).select_related('livro', 'leitor', 'tomador').order_by('data_devolucao', 'pk')[:5]
    if gestao:
        contexto['movimento_mes'] = Emprestimo.objects.aggregate(
            emprestimos=Count('pk', filter=Q(criado_em__date__gte=hoje.replace(day=1), criado_em__date__lte=hoje)),
            devolucoes=Count('pk', filter=Q(devolvido_em__date__gte=hoje.replace(day=1), devolvido_em__date__lte=hoje)),
        )
        contexto['leitores_ativos'] = Leitor.objects.filter(ativo=True).count()
    return contexto
