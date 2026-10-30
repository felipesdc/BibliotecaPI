from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, SetPasswordForm

from .models import PerfilAcesso


class CriarUsuarioForm(UserCreationForm):
    papel = forms.ChoiceField(label='Perfil', choices=[('', 'Selecione um perfil')] + list(PerfilAcesso.Papel.choices))

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ['username', 'first_name', 'last_name', 'email', 'papel', 'password1', 'password2']
        labels = {'username': 'Nome de acesso', 'first_name': 'Nome', 'last_name': 'Sobrenome', 'email': 'E-mail (opcional)'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['password1'].label = 'Senha temporária'
        self.fields['password2'].label = 'Repita a senha temporária'

    def clean_username(self):
        nome = self.cleaned_data['username']
        if get_user_model().objects.filter(username__iexact=nome).exists():
            raise forms.ValidationError('Esse nome de acesso já está em uso.')
        return nome


class EditarUsuarioForm(forms.ModelForm):
    papel = forms.ChoiceField(label='Perfil', choices=PerfilAcesso.Papel.choices)
    versao = forms.IntegerField(widget=forms.HiddenInput)

    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'email', 'papel']
        labels = {'first_name': 'Nome', 'last_name': 'Sobrenome', 'email': 'E-mail (opcional)'}

    def __init__(self, *args, proprio=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['papel'].disabled = proprio


class RedefinirSenhaForm(SetPasswordForm):
    versao = forms.IntegerField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].label = 'Nova senha temporária'
        self.fields['new_password2'].label = 'Repita a senha temporária'


class AlterarSituacaoForm(forms.Form):
    versao = forms.IntegerField(widget=forms.HiddenInput)
