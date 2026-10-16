import random, string
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Eleicao(models.Model):
    data_inicio = models.DateTimeField("Data de Início")
    data_fim = models.DateTimeField("Data de Fim")
    criada_em = models.DateTimeField(auto_now_add=True)
    vigente = models.BooleanField(default=False, verbose_name="Eleição Vigente")

    def save(self, *args, **kwargs):
        if self.vigente:
            Eleicao.objects.exclude(pk=self.pk).update(vigente=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Eleição {self.id} ({self.data_inicio.date()} - {self.data_fim.date()})"

    class Meta:
        verbose_name = "Eleição"
        verbose_name_plural = "Eleições"
        ordering = ['-data_inicio']


class Eleitor(models.Model):
    matricula_hash = models.CharField("Hash da Matrícula", max_length=64, unique=True)
    cpf_hash = models.CharField("Hash do CPF", max_length=64, unique=True, null=True, blank=True)
    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.matricula_hash[:8]

class Candidato(models.Model):
    UNIDADES = [
        ('HE', 'Hospital Evangélico'),
        ('LAB', 'Laboratório'),
        ('CORP', 'Corporativo'),
        ('CNBH', 'Centro de Nefrologia Contorno'),
        ('CNVN', 'Centro de Nefrologia Venda Nova'),
        ('CNCT', 'Centro de Nefrologia Contagem'),
        ('CESP', 'Centro de Especialidades'),
    ]

    nome_completo = models.CharField(max_length=120)
    cargo = models.CharField(max_length=100)
    setor = models.CharField(max_length=100)
    unidade = models.CharField(max_length=10, choices=UNIDADES)
    foto = models.ImageField(upload_to='candidatos/', blank=True, null=True)
    eleicao = models.ForeignKey(Eleicao, on_delete=models.CASCADE, related_name='candidatos')
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome_completo} ({self.eleicao})"

class Voto(models.Model):
    eleitor = models.ForeignKey(Eleitor, on_delete=models.CASCADE, related_name='votos')  # MUDANÇA: OneToOne para ForeignKey
    candidato = models.ForeignKey(Candidato, on_delete=models.CASCADE, related_name='votos', null=True, blank=True)
    eleicao = models.ForeignKey(Eleicao, on_delete=models.CASCADE, related_name='votos')  # NOVO CAMPO
    data_hora = models.DateTimeField(default=timezone.now)
    protocolo = models.CharField("Protocolo do Voto", max_length=20, unique=True, editable=False)
    voto_branco = models.BooleanField(default=False, verbose_name="Voto em Branco")

    class Meta:
        verbose_name = "Voto"
        verbose_name_plural = "Votos"
        ordering = ['-data_hora']
        # ADICIONE ESTA CONSTRAINT PARA GARANTIR 1 VOTO POR ELEITOR POR ELEIÇÃO
        constraints = [
            models.UniqueConstraint(fields=['eleitor', 'eleicao'], name='voto_unico_por_eleicao')
        ]

    def save(self, *args, **kwargs):
        if not self.protocolo:
            ano = self.data_hora.year
            aleatorio = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            self.protocolo = f"CIPA{ano}{aleatorio}"
        super().save(*args, **kwargs)

    def __str__(self):
        if self.voto_branco:
            return f"{self.eleitor.matricula_hash[:8]} -> VOTO EM BRANCO - {self.eleicao} ({self.protocolo})"
        return f"{self.eleitor.matricula_hash[:8]} -> {self.candidato.nome_completo} - {self.eleicao} ({self.protocolo})"

    @property
    def candidato_nome(self):
        """Retorna o nome do candidato ou 'Voto em Branco'"""
        if self.voto_branco:
            return "Voto em Branco"
        return self.candidato.nome_completo if self.candidato else "Candidato não encontrado"