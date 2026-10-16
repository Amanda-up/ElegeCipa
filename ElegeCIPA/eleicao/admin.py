from django.contrib import admin
from .models import Candidato, Voto, Eleicao

admin.site.register(Candidato)
admin.site.register(Voto)
admin.site.register(Eleicao)