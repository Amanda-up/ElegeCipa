import os
import logging

class DatabaseConnectionSQL:

    def __init__(self):
        self.connection = None
        self.host = os.getenv('SENIOR_DB_HOST', '').strip()
        self.port = os.getenv('SENIOR_DB_PORT', '').strip()
        self.database = os.getenv('SENIOR_DB_NAME', '').strip()
        self.user = os.getenv('SENIOR_DB_USER', '').strip()
        self.pswd = os.getenv('SENIOR_DB_PASSWORD', '')
        self.driver = os.getenv('SENIOR_ODBC_DRIVER', 'ODBC Driver 17 for SQL Server').strip()
        self.trust_server_certificate = os.getenv(
            'SENIOR_DB_TRUST_SERVER_CERTIFICATE', 'no'
        ).strip().lower() in {'yes', 'true', '1'}

    def conectar(self):
        """Conectar ao banco de dados SQL Server"""
        try:
            required = (self.host, self.database, self.user, self.pswd)
            if not all(required):
                raise ValueError("Configure SENIOR_DB_HOST, SENIOR_DB_NAME, SENIOR_DB_USER e SENIOR_DB_PASSWORD no .env")

            server = f"{self.host},{self.port}" if self.port else self.host
            password = self.pswd.replace("}", "}}")
            str_conexao = (
                f"DRIVER={{{self.driver}}};"
                f"SERVER={server};"
                f"DATABASE={self.database};"
                f"UID={self.user};"
                f"PWD={{{password}}};"
                "Encrypt=yes;"
                f"TrustServerCertificate={'yes' if self.trust_server_certificate else 'no'};"
            )
            import pyodbc
            self.connection = pyodbc.connect(str_conexao, timeout=5)
            return True
        except Exception:
            logging.exception("Erro ao conectar ao banco Senior")
            self.connection = None
            return False

    def execute_query(self, query, parametros=None):
        if self.connection is None:
            raise Exception("Sem conexão com o banco de dados SQL Server")
        if not query.lstrip().upper().startswith("SELECT"):
            raise ValueError("A conexão configurada com a Senior aceita somente consultas SELECT")
        
        cursor = self.connection.cursor()
        try:
            if parametros:
                cursor.execute(query, parametros)
            else:
                cursor.execute(query)
                
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Erro ao executar a consulta no SQL Server: {e}")
            raise 
        finally:
            cursor.close()

    def close(self):
        if self.connection:
            self.connection.close()
            logging.info('Conexão com o SQL Server fechada.')
