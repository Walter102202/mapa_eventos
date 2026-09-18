"""Rate limiter por IP compartido por todos los routers (slowapi)."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import get_settings

settings = get_settings()

# Nota: get_remote_address usa request.client.host. Detrás de un proxy hay que
# arrancar uvicorn con --proxy-headers para que sea la IP real.
limiter = Limiter(key_func=get_remote_address, enabled=settings.rate_limit_enabled)
