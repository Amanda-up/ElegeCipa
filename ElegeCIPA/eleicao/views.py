# Importações padrão
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, get_user_model
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Count
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.timezone import localtime
from .forms import EleitorLoginForm, AdminLoginForm
from .models import Eleitor, Candidato, Voto, Eleicao
from .utils import hash_matricula
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from reportlab.lib.utils import ImageReader
import os
from django.conf import settings

User = get_user_model()


# Login

def login_view(request):
    eleitor_form = EleitorLoginForm()
    admin_form = AdminLoginForm(request, data=request.POST or None)
    error_eleitor = error_admin = None
    active_tab = "eleitor"

    if request.method == "POST":
        # Login eleitor
        if "matricula" in request.POST and "cpf" in request.POST:
            active_tab = "eleitor"
            eleitor_form = EleitorLoginForm(request.POST)
            if eleitor_form.is_valid():
                matricula = eleitor_form.cleaned_data["matricula"].strip()
                cpf = eleitor_form.cleaned_data["cpf"].strip()
                h_matricula = hash_matricula(matricula)
                h_cpf = hash_matricula(cpf)

                try:
                    eleitor = Eleitor.objects.get(matricula_hash=h_matricula, cpf_hash=h_cpf)
                    if not eleitor.user:
                        user = User.objects.create(username=f"eleitor_{eleitor.id}")
                        eleitor.user = user
                        eleitor.save()
                    login(request, eleitor.user)

                    # CORREÇÃO: Redirecionar para a URL 'candidatos' em vez de renderizar o template
                    return redirect("candidatos")  # MUDANÇA AQUI
                    
                except Eleitor.DoesNotExist:
                    error_eleitor = "Matrícula ou CPF inválidos."

        # Login admin
        elif "username" in request.POST:
            active_tab = "admin"
            admin_form = AdminLoginForm(request, data=request.POST)
            if admin_form.is_valid():
                user = admin_form.get_user()
                if user and user.is_active and user.is_superuser:
                    login(request, user)
                    return redirect("painel_admin")
                error_admin = "Usuário/senha incorretos ou sem permissão."
            else:
                error_admin = "Preencha todos os campos corretamente."

    return render(request, "eleicao/login.html", {
        "eleitor_form": eleitor_form,
        "admin_form": admin_form,
        "error_eleitor": error_eleitor,
        "error_admin": error_admin,
        "active_tab": active_tab,
    })

# Checagem de superadmin

def is_superadmin(user):
    return user.is_superuser


# Painel Admin

@user_passes_test(is_superadmin)
def painel_admin(request):
    # Eleição vigente
    eleicao_vigente = Eleicao.objects.filter(vigente=True).first()

    # Consulta candidatos da eleição vigente
    candidatos = Candidato.objects.filter(eleicao=eleicao_vigente).order_by('nome_completo') if eleicao_vigente else []

    return render(request, 'eleicao/painel_admin.html', {
        'candidatos': candidatos,
        'eleicao_atual': eleicao_vigente,
        'eleicao_vigente': eleicao_vigente
    })


# CRUD de candidatos
@user_passes_test(is_superadmin)
def criar_candidato(request):
    if request.method == 'POST':
        eleicao_id = request.POST.get('eleicao_id')
        eleicao = get_object_or_404(Eleicao, id=eleicao_id)

        nome_completo = request.POST.get('nome_completo')
        cargo = request.POST.get('cargo')
        setor = request.POST.get('setor')
        unidade = request.POST.get('unidade') or "HE"
        foto = request.FILES.get('foto')

        if not nome_completo or not cargo or not setor:
            messages.error(request, "Preencha todos os campos obrigatórios.")
            return redirect('criar_candidato')

        Candidato.objects.create(
            nome_completo=nome_completo,
            cargo=cargo,
            setor=setor,
            unidade=unidade,
            foto=foto,
            eleicao=eleicao
        )
        messages.success(request, f"Candidato {nome_completo} cadastrado com sucesso!")
        return redirect('painel_admin')

    # Apenas eleições vigentes
    eleicoes = Eleicao.objects.filter(vigente=True).order_by('-data_inicio')
    return render(request, 'eleicao/criar_candidato.html', {'eleicoes': eleicoes})

@user_passes_test(is_superadmin)
def editar_candidato(request, candidato_id):
    candidato = get_object_or_404(Candidato, id=candidato_id)
    eleicoes = Eleicao.objects.all()  # Todas as eleições para o select

    if request.method == 'POST':
        # Atualiza os campos do candidato
        candidato.nome_completo = request.POST.get('nome_completo', candidato.nome_completo)
        candidato.cargo = request.POST.get('cargo', candidato.cargo)
        candidato.setor = request.POST.get('setor', candidato.setor)
        candidato.unidade = request.POST.get('unidade', candidato.unidade)

        # Atualiza a eleição vinculada
        eleicao_id = request.POST.get('eleicao_id')
        if eleicao_id:
            candidato.eleicao = Eleicao.objects.get(id=eleicao_id)

        # Atualiza foto apenas se enviada
        if request.FILES.get('foto'):
            candidato.foto = request.FILES['foto']

        candidato.save()
        messages.success(request, 'Candidato atualizado com sucesso!')
        return redirect('painel_admin')

    # Renderiza o template passando os dados do candidato e as eleições
    return render(request, 'eleicao/editar_candidato.html', {
        'candidato': candidato,
        'eleicoes': eleicoes
    })

@user_passes_test(is_superadmin)
def deletar_candidato(request, candidato_id):
    candidato = get_object_or_404(Candidato, id=candidato_id)
    candidato.delete()
    messages.success(request, 'Candidato removido com sucesso!')
    return redirect('painel_admin')


# Logout

@require_POST
def logout_view(request):
    logout(request)
    return redirect('landing')


# Views públicas

def home(request):
    return render(request, "eleicao/landing.html")


# Eleitores

@login_required
def candidatos(request):
    eleicao_vigente = Eleicao.objects.filter(vigente=True).first()
    candidatos = Candidato.objects.filter(eleicao=eleicao_vigente).order_by('nome_completo') if eleicao_vigente else []
    
    return render(request, 'eleicao/candidatos.html', {
        'candidatos': candidatos,
        'eleicao_vigente': eleicao_vigente  # Adicione esta linha
    })

@login_required
def confirmar_voto(request, candidato_id):
    candidato = get_object_or_404(Candidato, id=candidato_id)
    return render(request, 'eleicao/confirmar_voto.html', {'candidato': candidato})

@login_required
def confirmar_voto_branco(request):
    # Verifica se há eleição vigente
    eleicao_vigente = Eleicao.objects.filter(vigente=True).first()
    if not eleicao_vigente:
        messages.error(request, "Não há eleição vigente no momento.")
        return redirect('candidatos')
    
    return render(request, 'eleicao/confirmar_voto_branco.html')

@login_required
def registrar_voto(request, candidato_id):
    eleitor = get_object_or_404(Eleitor, user=request.user)
    candidato = get_object_or_404(Candidato, id=candidato_id)
    eleicao_vigente = Eleicao.objects.filter(vigente=True).first()

    if not eleicao_vigente:
        messages.error(request, "Não há eleição vigente no momento.")
        return redirect('candidatos')

    # CORREÇÃO: Verifica se já votou nesta eleição específica
    if Voto.objects.filter(eleitor=eleitor, eleicao=eleicao_vigente).exists():
        return render(request, "eleicao/confirmar_voto.html", {
            "candidato": candidato,
            "mensagem_alert": "Você já votou nesta eleição! Você será deslogado.",
            "logout_after": True
        })

    # CORREÇÃO: Cria voto com a eleição
    voto = Voto.objects.create(
        eleitor=eleitor,
        candidato=candidato,
        eleicao=eleicao_vigente,  # NOVO
        data_hora=timezone.now()
    )

    return render(request, "eleicao/protocolo_voto.html", {"voto": voto})

@login_required
def registrar_voto_branco(request):
    eleitor = get_object_or_404(Eleitor, user=request.user)
    eleicao_vigente = Eleicao.objects.filter(vigente=True).first()

    if not eleicao_vigente:
        messages.error(request, "Não há eleição vigente no momento.")
        return redirect('candidatos')

    # CORREÇÃO: Verifica se já votou nesta eleição específica
    if Voto.objects.filter(eleitor=eleitor, eleicao=eleicao_vigente).exists():
        return render(request, "eleicao/confirmar_voto_branco.html", {
            "mensagem_alert": "Você já votou nesta eleição! Você será deslogado.",
            "logout_after": True
        })

    # CORREÇÃO: Cria voto em branco com a eleição
    voto = Voto.objects.create(
        eleitor=eleitor,
        candidato=None,
        eleicao=eleicao_vigente,  # NOVO
        voto_branco=True
    )

    return render(request, "eleicao/protocolo_voto.html", {"voto": voto})

@login_required
def protocolo_voto(request, voto_id):
    voto = get_object_or_404(Voto, id=voto_id, eleitor__user=request.user)
    return render(request, 'eleicao/protocolo_voto.html', {'voto': voto})

# Admin extras

@user_passes_test(is_superadmin)
def criar_eleicao(request):
    # Verifica se já existe eleição vigente
    eleicao_atual = Eleicao.objects.filter(vigente=True).first()
    if eleicao_atual:
        # Retorna o template com alerta
        return render(request, "eleicao/criar_eleicao.html", {
            "alert_msg": "Existe eleição em andamento, gentileza encerrar antes de criar uma nova.",
            "eleicao_atual": eleicao_atual
        })

    if request.method == "POST":
        data_inicio = request.POST.get("data_inicio")
        data_fim = request.POST.get("data_fim")

        # Cria a nova eleição como vigente
        eleicao = Eleicao.objects.create(
            data_inicio=data_inicio,
            data_fim=data_fim,
            vigente=True
        )
        messages.success(request, f"Eleição criada com sucesso! ID: {eleicao.id}")
        return redirect('painel_admin')

    return render(request, "eleicao/criar_eleicao.html")

@user_passes_test(is_superadmin)
def editar_eleicao(request, eleicao_id):
    eleicao = get_object_or_404(Eleicao, id=eleicao_id)

    if request.method == 'POST':
        eleicao.data_inicio = request.POST.get('data_inicio', eleicao.data_inicio)
        eleicao.data_fim = request.POST.get('data_fim', eleicao.data_fim)
        vigente = request.POST.get("vigente") == "on"

        # CORREÇÃO: Só desmarca outras eleições se esta estiver sendo marcada como vigente
        if vigente and not eleicao.vigente:
            Eleicao.objects.exclude(id=eleicao_id).update(vigente=False)

        eleicao.vigente = vigente
        eleicao.save()
        messages.success(request, 'Eleição atualizada com sucesso!')
        return redirect('painel_admin')

    return render(request, 'eleicao/editar_eleicao.html', {'eleicao': eleicao})

@user_passes_test(is_superadmin)
def eleicoes_anteriores(request):
    eleicoes = Eleicao.objects.filter(vigente=False).order_by('-data_inicio')
    return render(request, 'eleicao/eleicoes_anteriores.html', {'eleicoes': eleicoes})

@user_passes_test(is_superadmin)
def detalhes_eleicao(request, eleicao_id):
    eleicao = get_object_or_404(Eleicao, id=eleicao_id, vigente=False)
    candidatos = eleicao.candidatos.all()
    return render(request, 'eleicao/detalhes_eleicao.html', {'eleicao': eleicao, 'candidatos': candidatos})

@user_passes_test(is_superadmin)
def escolher_eleicao_encerrar(request):
    # Busca apenas eleições vigentes
    eleicoes_vigentes = Eleicao.objects.filter(vigente=True).order_by('data_inicio')

    if request.method == "POST":
        eleicao_id = request.POST.get("eleicao_id")
        return redirect('encerrar_eleicao', eleicao_id=eleicao_id)

    return render(request, "eleicao/escolher_eleicao_encerrar.html", {
        "eleicoes_ativas": eleicoes_vigentes
    })

@user_passes_test(is_superadmin)
def encerrar_eleicao(request, eleicao_id):
    eleicao = get_object_or_404(Eleicao, id=eleicao_id)

    if request.method == "POST":
        # Atualiza a eleição para não vigente e atualiza data de fim
        eleicao.vigente = False
        eleicao.data_fim = timezone.now()
        eleicao.save()
        messages.success(request, f"Eleição ID {eleicao.id} encerrada com sucesso!")
        
        # CORREÇÃO: Use a URL correta para apuração com parâmetro
        return redirect('apuracao_votos_especifica', eleicao_id=eleicao.id)

    return render(request, "eleicao/confirmar_encerramento.html", {
        "eleicao": eleicao
    })

@user_passes_test(is_superadmin)
def apuracao_votos(request, eleicao_id=None):
    # Se não foi passado um ID específico, busca a eleição vigente
    if eleicao_id:
        eleicao = get_object_or_404(Eleicao, id=eleicao_id)
    else:
        eleicao = Eleicao.objects.filter(vigente=True).first()
    
    if not eleicao:
        return render(request, 'eleicao/apuracao_votos.html', {
            'eleitos': [],
            'suplementes': [],
            'nao_eleitos': [],
            'votos_brancos': 0,
            'votos_validos': 0,
            'total_votos': 0,
            'eleicao_atual': None
        })
    
    # Candidatos com votos
    candidatos_com_votos = (
        Candidato.objects
        .filter(eleicao=eleicao)
        .annotate(total_votos=Count('votos'))
        .filter(total_votos__gt=0)
        .order_by('-total_votos', 'nome_completo')
    )
    
    # Candidatos sem votos
    candidatos_sem_votos = (
        Candidato.objects
        .filter(eleicao=eleicao)
        .annotate(total_votos=Count('votos'))
        .filter(total_votos=0)
        .order_by('nome_completo')
    )
    
    # CORREÇÃO: Calcular totais de votos
    votos_brancos = Voto.objects.filter(
        voto_branco=True,
        eleicao=eleicao
    ).count()
    
    total_votos = Voto.objects.filter(eleicao=eleicao).count()
    votos_validos = total_votos - votos_brancos

    # 6 mais votados são eleitos, 4 seguintes são suplentes
    eleitos = candidatos_com_votos[:6]
    suplentes = candidatos_com_votos[6:10]
    
    # Não eleitos = resto dos candidatos com votos + todos os candidatos sem votos
    nao_eleitos = list(candidatos_com_votos[10:]) + list(candidatos_sem_votos)

    return render(request, 'eleicao/apuracao_votos.html', {
        'eleitos': eleitos,
        'suplentes': suplentes,
        'nao_eleitos': nao_eleitos,
        'votos_brancos': votos_brancos,
        'votos_validos': votos_validos, 
        'total_votos': total_votos,      
        'eleicao_atual': eleicao
    })

@user_passes_test(is_superadmin)
def escolher_eleicao_apurar(request):
    # Busca todas as eleições (vigentes e encerradas)
    eleicoes = Eleicao.objects.all().order_by('-data_inicio')

    if request.method == "POST":
        eleicao_id = request.POST.get("eleicao_id")
        if eleicao_id:
            return redirect('apuracao_votos_especifica', eleicao_id=eleicao_id)
        else:
            messages.error(request, "Selecione uma eleição para apurar.")

    return render(request, "eleicao/escolher_eleicao_apurar.html", {
        "eleicoes": eleicoes
    })

@login_required
def gerar_extrato_pdf(request, eleicao_id=None):
    if eleicao_id:
        eleicao = get_object_or_404(Eleicao, id=eleicao_id)
    else:
        eleicao = Eleicao.objects.filter(vigente=True).first()
    
    if eleicao:
        # CORREÇÃO: Filtrar pela relação direta com a eleição, não apenas pelas datas
        votos = Voto.objects.filter(
            eleicao=eleicao  # CORREÇÃO AQUI - usar o campo eleicao
        ).select_related('eleitor', 'candidato').order_by('data_hora')
        
        periodo_texto = f"{eleicao.data_inicio.strftime('%d/%m/%Y')} a {eleicao.data_fim.strftime('%d/%m/%Y')}"
        nome_arquivo = f"Apuracao_CIPA_{eleicao.data_inicio.strftime('%d_%m_%Y')}_{eleicao.data_fim.strftime('%d_%m_%Y')}.pdf"
        
        # DEBUG: Verificar quantos votos foram encontrados
        print(f"📊 PDF - Eleição {eleicao.id}: {votos.count()} votos encontrados")
    else:
        votos = Voto.objects.select_related('eleitor', 'candidato').order_by('data_hora')
        periodo_texto = "Período não especificado"
        nome_arquivo = "Apuracao_CIPA_geral.pdf"

    # Cálculos dos totais
    total_votos = votos.count()
    votos_brancos = votos.filter(voto_branco=True).count()
    votos_validos = total_votos - votos_brancos
    total_eleitores = Eleitor.objects.count()
    porcentagem_votos = (total_votos / total_eleitores * 100) if total_eleitores > 0 else 0

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{nome_arquivo}"'

    p = canvas.Canvas(response, pagesize=A4)
    largura, altura = A4

    try:
        logo_path = os.path.join(
            settings.BASE_DIR, 
            'ElegeCIPA', 'eleicao', 'static', 'eleicao', 'img', 'logo.png'
        )
        
        if os.path.exists(logo_path):
            logo = ImageReader(logo_path)
            p.drawImage(logo, 0.5 * cm, altura - 2.5 * cm, width=2.5 * cm, height=2.5 * cm, preserveAspectRatio=True)
            cabecalho_x = 3.5 * cm
        else:
            cabecalho_x = 2 * cm
    except Exception as e:
        cabecalho_x = 2 * cm

    p.setFont("Helvetica-Bold", 14)
    p.drawString(cabecalho_x, altura - 2 * cm, f"Extrato de Votos - Eleições CIPA {periodo_texto}")
    
    p.setFont("Helvetica-Bold", 11)
    y = altura - 3.5 * cm
    p.drawString(1 * cm, y, "#")
    p.drawString(2 * cm, y, "Data / Hora")
    p.drawString(7 * cm, y, "Candidato")
    p.drawString(14 * cm, y, "Protocolo")
    y -= 0.5 * cm
    p.setFont("Helvetica", 10)

    numero_linha = 1
    for voto in votos:
        data_local = localtime(voto.data_hora)
        texto_data = data_local.strftime('%d/%m/%Y %H:%M:%S')
        
        if voto.voto_branco:
            texto_candidato = "Voto em Branco"
        else:
            texto_candidato = voto.candidato.nome_completo if voto.candidato else "Candidato não encontrado"
            
        texto_protocolo = voto.protocolo

        p.drawString(1 * cm, y, f"{numero_linha}.")
        p.drawString(2 * cm, y, texto_data)
        p.drawString(7 * cm, y, texto_candidato)
        p.drawString(14 * cm, y, texto_protocolo)
        
        y -= 0.5 * cm
        numero_linha += 1

        if y < 2 * cm:
            p.showPage()
            y = altura - 2 * cm
            p.setFont("Helvetica", 10)
            
            p.setFont("Helvetica-Bold", 11)
            p.drawString(1 * cm, y, "#")
            p.drawString(2 * cm, y, "Data / Hora")
            p.drawString(7 * cm, y, "Candidato")
            p.drawString(14 * cm, y, "Protocolo")
            y -= 0.5 * cm
            p.setFont("Helvetica", 10)

    if y < 3 * cm:
        p.showPage()
        y = altura - 2 * cm
        p.setFont("Helvetica", 10)

    # RESUMO ESTATÍSTICO - NOVO
    p.setFont("Helvetica-Bold", 12)
    p.drawString(2 * cm, y - 1 * cm, "RESUMO DA ELEIÇÃO")
    
    p.setFont("Helvetica-Bold", 11)
    p.drawString(2 * cm, y - 1.7 * cm, f"Total de votos: {total_votos}")
    p.drawString(2 * cm, y - 2.4 * cm, f"Total de votos válidos: {votos_validos}")
    p.drawString(2 * cm, y - 3.1 * cm, f"Total de votos em branco: {votos_brancos}")
    p.drawString(2 * cm, y - 3.8 * cm, f"Participação dos eleitores: {porcentagem_votos:.2f}%")
    
    if eleicao:
        p.drawString(2 * cm, y - 4.5 * cm, f"Período da eleição: {periodo_texto}")

    p.save()
    return response