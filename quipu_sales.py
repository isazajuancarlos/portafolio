"""Venta del servicio Quipu OPRF: precios, suscripción PayPal, aprovisionamiento.

Flujo (todo automático):
  cliente elige plan -> botón de Suscripción PayPal -> PayPal cobra y envía un
  webhook -> este módulo VERIFICA la firma del webhook -> llama a la API /admin
  del quipu-oprf-server para EMITIR la API key -> se la envía al cliente por email.
  Si la suscripción se cancela/suspende -> DESACTIVA la key en el servidor.

Se activa solo si están las variables de PayPal + OPRF en el .env; si faltan, la
página de precios muestra un aviso de "lista de espera" en vez de botones rotos.

Sin dependencias nuevas: usa urllib (stdlib, con TLS) y el mismo SMTP de Zoho que
el resto del portafolio.
"""

import base64
import json
import os
import re
import smtplib
import threading
import urllib.error
import urllib.parse
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# --- Config (todo por .env) ---
PAYPAL_ENV = os.getenv("PAYPAL_ENV", "sandbox")  # "sandbox" | "live"
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_SECRET = os.getenv("PAYPAL_SECRET", "")
PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID", "")
PAYPAL_API = (
    "https://api-m.paypal.com"
    if PAYPAL_ENV == "live"
    else "https://api-m.sandbox.paypal.com"
)

# Endpoint de ADMINISTRACIÓN: emite y desactiva claves. Suele ser interno
# (127.0.0.1 en local), así que NUNCA se le manda a un cliente.
OPRF_SERVER_URL = os.getenv("OPRF_SERVER_URL", "").rstrip("/")
OPRF_ADMIN_TOKEN = os.getenv("OPRF_ADMIN_TOKEN", "")

# Lo que sí ve el cliente. Va aparte de OPRF_SERVER_URL a propósito: confundirlos
# significa mandarle a un cliente una dirección a la que no puede llegar.
OPRF_PUBLIC_URL = os.getenv("OPRF_PUBLIC_URL", "https://oprf.xiliux.com").rstrip("/")

# Clave pública del servidor, que el cliente debe FIJAR para verificar la prueba
# DLEQ. Va aquí, en el correo, porque este es el canal fuera de banda: pedirle
# que la descargue del mismo servidor que va a verificar sería circular.
# Es constante por diseño — el dominio y la clave k del OPRF no rotan jamás.
OPRF_PUBLIC_KEY = os.getenv(
    "OPRF_PUBLIC_KEY",
    "88b623ccc00c9eac39f8e02a0f41851535dc2e196ed9836cad00f77644af214b",
)

CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "contacto@xiliux.com")
EMAIL_PWD = os.getenv("PASSWORD")

# Página de planes, para que el cliente pueda consultar cuota y estado del
# servicio sin escribir. Configurable por si el dominio cambia.
DOMAIN_PRECIOS = os.getenv("DOMAIN_PRECIOS", "https://xiliux.com/quipu/precios")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SUBS_FILE = os.path.join(BASE_DIR, "subscriptions.json")

# Planes: única fuente de verdad para la página, el script de alta en PayPal y el
# mapeo webhook->plan. `quota` alinea con quipu-oprf-server (plans.rs). El precio
# mostrado DEBE coincidir con el que crees en el plan de PayPal (paypal_setup.py).
# El tramo de 9 USD se retiró al pasar a Live (2026-07-19). No era una vía de
# evaluación: esa ya existe y es el código abierto — auto-hospedar el servidor
# bajo AGPL, o usar quipu-voprf desde PyPI. Lo que se cobra es no tener que
# operarlo. Un tramo barato solo atraía al cliente que más soporte pide por dólar
# y señalaba "proyecto de hobby" para algo que va en la ruta de autenticación.
PLANS = [
    {
        "key": "starter",
        "name": "Starter",
        "price": "79",
        "quota": "250 000",
        "plan_env": "PAYPAL_PLAN_STARTER",
        "popular": True,
        "desc": "Para producción temprana.",
        "features": [
            "250 000 evaluaciones/mes",
            "Rate-limit por key",
            "Soporte prioritario",
        ],
    },
    {
        "key": "pro",
        "name": "Pro",
        "price": "299",
        "quota": "1 500 000",
        "plan_env": "PAYPAL_PLAN_PRO",
        "popular": False,
        "desc": "Para escalar.",
        "features": [
            "1 500 000 evaluaciones/mes",
            "SLA (tras la auditoría)",
            "Soporte dedicado",
        ],
    },
]


def plan_paypal_id(plan):
    """El plan_id de PayPal (P-XXXX) para un plan, desde el .env."""
    return os.getenv(plan["plan_env"], "")


def sales_ready():
    """True si se puede vender: credenciales completas Y catálogo coherente.

    Si lo anunciado no coincide con lo que cobra PayPal o con lo que concede el
    servidor, la página muestra "Próximamente" en vez de un botón. Cerrar la
    tienda cuesta una venta; cobrar 79 por algo anunciado a 49, o conceder
    100 000 evaluaciones de las 250 000 vendidas, cuesta el cliente y la
    reputación.
    """
    if _incoherencias:
        return False
    return bool(PAYPAL_CLIENT_ID and OPRF_SERVER_URL and OPRF_ADMIN_TOKEN)


# --- Coherencia del catálogo: lo anunciado == lo cobrado == lo concedido ---
#
# Tres sistemas guardan el mismo dato y nada los ataba: esta lista (lo que se
# anuncia), los planes de PayPal (lo que se cobra) y plans.rs del servidor OPRF
# (lo que se concede). Ya se descuadró dos veces en un día:
#   - la web decía 49 USD y PayPal iba a cobrar 79;
#   - la web ofrecía 250 000 evaluaciones y el servidor concedía 100 000.
# El segundo es el peor: el SDK falla CERRADO, así que el cliente lo descubre
# con sus usuarios sin poder iniciar sesión.
#
# `_incoherencias` se rellena al arrancar. Si hay alguna, los botones no se
# renderizan: es preferible una tienda cerrada a cobrar algo distinto de lo
# anunciado.
_incoherencias: list[str] = []


def verificar_catalogo():
    """Contrasta PLANS contra PayPal y contra el servidor OPRF.

    Devuelve la lista de incoherencias (vacía = todo cuadra). No poder
    comprobar NO es una incoherencia: si la red falla se avisa y se sigue,
    porque una caída ajena no debe tumbar la tienda. Lo que sí bloquea es un
    desacuerdo confirmado.
    """
    fallos = []

    # 1) Precio anunciado == precio que cobra PayPal.
    token = _paypal_token()
    if not token:
        print("AVISO catálogo: sin token de PayPal, no se pudo verificar el precio.")
    else:
        for p in PLANS:
            pid = plan_paypal_id(p)
            if not pid:
                fallos.append(f"{p['name']}: sin plan_id configurado")
                continue
            status, data = _http_json(
                "GET", f"{PAYPAL_API}/v1/billing/plans/{pid}",
                headers={"Authorization": f"Bearer {token}"})
            if status != 200:
                fallos.append(f"{p['name']}: el plan {pid} no existe en PayPal ({status})")
                continue
            try:
                real = data["billing_cycles"][0]["pricing_scheme"]["fixed_price"]["value"]
            except (KeyError, IndexError, TypeError):
                fallos.append(f"{p['name']}: respuesta de PayPal ininteligible")
                continue
            if float(real) != float(p["price"]):
                fallos.append(
                    f"{p['name']}: la web anuncia {p['price']} USD y PayPal cobra {real}")
            if data.get("status") != "ACTIVE":
                fallos.append(f"{p['name']}: el plan de PayPal está {data.get('status')}")

    # 2) Cuota anunciada == cuota que concede el servidor OPRF.
    status, data = _http_json("GET", f"{OPRF_PUBLIC_URL}/v1/plans")
    if status != 200:
        print(f"AVISO catálogo: no se pudo leer {OPRF_PUBLIC_URL}/v1/plans ({status}).")
    else:
        concede = {x["name"]: x["quota_monthly"] for x in data.get("plans", [])}
        for p in PLANS:
            # La cuota se muestra con separadores de millar ("250 000"): el
            # separador puede ser espacio normal o duro segun quien edito la
            # linea, asi que se extraen solo los digitos.
            anunciada = int(re.sub(r"\D", "", p["quota"]))
            real = concede.get(p["key"])
            if real is None:
                fallos.append(f"{p['key']}: el servidor OPRF no conoce este plan")
            elif real != anunciada:
                fallos.append(
                    f"{p['key']}: la web ofrece {anunciada} evaluaciones y el "
                    f"servidor concede {real}")

    return fallos


def comprobar_catalogo_al_arrancar():
    """Ejecuta la verificación y deja el resultado en `_incoherencias`."""
    global _incoherencias
    try:
        _incoherencias = verificar_catalogo()
    except Exception as e:  # noqa: BLE001 — nunca impedir el arranque del sitio
        print(f"AVISO catálogo: la verificación falló ({type(e).__name__}: {e}).")
        _incoherencias = []
    if _incoherencias:
        print("\n*** CATÁLOGO INCOHERENTE — botones de compra DESACTIVADOS ***")
        for f in _incoherencias:
            print(f"  - {f}")
        print()
    return _incoherencias


# --- HTTP (stdlib) ---
def _http_json(method, url, headers=None, data=None):
    body = data
    hdrs = dict(headers or {})
    if isinstance(data, (dict, list)):
        body = json.dumps(data).encode()
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode() or "{}"
            return r.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode(errors="replace")}
    except Exception as e:  # noqa: BLE001 - red/timeout: no romper el webhook
        return 0, {"error": str(e)}


def _paypal_token():
    auth = base64.b64encode(f"{PAYPAL_CLIENT_ID}:{PAYPAL_SECRET}".encode()).decode()
    status, data = _http_json(
        "POST",
        f"{PAYPAL_API}/v1/oauth2/token",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=b"grant_type=client_credentials",
    )
    return data.get("access_token") if status == 200 else None


# --- Verificación del webhook de PayPal ---
def verify_webhook(headers, raw_body):
    """Verifica la firma del webhook contra la API de PayPal. `headers` en minúsculas."""
    if not PAYPAL_WEBHOOK_ID:
        return False
    token = _paypal_token()
    if not token:
        return False
    try:
        event = json.loads(raw_body)
    except (ValueError, TypeError):
        return False
    payload = {
        "transmission_id": headers.get("paypal-transmission-id"),
        "transmission_time": headers.get("paypal-transmission-time"),
        "cert_url": headers.get("paypal-cert-url"),
        "auth_algo": headers.get("paypal-auth-algo"),
        "transmission_sig": headers.get("paypal-transmission-sig"),
        "webhook_id": PAYPAL_WEBHOOK_ID,
        "webhook_event": event,
    }
    status, data = _http_json(
        "POST",
        f"{PAYPAL_API}/v1/notifications/verify-webhook-signature",
        headers={"Authorization": f"Bearer {token}"},
        data=payload,
    )
    return status == 200 and data.get("verification_status") == "SUCCESS"


# --- Aprovisionamiento contra quipu-oprf-server ---
def oprf_issue_key(email, plan_key):
    """POST /admin/keys -> (api_key, prefix) o (None, None)."""
    data = urllib.parse.urlencode({"email": email, "plan": plan_key}).encode()
    status, resp = _http_json(
        "POST",
        f"{OPRF_SERVER_URL}/admin/keys",
        headers={
            "X-Admin-Token": OPRF_ADMIN_TOKEN,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=data,
    )
    if status == 200:
        return resp.get("api_key"), resp.get("prefix")
    print(f"OPRF issue_key falló ({status}): {resp}")
    return None, None


def oprf_deactivate(prefix):
    status, _ = _http_json(
        "POST",
        f"{OPRF_SERVER_URL}/admin/keys/{prefix}/deactivate",
        headers={"X-Admin-Token": OPRF_ADMIN_TOKEN},
    )
    return status == 200


# --- Registro local suscripción -> key (para poder desactivar al cancelar) ---
_lock = threading.Lock()


def _load_subs():
    if os.path.exists(SUBS_FILE):
        try:
            with open(SUBS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (ValueError, OSError):
            return {}
    return {}


def _save_subs(d):
    tmp = SUBS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    os.replace(tmp, SUBS_FILE)


def get_sub(sub_id):
    return _load_subs().get(sub_id)


def _record_sub(sub_id, email, plan_key, prefix):
    with _lock:
        d = _load_subs()
        d[sub_id] = {"email": email, "plan": plan_key, "prefix": prefix, "active": True}
        _save_subs(d)


def _mark_inactive(sub_id):
    with _lock:
        d = _load_subs()
        if sub_id in d:
            d[sub_id]["active"] = False
            _save_subs(d)


# --- Email con la API key ---
def send_key_email(to_email, plan_name, api_key):
    if not (EMAIL_PWD and to_email):
        return False
    try:
        server = smtplib.SMTP_SSL("smtp.zoho.com", 465)
        server.login(CONTACT_EMAIL, EMAIL_PWD)
        msg = MIMEMultipart()
        msg["From"] = CONTACT_EMAIL
        msg["To"] = to_email
        msg["Subject"] = "🔐 Tu API key de Quipu OPRF"
        # La cuota sale de PLANS para no repetirla: si cambia el plan, cambia el
        # correo. Se busca por nombre porque es lo que recibe esta función.
        cuota = next((p["quota"] for p in PLANS if p["name"] == plan_name), None)
        linea_cuota = f"Tu plan incluye {cuota} evaluaciones al mes.\n\n" if cuota else ""
        body = (
            f"¡Gracias por suscribirte al plan {plan_name}!\n\n"
            f"{linea_cuota}"
            f"Estos son los tres valores que necesitas para integrar. Los tres, no\n"
            f"solo la clave: sin la clave pública no puedes verificar las respuestas\n"
            f"del servidor, que es justamente lo que hace verificable a un VOPRF.\n\n"
            f"  BASE_URL    {OPRF_PUBLIC_URL}\n\n"
            f"  API_KEY     {api_key}\n\n"
            f"  PUBLIC_KEY  {OPRF_PUBLIC_KEY}\n\n"
            f"Guarda la API key: NO se vuelve a mostrar. Si la pierdes emitimos otra,\n"
            f"pero no podemos recuperarla — solo almacenamos su hash.\n\n"
            f"La PUBLIC_KEY, en cambio, no es secreta: fíjala en tu código. Sirve para\n"
            f"comprobar que las respuestas vienen de nuestra clave y no de un servidor\n"
            f"suplantado. No la descargues del servicio en tiempo de ejecución: eso\n"
            f"anularía la garantía. No cambia nunca.\n\n"
            f"--- Django, con el hasher de contraseñas de siempre ---\n\n"
            # PENDIENTE DE DECISIÓN DE JUAN (2026-08-11): el SDK `quipu-oprf-django`
            # está yanked en PyPI desde el 2026-08-10, así que `pip install` FALLA
            # («Ignored the following yanked versions», medido). Es Apache-2.0 y es
            # el conector del servicio de PAGO, no el núcleo criptográfico que se
            # retiró por seguridad: puede que su sitio siga siendo PyPI. Hasta que
            # se decida, el correo NO da un comando que revienta en la terminal de
            # un cliente que acaba de pagar.
            f"  El SDK (Apache-2.0) se entrega con esta misma clave: respóndenos a\n"
            f"  este correo y te lo enviamos firmado, con su SHA-256.\n\n"
            f"  # settings.py\n"
            f"  PASSWORD_HASHERS = [\n"
            f'      "quipu_oprf_django.hashers.OprfArgon2PasswordHasher",\n'
            f'      "django.contrib.auth.hashers.Argon2PasswordHasher",   # migración\n'
            f"  ]\n\n"
            f"  QUIPU_OPRF = {{\n"
            f'      "BASE_URL":   "{OPRF_PUBLIC_URL}",\n'
            f'      "API_KEY":    os.environ["QUIPU_OPRF_API_KEY"],\n'
            f'      "PUBLIC_KEY": os.environ["QUIPU_OPRF_PUBKEY"],\n'
            f"  }}\n\n"
            f"Los usuarios que ya existen migran solos al iniciar sesión: sin script\n"
            f"y sin obligar a nadie a cambiar su contraseña.\n\n"
            f"--- Antes de ponerlo en producción, lee esto ---\n\n"
            f"El hasher falla CERRADO, a propósito: si el servicio no responde o la\n"
            f"prueba no valida, la verificación levanta una excepción en vez de dejar\n"
            f"pasar al usuario. En la práctica significa que, si no puedes alcanzarnos\n"
            f"o agotas la cuota, tus usuarios NO PODRÁN INICIAR SESIÓN.\n\n"
            f"Es deliberado. La alternativa —seguir adelante sin endurecer— degradaría\n"
            f"tu seguridad justo cuando importa, y en silencio. Tampoco devolvemos\n"
            f"\"contraseña incorrecta\" ante un fallo nuestro: eso haría que tus usuarios\n"
            f"resetearan su clave por un problema de red.\n\n"
            f"Qué implica para ti:\n\n"
            f"  - La cuota es un límite duro, sin excedente. Al agotarla, respondemos\n"
            f"    429 y los inicios de sesión se detienen. Vigila tu consumo y avísanos\n"
            f"    antes de acercarte al tope; cambiar de plan es inmediato.\n"
            f"  - Cada inicio de sesión hace una llamada de red a nuestro servicio\n"
            f"    (timeout de 5 s por defecto, ajustable con TIMEOUT).\n"
            f"  - Monitoriza la excepción OprfUnavailable: es tu señal temprana, tanto\n"
            f"    de una caída como de una cuota a punto de agotarse.\n\n"
            f"Estamos en BETA y sin auditoría externa todavía, así que no te vendemos\n"
            f"un SLA que aún no podemos sostener. Si tu caso no tolera esta dependencia,\n"
            f"dínoslo y hablamos: auto-hospedar el servidor bajo AGPL es una opción\n"
            f"legítima y te la explicamos sin problema.\n\n"
            f"¿Otro stack? Pídenos las primitivas (VOPRF) por esta misma vía.\n"
            f"Conforme a RFC 9497 (VOPRF, ristretto255-SHA512), verificado contra los\n"
            f"vectores oficiales. El SDK es Apache-2.0: no arrastra la AGPL del núcleo\n"
            f"a tu servidor de autenticación.\n\n"
            f"Documentación: https://xiliux.com/quipu\n"
            f"Planes y estado: {DOMAIN_PRECIOS}\n\n"
            f"Cualquier duda, responde a este correo: lo leo yo.\n\n"
            f"— Xiliux"
        )
        msg.attach(MIMEText(body, "plain"))
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:  # noqa: BLE001
        print(f"ERROR SMTP (Quipu key): {type(e).__name__}: {e}")
        return False


# --- Webhook: despacho de eventos ---
def _plan_key_for(pp_plan_id):
    for p in PLANS:
        if pp_plan_id and plan_paypal_id(p) == pp_plan_id:
            return p["key"]
    return "beta"


def _plan_name(plan_key):
    for p in PLANS:
        if p["key"] == plan_key:
            return p["name"]
    return plan_key


def handle_event(event):
    """Procesa un evento de webhook YA VERIFICADO. Idempotente por sub_id."""
    etype = event.get("event_type", "")
    res = event.get("resource", {}) or {}

    if etype == "BILLING.SUBSCRIPTION.ACTIVATED":
        sub_id = res.get("id")
        if not sub_id or get_sub(sub_id):
            return  # ya aprovisionado (idempotencia)
        email = (res.get("subscriber") or {}).get("email_address")
        plan_key = _plan_key_for(res.get("plan_id"))
        api_key, prefix = oprf_issue_key(email or f"paypal-{sub_id}", plan_key)
        if api_key:
            _record_sub(sub_id, email, plan_key, prefix)
            send_key_email(email, _plan_name(plan_key), api_key)

    elif etype in (
        "BILLING.SUBSCRIPTION.CANCELLED",
        "BILLING.SUBSCRIPTION.SUSPENDED",
        "BILLING.SUBSCRIPTION.EXPIRED",
    ):
        sub_id = res.get("id")
        sub = get_sub(sub_id) if sub_id else None
        if sub and sub.get("prefix"):
            oprf_deactivate(sub["prefix"])
            _mark_inactive(sub_id)


# --- Frontend: SDK y botones de PayPal ---
def paypal_sdk_url():
    return (
        f"https://www.paypal.com/sdk/js?client-id={PAYPAL_CLIENT_ID}"
        f"&vault=true&intent=subscription"
    )


def button_script(plan):
    """JS que renderiza el botón de Suscripción de PayPal en #paypal-<key>."""
    pid = plan_paypal_id(plan)
    return f"""
    if (window.paypal && '{pid}') {{
      paypal.Buttons({{
        style: {{ layout: 'vertical', color: 'gold', shape: 'pill', label: 'subscribe' }},
        createSubscription: function(data, actions) {{
          return actions.subscription.create({{ plan_id: '{pid}' }});
        }},
        onApprove: function(data) {{
          window.location.href = '/quipu/gracias?sub=' + encodeURIComponent(data.subscriptionID);
        }}
      }}).render('#paypal-{plan["key"]}');
    }}
    """
