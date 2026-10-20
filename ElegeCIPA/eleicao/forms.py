from django import forms
from django.contrib.auth.forms import AuthenticationForm
from datetime import datetime, time
from django.utils import timezone
from .models import Eleicao
from .unidades import UNIDADES_ELEITORAIS

class EleitorLoginForm(forms.Form):
    matricula = forms.CharField(
        label="Matrícula",
        max_length=20,
        widget=forms.TextInput(attrs={
            "class": "mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm "
                     "focus:border-[#004876] focus:ring-[#004876] sm:text-sm",
            "placeholder": "Digite sua matrícula"
        })
    )
    cpf = forms.RegexField(
        label="CPF",
        regex=r'^\d{11}$',
        max_length=11,
        error_messages={
            "invalid": "Digite apenas números, com 11 dígitos."
        },
        widget=forms.PasswordInput(attrs={
            "class": "mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm "
                    "focus:border-[#004876] focus:ring-[#004876] sm:text-sm",
            "placeholder": "Digite seu CPF",
            "inputmode": "numeric"
        })
    )

class AdminLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Usuário",
        widget=forms.TextInput(attrs={
            "class": "mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm "
                     "focus:border-[#004876] focus:ring-[#004876] sm:text-sm",
            "placeholder": "Usuário"
        })
    )
    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={
            "class": "mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm "
                     "focus:border-[#004876] focus:ring-[#004876] sm:text-sm",
            "placeholder": "Senha"
        })
    )


class EleicaoForm(forms.Form):
    data_inicio = forms.DateField(
        label="Data de início",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    data_fim = forms.DateField(
        label="Data de fim",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    unidade = forms.ChoiceField(label="Estabelecimento", choices=UNIDADES_ELEITORAIS)
    vagas_efetivos = forms.IntegerField(label="Quantidade de efetivos", min_value=0)
    vagas_suplentes = forms.IntegerField(label="Quantidade de suplentes", min_value=0)

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        initial = kwargs.setdefault("initial", {})
        if instance:
            initial.setdefault("data_inicio", instance.data_inicio.date())
            initial.setdefault("data_fim", instance.data_fim.date())
            initial.setdefault("unidade", instance.unidade)
            initial.setdefault("vagas_efetivos", instance.vagas_efetivos)
            initial.setdefault("vagas_suplentes", instance.vagas_suplentes)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        inicio = cleaned.get("data_inicio")
        fim = cleaned.get("data_fim")
        if inicio and fim and fim < inicio:
            self.add_error("data_fim", "A data de fim deve ser igual ou posterior à data de início.")
        return cleaned

    def save(self, *, vigente, commit=True):
        election = self.instance or Eleicao()
        election.data_inicio = timezone.make_aware(datetime.combine(self.cleaned_data["data_inicio"], time.min))
        election.data_fim = timezone.make_aware(datetime.combine(self.cleaned_data["data_fim"], time.min))
        election.unidade = self.cleaned_data["unidade"]
        election.vagas_efetivos = self.cleaned_data["vagas_efetivos"]
        election.vagas_suplentes = self.cleaned_data["vagas_suplentes"]
        election.vigente = vigente
        if commit:
            election.save()
        return election
