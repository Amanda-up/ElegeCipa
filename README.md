# ElegeCIPA

Aplicação web para administrar eleições da CIPA. O sistema permite cadastrar eleições e candidatos, autenticar eleitores, registrar votos (incluindo voto em branco), acompanhar a apuração e gerar extrato em PDF. Também inclui importação de matrículas e CPFs a partir de planilhas Excel ou arquivos CSV.

## Tecnologias

- Python e Django
- PostgreSQL
- WhiteNoise para servir arquivos estáticos
- Pandas e openpyxl para importar eleitores
- ReportLab para gerar PDFs

## Requisitos

- Python 3.10 ou superior
- PostgreSQL 13 ou superior, em execução
- Git (opcional, para clonar o repositório)

## Instalação local (Windows / PowerShell)

Abra o PowerShell na pasta do projeto, onde estão `manage.py` e `requirements.txt`.

1. Crie e ative um ambiente virtual:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   Se o PowerShell bloquear a ativação, execute `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` uma vez e tente novamente. Também é possível usar o ambiente sem ativá-lo, chamando `\.venv\Scripts\python.exe` nos comandos abaixo.

2. Atualize o pip e instale todas as dependências listadas no projeto:

   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

3. Crie um banco PostgreSQL e configure as variáveis de ambiente. O Django lê um arquivo `.env` na raiz do projeto. Exemplo:

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

   Crie o banco `elegecipa` no PostgreSQL (ou ajuste `DB_NAME`). Use valores secretos próprios; não publique o `.env`. Em produção, use `DEBUG=False` e configure também os hosts permitidos em `ElegeCIPA/settings.py`.

4. Aplique as migrações e crie um usuário administrador:

   ```powershell
   python manage.py migrate
   python manage.py createsuperuser
   ```

5. Inicie o servidor de desenvolvimento:

   ```powershell
   python manage.py runserver
   ```

   Acesse <http://127.0.0.1:8000/>. O painel administrativo do Django fica em <http://127.0.0.1:8000/admin/>.

## Importar eleitores

O comando `import_matriculas` aceita planilhas `.xlsx`/`.xls` ou arquivos `.csv`. Por padrão, procura as colunas `matricula` e `CPF`:

```powershell
python manage.py import_matriculas .\eleitores.xlsx
python manage.py import_matriculas .\eleitores.csv --mat-col Matricula --cpf-col CPF
```

Para selecionar uma planilha pelo nome ou índice, use `--sheet` (por exemplo, `--sheet Funcionarios` ou `--sheet 0`). Os nomes das colunas diferenciam maiúsculas e minúsculas. A importação guarda hashes de matrícula e CPF no banco, não os valores originais.

## Arquivos estáticos e mídia

Em desenvolvimento, os arquivos estáticos e as fotos de candidatos são servidos pelo Django. Para preparar os estáticos em um ambiente de implantação:

```powershell
python manage.py collectstatic
```

O destino é `staticfiles/`. As fotos enviadas são armazenadas em `media/`; configure armazenamento persistente e acesso apropriado a essa pasta na implantação.

## Implantação

O `Procfile` inicia a aplicação com Gunicorn usando `ElegeCIPA.ElegeCIPA.wsgi:application`. A implantação precisa fornecer as variáveis de ambiente do banco e segredos, executar `python manage.py migrate` e `python manage.py collectstatic`. Configure corretamente HTTPS, hosts permitidos e armazenamento persistente para mídia antes de disponibilizar o sistema.

## Estrutura principal

```text
ElegeCIPA/
  settings.py       Configurações Django
  urls.py           Rotas principais
  eleicao/          Aplicação, modelos, páginas e migrações
manage.py           Comandos de administração Django
requirements.txt    Dependências Python
```
