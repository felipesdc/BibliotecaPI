import datetime

from django import forms
from .models import Leitor, LivroCopia, PoliticaCirculacao

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

class RenovacaoEmprestimoForm(forms.Form):
    data_renovacao = forms.DateField(help_text="Insira uma data entre hoje e daqui a 4 semanas (padrão 3).")

    def clean_data_renovacao(self):
        data = self.cleaned_data['data_renovacao']

        # Check if a date is not in the past.
        if data < datetime.date.today():
            raise ValidationError(_('Data inválida - renovação passada'))

        # Check if a date is in the allowed range (+4 weeks from today).
        if data > datetime.date.today() + datetime.timedelta(weeks=4):
            raise ValidationError(_('Data inválida - renovação para mais do que 4 semanas a frente'))

        # Remember to always return the cleaned data.
        return data


class UploadAcervoForm(forms.Form):
    arquivo = forms.FileField(label='Planilha do acervo (.xlsx ou .csv)', widget=forms.ClearableFileInput(attrs={'accept': '.xlsx,.csv'}))

    def clean_arquivo(self):
        arquivo = self.cleaned_data['arquivo']
        if arquivo.size > 5 * 1024 * 1024:
            raise forms.ValidationError('O arquivo deve ter no máximo 5 MB.')
        if not arquivo.name.lower().endswith(('.xlsx', '.csv')):
            raise forms.ValidationError('Use .xlsx ou .csv. Para .xls, salve como .xlsx no Excel.')
        return arquivo


class EmprestarForm(forms.Form):
    leitor = forms.ModelChoiceField(queryset=Leitor.objects.filter(ativo=True), label='Leitor')
    prazo = forms.DateField(label='Devolver até', widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))

    def clean_prazo(self):
        prazo = self.cleaned_data['prazo']
        from django.utils import timezone
        if prazo < timezone.localdate():
            raise forms.ValidationError('Escolha hoje ou uma data futura.')
        return prazo


class ExemplarForm(forms.ModelForm):
    class Meta:
        model = LivroCopia
        fields = ['livro', 'codigo', 'editora', 'estado']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['estado'].required = True
        if self.instance.pk and self.instance.estado == 'e':
            self.fields['estado'].disabled = True
            self.fields['estado'].help_text = 'Registre a devolução na tela de empréstimos para liberar este exemplar.'
        else:
            self.fields['estado'].choices = [('d', 'Disponível'), ('m', 'Manutenção')]
        if not self.instance._state.adding:
            self.fields.pop('livro')


class PeriodoRelatorioForm(forms.Form):
    inicio = forms.DateField(label='De', widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    fim = forms.DateField(label='Até', widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))

    def clean(self):
        from django.utils import timezone
        dados = super().clean()
        inicio, fim = dados.get('inicio'), dados.get('fim')
        if inicio and fim:
            if inicio > fim:
                raise forms.ValidationError('A data inicial deve ser anterior ou igual à final.')
            if (fim - inicio).days > 730:
                raise forms.ValidationError('Selecione um período de até dois anos.')
            if fim > timezone.localdate():
                raise forms.ValidationError('A data final não pode estar no futuro.')
        return dados


class PoliticaCirculacaoForm(forms.ModelForm):
    class Meta:
        model = PoliticaCirculacao
        fields = ['prazo_padrao', 'limite_emprestimos', 'bloquear_atrasados']

    def clean_prazo_padrao(self):
        valor = self.cleaned_data['prazo_padrao']
        if not 1 <= valor <= 365:
            raise forms.ValidationError('Informe um prazo entre 1 e 365 dias.')
        return valor

    def clean_limite_emprestimos(self):
        valor = self.cleaned_data['limite_emprestimos']
        if valor > 1000:
            raise forms.ValidationError('Informe um limite entre 0 e 1000.')
        return valor
