# ElegeCIPA

Aplicação web para administrar eleições da CIPA. Permite cadastrar eleições e candidatos, autenticar eleitores, registrar votos (inclusive em branco), acompanhar a apuração, gerar extratos em PDF e importar eleitores de planilhas.

## Índice

- [Tecnologias](#tecnologias)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Requisitos](#requisitos)
- [Instalação e configuração](#instalação-e-configuração)
- [Criar o banco PostgreSQL](#criar-o-banco-postgresql)
- [Executar localmente](#executar-localmente)
- [Importar eleitores](#importar-eleitores)
- [Arquivos estáticos e mídia](#arquivos-estáticos-e-mídia)
- [Implantação](#implantação)

## Tecnologias

- Python e Django
- PostgreSQL
- WhiteNoise para arquivos estáticos
- Pandas e openpyxl para importação de planilhas
- ReportLab para gerar PDFs

## Estrutura do projeto

```text
ElegeCIPA-main/                         # raiz do repositório
├── manage.py                           # comandos Django
├── requirements.txt                    # dependências Python
├── .env.example                        # exemplo de configuração local
├── ConexaoSQL.py                       # conexão somente de leitura com SQL Server/Senior
├── Procfile                            # comando de inicialização para hospedagem
├── README.md                           # documentação do projeto
├── media/                              # arquivos enviados (ex.: fotos)
├── staticfiles/                        # arquivos estáticos coletados
└── ElegeCIPA/                           # configuração do projeto Django
    ├── settings.py                     # configurações, banco, estáticos e segurança
    ├── urls.py                         # rotas principais e admin
    ├── asgi.py / wsgi.py               # pontos de entrada para servidores
    ├── eleicao/                         # aplicação de eleições
    │   ├── models.py                    # Eleicao, Eleitor, Candidato e Voto
    │   ├── views.py                     # páginas e regras dos fluxos
    │   ├── senior.py                    # consulta de colaboradores e mapeamento das filiais
    │   ├── unidades.py                  # agrupamento de filiais em estabelecimentos eleitorais
    │   ├── forms.py                     # formulários
    │   ├── urls.py                      # rotas da aplicação
    │   ├── admin.py                     # integração com Django Admin
    │   ├── migrations/                  # migrações do banco
    │   ├── management/commands/         # comandos Django (importação)
    │   ├── templates/                   # páginas HTML
    │   └── static/                      # CSS, JavaScript e imagens da aplicação
    └── staticfiles/                     # cópia estática dentro do pacote
```

`media/` e `staticfiles/` podem ser gerados ou preenchidos durante a execução/deploy. As migrações em `ElegeCIPA/eleicao/migrations/` definem a estrutura das tabelas.

## Requisitos

- Python 3.10 ou superior
- PostgreSQL 13 ou superior, em execução
- Git (opcional, para clonar o repositório)

## Instalação e configuração

Abra o PowerShell na raiz do projeto, onde estão `manage.py` e `requirements.txt`.

1. Crie e ative um ambiente virtual:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   Se a ativação for bloqueada, execute `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` uma vez. Como alternativa, chame `\.venv\Scripts\python.exe` no lugar de `python` nos comandos seguintes.

2. Instale todas as dependências do `requirements.txt`:

   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

3. Crie um arquivo `.env` na raiz do projeto com as configurações. Exemplo para desenvolvimento local:

   ```dotenv
   SECRET_KEY=gere-uma-chave-secreta-longa-e-aleatoria
   DEBUG=True
   MATRICULA_HASH_KEY=use-outra-chave-secreta-longa-e-aleatoria
   DB_NAME=elegecipa
   DB_USER=postgres
   DB_PASSWORD=sua-senha-do-postgres
   DB_HOST=localhost
   DB_PORT=5432
   ```

   Substitua as chaves e a senha por valores seus. O arquivo `.env` é ignorado pelo Git; não compartilhe segredos. Para produção, use `DEBUG=False` e configure os hosts permitidos em `ElegeCIPA/settings.py`.

   Para conexão à Senior, copie também as variáveis `SENIOR_DB_*` do `.env.example` para o `.env` e substitua os valores. A integração usa SQL Server via `pyodbc`; instale o [Microsoft ODBC Driver para SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server) indicado em `SENIOR_ODBC_DRIVER`, na mesma arquitetura do Python. Configure um usuário de banco com permissão somente de leitura. A conexão exige TLS (`Encrypt=yes`) e valida o certificado por padrão. Se o servidor usa certificado interno não confiável pelo Windows, peça à equipe de infraestrutura a cadeia de certificados; `SENIOR_DB_TRUST_SERVER_CERTIFICATE=yes` pode ser usado temporariamente em desenvolvimento para confiar no certificado apresentado, mantendo o tráfego criptografado.

   A elegibilidade consulta apenas `sitafa = 1`, `numemp = 1` e `tipcol = 1`. As filiais Senior `1` (CORP), `2` (HE) e `7` (LAB) são agrupadas na unidade eleitoral `HE`; `4` → `CNBH`, `6` → `CNVN`, `5` → `CNCT` e `15` → `CESP`. Cada eleição tem estabelecimento e quantidades próprias de efetivos e suplentes. O estabelecimento do eleitor é salvo no campo `Eleitor.unidade` após a validação na Senior.

## Criar o banco PostgreSQL

O projeto usa PostgreSQL. É necessário criar o banco vazio; as tabelas são criadas pelo Django através das migrações, não por um arquivo SQL manual.

### Opção 1: usando o `psql`

No PowerShell, conecte como um usuário administrador do PostgreSQL (normalmente `postgres`) e crie o banco:

```powershell
psql -U postgres -h localhost -p 5432 -d postgres
```

No prompt `postgres=#`, execute:

```sql
CREATE DATABASE elegecipa;
```

Saia do `psql` com `\q`. Se usar outro usuário ou senha para a aplicação, crie o usuário e conceda acesso antes de aplicar as migrações. Por exemplo:

```sql
CREATE USER elegecipa_user WITH PASSWORD 'escolha-uma-senha-forte';
GRANT ALL PRIVILEGES ON DATABASE elegecipa TO elegecipa_user;
```

Nesse caso, ajuste `DB_USER` e `DB_PASSWORD` no `.env`. Se for necessário conceder privilégios sobre o schema em instalações com permissões restritas, conecte ao banco (`psql -U postgres -d elegecipa`) e execute `GRANT ALL ON SCHEMA public TO elegecipa_user;`.

### Opção 2: usando pgAdmin

No pgAdmin, conecte ao servidor local, clique com o botão direito em **Databases → Create → Database...**, informe `elegecipa` como nome e salve. O usuário configurado em `DB_USER` precisa ter permissão para criar e alterar tabelas nesse banco.

### Se você queria criar um arquivo `postgres.sql`

Um arquivo `.sql` é opcional e serve para guardar comandos SQL. Por exemplo, crie `postgres.sql` com este conteúdo:

```sql
CREATE DATABASE elegecipa;
```

E execute no PowerShell:

```powershell
psql -U postgres -h localhost -p 5432 -d postgres -f .\postgres.sql
```

O comando Django abaixo cria as tabelas e aplica as migrações dentro do banco recém-criado:

```powershell
python manage.py migrate
```

## Executar localmente

Após configurar o `.env` e criar o banco:

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

A aplicação fica em <http://127.0.0.1:8000/>. O painel administrativo do Django fica em <http://127.0.0.1:8000/admin/>.

## Importar eleitores

O comando `import_matriculas` aceita arquivos `.xlsx`, `.xls` ou `.csv`. Por padrão, espera as colunas `matricula` e `CPF`:

```powershell
python manage.py import_matriculas .\eleitores.xlsx
python manage.py import_matriculas .\eleitores.csv --mat-col Matricula --cpf-col CPF
```

Para gravar o estabelecimento já na importação, inclua uma coluna `codfil` ou `unidade` no arquivo. A coluna `codfil` é mapeada com as regras acima; sem essas colunas, a unidade será preenchida quando o colaborador fizer login e for validado na Senior. Se o arquivo usar outro título de coluna, informe-o com `--filial-col` ou `--unit-col`.

Para selecionar uma planilha pelo nome ou índice, use `--sheet`, por exemplo `--sheet Funcionarios` ou `--sheet 0`. Os nomes das colunas diferenciam maiúsculas de minúsculas. O comando armazena hashes de matrícula e CPF, não os valores originais.

## Arquivos estáticos e mídia

Em desenvolvimento, os arquivos estáticos e fotos de candidatos são servidos pelo Django. Para preparar os estáticos para implantação:

```powershell
python manage.py collectstatic
```

Os estáticos coletados vão para `staticfiles/`. Fotos enviadas ficam em `media/`; a implantação deve manter essa pasta persistente e acessível.

## Implantação

O `Procfile` inicia a aplicação com Gunicorn usando `ElegeCIPA.ElegeCIPA.wsgi:application`. A implantação deve fornecer as variáveis do banco e os segredos, executar `python manage.py migrate` e `python manage.py collectstatic`, e configurar HTTPS, hosts permitidos e armazenamento persistente de mídia.
