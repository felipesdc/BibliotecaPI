import datetime

from django import forms

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

class RenovacaoEmprestimoForm(forms.Form):
    data_renovacao = forms.DateField(help_text="Insira uma data entre hoje e daqui a 4 semanas (padrão 3).")

    def limpar_data_renovacao(self):
        data = self.cleaned_data['data_renovacao']

        # Check if a date is not in the past.
        if data < datetime.date.today():
            raise ValidationError(_('Data inválida - renovação passada'))

        # Check if a date is in the allowed range (+4 weeks from today).
        if data > datetime.date.today() + datetime.timedelta(weeks=4):
            raise ValidationError(_('Data inválida - renovação para mais do que 4 semanas a frente'))

        # Remember to always return the cleaned data.
        return data
