"""Rate limiter por IP compartido por todos los routers (slowapi).

Nota sobre headers_enabled: se evaluó activarlo para que las respuestas 429 lleven
Retry-After y X-RateLimit-*, pero en esta versión de slowapi el wrapper del decorador
intenta inyectar esos headers también en la respuesta 200 de cada endpoint decorado,
y para eso necesita un parámetro `response: Response` en la firma del endpoint. Ninguno
de los endpoints de este proyecto lo tiene, así que activarlo rompe (500) las tres rutas
con `@limiter.limit(...)` en cada request exitosa. La alternativa sin tocar las firmas es
`SlowAPIMiddleware`/`SlowAPIASGIMiddleware` (slowapi.middleware) montado en main.py, que
queda fuera del alcance de este cambio puntual.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import get_settings

settings = get_settings()

# Nota: get_remote_address usa request.client.host. Detrás de un proxy hay que
# arrancar uvicorn con --proxy-headers para que sea la IP real.
limiter = Limiter(key_func=get_remote_address, enabled=settings.rate_limit_enabled)
