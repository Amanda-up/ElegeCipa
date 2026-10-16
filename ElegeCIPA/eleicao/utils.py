import hashlib
import hmac
from django.conf import settings

def hash_matricula(matricula: str) -> str:
    """
    Retorna HMAC-SHA256 hex digest da matrícula usando MATRICULA_HASH_KEY.
    Determinístico — mesmo input => mesmo hash.
    """
    key = getattr(settings, "MATRICULA_HASH_KEY", settings.SECRET_KEY)
    m = "" if matricula is None else str(matricula).strip()
    return hmac.new(key.encode("utf-8"), m.encode("utf-8"), hashlib.sha256).hexdigest()
