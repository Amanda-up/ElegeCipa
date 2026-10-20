# Importações padrão
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, get_user_model
from django.contrib import messages
from django.http import HttpResponse
from django.http import JsonResponse
from django.db.models import Count, Q
from functools import wraps
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.timezone import localtime
from .forms import EleitorLoginForm, AdminLoginForm, EleicaoForm
from .models import Eleitor, Candidato, Voto, Eleicao
from .utils import hash_matricula
from .senior import (
    SeniorConnectionError,
    buscar_colaborador_por_matricula,
    buscar_colaboradores,
    dados_do_colaborador_para_login,
)
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from reportlab.lib.utils import ImageReader
import os
from django.conf import settings

User = get_user_model()


def eleitor_senior_elegivel(view_func):
    """Exige sessão criada após validação de elegibilidade na Senior."""
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        eleitor = Eleitor.objects.filter(user=request.user).first()
        if (
            not request.session.get("eleitor_senior_elegivel")
            or not eleitor
            or not eleitor.unidade
        ):
            logout(request)
            messages.error(request, "Faça login novamente para validar sua elegibilidade para votar.")
            return redirect("login")
        request.eleitor = eleitor
        return view_func(request, *args, **kwargs)

    return _wrapped


def candidatos_elegiveis_para_voto(eleicao):
    """Retorna apenas candidatos da eleição e unidade, ocultando cargos não elegíveis."""
    if not eleicao:
        return Candidato.objects.none()
    candidatos = Candidato.objects.filter(eleicao=eleicao, unidade=eleicao.unidade)
    cargos_bloqueados = Q()
    for termo in ("estag", "academ", "aprendiz", "resident"):
        cargos_bloqueados |= Q(cargo__icontains=termo)
    return candidatos.exclude(cargos_bloqueados)


def eleicao_vigente_do_eleitor(request):
    eleitor = getattr(request, "eleitor", None)
    if not eleitor or not eleitor.unidade:
        return None
    return Eleicao.objects.filter(vigente=True, unidade=eleitor.unidade).first()


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
                matricula = matricula.lstrip("0") or "0"
                cpf = eleitor_form.cleaned_data["cpf"].strip()
                try:
                    dados_senior = dados_do_colaborador_para_login(matricula)
                except SeniorConnectionError:
                    error_eleitor = "Não foi possível validar seus dados agora. Tente novamente mais tarde."
                else:
                    cpf_senior = dados_senior.get("cpf") if dados_senior else None
                    unidade_senior = dados_senior.get("unidade") if dados_senior else None
                    cpf_senior = "".join(filter(str.isdigit, str(cpf_senior or ""))).zfill(11)
                    if not cpf_senior or cpf_senior != cpf or not unidade_senior:
                        error_eleitor = "Matrícula ou CPF inválidos, ou colaborador fora da situação permitida."
                    else:
                        h_matricula = hash_matricula(matricula)
                        h_cpf = hash_matricula(cpf)
                        eleitor, _ = Eleitor.objects.get_or_create(
                            matricula_hash=h_matricula,
                            defaults={"cpf_hash": h_cpf, "unidade": unidade_senior},
                        )
                        if eleitor.cpf_hash != h_cpf or eleitor.unidade != unidade_senior:
                            eleitor.cpf_hash = h_cpf
                            eleitor.unidade = unidade_senior
                            eleitor.save(update_fields=["cpf_hash", "unidade"])
                        if not eleitor.user:
                            eleitor.user = User.objects.create(username=f"eleitor_{eleitor.id}")
                            eleitor.save(update_fields=["user"])
                        login(request, eleitor.user)
                        request.session["eleitor_senior_elegivel"] = True
                        return redirect("candidatos")

        # Login admin
        elif "username" in request.POST:
            active_tab = "admin"
            admin_form = AdminLoginForm(request, data=request.POST)
            if admin_form.is_valid():
                user = admin_form.get_user()
                if user and user.is_active and user.is_superuser:
                    login(request, user)
                    request.session.pop("eleitor_senior_elegivel", None)
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
    eleicoes_vigentes = Eleicao.objects.filter(vigente=True).order_by("unidade", "data_inicio")
    for eleicao in eleicoes_vigentes:
        eleicao.candidatos_painel = Candidato.objects.filter(
            eleicao=eleicao,
            unidade=eleicao.unidade,
        ).order_by("nome_completo")

    return render(request, 'eleicao/painel_admin.html', {
        'eleicoes_vigentes': eleicoes_vigentes,
    })


# CRUD de candidatos
@user_passes_test(is_superadmin)
def buscar_colaboradores_senior(request):
    termo = request.GET.get("q", "")
    eleicao_id = request.GET.get("eleicao_id")
    unidade = None
    if eleicao_id:
        eleicao = get_object_or_404(Eleicao, id=eleicao_id, vigente=True)
        unidade = eleicao.unidade
    if len(termo.strip()) < 2:
        return JsonResponse({"results": []})
    try:
        colaboradores = buscar_colaboradores(termo, unidade=unidade)
    except SeniorConnectionError:
        return JsonResponse(
            {"error": "Não foi possível consultar os colaboradores na Senior."},
            status=503,
        )
    return JsonResponse({
        "results": [
            {
                "matricula": pessoa["matricula"],
                "nome_completo": pessoa["nome_completo"],
                "cargo": pessoa["cargo"],
                "setor": pessoa["setor"],
                "unidade": pessoa["unidade"],
                "unidade_nome": dict(Candidato.UNIDADES).get(pessoa["unidade"], ""),
            }
            for pessoa in colaboradores
        ]
    })


@user_passes_test(is_superadmin)
def criar_candidato(request):
    eleicoes = Eleicao.objects.filter(vigente=True).order_by("unidade", "data_inicio")
    if request.method == 'POST':
        eleicao = get_object_or_404(Eleicao, id=request.POST.get('eleicao_id'), vigente=True)
        matricula = request.POST.get('matricula', '').strip()
        foto = request.FILES.get('foto')

        erro_conexao_senior = False
        try:
            colaborador = buscar_colaborador_por_matricula(matricula, unidade=eleicao.unidade)
        except SeniorConnectionError:
            messages.error(request, "Não foi possível consultar os colaboradores na Senior.")
            colaborador = None
            erro_conexao_senior = True

        if erro_conexao_senior:
            pass
        elif not colaborador:
            messages.error(request, "Selecione um colaborador trabalhando e vinculado a uma filial elegível.")
        elif not colaborador["unidade"]:
            messages.error(request, "A filial do colaborador não está mapeada para uma unidade do ElegeCIPA.")
        elif Candidato.objects.filter(matricula=colaborador["matricula"], eleicao=eleicao).exists():
            messages.error(request, "Este colaborador já está cadastrado como candidato nesta eleição.")
        else:
            Candidato.objects.create(
                matricula=colaborador["matricula"],
                nome_completo=colaborador["nome_completo"],
                cargo=colaborador["cargo"] or "Não informado",
                setor=colaborador["setor"] or "Não informado",
                unidade=colaborador["unidade"],
                foto=foto,
                eleicao=eleicao,
            )
            messages.success(request, f"Candidato {colaborador['nome_completo']} cadastrado com sucesso!")
            return redirect('painel_admin')

    return render(request, 'eleicao/criar_candidato.html', {
        'eleicoes': eleicoes,
        'selected_eleicao_id': request.POST.get('eleicao_id', request.GET.get('eleicao_id', '')),
    })

@user_passes_test(is_superadmin)
def editar_candidato(request, candidato_id):
    candidato = get_object_or_404(Candidato, id=candidato_id)
    eleicoes = Eleicao.objects.filter(vigente=True).order_by("unidade", "data_inicio")

    if request.method == 'POST':
        eleicao_id = request.POST.get('eleicao_id', candidato.eleicao_id)
        nova_eleicao = get_object_or_404(Eleicao, id=eleicao_id, vigente=True)
        # Candidatos vinculados à Senior não podem alterar seus dados funcionais manualmente.
        if candidato.matricula:
            try:
                colaborador = buscar_colaborador_por_matricula(
                    candidato.matricula,
                    unidade=nova_eleicao.unidade,
                )
            except SeniorConnectionError:
                messages.error(request, "Não foi possível validar o candidato na Senior agora.")
                return redirect('editar_candidato', candidato_id=candidato.id)

            if not colaborador:
                messages.error(request, "O candidato não pertence ao estabelecimento da eleição selecionada.")
                return redirect('editar_candidato', candidato_id=candidato.id)

            candidato.nome_completo = colaborador["nome_completo"]
            candidato.cargo = colaborador["cargo"] or "Não informado"
            candidato.setor = colaborador["setor"] or "Não informado"
            candidato.unidade = colaborador["unidade"]
        else:
            # Mantém compatibilidade com candidatos legados sem matrícula associada.
            candidato.nome_completo = request.POST.get('nome_completo', candidato.nome_completo)
            candidato.cargo = request.POST.get('cargo', candidato.cargo)
            candidato.setor = request.POST.get('setor', candidato.setor)
            candidato.unidade = request.POST.get('unidade', candidato.unidade)

        if nova_eleicao.unidade != candidato.unidade:
            messages.error(request, "O estabelecimento do candidato deve ser o mesmo da eleição.")
            return redirect('editar_candidato', candidato_id=candidato.id)
        candidato.eleicao = nova_eleicao

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

@eleitor_senior_elegivel
def candidatos(request):
    eleicao_vigente = eleicao_vigente_do_eleitor(request)
    candidatos = candidatos_elegiveis_para_voto(eleicao_vigente).order_by('nome_completo')
    
    return render(request, 'eleicao/candidatos.html', {
        'candidatos': candidatos,
        'eleicao_vigente': eleicao_vigente  # Adicione esta linha
    })

@eleitor_senior_elegivel
def confirmar_voto(request, candidato_id):
    eleicao_vigente = eleicao_vigente_do_eleitor(request)
    if not eleicao_vigente:
        messages.error(request, "Não há eleição vigente para o seu estabelecimento.")
        return redirect('candidatos')
    candidato = get_object_or_404(
        candidatos_elegiveis_para_voto(eleicao_vigente),
        id=candidato_id,
    )
    return render(request, 'eleicao/confirmar_voto.html', {'candidato': candidato})

@eleitor_senior_elegivel
def confirmar_voto_branco(request):
    # Verifica se há eleição vigente
    eleicao_vigente = eleicao_vigente_do_eleitor(request)
    if not eleicao_vigente:
        messages.error(request, "Não há eleição vigente no momento.")
        return redirect('candidatos')
    
    return render(request, 'eleicao/confirmar_voto_branco.html')

@eleitor_senior_elegivel
def registrar_voto(request, candidato_id):
    eleitor = request.eleitor
    eleicao_vigente = eleicao_vigente_do_eleitor(request)

    if not eleicao_vigente:
        messages.error(request, "Não há eleição vigente para o seu estabelecimento.")
        return redirect('candidatos')

    candidato = get_object_or_404(
        candidatos_elegiveis_para_voto(eleicao_vigente),
        id=candidato_id,
    )

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

@eleitor_senior_elegivel
def registrar_voto_branco(request):
    eleitor = request.eleitor
    eleicao_vigente = eleicao_vigente_do_eleitor(request)

    if not eleicao_vigente:
        messages.error(request, "Não há eleição vigente para o seu estabelecimento.")
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

@eleitor_senior_elegivel
def protocolo_voto(request, voto_id):
    voto = get_object_or_404(Voto, id=voto_id, eleitor__user=request.user)
    return render(request, 'eleicao/protocolo_voto.html', {'voto': voto})

# Admin extras

@user_passes_test(is_superadmin)
def criar_eleicao(request):
    form = EleicaoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        unidade = form.cleaned_data["unidade"]
        if Eleicao.objects.filter(vigente=True, unidade=unidade).exists():
            form.add_error("unidade", "Já existe uma eleição vigente para este estabelecimento.")
        else:
            eleicao = form.save(vigente=True)
            messages.success(request, f"Eleição criada para {eleicao.get_unidade_display()}!")
            return redirect('painel_admin')
    return render(request, "eleicao/criar_eleicao.html", {"form": form})

@user_passes_test(is_superadmin)
def editar_eleicao(request, eleicao_id):
    eleicao = get_object_or_404(Eleicao, id=eleicao_id)
    vigente_atual = request.POST.get("vigente") == "on" if request.method == "POST" else eleicao.vigente
    form = EleicaoForm(request.POST or None, instance=eleicao)
    if request.method == 'POST':
        vigente = request.POST.get("vigente") == "on"
        if form.is_valid():
            unidade = form.cleaned_data["unidade"]
            if unidade != eleicao.unidade and (eleicao.candidatos.exists() or eleicao.votos.exists()):
                form.add_error("unidade", "Não é possível mudar o estabelecimento depois de cadastrar candidatos ou votos.")
            elif vigente and Eleicao.objects.filter(vigente=True, unidade=unidade).exclude(pk=eleicao.pk).exists():
                form.add_error("unidade", "Já existe outra eleição vigente para este estabelecimento.")
            elif eleicao.votos.exists() and (
                form.cleaned_data["vagas_efetivos"] != eleicao.vagas_efetivos
                or form.cleaned_data["vagas_suplentes"] != eleicao.vagas_suplentes
            ):
                form.add_error(None, "As quantidades de efetivos e suplentes não podem mudar após o primeiro voto.")
            else:
                form.save(vigente=vigente)
                messages.success(request, 'Eleição atualizada com sucesso!')
                return redirect('painel_admin')
    return render(request, 'eleicao/editar_eleicao.html', {
        'eleicao': eleicao,
        'form': form,
        'vigente_atual': vigente_atual,
    })

@user_passes_test(is_superadmin)
def eleicoes_anteriores(request):
    eleicoes = Eleicao.objects.filter(vigente=False).order_by('-data_inicio', 'unidade')
    return render(request, 'eleicao/eleicoes_anteriores.html', {'eleicoes': eleicoes})

@user_passes_test(is_superadmin)
def detalhes_eleicao(request, eleicao_id):
    eleicao = get_object_or_404(Eleicao, id=eleicao_id, vigente=False)
    candidatos = eleicao.candidatos.all()
    return render(request, 'eleicao/detalhes_eleicao.html', {'eleicao': eleicao, 'candidatos': candidatos})

@user_passes_test(is_superadmin)
def escolher_eleicao_encerrar(request):
    # Busca apenas eleições vigentes
    eleicoes_vigentes = Eleicao.objects.filter(vigente=True).order_by('unidade', 'data_inicio')

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
    # Sem ID, abre a escolha quando há eleições vigentes em mais de uma unidade.
    if eleicao_id:
        eleicao = get_object_or_404(Eleicao, id=eleicao_id)
    else:
        vigentes = Eleicao.objects.filter(vigente=True).order_by("unidade")
        if vigentes.count() > 1:
            return redirect("escolher_eleicao_apurar")
        eleicao = vigentes.first()
    
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
    
    votos_da_eleicao = Voto.objects.filter(eleicao=eleicao)

    # Candidatos e votos ficam restritos ao estabelecimento da eleição.
    candidatos_com_votos = (
        Candidato.objects
        .filter(eleicao=eleicao, unidade=eleicao.unidade)
        .annotate(total_votos=Count(
            'votos',
            filter=Q(votos__eleicao=eleicao),
        ))
        .filter(total_votos__gt=0)
        .order_by('-total_votos', 'nome_completo')
    )
    
    # Candidatos sem votos
    candidatos_sem_votos = (
        Candidato.objects
        .filter(eleicao=eleicao, unidade=eleicao.unidade)
        .annotate(total_votos=Count(
            'votos',
            filter=Q(votos__eleicao=eleicao),
        ))
        .filter(total_votos=0)
        .order_by('nome_completo')
    )
    
    # CORREÇÃO: Calcular totais de votos
    votos_brancos = votos_da_eleicao.filter(voto_branco=True).count()
    
    total_votos = votos_da_eleicao.count()
    votos_validos = total_votos - votos_brancos
    total_eleitores = Eleitor.objects.filter(unidade=eleicao.unidade).count()

    eleitos = candidatos_com_votos[:eleicao.vagas_efetivos]
    suplentes_inicio = eleicao.vagas_efetivos
    suplentes = candidatos_com_votos[suplentes_inicio:suplentes_inicio + eleicao.vagas_suplentes]
    
    # Não eleitos = resto dos candidatos com votos + todos os candidatos sem votos
    classificados = eleicao.vagas_efetivos + eleicao.vagas_suplentes
    nao_eleitos = list(candidatos_com_votos[classificados:]) + list(candidatos_sem_votos)

    return render(request, 'eleicao/apuracao_votos.html', {
        'eleitos': eleitos,
        'suplentes': suplentes,
        'nao_eleitos': nao_eleitos,
        'votos_brancos': votos_brancos,
        'votos_validos': votos_validos, 
        'total_votos': total_votos,      
        'total_eleitores': total_eleitores,
        'eleicao_atual': eleicao
    })

@user_passes_test(is_superadmin)
def escolher_eleicao_apurar(request):
    # Busca todas as eleições (vigentes e encerradas)
    eleicoes = Eleicao.objects.all().order_by('-data_inicio', 'unidade')

    if request.method == "POST":
        eleicao_id = request.POST.get("eleicao_id")
        if eleicao_id:
            return redirect('apuracao_votos_especifica', eleicao_id=eleicao_id)
        else:
            messages.error(request, "Selecione uma eleição para apurar.")

    return render(request, "eleicao/escolher_eleicao_apurar.html", {
        "eleicoes": eleicoes
    })

@user_passes_test(is_superadmin)
def gerar_extrato_pdf(request, eleicao_id=None):
    if eleicao_id:
        eleicao = get_object_or_404(Eleicao, id=eleicao_id)
    else:
        vigentes = Eleicao.objects.filter(vigente=True).order_by("unidade")
        if vigentes.count() > 1:
            return redirect("escolher_eleicao_apurar")
        eleicao = vigentes.first()
    
    if eleicao:
        # CORREÇÃO: Filtrar pela relação direta com a eleição, não apenas pelas datas
        votos = Voto.objects.filter(
            eleicao=eleicao,
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
    total_eleitores = Eleitor.objects.filter(unidade=eleicao.unidade).count() if eleicao else 0
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
    unidade_texto = eleicao.get_unidade_display() if eleicao else "Todas as unidades"
    p.drawString(cabecalho_x, altura - 2 * cm, f"Extrato CIPA - {unidade_texto} - {periodo_texto}")
    
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
