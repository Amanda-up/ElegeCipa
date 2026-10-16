from django import forms
from django.contrib.auth.forms import AuthenticationForm

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
