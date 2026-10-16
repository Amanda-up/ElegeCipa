from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='landing'),
    path("login/", views.login_view, name="login"),
    path('logout/', views.logout_view, name='logout'),

    path("candidatos/", views.candidatos, name="candidatos"),
    path('confirmar_voto/<int:candidato_id>/', views.confirmar_voto, name='confirmar_voto'),
    path('registrar_voto/<int:candidato_id>/', views.registrar_voto, name='registrar_voto'),
    path('confirmar-voto-branco/', views.confirmar_voto_branco, name='confirmar_voto_branco'),
    path('registrar-voto-branco/', views.registrar_voto_branco, name='registrar_voto_branco'),
    path('protocolo_voto/<int:voto_id>/', views.protocolo_voto, name='protocolo_voto'),

    path("painel_admin/", views.painel_admin, name="painel_admin"),
    path("apuracao_votos/", views.apuracao_votos, name="apuracao_votos"),
    path("apuracao_votos/pdf/", views.gerar_extrato_pdf, name='gerar_extrato_pdf'),
    path('apuracao-votos/', views.apuracao_votos, name='apuracao_votos'),
    path('apuracao-votos/<int:eleicao_id>/', views.apuracao_votos, name='apuracao_votos_especifica'),
    path('escolher-eleicao-apurar/', views.escolher_eleicao_apurar, name='escolher_eleicao_apurar'),
    # PDF geral (eleição vigente)
    path('gerar-extrato-pdf/', views.gerar_extrato_pdf, name='gerar_extrato_pdf'),
    
    # PDF específico para uma eleição
    path('gerar-extrato-pdf/<int:eleicao_id>/', views.gerar_extrato_pdf, name='gerar_extrato_pdf_especifico'),
    path("criar_eleicao/", views.criar_eleicao, name="criar_eleicao"),
    path('eleicao/editar/<int:eleicao_id>/', views.editar_eleicao, name='editar_eleicao'),
    path("eleicoes_anteriores/", views.eleicoes_anteriores, name="eleicoes_anteriores"),
    path("detalhes_eleicao/<int:eleicao_id>/", views.detalhes_eleicao, name="detalhes_eleicao"),
    path('eleicao/encerrar/', views.escolher_eleicao_encerrar, name='escolher_eleicao_encerrar'),
    path('eleicao/encerrar/<int:eleicao_id>/', views.encerrar_eleicao, name='encerrar_eleicao'),
    path("candidato/criar/", views.criar_candidato, name="criar_candidato"),
    path("candidato/editar/<int:candidato_id>/", views.editar_candidato, name="editar_candidato"),
    path("candidato/deletar/<int:candidato_id>/", views.deletar_candidato, name="deletar_candidato"),
]
