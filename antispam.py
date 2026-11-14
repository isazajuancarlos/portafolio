"""Filtro de CONTENIDO anti-spam para los formularios públicos (cero dependencias).

Complementa las capas de `main.py` (honeypot + trampa de tiempo firmada + cooldown
por IP): esas cazan al bot naive; ESTA caza el spam de TOKENS ALEATORIOS que llega
con un formulario bien formado y un correo desechable — el patrón medido el
2026-11-08: nombre/mensaje tipo 'NATREGTEGH1610646NEHTYHYHTR' con remitente
'@notlettersmail.com', que pasó honeypot, trampa de tiempo y cooldown.

Sesgo a DEJAR PASAR (directiva 21): el costo de un falso positivo es perder un lead
REAL, que es justo para lo que existe el sitio. Solo marca lo inequívocamente
no-humano. Discrimina con pareja roja/verde en `test_antispam.py`.
"""

import re

# Dominios de correo desechable/temporal más comunes + el visto en campaña
# (2026-11-08). Lista corta y ampliable; no pretende ser exhaustiva.
DOMINIOS_DESECHABLES = {
    "notlettersmail.com", "mailinator.com", "guerrillamail.com", "guerrillamail.info",
    "10minutemail.com", "temp-mail.org", "tempmail.com", "throwawaymail.com",
    "yopmail.com", "trashmail.com", "sharklasers.com", "getnada.com", "maildrop.cc",
    "dispostable.com", "fakeinbox.com", "mohmal.com", "emailondeck.com", "moakt.cc",
}

_TOKEN = re.compile(r"\S+")
# Token puramente alfanumérico que MEZCLA letras y dígitos (la firma del spam de
# tokens aleatorios). Una URL o un correo —con '/', ':', '.', '@'— NO casa.
_ALNUM_MIXTO = re.compile(r"^(?=[A-Za-z0-9]*[A-Za-z])(?=[A-Za-z0-9]*\d)[A-Za-z0-9]+$")


def dominio_desechable(email: str) -> bool:
    """True si el dominio del correo está en la lista de desechables."""
    dom = email.rsplit("@", 1)[-1].strip().lower()
    return bool(dom) and dom in DOMINIOS_DESECHABLES


def _tiene_token_basura(texto: str) -> bool:
    """True si hay un token (sin espacios) de >=18 chars que es alfanumérico
    mezclando letras y dígitos. Ningún nombre ni frase humana es así; una URL o
    un correo quedan fuera por llevar caracteres no alfanuméricos."""
    for m in _TOKEN.finditer(texto):
        tok = m.group(0)
        if len(tok) >= 18 and _ALNUM_MIXTO.match(tok):
            return True
    return False


def es_spam_contenido(nombre: str, email: str, mensaje: str = "") -> bool:
    """¿El contenido del formulario es spam no-humano? Conservador a propósito."""
    nombre = (nombre or "").strip()
    email = (email or "").strip()
    mensaje = (mensaje or "").strip()
    # 1) Correo desechable/temporal.
    if dominio_desechable(email):
        return True
    # 2) Token basura (alfanumérico aleatorio) en el nombre o el mensaje.
    if _tiene_token_basura(nombre) or _tiene_token_basura(mensaje):
        return True
    # 3) Nombre de una sola 'palabra' absurdamente larga (>=30): ningún nombre
    #    humano lo es, y un bot que no mete dígitos cae aquí.
    if " " not in nombre and len(nombre) >= 30:
        return True
    return False
