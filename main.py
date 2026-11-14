import json
import os
import re
import time
import hmac
import hashlib
import secrets
import smtplib
import asyncio
import datetime
import html as _htmlmod
import markdown2
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import antispam  # filtro de CONTENIDO (tokens aleatorios + correo desechable)
from nicegui import ui, app
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
# Importamos Response para manejar XML y archivos directamente
from fastapi import Request
from fastapi.responses import PlainTextResponse, FileResponse, Response, RedirectResponse
from dotenv import load_dotenv

# Cargar variables de entorno (Asegúrate de tener tu archivo .env)
load_dotenv()

# Ventas del servicio Quipu OPRF (PayPal + aprovisionamiento). Se importa DESPUÉS
# de load_dotenv() porque lee el .env al importarse.
import quipu_sales

# --- CONFIGURACIÓN DE RUTAS ---
# Usamos rutas absolutas para evitar errores en producción (Systemd/Nginx)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'portfolio_data.json')
LEADS_FILE = os.path.join(BASE_DIR, 'leads.json')
BLOG_FILE = os.path.join(BASE_DIR, 'blog_posts.json')
LOGO_PATH = os.path.join(BASE_DIR, 'logo.png')
PDF_PATH = os.path.join(BASE_DIR, 'guia_automatizacion.pdf')
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')

# --- CONFIGURACIÓN GENERAL ---
DOMAIN = "https://xiliux.com"
# Imagen social estable servida por el propio dominio (antes dependía de Imgur,
# un host externo que puede caerse o limitar peticiones). Usada en OG/Twitter/Schema.
SOCIAL_IMAGE = f"{DOMAIN}/logo.png"

# Perfil de Mastodon de Xiliux. Sirve para la verificación RECÍPROCA: el perfil
# ya enlaza a xiliux.com, y Mastodon solo pinta la marca verde si esta web
# devuelve el enlace con `rel="me"`.
#
# LA TRAMPA, y es la misma que obliga a servir el blog como HTML de servidor:
# **el verificador de Mastodon pide el HTML crudo y no ejecuta JavaScript.** La
# portada es NiceGUI, que se pinta por WebSocket, así que un `ui.link(...)` con
# `rel="me"` en el pie NO lo vería nunca — se vería igual de bien en el navegador
# y no verificaría jamás, que es el peor modo de fallo. Por eso el enlace va en el
# `<head>` como `<link rel="me">`, que sí viaja en la primera respuesta:
#   · páginas SSR (`/blog`, `/servicios`, `/quipu`, `/informes`) -> `_seo_head()`
#   · portada NiceGUI (`/`)                                     -> `ui.add_head_html`
# Mastodon acepta `<link rel="me">` en el head igual que `<a rel="me">` en el
# cuerpo; el `<link>` es el único que funciona en las dos mitades de este sitio.
#
# El perfil tiene CUATRO campos y esto solo puede verificar dos —«Web» y «Blog»,
# los que apuntan aquí—. Los otros dos apuntan a GitHub, y ésos se verifican
# poniendo el enlace a Mastodon en el perfil de GitHub: no depende de este código.
MASTODON_PROFILE = "https://mastodon.social/@xiliux"
REL_ME = f'<link rel="me" href="{MASTODON_PROFILE}">'

# --- SECRETOS ---

EMAIL_PWD = os.getenv("PASSWORD")

# APP_SECRET cifra las sesiones. Sin él, un valor público permitiría falsificar
# sesiones (incl. la de admin). Si falta, usamos uno efímero seguro (las sesiones
# no persistirán entre reinicios, pero no habrá secreto conocido).
APP_SECRET = os.getenv("APP_SECRET")
if not APP_SECRET:
    APP_SECRET = secrets.token_hex(32)
    print("⚠️  APP_SECRET no definido: usando uno efímero (sesiones no persisten). Configúralo en .env")
GOOGLE_ANALYTICS_ID = os.getenv("GOOGLE_ANALYTICS_ID", "")
GOOGLE_SEARCH_CONSOLE = os.getenv("GOOGLE_SEARCH_CONSOLE_VERIFICATION", "")

# --- CONTACTO / VENTAS ---
# Todo configurable por .env. Cada CTA se renderiza SOLO si su valor está definido,
# así el sitio nunca muestra un botón roto ni datos inventados.
from urllib.parse import quote as _urlquote
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "contacto@xiliux.com")
WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER", "")   # intl. sin '+', ej: 34600111222
BOOKING_URL = os.getenv("BOOKING_URL", "")           # Calendly / Cal.com para agendar llamada
WHATSAPP_MSG = "Hola Xiliux, vi tu portafolio y quiero cotizar un proyecto."

# --- RESPONSABLE DEL TRATAMIENTO (política de privacidad) ---
# Mismo principio que arriba: no se inventan. Mientras alguno falte, /privacidad
# se marca como BORRADOR y queda fuera del sitemap y de los buscadores. Una
# política publicada con huecos es peor que no tenerla.
PRIVACY_RAZON_SOCIAL = os.getenv("PRIVACY_RAZON_SOCIAL", "")   # nombre legal exacto
PRIVACY_IDENT = os.getenv("PRIVACY_IDENT", "")                 # NIT / cédula del responsable
PRIVACY_DIRECCION = os.getenv("PRIVACY_DIRECCION", "")         # dirección registrada
PRIVACY_RETENCION = os.getenv("PRIVACY_RETENCION", "")         # p.ej. "5 años desde la cancelación"
PRIVACY_VIGENCIA = os.getenv("PRIVACY_VIGENCIA", "17 de julio de 2026")

def privacy_ready():
    """True solo si la política puede publicarse sin datos a medias."""
    return all([PRIVACY_RAZON_SOCIAL, PRIVACY_IDENT, PRIVACY_DIRECCION, PRIVACY_RETENCION])

def whatsapp_link(text=WHATSAPP_MSG):
    return f"https://wa.me/{WHATSAPP_NUMBER}?text={_urlquote(text)}" if WHATSAPP_NUMBER else ""

# Catálogo de servicios (fuente única: alimenta las tarjetas y el Schema.org de precios).
# pay_env: nombre de la variable .env con el Stripe Payment Link; si existe -> botón "Reservar".
SERVICES = [
    {"icon": "terminal", "color": "cyan", "title": "Scripts y automatización",
     "desc": "Automatización de procesos, web scraping y bots. Resultados rápidos y medibles: el primer valor en días, no en meses.",
     "price_num": "200", "price_label": "Desde $200 USD", "popular": False, "pay_env": "STRIPE_SCRIPT",
     "quote": "Hola Xiliux, quiero automatizar un proceso con un script/bot."},
    {"icon": "rocket_launch", "color": "indigo", "title": "Prototipo / MVP en Python",
     "desc": "Valida la idea rápido en Python (NiceGUI, FastAPI). Es el primer peldaño: cuando el prototipo prueba su valor, crece al sistema definitivo en Rust —un solo binario, sin Node.",
     "price_num": "500", "price_label": "Desde $500 USD", "popular": False, "pay_env": "STRIPE_MVP",
     "quote": "Hola Xiliux, quiero cotizar un prototipo/MVP en Python."},
    {"icon": "psychology", "color": "purple", "title": "Integración de IA con LLMs",
     "desc": "Chatbots y automatización con GPT-4, Claude y Gemini, integrados en tu producto o tu operación.",
     "price_num": "800", "price_label": "Desde $800 USD", "popular": True, "pay_env": "STRIPE_IA",
     "quote": "Hola Xiliux, quiero integrar IA/LLMs en mi negocio."},
    {"icon": "dns", "color": "emerald", "title": "Sistema a la medida — Rust",
     "desc": "Sistemas que resisten: backend en Rust (axum + SQLx sobre SQLite), interfaz en maud + htmx —un solo binario, sin Node, corre offline— y firma post-cuántica con Quipu. Es lo que sostengo en producción (SIGER, medico, inventario). Se cotiza por alcance: número de requerimientos y su complejidad.",
     "price_num": "", "price_label": "A cotización", "popular": False, "pay_env": "STRIPE_ENTERPRISE",
     "quote": "Hola Xiliux, quiero un sistema a la medida en Rust.",
     "cotizar_url": "/cotizador"},
]

# Cómo trabajo (genera confianza + contenido indexable para SEO).
PROCESS = [
    ("chat", "1. Hablamos", "Cuéntame tu idea por WhatsApp, email o el formulario. Sin compromiso."),
    ("description", "2. Propuesta", "Recibes alcance, tiempos y precio cerrado en menos de 24–48 h."),
    ("code", "3. Desarrollo", "Construyo con entregas incrementales y comunicación constante."),
    ("rocket_launch", "4. Entrega", "Despliegue, documentación y soporte inicial incluidos."),
]

# FAQ visible en la página (mismas preguntas que el FAQPage Schema.org del <head>).
FAQS = [
    ("¿Cuánto cuesta desarrollar un MVP en Python?",
     "Un prototipo/MVP en Python (NiceGUI, FastAPI) comienza desde $500 USD y sirve para validar la idea rápido. Cuando prueba su valor, crece a un sistema a la medida en Rust —un solo binario, sin Node—, que se cotiza por alcance (número de requerimientos y su complejidad)."),
    ("¿Qué servicios de IA ofrece Xiliux?",
     "Integración de IA con LLMs (GPT-4, Claude, Gemini) desde $800 USD: chatbots inteligentes, automatización con IA, procesamiento de lenguaje natural y sistemas de recomendación, todo en Python."),
    ("¿Qué es NiceGUI y por qué usarlo?",
     "NiceGUI es un framework Python para crear interfaces web rápido, sin JavaScript. Lo uso en el peldaño de prototipo/MVP, para validar una idea en días. Los sistemas definitivos van en Rust (axum + SQLx) con interfaz maud + htmx —un solo binario que corre offline, sin Node—, que es donde la solución tiene que resistir años."),
    ("¿Cuánto tiempo toma desarrollar un proyecto?",
     "Un script o bot simple: 1–3 días. Un MVP básico: 1–2 semanas. Integraciones de IA más complejas: 2–4 semanas. Doy estimaciones detalladas tras analizar los requisitos."),
    ("¿Ofrecen soporte después del desarrollo?",
     "Sí. Todos los proyectos incluyen documentación y soporte inicial. Ofrezco planes de mantenimiento mensual para actualizaciones, correcciones y nuevas funcionalidades, además de capacitación si hace falta."),
]

# --- GESTIÓN DE DATOS ---
# Desde el 2026-08-10 el código NO se distribuye por registros públicos y la
# entrega es a pedido. Aquí solo quedan destinos COMPROBADOS ese día:
#
#   github.com/isazajuancarlos/quipu  200 — ya no aloja el código, pero explica
#                                     el cambio y adónde ir. Se conserva: es la
#                                     puerta por la que llega quien busca quipu.
#   docs.rs/quipu                     404 — RETIRADO. docs.rs se construye desde
#                                     crates.io y cayó con el yank.
#   crates.io / PyPI / npm            RETIRADOS como vía de obtención: las
#                                     páginas existen, pero `cargo add quipu`
#                                     responde «could not be found in registry
#                                     index» y `pip install quipu-crypto`, «No
#                                     matching distribution found» (medido el
#                                     2026-08-11). Un enlace que promete una
#                                     instalación que falla es peor que ninguno.
QUIPU_LINKS = {
    "repo": "https://github.com/isazajuancarlos/quipu",
    "obtener": "/#contacto",
}
# --- INFORMES: sistema de monitoreo y seguimiento de obligaciones de reporte ---
# Nace del paso por la Secretaría de Salud de Medellín, donde el sistema se
# llamaba "Subsistema de monitoreo y seguimiento informes de obligatorio
# cumplimiento". Esa es la terminología con la que las entidades lo buscan.
# Anclas del menú, compartidas por la cabecera de escritorio y la barra móvil.
# El sexto enlace hace que la barra móvil pase a desplazarse en pantallas muy
# estrechas. Se acepta: la barra ya es desplazable por diseño (`overflow-x`), no
# un menú de estado que pueda romperse.
NAV_ANCLAS = [('Inicio', 'home'), ('Servicios', 'services'), ('Informes', 'informes'),
              ('Inventario', 'inventario'), ('Salud', 'salud'), ('Quipu', 'quipu'),
              ('FAQ', 'faq')]

# AVISO (2026-09-28): las listas de producto `*_FEATURES` y `*_TAGS`
# (INFORMES/INVENTARIO/SALUD/QUIPU/TUNJO/GUACA) YA NO SE RENDERIZAN. Son sobras del
# render NiceGUI anterior a que la portada y las páginas de producto pasaran a SSR
# (2026-08-31): hoy el contenido va INCRUSTADO en las funciones `@app.get`
# (`quipu_modelo`, `informes_producto`, la sección "productos" de `_home_body`).
# Editar aquí NO cambia la web — se edita el HTML en esas funciones. Se conservan
# accesibles (grep las encuentra) hasta decidir si se borran o se recablean.
# (SERVICES, PROCESS, FAQS sí se renderizan; ver `_home_body`.)
INFORMES_FEATURES = [
    ("rule", "Reglas, no recordatorios",
     "Las obligaciones se definen una vez con su periodicidad y su regla de cálculo. "
     "El sistema genera los pendientes solo, con los festivos colombianos ya contemplados."),
    ("history", "Trazabilidad completa",
     "Quién entregó, cuándo, qué archivo y qué se modificó después. Auditoría de todos "
     "los cambios, no solo del resultado final."),
    ("group", "Portal para terceros",
     "Los sujetos obligados a reportarle a usted entregan por su propio acceso, sin "
     "correos ni archivos sueltos que nadie sabe dónde quedaron."),
    ("upload_file", "El calendario se siembra desde SECOP II",
     "Una foto de sus contratos en SECOP II genera las obligaciones y su periodicidad de "
     "una sola pasada, en vez de cargarlas a mano contrato por contrato. El sistema "
     "arranca con el calendario ya poblado."),
    ("verified", "Firma post-cuántica de entregas",
     "Cada entrega puede firmarse con Quipu: se detecta si el documento fue alterado "
     "después de entregado, y la firma resiste a un computador cuántico."),
]

INFORMES_DESPLIEGUE = [
    ("dns", "En su servidor", "Dentro de su red, sin salir a internet. Los datos no salen de su infraestructura."),
    ("lock", "Aislado por completo", "Instalación air-gapped, sin conexión ni siquiera para instalarlo."),
    ("cloud", "Hospedado", "Nosotros lo operamos. Sin servidores que administrar."),
]

# «PostgreSQL» salió el 2026-08-04: era cierto del SIGER en Python y dejó de
# serlo con el cutover a Rust del 2026-07-28. Hoy `siger-api` abre un
# `SqlitePool` y no tiene una sola línea de PostgreSQL — la característica sigue
# activada en el Cargo.toml de SQLx y no la usa nadie. Anunciar un motor de base
# de datos que el producto no puede abrir es la clase de detalle que un comité
# técnico comprueba antes de comprar.
INFORMES_TAGS = ["Supersalud", "Supersociedades", "SAGRILAFT", "PTEE", "SST",
                 "Reportes ambientales", "SECOP II", "On-premise", "Air-gapped", "Rust",
                 "axum", "maud", "htmx", "SQLite"]

# --- INVENTARIO: producto con demostración pública ---
#
# ES LO ÚNICO DE ESTA PÁGINA QUE EL LECTOR PUEDE PROBAR SIN HABLAR CON NADIE, y
# por eso el rótulo dice «DEMOSTRACIÓN EN VIVO» y no «EN PRODUCCIÓN»: no hay
# cliente todavía. La distinción es la misma que se cuidó en SALUD_FEATURES, con
# una diferencia a favor: aquí la afirmación se verifica haciendo clic.
#
# Lo que NO se puede decir, y por qué:
#
#   «Factura electrónica DIAN» a secas. El sistema calcula el CUFE y el CUDE
#   —probados contra los ejemplos oficiales del anexo técnico 1.9— y guarda todo
#   lo que la Resolución 000165 de 2023 exige, pero NO firma con XAdES-BES ni
#   transmite al servicio de validación previa: eso necesita el certificado
#   digital y la habilitación DEL CLIENTE, que solo él puede tener. Prometerlo
#   entero convertiría en falsa la única sección que hoy se puede comprobar
#   sola. Se dice «listo para certificar» y se explica de quién es el paso que
#   falta.
INVENTARIO_FEATURES = [
    ("inventory_2", "La existencia sale del kardex, no de un campo",
     "No hay ninguna columna «existencia» que se pueda actualizar por otro camino. "
     "Facturar mueve el inventario en la misma transacción: si no hay stock, la factura "
     "no se emite y no se quema un número de resolución."),
    ("calculate", "Costeo NIC 2 completo",
     "PEPS o promedio ponderado, a elección, con el flete y los aranceles repartidos "
     "entre las líneas de la compra. Deterioro al menor entre costo y valor neto "
     "realizable, con su reversión. UEPS se rechaza citando la norma que lo prohíbe."),
    ("gavel", "El IVA que casi nadie liquida",
     "Un obsequio, un consumo interno o un retiro de socios es venta para efectos de IVA "
     "(Estatuto Tributario, art. 421 lit. b), y la base es el valor comercial, no el costo. "
     "Aquí ese movimiento no se puede registrar sin él. También mide el tope del 3 % del "
     "artículo 64 y produce el acta de baja con los campos que la norma enumera."),
    ("fact_check", "Un diagnóstico que dice qué falta",
     "Antes de operar, el sistema revisa su propio estado y enumera qué impide trabajar, "
     "qué impide facturar electrónicamente y qué conviene revisar — cada punto con qué "
     "hacer, no solo con qué falta."),
]

INVENTARIO_CIFRA = ("3.154", "facturas emitidas entre 2004 y 2020 sobre un kardex que llevaba "
                    "parado desde septiembre de 2004: dieciséis años de existencias que no "
                    "eran ciertas, en el sistema que este reemplaza.")

# La etiqueta «Visual FoxPro» salió el 2026-08-18, igual que en la sección de
# salud: nombraba la tecnología del sistema REEMPLAZADO, no la de este. Una
# etiqueta se lee como «está hecho con esto», y aquí decía lo contrario de lo
# que quería decir.
INVENTARIO_TAGS = ["Kardex permanente", "NIC 2", "PEPS y promedio", "CUFE / CUDE",
                   "Resolución 000165 de 2023", "Artículo 64 ET", "GS1 / GTIN",
                   "Rust", "axum", "maud", "htmx", "SQLite"]

# --- SALUD: medico, el sistema clínico ---
#
# EL TITULAR CAMBIÓ EL 2026-08-18, por decisión de Juan. Decía «Sacar una
# historia clínica de Visual FoxPro» y ponía en primer plano el encargo de
# extracción de un cliente, que es trabajo hecho pero no es lo que se muestra.
# Lo que se muestra es EL SISTEMA: medico. La descripción de una línea sale del
# propio producto —«Historia clínica y facturación para prestadores de salud»,
# leída de medico.xiliux.com—, no de una redacción de marketing.
#
# NO SE LE PUSO ENLACE A LA DEMOSTRACIÓN, y es a propósito: medico.xiliux.com
# responde 303 a un formulario de acceso y NO publica las credenciales en la
# pantalla, al revés que inventario.xiliux.com. Un botón «pruébelo» contra un
# muro de acceso es peor que no tener botón.
#
# ES UN CASO, NO UNA OFERTA, y la distinción es deliberada.
#
# Informes puede llevar el rótulo «SISTEMA EN PRODUCCIÓN» porque lo está. Este no:
# el Visual FoxPro sigue corriendo hoy en el consultorio del cliente y la versión
# nueva todavía no emite FEV-RIPS, que es lo único por lo que una IPS compra un
# sistema de historia clínica — sin RIPS no factura. Ponerle la misma etiqueta
# sería la única afirmación falsa de la página, a tres párrafos de la que sí es
# verificable (los contratos de SECOP).
#
# Y hay una asimetría que no se arregla con redacción: informes trata
# obligaciones de reporte; esto trata DATOS DE SALUD, categoría especial de la
# Ley 1581 (arts. 5 y 6). Ofrecerlo como producto convierte a Xiliux en encargado
# del tratamiento frente a una IPS responsable, con política, contrato de
# transmisión y responsabilidad propia — sobre una persona natural, porque Xiliux
# es nombre comercial. Un prestador que evalúa un sistema pregunta además si le
# sirve para la habilitación (Res. 3100 de 2019); el software no se habilita, se
# habilita el servicio, pero una página que dice «para su IPS» provoca esa
# pregunta y una que dice «esto es lo que hicimos» no.
#
# El objetivo comercial de esta sección es la tarjeta «Sistema a la medida —
# Rust, a cotización»: vende el SERVICIO que sí se puede entregar hoy,
# usando este trabajo como prueba. El día que haya cliente y el FEV-RIPS pase el
# validador de MinSalud, se reescribe a oferta. Al revés —retirar una promesa ya
# publicada— no se puede.
SALUD_FEATURES = [
    ("swap_horiz", "Migrar sin que los números cambien",
     "Las fórmulas de antropometría y los informes epidemiológicos se trasladan "
     "literalmente, aunque parezcan mejorables. Si las cifras no coinciden con las que el "
     "prestador viene reportando, el sistema nuevo no le sirve para nada."),
    ("receipt_long", "La cadena RIPS → FEV-RIPS → validador",
     "El documento único de la Resolución 948 de 2026, hasta obtener el CUV del Mecanismo "
     "Único de Validación de MinSalud. Contra el validador solo se prueba en su ambiente "
     "de pruebas: en producción una factura inventada obtiene un CUV verdadero, con "
     "efectos jurídicos reales."),
    ("shield_person", "Una institución no ve a la otra, y no puede",
     "El alcance de quien consulta es un parámetro obligatorio de toda consulta: no hay "
     "forma de leer un registro sin decir desde dónde se mira. Y lo ajeno responde «no "
     "existe», nunca «no autorizado» — un «no autorizado» confirma que el registro está "
     "ahí, y con eso se averigua quién es paciente de la clínica de al lado."),
    ("hub", "Interoperable con la historia clínica nacional",
     "Produce los recursos clínicos en HL7 FHIR R4 según la Resolución 1888 de 2025 "
     "(RDA / IHCE), validados contra el perfil oficial del país — hoy sin incumplidas en "
     "los recursos de consulta. Como con el FEV-RIPS, el paso que falta no es de código "
     "sino de habilitación: las credenciales del ambiente de pruebas del prestador."),
    ("auto_delete", "El ciclo del dato, cerrado hasta el final",
     "A los veinte años de la defunción la historia se archiva cifrada y firmada, se purga "
     "la copia viva y se emite un certificado de supresión: el cierre que la Ley 1581 exige "
     "y que casi ningún sistema clínico completa. Nace inactivo y con prueba-de-vida, para "
     "que un dato no se borre por accidente."),
    ("fact_check", "De dónde salió cada dato",
     "El clínico tiene doce minutos por paciente, así que los sistemas rellenan solos: un "
     "código de consulta por defecto, un estado de salida «estable», un valor de servicio "
     "en cero. Datos que nadie afirmó, indistinguibles de los reales. Aquí cada valor "
     "queda marcado como confirmado, derivado, propuesto y aceptado, o ausente."),
]

# El dato verificable de esta sección, medido en el propio sistema y no estimado.
# Es lo que mejor explica el método: donde otro pone el primero de la lista y
# produce un dato con la forma correcta que nadie afirmó, aquí el campo se deja
# vacío — y la norma lo admite vacío.
SALUD_CIFRA = ("1.402", "códigos CIE-10 (el 11,3 %) tienen más de una equivalencia en CIE-11, "
               "hasta 42 destinos distintos para uno solo.")

# El port a Rust TERMINÓ: desde el 2026-08-08 salió Angular (0 archivos .ts
# versionados) y el 2026-08-09 el backend Python perdió su API. Hoy medico corre
# en producción (medico.xiliux.com) como UN binario Rust —axum + SQLx sobre
# SQLite, las pantallas tejidas con maud + htmx—. Las etiquetas dicen el stack
# real desplegado; ya no hay Python ni Angular que sostengan la operación.
SALUD_TAGS = ["Historia clínica", "RIPS", "FEV-RIPS", "Resolución 948 de 2026",
              "HL7 FHIR R4", "RDA / IHCE", "Resolución 1888 de 2025", "Habeas data",
              "CIE-11", "CUPS", "CUM INVIMA", "Multi-institucional", "Rust", "axum",
              "maud", "htmx", "SQLite"]

QUIPU_FEATURES = [
    ("lock", "Híbrido post-cuántico", "Cifrado X25519 + ML-KEM-1024 y firma Ed25519 + ML-DSA-87 — clásico y post-cuántico a la vez, para que romper uno no baste. Opción de X-Wing-768 interoperable (borrador CFRG, conforme a sus vectores oficiales) y de firma triple que suma SLH-DSA: tres esquemas, y las tres firmas tienen que validar."),
    ("fact_check", "Verificado contra tres implementaciones independientes", "Su ML-KEM y su ML-DSA se comparan byte a byte, en los tres niveles de seguridad, contra la referencia C de pq-crystals, contra libcrux (formalmente verificada) y contra AWS-LC (producción). Coincidir con tres implementaciones que no se conocen entre sí es prueba de que el estándar está bien implementado, no solo afirmado — cada discrepancia sería un fallo real."),
    ("verified_user", "Solo primitivas verificadas", "XChaCha20-Poly1305, Argon2id y HKDF. Nunca inventa criptografía: la seguridad vive en la clave, no en ocultar el formato."),
    ("key", "La llave no sale del HSM", "La clave privada de firma puede vivir en un módulo de hardware (HSM, token o tarjeta) y no salir nunca de ahí: se firma dentro del dispositivo. Es la primera pregunta de todo comité de seguridad."),
    ("gpp_good", "Sin llaves débiles por diseño", "Si el sistema no puede dar aleatoriedad, se detiene y avisa en vez de generar una clave predecible que parece correcta. El fallo que hundió a media internet en 2008, imposible por construcción."),
    ("integration_instructions", "Rust puro", "Escrita íntegramente en Rust, sin unsafe de primera parte. Se usa nativa desde Rust y, para quien no programa en Rust, como rueda de Python (PyO3)."),
    ("tune", "Modos para problemas reales", "Cifrado <em>discreto</em> (sin cabecera en claro, indistinguible de bytes al azar), cifrado <em>perforable</em> (la clave se destruye al abrir, con registro encadenado de cada apertura), custodia por umbral (Shamir, k-de-n para respaldar la clave) y evaluación ciega online por VOPRF conforme a la RFC 9497. No son adornos: cada modo salió de un requisito que un cifrado normal no cubre."),
    ("shield", "Algoritmos post-cuánticos de CNSA 2.0", "ML-KEM-1024 y ML-DSA-87, categoría de seguridad NIST 5 — los que exige CNSA 2.0. La parte simétrica usa XChaCha20-Poly1305 en vez de AES-256-GCM, a propósito: es de tiempo constante en cualquier CPU, y AES no lo es sin aceleración por hardware. Si su mandato exige la suite completa, el perfil hermano <code class=\"font-mono text-cyan-400 bg-slate-950 px-1.5 py-0.5 rounded\">quipu-cnsa</code> la sigue. Alinearse con los algoritmos no es estar validado FIPS 140-3, y eso no está en el plan."),
]
# Aquí había `cargo add quipu` y `pip install quipu-crypto`. Los dos FALLAN
# desde el 2026-08-10, y un comando que el visitante pega en su terminal y le da
# error hace más daño que un enlace roto: el enlace roto se ve antes de hacer
# clic. Lo que se muestra ahora es lo que de verdad ocurre al pedir el código.
QUIPU_ENTREGA = [
    ("1", "Escríbenos por el formulario de contacto"),
    ("2", "Recibes el código con su firma y su SHA-256"),
    ("3", "Verificas la firma antes de compilar"),
]
QUIPU_TAGS = ["Rust", "Python", "ML-KEM-1024", "ML-DSA-87", "SLH-DSA", "X-Wing", "VOPRF (RFC 9497)", "XChaCha20-Poly1305", "Argon2id", "PKCS#11", "HSM", "AGPL-3.0"]

# --- TUNJO: Quipu aplicado a la integridad de evidencia digital ---
# Va en su propio bloque y NO en OSS_LIBS: aquella sección es de micro-librerías
# Apache-2.0 extraídas de sistemas en producción, y esto es una herramienta AGPL
# en Rust construida sobre Quipu. Mezclarlas volvería mentira el encabezado.
TUNJO_LINKS = {"repo": "https://github.com/isazajuancarlos/tunjo"}
TUNJO_FEATURES = [
    ("fingerprint", "Un hash por archivo, una raíz por conjunto",
     "Árbol de Merkle sobre todo lo recogido. Permite demostrar que un archivo estaba "
     "en la adquisición sin exhibir los demás: verificar el correo que interesa no "
     "obliga a abrir los otros cuatro mil."),
    ("verified", "Firma triple, y las tres deben validar",
     "Ed25519 + ML-DSA-87 + SLH-DSA sobre el acta completa. Una prueba tiene que seguir "
     "verificándose años después, cuando el proceso llegue a instancias superiores."),
    ("public", "Lo verifica cualquiera, sin pedirte nada",
     "El verificador es libre y su código es público. Un sello que solo su autor puede "
     "comprobar no es una prueba: es una afirmación."),
    ("report_problem", "Ante la duda, ruido",
     "Un archivo que no se puede leer detiene el sellado en vez de desaparecer del acta. "
     "Y si no se declara cómo se contrastó el reloj, queda escrito que no se verificó."),
]
TUNJO_TAGS = ["Rust", "SHA-256", "Merkle", "ML-DSA-87", "SLH-DSA", "Ed25519",
              "Cadena de custodia", "AGPL-3.0"]

# --- GUACA: Quipu puesto a trabajar dentro de una aplicación ---
# Hermana de Tunjo (AGPL, Rust, sobre Quipu), NO va en OSS_LIBS (Apache). Una
# guaca es un tesoro enterrado y protegido: aquí, los datos en reposo.
GUACA_LINKS = {"repo": "https://github.com/isazajuancarlos/guaca"}
GUACA_FEATURES = [
    ("lock", "Cifrado en reposo, no solo en tránsito",
     "Los archivos sensibles —una historia clínica, una entrega— se guardan cifrados "
     "con AEAD: un backup robado o el acceso al disco solo obtiene ruido. La frase de "
     "cifrado nunca vive junto al dato."),
    ("verified", "Firma que delata cualquier cambio",
     "Cada registro se firma (Ed25519 + ML-DSA-87). Si alguien edita la fila por debajo "
     "de la aplicación, la verificación lo detecta: distingue «intacto» de «alterado»."),
    ("receipt_long", "Bitácora encadenada, no solo una tabla",
     "Cada acceso se enlaza por hash al anterior y va firmado: borrar o reordenar un "
     "evento rompe la cadena, no solo alterarlo. El rastro a prueba de manipulación que "
     "pide la ley de datos personales."),
    ("key", "La clave no vive en un solo sitio",
     "Se deriva de un secreto de despliegue (Argon2) y se reparte con Shamir en las partes "
     "que usted decida, bastando el umbral que fije —tres de las que basten dos, cinco de "
     "las que basten tres— para respaldarla: ningún lugar único la tiene entera."),
]
GUACA_TAGS = ["Rust", "ML-DSA-87", "XChaCha20-Poly1305", "Argon2id", "Shamir",
              "Hash-chain", "AGPL-3.0"]

# Librerías extraídas de sistemas propios en producción. Infraestructura pura —
# el contrapunto ligero al insignia (Quipu). Cada una nace de un problema real,
# no de un ejercicio.
#
# Casi todas son Python/Apache-2.0; `mirilla` es Rust/MIT y rompe el patrón a
# propósito: es un arnés de PRUEBAS, y una licencia permisiva sin cláusula de
# patentes le quita fricción a quien solo quiere probar su pantalla. La licencia
# de cada una va en sus `tags`, que es donde se lee.
OSS_LIBS = [
    {
        "name": "position-sizing",
        "icon": "balance",
        "desc": "Traduce un presupuesto de riesgo a una cantidad que el exchange acepte, sin pasarse nunca del riesgo. Redondea hacia abajo, respeta mínimos, nocional y contract size, y cuenta las comisiones. Nace de un bug real: <code class=\"font-mono text-cyan-400 bg-slate-950 px-1.5 py-0.5 rounded\">max(1, int(cantidad))</code> abre posiciones que arriesgan diez veces lo autorizado.",
        "post": "/blog/dimensionar-posicion-sin-pasarse-del-riesgo",
        "repo": "https://github.com/isazajuancarlos/position-sizing",
        "tags": ["Python", "trading", "Decimal", "Apache-2.0"],
    },
    {
        "name": "ccxt-resilience",
        "icon": "shield_moon",
        "desc": "Endurece un cliente ccxt legítimo contra los falsos positivos de Cloudflare: hardening de cabeceras y retry selectivo con backoff que reintenta solo lo transitorio (403/429/timeout) y re-lanza los errores reales al instante.",
        "post": "/blog/por-que-tu-bot-recibe-403-de-cloudflare-ccxt",
        "repo": "https://github.com/isazajuancarlos/ccxt-resilience",
        "tags": ["Python", "ccxt", "Apache-2.0"],
    },
    {
        "name": "honest-eval",
        "icon": "insights",
        "desc": "Dos primitivas para no mentirte en un backtest: split walk-forward con embargo (sin fuga de futuro) y un gate de significancia apareado con n efectivo de Kish y cota inferior de confianza. Python puro, sin dependencias.",
        "post": "/blog/dos-formas-en-que-un-backtest-te-miente",
        "repo": "https://github.com/isazajuancarlos/honest-eval",
        "tags": ["Python", "Estadística", "Apache-2.0"],
    },
    {
        "name": "hysteresis-state",
        "icon": "toggle_on",
        "desc": "Máquina de estados con histéresis por confirmación: un estado nuevo solo se commitea tras sostenerse N observaciones consecutivas. Anti-flapping para clasificadores ruidosos, con histéresis asimétrica opcional. Python puro, sin dependencias.",
        "post": "/blog/anti-flapping-histeresis-clasificador-ruidoso",
        "repo": "https://github.com/isazajuancarlos/hysteresis-state",
        "tags": ["Python", "Máquinas de estado", "Apache-2.0"],
    },
    {
        "name": "fanout-broadcast",
        "icon": "hub",
        "desc": "Reparte un mensaje a varios canales con aislamiento de fallos: un canal caído no detiene a los demás, y un reporte dice qué se entregó, qué se omitió y qué falló. Para notificaciones, webhooks o alertas. Python puro, sin dependencias.",
        "post": "/blog/repartir-a-varios-canales-sin-que-uno-tumbe-al-resto",
        "repo": "https://github.com/isazajuancarlos/fanout-broadcast",
        "tags": ["Python", "Notificaciones", "Apache-2.0"],
    },
    {
        "name": "dotkey-i18n",
        "icon": "translate",
        "desc": "Internacionalización mínima: claves con notación de punto sobre ficheros JSON, con caché, fallback al idioma por defecto e interpolación. Sin gettext ni paso de compilación, agnóstica del framework. Python puro, sin dependencias.",
        "post": "/blog/i18n-minima-sin-gettext-claves-de-punto-json",
        "repo": "https://github.com/isazajuancarlos/dotkey-i18n",
        "tags": ["Python", "i18n", "Apache-2.0"],
    },
    {
        "name": "tumbaga",
        "icon": "key",
        "desc": "Verificación de contraseñas con cadena de esquemas y actualización oportunista: el usuario migra de bcrypt a Argon2id al iniciar sesión, sin restablecer nada y sin enterarse. Existe porque un hash es de una sola vía —de <code class=\"font-mono text-cyan-400 bg-slate-950 px-1.5 py-0.5 rounded\">bcrypt(clave)</code> no se saca la clave—, así que no hay script que migre contraseñas: el único instante en que se puede es el inicio de sesión.",
        "repo": "https://github.com/isazajuancarlos/tumbaga",
        "tags": ["Python", "Argon2id", "bcrypt", "Apache-2.0"],
    },
    {
        "name": "chibcha",
        "icon": "gavel",
        "desc": "Constantes legislativas colombianas <strong>con la norma que las fija</strong>: SMMLV, UVT, auxilio de transporte, IPC, aportes, ARL, jornada y festivos. Nada devuelve un número pelado —<code class=\"font-mono text-cyan-400 bg-slate-950 px-1.5 py-0.5 rounded\">smmlv(2026).norma</code> dice de qué decreto sale—, porque en una liquidación el valor sin su fuente no se sustenta ante nadie. Si un año no está, levanta excepción en vez de devolver el más cercano.",
        "repo": "https://github.com/isazajuancarlos/chibcha",
        "tags": ["Python", "Derecho colombiano", "Decimal", "Apache-2.0"],
    },
    {
        "name": "mirilla",
        "icon": "visibility",
        "desc": "Conduce un Chromium sin cabeza por CDP <strong>sobre una tubería</strong> —los descriptores 3 y 4— en vez de por un puerto: nada que descubrir, nada a lo que esperar, y dos pruebas en paralelo no se pisan. Existe porque un banco que afirma sobre el texto que devuelve el servidor mide el códec y no el producto: un fragmento insertado en el sitio equivocado devuelve <code class=\"font-mono text-cyan-400 bg-slate-950 px-1.5 py-0.5 rounded\">el mismo 200 con el mismo cuerpo</code>. Entra por el formulario en vez de inyectar la cookie, así que mide el acceso de paso. Dos dependencias.",
        "post": "/blog/tu-banco-e2e-mide-el-codec-no-el-producto",
        "repo": "https://github.com/isazajuancarlos/mirilla",
        "tags": ["Rust", "CDP", "Chromium", "Pruebas E2E", "MIT"],
    },
]

# Patrocinadores del tier "logo en la web" ($100/mes de GitHub Sponsors).
# Para añadir uno, agrega un dict aquí:
#   {"name": "Acme Corp", "url": "https://acme.com", "logo": "https://acme.com/logo.png"}
# - "logo": URL de una imagen (mejor con fondo transparente). Si es None o falta,
#   se muestra el nombre en texto. La galería solo aparece cuando hay al menos uno.
SPONSORS = []


def load_projects():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_projects(projects):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(projects, f, indent=4)

def save_lead(name, email):
    leads = []
    if os.path.exists(LEADS_FILE):
        try:
            with open(LEADS_FILE, 'r', encoding='utf-8') as f:
                leads = json.load(f)
        except Exception:
            pass
    leads.append({
        'name': name, 'email': email,
        'date': str(datetime.datetime.now()), 'source': 'Lead Magnet'
    })
    with open(LEADS_FILE, 'w', encoding='utf-8') as f:
        json.dump(leads, f, indent=4)

projects_data = load_projects()

# nginx (mismo host) es el único proxy: solo se confía en X-Forwarded-* de
# 127.0.0.1. Con "*" cualquiera podía falsear su IP/protocolo vía cabeceras.
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["127.0.0.1"])


class HeadComoGet:
    """`HEAD` responde lo mismo que `GET`, sin cuerpo (RFC 9110 §9.3.2).

    Medido el 2026-08-05 contra producción: **diez de once rutas devolvían 405**
    —`/`, `/blog`, `/servicios`, `/quipu`, `/informes`, `/cotizador`,
    `/quipu/precios`, `/robots.txt`, `/sitemap.xml`, `/manifest.json`—; solo
    `/favicon.ico` contestaba. Dos consecuencias, y la segunda tardó en verse:

    1. Un monitor de disponibilidad estándar sondea con `HEAD`, así que veía
       CAÍDA la página que cobra con PayPal. Una alarma que resulta falsa dos
       veces es una alarma que a la tercera nadie mira.
    2. `/robots.txt` y `/sitemap.xml` también daban 405, y los rastreadores
       usan `HEAD`. En un sitio cuyo propósito es posicionar, eso no es un
       detalle de monitorización.

    POR QUÉ VA COMO MIDDLEWARE Y NO COMO `@app.head('/')`: la causa no es que a
    la portada le falte un método, es que **FastAPI no añade `HEAD` cuando
    registras un `GET`** —Starlette sí lo hace en su `Route`, `APIRoute` no—,
    así que la regla vale para todas las rutas de golpe y para las que se
    escriban mañana. Arreglar solo `/` habría dejado nueve rotas y la próxima
    página nacería rota otra vez (directiva 23: el arreglo va en la REGLA).

    POR QUÉ NO SE ARREGLA EN NGINX, que era la otra salida obvia y es peor: si
    nginx contesta el `HEAD` por su cuenta, el monitor recibe 200 aunque el
    proceso esté muerto — «sano y quieto» y «muerto» pasarían a verse igual, que
    es exactamente lo que un monitor existe para distinguir. Contestando desde
    la aplicación, un 200 prueba que el proceso vive y que su router funciona.

    El `Content-Length` que viaja es el que habría devuelto el `GET`, y eso es
    lo correcto según la RFC: describe el recurso, no este mensaje.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get('type') != 'http' or scope.get('method') != 'HEAD':
            await self.app(scope, receive, send)
            return
        cuerpo_enviado = False

        async def send_sin_cuerpo(message):
            nonlocal cuerpo_enviado
            if message['type'] != 'http.response.body':
                await send(message)
                return
            # El GET puede emitir el cuerpo en varios trozos; se traga entero y
            # se responde con uno vacío. Sin este guardia, una respuesta
            # troceada mandaría varios `http.response.body` tras el final.
            if cuerpo_enviado:
                return
            cuerpo_enviado = True
            await send({'type': 'http.response.body', 'body': b'', 'more_body': False})

        await self.app(dict(scope, method='GET'), receive, send_sin_cuerpo)


app.add_middleware(HeadComoGet)

# --- RUTAS SEO ---
@app.get('/robots.txt', response_class=PlainTextResponse)
def robots():
    # AEO/GEO: bienvenida EXPLÍCITA a los rastreadores de IA. El objetivo no es
    # solo que Google indexe, sino que ChatGPT/Claude/Perplexity/Gemini CITEN el
    # contenido — para eso hay que dejarlos entrar a propósito. Un bloque nombrado
    # por agente es la señal que algunos buscan; el `User-agent: *` de cierre
    # cubre al resto. Ver también /llms.txt.
    ia = ("GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "anthropic-ai",
          "Claude-User", "PerplexityBot", "Perplexity-User", "Google-Extended", "CCBot")
    bloques = "".join(f"User-agent: {b}\nAllow: /\n\n" for b in ia)
    return f"{bloques}User-agent: *\nAllow: /\nSitemap: {DOMAIN}/sitemap.xml\n"

@app.get('/sitemap.xml')
def sitemap():
    lastmod = datetime.datetime.now().strftime('%Y-%m-%d')
    # Página principal con logo
    urls = [f"""<url><loc>{DOMAIN}/</loc><lastmod>{lastmod}</lastmod><changefreq>weekly</changefreq><priority>1.0</priority><image:image><image:loc>{DOMAIN}/logo.png</image:loc><image:caption>Xiliux — Python y Rust · Cripto post-cuántica e IA</image:caption></image:image></url>"""]
    # Proyectos con sus imágenes
    for p in projects_data:
        img_tag = f'<image:image><image:loc>{p["image"]}</image:loc><image:caption>{p["title"]} - {p["category"]}</image:caption></image:image>' if p.get('image') else ''
        urls.append(f'<url><loc>{DOMAIN}/project/{p["id"]}</loc><lastmod>{lastmod}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority>{img_tag}</url>')
    # Páginas de producto. Prioridad alta: son las que deben posicionar.
    # `cotizador` y `quipu/precios` son páginas de CONVERSIÓN (estimador y planes);
    # faltaban aquí y Google las descubría solo por enlace interno.
    for ruta in ('servicios', 'informes', 'cotizador', 'quipu', 'quipu/cbom', 'quipu/precios',
                 'quipu/codigo', 'en', 'en/quipu',
                 'en/services', 'en/quipu/code', 'librerias/codigo', 'en/libraries/code'):
        urls.append(f'<url><loc>{DOMAIN}/{ruta}</loc><lastmod>{lastmod}</lastmod>'
                    f'<changefreq>monthly</changefreq><priority>0.9</priority></url>')
    # Blog: índice + artículos
    urls.append(f'<url><loc>{DOMAIN}/blog</loc><lastmod>{lastmod}</lastmod><changefreq>weekly</changefreq><priority>0.7</priority></url>')
    # La política solo entra al sitemap cuando deja de ser un borrador.
    if privacy_ready():
        urls.append(f'<url><loc>{DOMAIN}/privacidad</loc><lastmod>{lastmod}</lastmod><changefreq>yearly</changefreq><priority>0.3</priority></url>')
    for post in posts_data:
        urls.append(f'<url><loc>{DOMAIN}/blog/{post["slug"]}</loc><lastmod>{post.get("date", lastmod)}</lastmod><changefreq>monthly</changefreq><priority>0.7</priority></url>')
    # Tier 3: versiones en inglés (las que tienen campo `en`) + su índice. La
    # relación ES<->EN la lleva el hreflang de cada página; aquí solo se declaran
    # para que Google las descubra.
    en_posts = [p for p in posts_data if p.get('en')]
    if en_posts:
        urls.append(f'<url><loc>{DOMAIN}/en/blog</loc><lastmod>{lastmod}</lastmod><changefreq>weekly</changefreq><priority>0.7</priority></url>')
        for post in en_posts:
            urls.append(f'<url><loc>{DOMAIN}/en/blog/{post["slug"]}</loc><lastmod>{post.get("date", lastmod)}</lastmod><changefreq>monthly</changefreq><priority>0.7</priority></url>')
    return Response(content=f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">{"".join(urls)}</urlset>', media_type="application/xml")

# --- RSS ---
# El blog llevaba 25 entradas y ningún canal de suscripción: /rss.xml daba 404.
# Es el canal más barato que existe para que a uno lo sigan, y el único que no
# depende de ninguna plataforma.
#
# Los días y meses van por CONSTANTE y no por `strftime('%a')`: RFC-822 los
# exige en inglés, y `%a`/`%b` los traduce según la configuración regional del
# proceso. Un servidor con locale es_CO produciría «mar, 18 ago 2026», que
# ningún lector entiende — y el fallo no daría ningún error, solo un feed que
# nadie puede leer.
_RSS_DIAS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_RSS_MESES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

def _rfc822(fecha_iso):
    """`2026-08-18` -> `Tue, 18 Aug 2026 00:00:00 +0000`. Sin hora en el JSON,
    se publica a medianoche UTC: es determinista y no inventa una precisión que
    el dato no tiene."""
    try:
        d = datetime.date.fromisoformat(str(fecha_iso))
    except (ValueError, TypeError):
        d = datetime.date.today()
    return (f"{_RSS_DIAS[d.weekday()]}, {d.day:02d} {_RSS_MESES[d.month - 1]} "
            f"{d.year} 00:00:00 +0000")

def _xml(texto):
    """Escapa `&`, `<` y `>`. Los títulos llevan comillas angulares y rayas, que
    en XML no molestan; el `&` sí, y basta uno para dejar el feed ilegible."""
    return _htmlmod.escape(texto or "", quote=False)

# Los dos idiomas comparten generador. Se extrae en cuanto existe el segundo y
# no se copia (directiva 9): un feed duplicado a mano diverge en el primer
# arreglo que alguien aplique solo a uno de los dos, y nadie lo nota porque los
# dos siguen devolviendo XML válido.
RSS_CANALES = {
    "es": {
        "ruta": "/rss.xml",
        "indice": "/blog",
        "titulo": "Xiliux — Blog",
        "descripcion": ("Criptografía post-cuántica, librerías fiables en Rust y Python, "
                        "y sistemas que se prueban antes de prometer. Cada entrada con su "
                        "número medido."),
    },
    "en": {
        "ruta": "/en/rss.xml",
        "indice": "/en/blog",
        "titulo": "Xiliux — Blog (English)",
        "descripcion": ("Post-quantum cryptography, dependable Rust and Python libraries, "
                        "and systems measured before they are promised. Every post carries "
                        "its number."),
    },
}

def _rss_entradas(lang):
    """Las entradas del feed de `lang`, ya ordenadas (posts_data viene del más
    reciente al más antiguo). En inglés solo entran las que TIENEN traducción:
    un ítem en inglés que enlaza a una página en español es peor que no estar,
    porque el lector se suscribe y recibe algo que no puede leer."""
    for post in posts_data:
        if lang == "en":
            en = post.get("en") or {}
            if not en.get("title"):
                continue
            yield post, en.get("title", ""), en.get("description", "")
        else:
            yield post, post.get("title", ""), post.get("description", "")

def _rss_canal(lang):
    cfg = RSS_CANALES[lang]
    prefijo = "/en/blog" if lang == "en" else "/blog"
    items, fechas = [], []
    for post, titulo, descripcion in _rss_entradas(lang):
        enlace = f'{DOMAIN}{prefijo}/{post["slug"]}'
        fechas.append(post.get("date"))
        categorias = "".join(f'<category>{_xml(t)}</category>' for t in post.get('tags', []))
        items.append(
            '<item>'
            f'<title>{_xml(titulo)}</title>'
            f'<link>{enlace}</link>'
            f'<guid isPermaLink="true">{enlace}</guid>'
            f'<pubDate>{_rfc822(post.get("date"))}</pubDate>'
            f'<description>{_xml(descripcion)}</description>'
            f'{categorias}'
            '</item>')
    # lastBuildDate de la entrada más reciente DEL FEED, no de now() ni de la
    # más reciente del sitio: describe cuándo cambió ESTE contenido, y así dos
    # peticiones seguidas devuelven lo mismo. En inglés suele ser anterior.
    ultima = _rfc822(max(f for f in fechas if f)) if any(fechas) else _rfc822(None)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">'
        '<channel>'
        f'<title>{_xml(cfg["titulo"])}</title>'
        f'<link>{DOMAIN}{cfg["indice"]}</link>'
        f'<description>{_xml(cfg["descripcion"])}</description>'
        f'<language>{lang}</language>'
        f'<lastBuildDate>{ultima}</lastBuildDate>'
        f'<atom:link href="{DOMAIN}{cfg["ruta"]}" rel="self" type="application/rss+xml"/>'
        f'{"".join(items)}'
        '</channel></rss>')

@app.get('/rss.xml')
def rss():
    return Response(content=_rss_canal("es"), media_type="application/rss+xml; charset=utf-8")

@app.get('/en/rss.xml')
def rss_en():
    return Response(content=_rss_canal("en"), media_type="application/rss+xml; charset=utf-8")

@app.get('/feed.xml')
def feed_alias():
    # Segunda ruta más tecleada por los lectores. Un 301 evita mantener dos.
    return RedirectResponse('/rss.xml', status_code=301)

@app.get('/en/feed.xml')
def feed_alias_en():
    return RedirectResponse('/en/rss.xml', status_code=301)

@app.get('/llms.txt', response_class=PlainTextResponse)
def llms_txt():
    """Índice curado para asistentes de IA (estándar llms.txt / AEO-GEO). No es
    robots ni sitemap: es un resumen en markdown, legible por un LLM, de lo que
    Xiliux hace y de su mejor contenido, para que ChatGPT/Claude/Perplexity CITEN
    con precisión en vez de adivinar. Se deriva de las MISMAS fuentes que el sitio
    (OSS_LIBS, posts_data) para no envejecer con él."""
    def plano(s):  # OSS_LIBS.desc trae HTML; los artículos, texto llano
        return re.sub(r'<[^>]+>', '', s or '').strip()
    L = [
        "# Xiliux",
        "",
        "> Software honesto en Rust y Python: criptografía post-cuántica, "
        "herramientas de trading fiables y automatización con IA. Detrás está "
        "Juan Carlos Isaza, el desarrollador que escribe cada línea y cada "
        "artículo con conocimiento de primera mano.",
        "",
        "## Productos",
        f"- [Quipu — cifrado post-cuántico en Rust]({DOMAIN}/quipu): KEM híbrido "
        "X25519 + ML-KEM-1024 y firma híbrida Ed25519 + ML-DSA-87, con perfil "
        "CNSA 2.0. Resistente al algoritmo de Shor.",
        f"- [Informes — obligaciones recurrentes]({DOMAIN}/informes): no perder un "
        "reporte con vencimiento (LegalTech).",
        f"- [Servicios y MVPs]({DOMAIN}/servicios): del brief al MVP en 2 semanas.",
        f"- [English landing]({DOMAIN}/en): the same work described in English, for "
        f"readers outside Colombia, with [Quipu]({DOMAIN}/en/quipu) and "
        f"[services]({DOMAIN}/en/services) translated.",
        f"- [Código de las librerías]({DOMAIN}/librerias/codigo): fuente completo de las nueve micro-librerías, descarga directa y firmada (Ed25519 + ML-DSA-87).",
        "",
        "## Librerías de código abierto",
    ]
    L += [f"- [{lib['name']}]({lib['repo']}): {plano(lib['desc'])}" for lib in OSS_LIBS]
    L += ["", "## Artículos"]
    L += [f"- [{p['title']}]({DOMAIN}/blog/{p['slug']}): {plano(p.get('description'))}"
          for p in posts_data]
    return "\n".join(L) + "\n"

@app.get('/logo.png')
def logo_file():
    if os.path.exists(LOGO_PATH): return FileResponse(LOGO_PATH, media_type='image/png')
    return PlainTextResponse("Not found", status_code=404)

@app.get('/logo.webp')
def logo_webp_file():
    webp_path = os.path.join(BASE_DIR, 'logo.webp')
    if os.path.exists(webp_path): return FileResponse(webp_path, media_type='image/webp')
    return PlainTextResponse("Not found", status_code=404)

@app.get('/favicon.ico')
def favicon_file():
    favicon_path = os.path.join(BASE_DIR, 'favicon.ico')
    if os.path.exists(favicon_path): return FileResponse(favicon_path, media_type='image/x-icon')
    return PlainTextResponse("Not found", status_code=404)

@app.get('/assets/{fname}')
def asset_file(fname: str):
    # Imágenes de proyecto desde assets/. Sin traversal: solo basename y extensión en lista.
    if fname != os.path.basename(fname):
        return PlainTextResponse("Not found", status_code=404)
    tipos = {'.png': 'image/png', '.webp': 'image/webp', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}
    tipo = tipos.get(os.path.splitext(fname)[1].lower())
    ruta = os.path.join(ASSETS_DIR, fname)
    if tipo and os.path.exists(ruta):
        return FileResponse(ruta, media_type=tipo)
    return PlainTextResponse("Not found", status_code=404)

@app.get('/guia_automatizacion.pdf')
def download_guide():
    if os.path.exists(PDF_PATH): return FileResponse(PDF_PATH, media_type='application/pdf', filename='Guia_Automatizacion.pdf')
    return PlainTextResponse("No encontrado", status_code=404)

# --- ENTREGA DEL CÓDIGO DE QUIPU (descarga directa, firmada) ---
#
# El código de Quipu se entrega a pedido (ver /quipu/codigo). Estos dos archivos
# son la entrega en sí, servida por el mismo binario que sirve el sitio para no
# depender de nadie más. El .zip es solo el sobre: la firma va sobre el .tar.gz
# de dentro, así que sobrevive a que un servidor de correo lo reempaquete.
#
# La huella de la clave con la que se comprueba la firma está PUBLICADA en
# /quipu/codigo, que es un canal distinto de la descarga — una clave que viaje
# solo dentro del paquete que autentica no prueba nada.

ENTREGA_DIR = os.path.join(BASE_DIR, 'entrega')

# LA ENTREGA DE OTF SE QUEDA DONDE ESTÁ, Y NO SE TOCA.
#
# Esta URL y las sumas SHA-256 de su manifiesto están citadas en la solicitud
# #22572 al Open Technology Fund, o sea en un registro que no controlamos y que
# no se puede editar después. Cambiar el archivo detrás de esta ruta invalidaría
# esa cita: quien fuera a comprobarla encontraría otras sumas y tendría razón al
# desconfiar. Es una entrega CONGELADA de la v0.11.1, y así se queda.
#
# La fuente al día vive en la ruta de abajo.
@app.get('/quipu/entrega/quipu-otf-22572.zip')
def entrega_zip():
    ruta = os.path.join(ENTREGA_DIR, 'quipu-otf-22572.zip')
    if os.path.exists(ruta):
        return FileResponse(ruta, media_type='application/zip',
                            filename='quipu-otf-22572.zip')
    return PlainTextResponse("No encontrado", status_code=404)


# LA FUENTE AL DÍA, con nombre ESTABLE.
#
# El nombre del archivo no lleva la versión a propósito: quien enlace esto una
# vez tiene que seguir llegando a la fuente actual, y la versión concreta la dice
# la página y el manifiesto. El nombre con el que se descarga sí la lleva, para
# que en el disco de quien lo baje no se confundan dos.
ENTREGA_ACTUAL = 'quipu-fuente.zip'


@app.get('/quipu/entrega/quipu-fuente.zip')
def entrega_actual():
    ruta = os.path.join(ENTREGA_DIR, ENTREGA_ACTUAL)
    if not os.path.exists(ruta):
        return PlainTextResponse("No encontrado", status_code=404)
    # El nombre de descarga se deriva del manifiesto, que es el artefacto que
    # dice qué versión es esto. Si no se puede leer, se sirve con el nombre
    # genérico en vez de inventarse una versión (directiva 20).
    nombre = 'quipu-fuente.zip'
    try:
        with open(os.path.join(ENTREGA_DIR, 'MANIFIESTO-ACTUAL.txt'), encoding='utf-8') as f:
            for linea in f:
                if linea.startswith('VERSION '):
                    nombre = f"quipu-{linea.split()[1]}.zip"
                    break
    except OSError:
        pass
    return FileResponse(ruta, media_type='application/zip', filename=nombre)


@app.get('/quipu/entrega/MANIFIESTO-ACTUAL.txt')
def entrega_manifiesto_actual():
    ruta = os.path.join(ENTREGA_DIR, 'MANIFIESTO-ACTUAL.txt')
    if os.path.exists(ruta):
        return FileResponse(ruta, media_type='text/plain; charset=utf-8')
    return PlainTextResponse("No encontrado", status_code=404)

@app.get('/quipu/entrega/MANIFIESTO.txt')
def entrega_manifiesto():
    ruta = os.path.join(ENTREGA_DIR, 'MANIFIESTO.txt')
    if os.path.exists(ruta):
        return FileResponse(ruta, media_type='text/plain; charset=utf-8')
    return PlainTextResponse("No encontrado", status_code=404)

@app.get('/manifest.json')
def manifest_file():
    manifest_path = os.path.join(BASE_DIR, 'manifest.json')
    if os.path.exists(manifest_path): return FileResponse(manifest_path, media_type='application/json')
    return PlainTextResponse("Not found", status_code=404)

# --- WEBHOOK PAYPAL (venta Quipu OPRF) ---
@app.post('/paypal/webhook')
async def paypal_webhook(request: Request):
    raw = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    # Verifica la firma con PayPal ANTES de aprovisionar nada.
    if not quipu_sales.verify_webhook(headers, raw):
        return Response(status_code=400)
    try:
        event = json.loads(raw)
    except (ValueError, TypeError):
        return Response(status_code=400)
    quipu_sales.handle_event(event)
    return Response(status_code=200)

# --- HELPERS ---
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
def valid_email(value):
    return bool(value and EMAIL_RE.match(value.strip()))

def rate_ok(key, seconds=30):
    """Cooldown por sesión: evita el abuso del envío de correo (spam / daño a la
    reputación del dominio). Devuelve False si se envió hace menos de `seconds`."""
    now = time.time()
    if now - app.storage.user.get(key, 0) < seconds:
        return False
    app.storage.user[key] = now
    return True

def get_project_by_id(p_id):
    for p in projects_data:
        if str(p['id']) == str(p_id): return p
    return None

# --- BLOG ---
def load_posts():
    if os.path.exists(BLOG_FILE):
        try:
            with open(BLOG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Orden: más reciente primero.
                return sorted(data, key=lambda p: p.get('date', ''), reverse=True)
        except Exception:
            return []
    return []

posts_data = load_posts()

def get_post_by_slug(slug):
    for p in posts_data:
        if p.get('slug') == slug:
            return p
    return None

def markdown_to_plain(md):
    """Texto plano aproximado para el articleBody del Schema.org (indexable)."""
    txt = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', md)   # [texto](url) -> texto
    txt = re.sub(r'[#*`>_]', '', txt)                    # símbolos markdown
    txt = re.sub(r'\s+', ' ', txt)
    return txt.strip()

# --- PÁGINA PROYECTO ---
@ui.page('/project/{p_id}')
def project_page(p_id: str):
    project = get_project_by_id(p_id)
    ui.dark_mode().enable()
    ui.colors(primary='#6366f1', secondary='#06b6d4', accent='#8b5cf6', dark='#0f172a')
    
    if not project:
        ui.label('No encontrado').classes('text-white text-center mt-20 text-4xl')
        ui.button('Inicio', on_click=lambda: ui.navigate.to('/')).classes('mx-auto mt-4')
        return

    # SEO mejorado para página de proyecto
    escaped_desc = project['description'].replace('"', '&quot;').replace("'", '&#39;')
    escaped_title = project['title'].replace('"', '&quot;')
    tech_str = ', '.join(project['tech'])
    ui.page_title(f"{project['title']} | Xiliux — Desarrollo Python y IA")
    analytics_tag = f'<script async src="https://www.googletagmanager.com/gtag/js?id={GOOGLE_ANALYTICS_ID}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag("js",new Date());gtag("config","{GOOGLE_ANALYTICS_ID}");</script>' if GOOGLE_ANALYTICS_ID else ''
    search_console_tag = f'<meta name="google-site-verification" content="{GOOGLE_SEARCH_CONSOLE}" />' if GOOGLE_SEARCH_CONSOLE else ''

    ui.add_head_html(f'''<html lang="es">
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="description" content="🎯 {escaped_desc[:140]} | Proyecto {project['category']} desarrollado con {', '.join(project['tech'][:3])}." />
<meta name="keywords" content="{tech_str}, desarrollo python, {project['category']}" />
<meta name="author" content="Xiliux" />
<link rel="canonical" href="{DOMAIN}/project/{project['id']}" />
<meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large" />
<link rel="icon" type="image/png" href="/logo.png">
<link rel="apple-touch-icon" sizes="180x180" href="/logo.png">
<link rel="apple-touch-icon" sizes="152x152" href="/logo.png">
<link rel="apple-touch-icon" sizes="120x120" href="/logo.png">
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#0f172a">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="referrer" content="strict-origin-when-cross-origin">
<meta http-equiv="X-Content-Type-Options" content="nosniff">
<meta http-equiv="X-Frame-Options" content="SAMEORIGIN">
{search_console_tag}

<!-- Open Graph -->
<meta property="og:type" content="article" />
<meta property="og:title" content="{escaped_title} | Xiliux" />
<meta property="og:description" content="{escaped_desc[:155]}" />
<meta property="og:image" content="{project['image']}" />
<meta property="og:url" content="{DOMAIN}/project/{project['id']}" />
<meta property="og:site_name" content="Xiliux Portfolio" />
<meta property="og:locale" content="es_ES" />

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{escaped_title}" />
<meta name="twitter:description" content="{escaped_desc[:155]}" />
<meta name="twitter:image" content="{project['image']}" />

<!-- Schema.org JSON-LD - CreativeWork -->
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "CreativeWork",
  "name": "{escaped_title}",
  "description": "{escaped_desc}",
  "image": {{
    "@type": "ImageObject",
    "contentUrl": "{project['image']}",
    "description": "{escaped_title} - Proyecto de {project['category']} desarrollado en Python",
    "name": "{escaped_title}",
    "caption": "Screenshot del proyecto {escaped_title}"
  }},
  "author": {{
    "@type": "Person",
    "name": "Xiliux",
    "jobTitle": "Desarrollador Full Stack Python",
    "url": "{DOMAIN}"
  }},
  "keywords": "{tech_str}",
  "url": "{DOMAIN}/project/{project['id']}",
  "programmingLanguage": "Python",
  "datePublished": "{datetime.datetime.now().strftime('%Y-%m-%d')}",
  "inLanguage": "es-ES"
}}
</script>

<!-- Schema.org JSON-LD - BreadcrumbList -->
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {{
      "@type": "ListItem",
      "position": 1,
      "name": "Inicio",
      "item": "{DOMAIN}/"
    }},
    {{
      "@type": "ListItem",
      "position": 2,
      "name": "Proyectos",
      "item": "{DOMAIN}/#proyectos"
    }},
    {{
      "@type": "ListItem",
      "position": 3,
      "name": "{escaped_title}",
      "item": "{DOMAIN}/project/{project['id']}"
    }}
  ]
}}
</script>

{analytics_tag}
<style>.glass {{ background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(12px); }}</style>
''')

    with ui.header().classes('glass border-b border-slate-800 h-16 px-4 flex items-center justify-between'):
        with ui.row().classes('items-center gap-4 cursor-pointer').on('click', lambda: ui.navigate.to('/')):
            ui.image('/logo.png').classes('w-8 h-8 rounded-full').props('alt="Xiliux - Desarrollador Python especializado en NiceGUI e IA"')
            ui.label('Xiliux').classes('text-xl font-bold text-white')
        ui.button('Volver', icon='arrow_back', on_click=lambda: ui.navigate.to('/')).props('flat text-color=white')

    with ui.column().classes('w-full min-h-screen bg-slate-950 text-slate-200 p-0 items-center pt-24 pb-20'):
        with ui.card().classes('w-full max-w-4xl bg-slate-900 border border-slate-700 p-0 overflow-hidden shadow-2xl'):
            ui.image(project['image']).classes('w-full h-64 md:h-96 object-cover').props(f'alt="{escaped_title} - Proyecto de {project["category"]} desarrollado en Python por Xiliux" loading="lazy"')
            with ui.column().classes('p-8 gap-6'):
                with ui.row().classes('w-full justify-between items-start wrap'):
                    with ui.column().classes('gap-2'):
                        ui.label(project['category'].upper()).classes('text-sm font-bold text-indigo-400 tracking-widest')
                        ui.html(f'<h1 class="text-4xl md:text-5xl font-bold text-white leading-tight">{escaped_title}</h1>', sanitize=False)
                    with ui.row().classes('gap-4'):
                        if project['link'] != '#': ui.button('Demo', icon='open_in_new', on_click=lambda: ui.navigate.to(project['link'], new_tab=True)).classes('bg-indigo-600')
                        if project['repo'] != '#': ui.button('Código', icon='code', on_click=lambda: ui.navigate.to(project['repo'], new_tab=True)).props('outline color=white')
                ui.html(f'<p class="text-lg text-slate-400 leading-relaxed">{escaped_desc}</p>', sanitize=False)
                with ui.row().classes('gap-2'):
                    for t in project['tech']: ui.label(t).classes('px-4 py-2 bg-slate-800 rounded-full text-indigo-300 border border-slate-700')
    with ui.footer().classes('bg-slate-950 border-t border-slate-800 py-8 justify-center'):
        with ui.row().classes('items-center gap-4'):
            ui.label(f'© {datetime.datetime.now().year} Xiliux').classes('text-slate-500 text-sm')
            ui.link('Privacidad', '/privacidad').classes('no-underline text-slate-500 hover:text-cyan-400 text-sm')

# --- PÁGINA PRINCIPAL ---
# --- BLOG (helpers de layout) ---
def blog_header():
    with ui.header().classes('glass border-b border-slate-800 h-16 px-4 flex items-center justify-between'):
        with ui.row().classes('items-center gap-3 cursor-pointer').on('click', lambda: ui.navigate.to('/')):
            ui.image('/logo.png').classes('w-8 h-8 rounded-full').props('alt="Xiliux - Desarrollo Python e IA"')
            ui.label('Xiliux').classes('text-xl font-bold text-white')
        with ui.row().classes('gap-4 items-center'):
            ui.link('Blog', '/blog').classes('no-underline text-slate-300 hover:text-cyan-400 font-medium')
            ui.link('Inicio', '/').classes('no-underline bg-indigo-600 text-white rounded-full px-4 py-2 text-sm font-semibold')

def blog_footer():
    with ui.footer().classes('bg-slate-950 border-t border-slate-800 py-8 justify-center'):
        with ui.row().classes('items-center gap-4'):
            ui.label(f'© {datetime.datetime.now().year} Xiliux').classes('text-slate-500 text-sm')
            ui.link('Privacidad', '/privacidad').classes('no-underline text-slate-500 hover:text-cyan-400 text-sm')

# --- BLOG: RENDER DE SERVIDOR (HTML real, rastreable por Google) ---
# El blog es el motor de tráfico orgánico. NiceGUI renderiza en el cliente por
# WebSocket, invisible para el rastreador; por eso /blog y /blog/{slug} se sirven
# como HTML de servidor: semántico, sin JS (LCP rápido) y con JSON-LD BlogPosting.
_BLOG_CSS = """
*{box-sizing:border-box}
body{margin:0;background:#020617;color:#cbd5e1;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;line-height:1.7}
a{color:#22d3ee}
.nav{position:sticky;top:0;z-index:10;display:flex;align-items:center;justify-content:space-between;padding:14px 20px;background:rgba(2,6,23,.85);backdrop-filter:blur(12px);border-bottom:1px solid #1e293b}
.nav .brand{display:flex;align-items:center;gap:10px;color:#fff;font-weight:700;font-size:1.15rem;text-decoration:none}
.nav .brand img{width:32px;height:32px;border-radius:50%}
.nav .links a{margin-left:18px;color:#cbd5e1;text-decoration:none;font-weight:600}
.nav .links a:hover{color:#22d3ee}
.nav .links .dd{position:relative;display:inline-block;margin-left:18px}
.nav .links .dd>.t{color:#cbd5e1;font-weight:600;cursor:pointer;user-select:none}
.nav .links .dd:hover>.t,.nav .links .dd:focus-within>.t{color:#22d3ee}
.nav .links .dd .menu{position:absolute;right:0;top:100%;margin-top:8px;background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:8px;min-width:210px;display:none;flex-direction:column;box-shadow:0 10px 30px rgba(0,0,0,.45);z-index:20}
.nav .links .dd:hover .menu,.nav .links .dd:focus-within .menu{display:flex}
.nav .links .dd .menu a{margin:0;padding:9px 12px;border-radius:8px;white-space:nowrap;font-weight:500}
.nav .links .dd .menu a:hover{background:#1e293b;color:#22d3ee}
.wrap{max-width:1100px;margin:0 auto;padding:56px 20px 80px}
.article{max-width:760px}
h1{color:#fff;font-size:2.4rem;line-height:1.15;margin:0 0 .5rem}
.sub{color:#94a3b8;font-size:1.1rem;margin:0 0 40px}
.meta{color:#64748b;font-size:.9rem;margin:0 0 32px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:26px}
.card{display:block;background:#0f172a;border:1px solid #1e293b;border-radius:16px;padding:24px;text-decoration:none;transition:border-color .2s,transform .2s}
.card:hover{border-color:#06b6d4;transform:translateY(-4px)}
html{scroll-behavior:smooth}
@supports ((-webkit-background-clip:text) or (background-clip:text)){.home>h1{background:linear-gradient(90deg,#818cf8,#c084fc,#22d3ee);-webkit-background-clip:text;background-clip:text;color:transparent}}
.home>h1{animation:fadeInUp .5s cubic-bezier(.215,.61,.355,1) both}
.home>.sub{animation:fadeInUp .5s cubic-bezier(.215,.61,.355,1) .08s both}
@keyframes fadeInUp{from{opacity:0;transform:translate3d(0,16px,0)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){.home>h1,.home>.sub{animation:none}}
.card time{color:#22d3ee;font-size:.75rem;font-weight:700}
.card h2{color:#fff;font-size:1.25rem;margin:.5rem 0}
.card p{color:#94a3b8;font-size:.9rem;margin:0 0 14px}
.tags{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}
.tag{padding:4px 10px;background:#0b1220;border:1px solid #1e293b;border-radius:6px;font-size:.72rem;color:#a5b4fc}
.prose h2{color:#fff;font-size:1.55rem;margin:2rem 0 .6rem}
.prose h3{color:#fff;font-size:1.2rem;margin:1.4rem 0 .4rem}
.prose p{margin:1rem 0}
.prose ul,.prose ol{padding-left:1.4rem;margin:1rem 0}
.prose li{margin:.35rem 0}
.prose strong{color:#fff}
.prose a{text-decoration:underline}
.prose code{background:#0b1220;border:1px solid #1e293b;border-radius:4px;padding:.1rem .35rem;font-size:.9em}
.prose pre{background:#0b1220;border:1px solid #1e293b;border-radius:10px;padding:16px;overflow-x:auto;margin:1.2rem 0}
.prose pre code{background:none;border:0;padding:0}
.prose blockquote{border-left:3px solid #6366f1;margin:1rem 0;padding:.2rem 0 .2rem 1rem;color:#94a3b8}
.cta{display:flex;flex-wrap:wrap;gap:16px;align-items:center;margin-top:48px}
.cta .btn{background:#4f46e5;color:#fff;border-radius:999px;padding:10px 24px;text-decoration:none;font-weight:600}
footer{border-top:1px solid #1e293b;padding:28px 20px;text-align:center;color:#64748b;font-size:.85rem}
footer a{color:#64748b;text-decoration:none;margin-left:16px}
footer a:hover{color:#22d3ee}
.ok-banner{background:#052e16;border:1px solid #16a34a;color:#86efac;border-radius:10px;padding:14px 18px;margin:0 0 28px;font-weight:600}
.ok-banner.err{background:#3f1d1d;border-color:#b91c1c;color:#fca5a5}
.ok-banner.err a{color:#fca5a5}
.lead-form{display:flex;flex-direction:column;gap:12px;max-width:480px;margin:16px 0 8px}
.lead-form input,.lead-form textarea{background:#0b1220;border:1px solid #1e293b;border-radius:10px;padding:12px 14px;color:#e2e8f0;font-size:1rem;font-family:inherit;width:100%}
.lead-form input:focus,.lead-form textarea:focus{outline:none;border-color:#6366f1}
.lead-form button{background:#4f46e5;color:#fff;border:0;border-radius:999px;padding:12px 24px;font-weight:700;font-size:1rem;cursor:pointer;align-self:flex-start}
.lead-form button:hover{background:#4338ca}
.hp{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden}
@media(max-width:640px){h1{font-size:1.8rem}.wrap{padding:36px 16px 60px}}
"""

def _ga_snippet():
    if not GOOGLE_ANALYTICS_ID:
        return ""
    g = GOOGLE_ANALYTICS_ID
    return ('<script async src="https://www.googletagmanager.com/gtag/js?id=' + g + '"></script>'
            '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}'
            'gtag("js",new Date());gtag("config","' + g + '");</script>')

def _seo_head(title, description, canonical, og_type="website", og_image=None, jsonld="",
              lang="es", alternates=""):
    # `lang` fija el idioma del documento; `alternates` inyecta los <link
    # hreflang> cuando hay versión en otro idioma (Tier 3). Ambos con defaults,
    # así las llamadas existentes (todas en español) no cambian.
    og_image = og_image or SOCIAL_IMAGE
    et = _htmlmod.escape(title, quote=True)
    ed = _htmlmod.escape(description, quote=True)
    og_locale = "en_US" if lang == "en" else "es_ES"
    verify = f'<meta name="google-site-verification" content="{GOOGLE_SEARCH_CONSOLE}">' if GOOGLE_SEARCH_CONSOLE else ''
    feed = RSS_CANALES.get(lang, RSS_CANALES["es"])
    return (f'<!doctype html><html lang="{lang}"><head>'
            f'<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">'
            f'<title>{et}</title><meta name="description" content="{ed}">'
            f'<link rel="canonical" href="{canonical}">{alternates}'
            # Sin esta línea el feed existe y no lo encuentra nadie: es lo que
            # hace que el navegador y los lectores lo ofrezcan solos.
            f'<link rel="alternate" type="application/rss+xml" title="{feed["titulo"]}" href="{DOMAIN}{feed["ruta"]}">'
            f'<meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">'
            f'<link rel="icon" type="image/png" href="/logo.png"><meta name="theme-color" content="#0f172a">'
            f'<meta property="og:type" content="{og_type}"><meta property="og:title" content="{et}">'
            f'<meta property="og:description" content="{ed}"><meta property="og:image" content="{og_image}">'
            f'<meta property="og:url" content="{canonical}"><meta property="og:locale" content="{og_locale}">'
            f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{et}">'
            f'<meta name="twitter:description" content="{ed}"><meta name="twitter:image" content="{og_image}">'
            f'{REL_ME}'
            f'{verify}{_ga_snippet()}{jsonld}<style>{_BLOG_CSS}</style></head>')

def _nav_html(lang="es"):
    # La barra inglesa apunta SOLO a rutas que sirven inglés. Antes llevaba a
    # `/quipu`, `/#contacto` y `/` —las tres en español—, así que el lector
    # anglófono salía del idioma al primer clic y el Tier 3 entero moría ahí.
    # El último enlace es el conmutador de idioma, no un destino más: va al
    # final y dice «ES», que es lo que un hispanohablante busca.
    if lang == "en":
        return ('<header class="nav"><a class="brand" href="/en"><img src="/logo.png" alt="Xiliux">Xiliux</a>'
                '<nav class="links"><a href="/en/services">Services</a>'
                '<a href="/en/quipu">Quipu</a><a href="/en/blog">Blog</a>'
                f'<a href="/#contacto">Contact</a>'
                '<a href="/en">Home</a><a href="/">ES</a></nav></header>')
    # El menú "Proyectos" reúne los enlaces a TODOS los proyectos (páginas
    # internas + demos vivas en subdominios). Va como desplegable y no como
    # enlaces planos porque nueve caberían mal en la barra (y romperían la móvil).
    proyectos_menu = (
        '<span class="dd" tabindex="0"><span class="t">Proyectos ▾</span>'
        '<span class="menu">'
        '<a href="/informes">Informes (SIGER)</a>'
        '<a href="/quipu">Quipu</a>'
        '<a href="https://inventario.xiliux.com" rel="noopener">Inventario</a>'
        '<a href="https://medico.xiliux.com" rel="noopener">Salud (medico)</a>'
        '<a href="https://chimini.xiliux.com" rel="noopener">Chimini</a>'
        '<a href="https://agua.xiliux.com" rel="noopener">Agua</a>'
        '<a href="https://rips.xiliux.com" rel="noopener">Validador RIPS</a>'
        '<a href="https://tunjo.xiliux.com" rel="noopener">Tunjo</a>'
        '<a href="https://chasqui.xiliux.com" rel="noopener">Chasqui</a>'
        '</span></span>')
    return ('<header class="nav"><a class="brand" href="/"><img src="/logo.png" alt="Xiliux">Xiliux</a>'
            '<nav class="links"><a href="/servicios">Servicios</a>'
            f'{proyectos_menu}'
            '<a href="/blog">Blog</a><a href="/#contacto">Contacto</a>'
            '<a href="/">Inicio</a></nav></header>')

def _footer_html(lang="es"):
    year = datetime.datetime.now().year
    if lang == "en":
        return (f'<footer>© {year} Xiliux <a href="/en">Home</a> '
                f'<a href="/en/blog">Blog</a> <a href="/en/quipu/code">Quipu source</a> '
                f'<a href="/privacidad">Privacy (ES)</a></footer>')
    return (f'<footer>© {year} Xiliux <a href="/privacidad">Privacidad</a> '
            f'<a href="/blog">Blog</a></footer>')

def _blog_page(head, body, lang="es"):
    return f'{head}<body>{_nav_html(lang)}{body}{_footer_html(lang)}</body></html>'

# Clusters temáticos del blog (Tier 2 SEO): agrupar e interconectar los
# artículos hermanos construye autoridad temática. El id vive en cada post
# (campo `cluster`); aquí solo el nombre visible y el orden (cripto primero: es
# el moat). Un cluster de un solo post no genera enlaces internos, y está bien.
CLUSTERS = {
    "cripto-postcuantica": "Criptografía post-cuántica",
    "trading-algoritmico": "Trading algorítmico fiable",
    "python-ia": "Python, IA y desarrollo",
    "libs-fiables": "Micro-librerías fiables",
    "legaltech": "LegalTech",
    "software-educativo": "Software educativo",
    "datos-colombia": "Colombia en datos",
}

# Nombres de cluster en inglés (Tier 3). Mismos ids que CLUSTERS.
CLUSTERS_EN = {
    "cripto-postcuantica": "Post-quantum cryptography",
    "trading-algoritmico": "Reliable algorithmic trading",
    "python-ia": "Python, AI & development",
    "libs-fiables": "Small reliable libraries",
    "legaltech": "LegalTech",
    "software-educativo": "Educational software",
    "datos-colombia": "Colombia in data",
}

def _blog_card(p, lang="es"):
    src = p.get('en', {}) if lang == 'en' else p
    t = _htmlmod.escape(src.get('title') or p['title'])
    d = _htmlmod.escape(src.get('description') or p.get('description', ''))
    date = _htmlmod.escape(p.get('date', ''))
    tags = ''.join(f'<span class="tag">{_htmlmod.escape(x)}</span>' for x in p.get('tags', [])[:3])
    prefix = '/en/blog' if lang == 'en' else '/blog'
    return (f'<a class="card" href="{prefix}/{p["slug"]}"><time>{date}</time>'
            f'<h2>{t}</h2><p>{d}</p><div class="tags">{tags}</div></a>')

# El índice del blog tiene versión ES y EN; comparten enlace hreflang mutuo.
_BLOG_ALT = (f'<link rel="alternate" hreflang="es" href="{DOMAIN}/blog">'
             f'<link rel="alternate" hreflang="en" href="{DOMAIN}/en/blog">'
             f'<link rel="alternate" hreflang="x-default" href="{DOMAIN}/blog">')

@app.get('/blog')
def blog_index():
    # Agrupado por cluster: el índice deja de ser una lista plana y pasa a ser un
    # hub temático, con enlaces internos desde cada encabezado a su racimo.
    secciones = []
    for cid, cname in CLUSTERS.items():
        grupo = [p for p in posts_data if p.get('cluster') == cid]
        if not grupo:
            continue
        secciones.append(f'<h2 style="margin:2.5rem 0 1rem;color:#fff">{_htmlmod.escape(cname)}</h2>'
                         f'<div class="grid">{"".join(_blog_card(p) for p in grupo)}</div>')
    sin = [p for p in posts_data if p.get('cluster') not in CLUSTERS]
    if sin:
        secciones.append(f'<div class="grid">{"".join(_blog_card(p) for p in sin)}</div>')
    cuerpo = "".join(secciones) if secciones else '<p class="sub">Pronto habrá artículos.</p>'
    body = (f'<main class="wrap"><h1>Blog</h1>'
            f'<p class="sub">Guías prácticas sobre criptografía post-cuántica, trading '
            f'algorítmico, Python e IA — cada una escrita desde el código que la respalda.</p>{cuerpo}</main>')
    head = _seo_head('Blog | Xiliux — Cripto post-cuántica, Trading, Python e IA',
                     'Guías técnicas sobre criptografía post-cuántica, trading algorítmico fiable, '
                     'Python e integración de IA, por el desarrollador de Xiliux.',
                     f'{DOMAIN}/blog', alternates=_BLOG_ALT)
    return Response(content=_blog_page(head, body), media_type='text/html')

@app.get('/en/blog')
def blog_index_en():
    # Solo los artículos que tienen traducción (campo `en`), agrupados por cluster.
    en_posts = [p for p in posts_data if p.get('en')]
    secciones = []
    for cid, cname in CLUSTERS_EN.items():
        grupo = [p for p in en_posts if p.get('cluster') == cid]
        if not grupo:
            continue
        secciones.append(f'<h2 style="margin:2.5rem 0 1rem;color:#fff">{_htmlmod.escape(cname)}</h2>'
                         f'<div class="grid">{"".join(_blog_card(p, "en") for p in grupo)}</div>')
    cuerpo = "".join(secciones) if secciones else '<p class="sub">Articles coming soon.</p>'
    body = (f'<main class="wrap"><h1>Blog</h1>'
            f'<p class="sub">Technical guides on post-quantum cryptography, reliable algorithmic '
            f'trading, Python and AI — each one written from the code behind it.</p>{cuerpo}</main>')
    head = _seo_head('Blog | Xiliux — Post-Quantum Crypto, Trading, Python & AI',
                     'Technical guides on post-quantum cryptography, reliable algorithmic trading, '
                     'Python and AI integration, by the developer of Xiliux.',
                     f'{DOMAIN}/en/blog', lang='en', alternates=_BLOG_ALT)
    return Response(content=_blog_page(head, body, 'en'), media_type='text/html')

# --- BLOG: ARTÍCULO (HTML de servidor) ---
# Etiquetas por idioma (Tier 3). Fuente única del render; solo cambian textos.
_LBL = {
    "es": {"pub": "Publicado el", "site": "Blog de Xiliux", "short": "En corto:",
           "faq": "Preguntas frecuentes", "keep": "Sigue leyendo",
           "more": "← Ver más artículos", "cta": "Cotizar un proyecto",
           "cta_href": "/#contacto",
           "prefix": "/blog", "iso": "es-ES"},
    "en": {"pub": "Published on", "site": "Xiliux Blog", "short": "In short:",
           "faq": "FAQ", "keep": "Keep reading",
           "more": "← More articles", "cta": "Request a quote",
           "cta_href": "/en",
           "prefix": "/en/blog", "iso": "en-US"},
}

# Nuestros paquetes retirados de los registros el 2026-08-10. La lista es
# EXPLÍCITA a propósito: un patrón como «pip install .*» marcaría también
# `pip install anthropic` o `ccxt`, que son de terceros y siguen funcionando
# perfectamente, y un aviso que sale donde no toca es un aviso que nadie lee
# (directiva 23). Aquí se enumera lo que SÍ significa algo.
PAQUETES_RETIRADOS = (
    "quipu", "quipu-crypto", "quipu-voprf", "quipu-oprf-django", "quipu-cnsa",
    "quipu-nucleo", "padme-frame", "ccxt-resilience", "honest-eval",
    "hysteresis-state", "fanout-broadcast", "dotkey-i18n", "position-sizing",
)

_AVISO_RETIRADA = {
    "es": ('<div style="border:1px solid #b45309;background:#1c1917;border-radius:12px;padding:16px 20px;margin:0 0 28px">'
           '<strong style="color:#fbbf24">Nota de agosto de 2026 —</strong> '
           '<span style="color:#cbd5e1">este artículo muestra comandos como <code>pip install</code> o '
           '<code>cargo add</code> que <strong>ya no funcionan</strong>: nuestras librerías se retiraron de '
           'crates.io, PyPI y npm por seguridad, tras los ataques encadenados de ciberdelincuentes contra '
           'esas plataformas durante 2026. El texto se conserva tal como se publicó. La licencia no cambia y '
           'el código sigue siendo libre: se entrega a pedido en '
           '<a href="/#contacto" style="color:#22d3ee">el formulario de contacto</a>, con firma y '
           'SHA-256.</span></div>'),
    "en": ('<div style="border:1px solid #b45309;background:#1c1917;border-radius:12px;padding:16px 20px;margin:0 0 28px">'
           '<strong style="color:#fbbf24">August 2026 note —</strong> '
           '<span style="color:#cbd5e1">this article shows <code>pip install</code> / <code>cargo add</code> '
           'commands that <strong>no longer work</strong>: our libraries were withdrawn from crates.io, PyPI '
           'and npm for security reasons, following the sustained supply-chain attacks by criminal actors '
           'against those platforms during 2026. The text is kept as published. The license is unchanged and '
           'the code is still free software: it is provided on request at '
           '<a href="/#contacto" style="color:#22d3ee">the contact form</a>, with a '
           'signature and SHA-256.</span></div>'),
}


def _promete_instalacion(md: str) -> bool:
    """¿El artículo le pide al lector instalar algo NUESTRO que ya no se instala?"""
    for gestor in ("pip install ", "cargo add ", "npm install ", "npm i "):
        for trozo in md.split(gestor)[1:]:
            nombre = trozo.strip().split()[0].strip("`\"'.,;)") if trozo.strip() else ""
            if nombre in PAQUETES_RETIRADOS:
                return True
    return False


def _render_post(post, lang):
    """Renderiza un artículo en `lang`. FUENTE ÚNICA para ES y EN: los mismos
    bloques (JSON-LD TechArticle + FAQPage, answer-first, FAQ, 'sigue leyendo'),
    cambiando solo de dónde salen los textos y las etiquetas. Añade hreflang si el
    post tiene la pareja en el otro idioma (campo `en`)."""
    slug = post['slug']
    L = _LBL[lang]
    src = post.get('en', {}) if lang == 'en' else post
    title = src.get('title') or post['title']
    desc = src.get('description') or post.get('description', '')
    body_md = src.get('body') or post['body']
    answer = src.get('answer')
    faq = src.get('faq') or []
    date = post.get('date', '')
    cover = post.get('cover') or SOCIAL_IMAGE
    tags = post.get('tags', [])
    canonical = f"{DOMAIN}{L['prefix']}/{slug}"
    body_html = markdown2.markdown(body_md,
        extras=["fenced-code-blocks", "tables", "cuddled-lists", "code-friendly"])
    # El aviso va ARRIBA del cuerpo y el cuerpo NO se toca: reescribir un artículo
    # publicado para que encaje con la realidad de hoy falsea el registro, y estos
    # posts llevan fecha. Se avisa y se conserva.
    if _promete_instalacion(body_md):
        body_html = _AVISO_RETIRADA[lang] + body_html
    plain = markdown_to_plain(body_md)
    jsonld_data = {
        "@context": "https://schema.org", "@type": "TechArticle",
        "headline": title, "description": desc,
        "datePublished": date, "dateModified": date,
        # E-E-A-T: autor verificable por sameAs (identidad de SOFTWARE de Xiliux).
        "author": {"@type": "Person", "name": "Juan Carlos Isaza", "url": DOMAIN,
                    "sameAs": ["https://github.com/isazajuancarlos"]},
        "publisher": {"@type": "Organization", "name": "Xiliux",
                      "logo": {"@type": "ImageObject", "url": SOCIAL_IMAGE}},
        "mainEntityOfPage": canonical, "image": cover,
        "inLanguage": L['iso'], "keywords": ", ".join(tags), "articleBody": plain,
    }
    bloques = [jsonld_data]
    if faq:
        bloques.append({"@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": f["q"],
                            "acceptedAnswer": {"@type": "Answer", "text": f["a"]}}
                           for f in faq]})
    # <\/ evita que un "</script>" en el contenido rompa el bloque JSON-LD.
    jsonld = "".join('<script type="application/ld+json">'
                     + json.dumps(b, ensure_ascii=False).replace("</", "<\\/")
                     + '</script>' for b in bloques)
    # hreflang: solo si existe la pareja EN. x-default apunta al español (original).
    alternates = ''
    if post.get('en'):
        es_url = f"{DOMAIN}/blog/{slug}"; en_url = f"{DOMAIN}/en/blog/{slug}"
        alternates = (f'<link rel="alternate" hreflang="es" href="{es_url}">'
                      f'<link rel="alternate" hreflang="en" href="{en_url}">'
                      f'<link rel="alternate" hreflang="x-default" href="{es_url}">')
    tags_html = ''.join(f'<span class="tag">{_htmlmod.escape(x)}</span>' for x in tags)
    answer_html = (f'<aside style="border-left:4px solid #6366f1;background:#0f172a;'
                   f'padding:.75rem 1rem;margin:1.25rem 0;border-radius:.5rem;color:#e2e8f0">'
                   f'<strong>{L["short"]}</strong> {_htmlmod.escape(answer)}</aside>') if answer else ''
    faq_html = ''
    if faq:
        items = ''.join(f'<details style="margin:.5rem 0"><summary style="cursor:pointer;'
                        f'font-weight:600;color:#fff">{_htmlmod.escape(f["q"])}</summary>'
                        f'<p style="color:#cbd5e1;margin:.5rem 0 0">{_htmlmod.escape(f["a"])}</p>'
                        f'</details>' for f in faq)
        faq_html = f'<section class="faq"><h2>{L["faq"]}</h2>{items}</section>'
    # Enlazado interno: hermanos del cluster. En EN, solo los que tengan versión EN.
    if lang == 'en':
        hermanos = [q for q in posts_data if q.get('cluster') == post.get('cluster')
                    and q['slug'] != slug and q.get('en')]
        h_title = lambda q: q['en'].get('title') or q['title']
    else:
        hermanos = [q for q in posts_data if q.get('cluster') == post.get('cluster')
                    and q['slug'] != slug]
        h_title = lambda q: q['title']
    related_html = ''
    if hermanos:
        cname = CLUSTERS.get(post.get('cluster'), '')
        li = ''.join(f'<li><a href="{L["prefix"]}/{q["slug"]}">{_htmlmod.escape(h_title(q))}</a></li>'
                     for q in hermanos)
        related_html = (f'<section class="related" style="margin-top:2.5rem">'
                        f'<h2>{L["keep"]} — {_htmlmod.escape(cname)}</h2><ul>{li}</ul></section>')
    body = (f'<main class="wrap article"><div class="tags">{tags_html}</div>'
            f'<h1>{_htmlmod.escape(title)}</h1>'
            f'<p class="meta">{L["pub"]} {_htmlmod.escape(date)} · Xiliux</p>'
            f'{answer_html}'
            f'<article class="prose">{body_html}</article>'
            f'{faq_html}{related_html}'
            f'<div class="cta"><a href="{L["prefix"]}">{L["more"]}</a>'
            f'<a class="btn" href="{L["cta_href"]}">{L["cta"]}</a></div></main>')
    head = _seo_head(f"{title} | {L['site']}", desc, canonical,
                     og_type="article", og_image=cover, jsonld=jsonld,
                     lang=lang, alternates=alternates)
    return Response(content=_blog_page(head, body, lang), media_type='text/html')

@app.get('/blog/{slug}')
def blog_post(slug: str):
    post = get_post_by_slug(slug)
    if not post:
        head = _seo_head('Artículo no encontrado | Xiliux', 'El artículo no existe.', f'{DOMAIN}/blog')
        body = ('<main class="wrap"><h1>Artículo no encontrado</h1>'
                '<p class="sub"><a href="/blog">← Ver el blog</a></p></main>')
        return Response(content=_blog_page(head, body), media_type='text/html', status_code=404)
    return _render_post(post, 'es')

@app.get('/en/blog/{slug}')
def blog_post_en(slug: str):
    post = get_post_by_slug(slug)
    if not post or not post.get('en'):
        # Sin traducción: 302 a la versión ES (evita 404 y consolida la señal).
        return Response(status_code=302, headers={"Location": f"/blog/{slug}"})
    return _render_post(post, 'en')

# --- POLÍTICA DE PRIVACIDAD ---
def _priv_h2(texto):
    ui.html(f'<h2 class="text-2xl font-bold text-white mt-12 mb-3">{texto}</h2>', sanitize=False)

def _priv_p(texto):
    ui.html(f'<p class="text-slate-300 leading-relaxed mb-4">{texto}</p>', sanitize=False)

# --- SERVICIOS: PÁGINA DE PRODUCTO (HTML de servidor, rastreable) ---
#
# La home es NiceGUI: su contenido vive dentro del JSON que renderiza el
# navegador, así que un rastreador no lo lee. Verificado el 2026-07-18 — el HTML
# servido de "/" no contiene ni una frase de servicios, solo la hoja de estilos.
#
# Convertir la home entera a SSR sería reescribir splash, formulario, botones de
# pago y flotante de WhatsApp, con riesgo alto sobre un sitio que funciona. Se
# hace lo que rinde: una página propia rastreable con el mismo contenido, y la
# home sigue haciendo su trabajo (impacto y conversión) para quien ya llegó.

@app.get('/servicios')
def servicios_pagina():
    tarjetas = []
    for s in SERVICES:
        tarjetas.append(
            f'<div class="card"><h2>{_htmlmod.escape(s["title"])}</h2>'
            f'<p>{_htmlmod.escape(s["desc"])}</p>'
            f'<div class="tags"><span class="tag">{_htmlmod.escape(s["price_label"])}</span></div></div>')
    pasos = ''.join(
        f'<div class="card"><h2>{_htmlmod.escape(t)}</h2><p>{_htmlmod.escape(d)}</p></div>'
        for _ic, t, d in PROCESS)

    body = (f'<main class="wrap"><h1>Servicios</h1>'
            f'<p class="sub">Desarrollo en Python, integración de IA y automatización. '
            f'Trabajo directo con quien construye — sin capas intermedias, sin gestor de cuenta.</p>'
            f'<div class="grid">{"".join(tarjetas)}</div>'
            f'<h2>Cómo trabajo</h2>'
            f'<p class="sub">Precio cerrado antes de empezar. Sin sorpresas a mitad de camino.</p>'
            f'<div class="grid">{pasos}</div>'
            f'<h2>Y lo que construyo para mí</h2>'
            f'<p class="sub">La mejor referencia de cómo trabajo es lo que sostengo en producción: '
            f'<a href="/informes">SIGER</a>, un sistema de seguimiento de obligaciones de reporte, '
            f'y <a href="/quipu">Quipu</a>, una librería de criptografía post-cuántica en uso '
            f'en producción. No son demos, y el código se entrega a quien quiera auditarlo.</p>'
            f'<p><a class="card" href="/#contacto" style="display:inline-block;margin-top:1rem">'
            f'Cotizar un proyecto &rarr;</a></p></main>')

    head = _seo_head(
        'Servicios — de Python a Rust (un solo binario, sin Node), IA y automatización | Xiliux',
        'Del prototipo rápido en Python (NiceGUI/FastAPI) al sistema a la medida en Rust '
        '—axum + maud + htmx, un solo binario que corre offline—, con integración de IA '
        '(GPT-4, Claude, Gemini) y automatización. Precio cerrado antes de empezar, desde $200 USD.',
        f'{DOMAIN}/servicios', alternates=_SERVICIOS_ALT)
    return Response(content=_blog_page(head, body), media_type='text/html')


# --- QUIPU: EL MODELO DE LICENCIAMIENTO (HTML de servidor, rastreable) ---
#
# Responde antes de que la formulen la primera objeción de cualquiera que llega
# a un proyecto AGPL con licencia comercial: "¿por qué pago por software libre?".
# La respuesta corta es que no se paga por el uso — se paga por el derecho a no
# publicar. Ver docs/LICENSING.md del repositorio de Quipu.

# --- COTIZADOR: estimador de referencia (HTML autocontenido, servido como
# página propia para no chocar con la cascada del sitio; #111). ---
COTIZADOR_HTML = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="description" content="Estimador de cotización de Xiliux: arma tu sistema a la medida por requerimientos y complejidad y mira un rango de referencia (no vinculante).">
<title>Estimador de cotización — Xiliux</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {
    --bg: #0f172a; --surface: #1e293b; --surface-2: #172033; --line: #2b3a52;
    --text: #e6edf6; --muted: #94a3b8; --faint: #64748b;
    --cyan: #22d3ee; --emerald: #34d399; --indigo: #818cf8;
    --shadow: 0 10px 30px rgba(0,0,0,.35);
    --radius: 14px;
  }
  @media (prefers-color-scheme: light) {
    :root {
      --bg: #eef2f7; --surface: #ffffff; --surface-2: #f5f8fc; --line: #d7e0ec;
      --text: #14243b; --muted: #536479; --faint: #7d8da3;
      --cyan: #0891b2; --emerald: #059669; --indigo: #4f46e5;
      --shadow: 0 8px 24px rgba(20,40,80,.10);
    }
  }
  :root[data-theme="dark"] {
    --bg: #0f172a; --surface: #1e293b; --surface-2: #172033; --line: #2b3a52;
    --text: #e6edf6; --muted: #94a3b8; --faint: #64748b;
    --cyan: #22d3ee; --emerald: #34d399; --indigo: #818cf8;
    --shadow: 0 10px 30px rgba(0,0,0,.35);
  }
  :root[data-theme="light"] {
    --bg: #eef2f7; --surface: #ffffff; --surface-2: #f5f8fc; --line: #d7e0ec;
    --text: #14243b; --muted: #536479; --faint: #7d8da3;
    --cyan: #0891b2; --emerald: #059669; --indigo: #4f46e5;
    --shadow: 0 8px 24px rgba(20,40,80,.10);
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    line-height: 1.5; -webkit-font-smoothing: antialiased;
  }
  .wrap { max-width: 1080px; margin: 0 auto; padding: clamp(1.2rem, 3vw, 2.5rem); }
  .eyebrow { font-size: .72rem; letter-spacing: .18em; text-transform: uppercase;
    color: var(--cyan); font-weight: 700; }
  h1 { font-size: clamp(1.7rem, 3.4vw, 2.5rem); line-height: 1.08; margin: .5rem 0 .4rem;
    letter-spacing: -.02em; text-wrap: balance; font-weight: 800; }
  .lede { color: var(--muted); max-width: 60ch; margin: 0; }
  .grid { display: grid; grid-template-columns: 1fr; gap: 1.25rem; margin-top: 2rem; }
  @media (min-width: 860px) { .grid { grid-template-columns: 1.35fr 1fr; align-items: start; } }

  .panel { background: var(--surface); border: 1px solid var(--line);
    border-radius: var(--radius); padding: 1.25rem 1.25rem 1.4rem; }
  .panel + .panel { margin-top: 1.25rem; }
  .panel h2 { font-size: 1.02rem; margin: 0 0 .2rem; letter-spacing: -.01em; }
  .panel .hint { color: var(--faint); font-size: .82rem; margin: 0 0 1rem; }

  .row { display: flex; align-items: center; justify-content: space-between; gap: 1rem;
    padding: .7rem 0; border-top: 1px solid var(--line); }
  .row:first-of-type { border-top: none; }
  .row .label { min-width: 0; }
  .row .label .name { font-weight: 650; }
  .row .label .ex { color: var(--faint); font-size: .78rem; }
  .row .band { color: var(--muted); font-size: .78rem; font-variant-numeric: tabular-nums; white-space: nowrap; }

  .stepper { display: inline-flex; align-items: center; border: 1px solid var(--line);
    border-radius: 999px; background: var(--surface-2); }
  .stepper button { width: 2rem; height: 2rem; border: none; background: transparent;
    color: var(--text); font-size: 1.15rem; cursor: pointer; border-radius: 999px; line-height: 1; }
  .stepper button:hover { color: var(--cyan); }
  .stepper button:focus-visible { outline: 2px solid var(--cyan); outline-offset: 2px; }
  .stepper .val { min-width: 2.1rem; text-align: center; font-variant-numeric: tabular-nums;
    font-weight: 700; }

  .seg { display: inline-flex; background: var(--surface-2); border: 1px solid var(--line);
    border-radius: 999px; padding: .2rem; gap: .2rem; flex-wrap: wrap; }
  .seg button { border: none; background: transparent; color: var(--muted); cursor: pointer;
    padding: .4rem .8rem; border-radius: 999px; font-size: .85rem; font-weight: 600; }
  .seg button[aria-pressed="true"] { background: var(--emerald); color: #06281c; }
  .seg button:focus-visible { outline: 2px solid var(--cyan); outline-offset: 2px; }

  .check { display: flex; align-items: center; gap: .6rem; padding: .6rem 0;
    border-top: 1px solid var(--line); cursor: pointer; }
  .check input { accent-color: var(--cyan); width: 1.1rem; height: 1.1rem; }
  .check .name { font-weight: 600; }
  .check .band { margin-left: auto; color: var(--muted); font-size: .8rem;
    font-variant-numeric: tabular-nums; white-space: nowrap; }

  /* Resumen sticky */
  .summary { position: sticky; top: 1rem; background:
      linear-gradient(180deg, var(--surface), var(--surface-2));
    border: 1px solid var(--line); border-radius: var(--radius); padding: 1.4rem;
    box-shadow: var(--shadow); }
  .summary .cap { font-size: .72rem; letter-spacing: .16em; text-transform: uppercase;
    color: var(--muted); font-weight: 700; }
  .total { font-variant-numeric: tabular-nums; font-weight: 850; letter-spacing: -.02em;
    line-height: 1.05; margin: .35rem 0 .1rem; }
  .total .num { font-size: clamp(1.9rem, 4.6vw, 2.6rem); }
  .total .dash { color: var(--faint); margin: 0 .35rem; }
  .total .unit { color: var(--cyan); font-size: 1rem; font-weight: 700; margin-left: .3rem; }
  .subtotal-note { color: var(--faint); font-size: .78rem; margin: 0 0 1rem; }

  .break { border-top: 1px dashed var(--line); margin-top: .5rem; padding-top: .8rem; }
  .break .l { display: flex; justify-content: space-between; gap: 1rem; font-size: .86rem;
    padding: .22rem 0; color: var(--muted); }
  .break .l span:last-child { font-variant-numeric: tabular-nums; color: var(--text); }
  .break .l.zero { display: none; }

  .cta { display: block; width: 100%; text-align: center; margin-top: 1.1rem;
    background: var(--cyan); color: #062730; text-decoration: none; font-weight: 800;
    padding: .8rem 1rem; border-radius: 999px; }
  .cta:hover { filter: brightness(1.06); }
  .cta:focus-visible { outline: 2px solid var(--text); outline-offset: 2px; }
  .disclaimer { color: var(--faint); font-size: .74rem; margin: .9rem 0 0; text-align: center; }

  .foot { color: var(--faint); font-size: .78rem; margin-top: 2rem; text-align: center; }
  a.inline { color: var(--cyan); }
  @media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
  .total .num, .cta { transition: opacity .12s ease; }
</style>
</head>
<body>
<div style="max-width:1080px;margin:0 auto;padding:1rem .6rem 0"><a href="/" style="color:var(--cyan);text-decoration:none;font-weight:700">&larr; Xiliux</a></div>


<div class="wrap">
  <header>
    <div class="eyebrow">Xiliux · estimador de referencia</div>
    <h1>¿Cuánto costaría tu sistema a la medida?</h1>
    <p class="lede">Arma tu proyecto por <strong>requerimientos y su complejidad</strong> y mira
      un rango estimado al instante. Es la misma lógica con la que cotizamos de verdad — pero
      esto es <strong>informativo y no vinculante</strong>: la cotización formal se confirma según
      el alcance acordado.</p>
  </header>

  <div class="grid">
    <div class="builder">
      <section class="panel">
        <h2>Requerimientos por complejidad</h2>
        <p class="hint">Cuántas funcionalidades necesitas de cada tipo. Si no estás seguro, deja
          una estimación gruesa — el rango lo absorbe.</p>
        <div id="reqs"></div>
      </section>

      <section class="panel">
        <h2>Propiedad intelectual del desarrollo</h2>
        <p class="hint">Quién queda como titular de lo desarrollado a la medida cambia el precio.</p>
        <div class="seg" id="pi" role="group" aria-label="Modalidad de propiedad intelectual">
          <button data-pi="a1" aria-pressed="true">Licencia de uso (más económico)</button>
          <button data-pi="a2" aria-pressed="false">Titularidad exclusiva (+50–80%)</button>
        </div>
      </section>

      <section class="panel">
        <h2>Servicios (opcionales)</h2>
        <p class="hint">Puesta en marcha, datos y acompañamiento. Se suman si los necesitas.</p>
        <div id="svcs"></div>
        <label class="check">
          <input type="checkbox" id="cap-on">
          <span class="name">Capacitación</span>
          <span class="stepper" style="margin-left:auto" aria-label="Sesiones de capacitación">
            <button type="button" data-cap="-1" aria-label="Menos sesiones">−</button>
            <span class="val" id="cap-n">1</span>
            <button type="button" data-cap="1" aria-label="Más sesiones">+</button>
          </span>
          <span class="band" style="margin-left:.6rem">$650.000 / sesión</span>
        </label>
      </section>
    </div>

    <aside>
      <div class="summary">
        <div class="cap">Estimación de referencia</div>
        <div class="total">
          <span class="num" id="tmin">$0</span><span class="dash">–</span><span class="num" id="tmax">$0</span>
          <span class="unit">COP</span>
        </div>
        <p class="subtotal-note">antes de IVA (19%)</p>

        <div class="break">
          <div class="l" id="b-dev"><span>Desarrollo</span><span></span></div>
          <div class="l" id="b-pi"><span>Titularidad exclusiva</span><span></span></div>
          <div class="l" id="b-svc"><span>Servicios</span><span></span></div>
          <div class="l" id="b-cap"><span>Capacitación</span><span></span></div>
          <div class="l" id="b-mant"><span>Mantenimiento (1er año)</span><span></span></div>
        </div>

        <a class="cta" id="cta" href="#" target="_blank" rel="noopener">Pedir cotización formal</a>
        <p class="disclaimer">Valores de referencia, no vinculantes y sin IVA. La cotización
          formal fija el alcance (requerimientos y complejidad acordados) y el precio cerrado.</p>
      </div>
    </aside>
  </div>

  <p class="foot">Basado en el modelo de valoración de Xiliux: tarifa de arquitecto + IA sobre el
    esfuerzo por complejidad. ¿Prefieres un producto ya listo (p. ej. SIGER)? Eso va con precio de
    lista aparte.</p>
</div>

<script>
  "use strict";
  // Bandas en COP (del modelo §10): [min, max] por requerimiento, por complejidad.
  const REQS = [
    { key: "leve",    name: "Leve",     ex: "un campo, una validación, un reporte simple", band: [560000, 1680000] },
    { key: "moderado",name: "Moderado", ex: "una funcionalidad con lógica, una integración simple", band: [2240000, 5600000] },
    { key: "grave",   name: "Grave",    ex: "un subsistema, lógica compleja, varias pantallas", band: [6720000, 14000000] },
    { key: "critico", name: "Crítico",  ex: "un módulo nuevo, seguridad/criptografía, integración pesada", band: [16800000, 33600000] },
  ];
  const SVCS = [
    { key: "impl", name: "Implementación y parametrización", band: [3500000, 6000000] },
    { key: "migr", name: "Migración de datos",               band: [1800000, 4000000] },
  ];
  const CAP_UNIT = 650000;          // por sesión
  const PI_A2 = [1.5, 1.8];         // titularidad exclusiva: +50% a +80%
  const MANT = 0.20;                // mantenimiento 1er año ~20% del desarrollo
  const WA = "https://wa.me/?text=" + encodeURIComponent(
    "Hola Xiliux, quiero cotizar un sistema a la medida. Mi estimación de referencia fue: ");

  const state = {
    counts: { leve: 0, moderado: 0, grave: 0, critico: 0 },
    pi: "a1", svc: { impl: false, migr: false }, capOn: false, capN: 1, mant: false,
  };

  const fmt = (n) => "$" + Math.round(n).toLocaleString("es-CO");
  const fmtM = (n) => {
    if (n >= 1e6) return "$" + (n / 1e6).toLocaleString("es-CO", { maximumFractionDigits: 1 }) + " M";
    return fmt(n);
  };

  // Construir filas de requerimientos
  const reqsEl = document.getElementById("reqs");
  REQS.forEach((r) => {
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML =
      '<div class="label"><div class="name">' + r.name + '</div><div class="ex">' + r.ex + '</div></div>' +
      '<div style="display:flex;align-items:center;gap:.9rem">' +
        '<span class="band">' + fmtM(r.band[0]) + "–" + fmtM(r.band[1]) + " c/u</span>" +
        '<span class="stepper" aria-label="Cantidad ' + r.name + '">' +
          '<button type="button" data-req="' + r.key + '" data-d="-1" aria-label="Menos">−</button>' +
          '<span class="val" id="n-' + r.key + '">0</span>' +
          '<button type="button" data-req="' + r.key + '" data-d="1" aria-label="Más">+</button>' +
        "</span></div>";
    reqsEl.appendChild(row);
  });

  const svcsEl = document.getElementById("svcs");
  SVCS.forEach((s) => {
    const lab = document.createElement("label");
    lab.className = "check";
    lab.innerHTML = '<input type="checkbox" data-svc="' + s.key + '">' +
      '<span class="name">' + s.name + "</span>" +
      '<span class="band">' + fmtM(s.band[0]) + "–" + fmtM(s.band[1]) + "</span>";
    svcsEl.appendChild(lab);
  });

  function compute() {
    let devMin = 0, devMax = 0;
    REQS.forEach((r) => { devMin += state.counts[r.key] * r.band[0]; devMax += state.counts[r.key] * r.band[1]; });
    // Palanca de PI
    let piMin = 0, piMax = 0;
    if (state.pi === "a2") { piMin = devMin * (PI_A2[0] - 1); piMax = devMax * (PI_A2[1] - 1); }
    let svcMin = 0, svcMax = 0;
    SVCS.forEach((s) => { if (state.svc[s.key]) { svcMin += s.band[0]; svcMax += s.band[1]; } });
    const capMin = state.capOn ? CAP_UNIT * state.capN : 0, capMax = capMin;
    // Mantenimiento sobre el desarrollo (con PI aplicada)
    const mantMin = state.mant ? (devMin + piMin) * MANT : 0;
    const mantMax = state.mant ? (devMax + piMax) * MANT : 0;
    const min = devMin + piMin + svcMin + capMin + mantMin;
    const max = devMax + piMax + svcMax + capMax + mantMax;
    return { devMin, devMax, piMin, piMax, svcMin, svcMax, capMin, capMax, mantMin, mantMax, min, max };
  }

  function line(id, min, max) {
    const el = document.getElementById(id);
    if (max <= 0) { el.classList.add("zero"); return; }
    el.classList.remove("zero");
    el.querySelector("span:last-child").textContent =
      min === max ? fmtM(min) : fmtM(min) + "–" + fmtM(max);
  }

  function render() {
    const c = compute();
    document.getElementById("tmin").textContent = fmtM(c.min);
    document.getElementById("tmax").textContent = fmtM(c.max);
    line("b-dev", c.devMin, c.devMax);
    line("b-pi", c.piMin, c.piMax);
    line("b-svc", c.svcMin, c.svcMax);
    line("b-cap", c.capMin, c.capMax);
    line("b-mant", c.mantMin, c.mantMax);
    document.getElementById("cta").href = WA + encodeURIComponent(fmtM(c.min) + "–" + fmtM(c.max) + " COP");
  }

  // Eventos
  document.addEventListener("click", (e) => {
    const rq = e.target.closest("[data-req]");
    if (rq) {
      const k = rq.dataset.req, d = +rq.dataset.d;
      state.counts[k] = Math.max(0, state.counts[k] + d);
      document.getElementById("n-" + k).textContent = state.counts[k];
      render(); return;
    }
    const pi = e.target.closest("[data-pi]");
    if (pi) {
      state.pi = pi.dataset.pi;
      document.querySelectorAll("#pi button").forEach((b) => b.setAttribute("aria-pressed", b === pi));
      render(); return;
    }
    const cap = e.target.closest("[data-cap]");
    if (cap) {
      state.capN = Math.max(1, state.capN + +cap.dataset.cap);
      document.getElementById("cap-n").textContent = state.capN;
      if (state.capOn) render(); return;
    }
  });
  document.addEventListener("change", (e) => {
    const sv = e.target.closest("[data-svc]");
    if (sv) { state.svc[sv.dataset.svc] = sv.checked; render(); return; }
    if (e.target.id === "cap-on") { state.capOn = e.target.checked; render(); return; }
  });

  // Mantenimiento como una opción más (se añade al panel de servicios por JS para no romper el HTML)
  (function addMant() {
    const lab = document.createElement("label");
    lab.className = "check";
    lab.innerHTML = '<input type="checkbox" id="mant-on">' +
      '<span class="name">Mantenimiento y actualizaciones (1er año)</span>' +
      '<span class="band">~20% del desarrollo</span>';
    document.getElementById("svcs").appendChild(lab);
    document.getElementById("mant-on").addEventListener("change", (e) => { state.mant = e.target.checked; render(); });
  })();

  render();
</script>

</body>
</html>"""

@app.get('/cotizador')
def cotizador_pagina():
    return Response(content=COTIZADOR_HTML, media_type="text/html")


# ============ /quipu/cbom — radiografía criptográfica firmada ============
# La página LEE los CBOM firmados de assets/cbom/ (fuente de verdad); si Quipu
# regenera su CBOM, se recopian esos JSON y la página se actualiza sola.
_CBOM_CSS = """<style>
.cbom-perfil{margin:2.4rem 0;border:1px solid #1e293b;border-radius:16px;background:#0f172a;padding:22px}
.cbom-head{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:14px}
.cbom-head h2{margin:0;color:#fff;font-size:1.4rem}
.cbom-eyebrow{font-family:ui-monospace,monospace;font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;color:#64748b}
.cbom-chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:18px}
.cbom-chip{font-family:ui-monospace,monospace;font-size:.74rem;padding:4px 10px;border-radius:7px;border:1px solid #1e293b;background:#0b1220;color:#94a3b8}
.cbom-chip b{color:#e2e8f0}
.cbom-verdict{display:flex;gap:14px;align-items:center;padding:16px;border:1px solid #14532d;border-radius:12px;background:rgba(16,185,129,.07);margin-bottom:16px}
.cbom-badge{width:40px;height:40px;flex:none;border-radius:11px;display:grid;place-items:center;background:rgba(52,211,153,.16);color:#34d399;font-size:1.3rem}
.cbom-verdict b{color:#6ee7b7}
.cbom-verdict p{margin:.2rem 0 0;color:#94a3b8;font-size:.9rem}
.cbom-tablewrap{overflow-x:auto;border:1px solid #1e293b;border-radius:12px}
.cbom-tablewrap table{border-collapse:collapse;width:100%;min-width:620px;font-size:.88rem}
.cbom-tablewrap th{text-align:left;font-family:ui-monospace,monospace;font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;color:#64748b;padding:12px 14px;border-bottom:1px solid #1e293b}
.cbom-tablewrap td{padding:11px 14px;border-bottom:1px solid #1e293b;color:#cbd5e1;vertical-align:middle}
.cbom-tablewrap tr:last-child td{border-bottom:0}
.cbom-alg{font-weight:600;color:#fff}
.cbom-mono{font-family:ui-monospace,monospace;font-size:.8rem;color:#94a3b8}
.cbom-pill{display:inline-block;font-size:.74rem;font-weight:600;padding:3px 9px;border-radius:999px;white-space:nowrap}
.cbom-pill.pq{color:#6ee7b7;background:rgba(52,211,153,.13)}
.cbom-pill.cl{color:#fbbf24;background:rgba(251,191,36,.14)}
.cbom-pill.sm{color:#22d3ee;background:rgba(34,211,238,.12)}
.cbom-cat{font-family:ui-monospace,monospace;font-size:.7rem;color:#64748b;margin-left:6px}
.cbom-sign{margin-top:14px;font-family:ui-monospace,monospace;font-size:.78rem;color:#94a3b8;padding:12px 14px;border:1px solid #1e293b;border-radius:10px;background:#0b1220;word-break:break-all}
.cbom-sign b{color:#6ee7b7}
</style>"""

_CBOM_CLAIMS = {
    'quipu-cnsa': ('0 primitivas cuánticamente vulnerables entre las requeridas por CNSA 2.0',
                   'Perfil puro: los algoritmos que exige el mandato de la NSA, sin socio clásico. Más simple, pero si una familia PQ cayera no queda respaldo — por eso existe el perfil híbrido.',
                   'puro CNSA 2.0'),
    'quipu': ('Ningún canal depende solo de criptografía clásica',
              'Cifrado, establecimiento de clave y firma combinan una primitiva clásica con una post-cuántica. El sistema resiste aunque una de las dos familias caiga.',
              'híbrido'),
}

def _cbom_pill(comp):
    props = {p['name']: p['value'] for p in comp.get('properties', [])}
    lvl = comp['cryptoProperties']['algorithmProperties'].get('nistQuantumSecurityLevel', 0)
    rol = props.get('quipu:rol')
    if rol == 'clasico':
        return ('cl', 'clásico', 'emparejado')
    if rol == 'pq':
        return ('pq', 'post-cuántico', f'cat {lvl}')
    if rol == 'simetrico':
        return ('sm', 'simétrico', f'cat {lvl}' if lvl else '')
    if lvl >= 4:
        return ('pq', 'post-cuántico', f'cat {lvl}')
    return ('sm', 'simétrico', f'cat {lvl}' if lvl else '')

def _cbom_seccion(cbom, sig, sha_real=None):
    perfil = cbom['metadata']['component']
    nombre = perfil['name']
    claim, sub, tag = _CBOM_CLAIMS.get(nombre, ('Inventario criptográfico', '', ''))
    comps = cbom['components']
    filas = []
    for c in comps:
        ap = c['cryptoProperties']['algorithmProperties']
        oid = c['cryptoProperties'].get('oid') or '—'
        cls, etq, cat = _cbom_pill(c)
        cathtml = f'<span class="cbom-cat">{_htmlmod.escape(cat)}</span>' if cat else ''
        filas.append(
            f'<tr><td class="cbom-alg">{_htmlmod.escape(c["name"])}</td>'
            f'<td class="cbom-mono">{_htmlmod.escape(ap.get("primitive", ""))}</td>'
            f'<td class="cbom-mono">{_htmlmod.escape(oid)}</td>'
            f'<td><span class="cbom-pill {cls}">{etq}</span>{cathtml}</td></tr>')
    lic = perfil.get('licenses', [{}])[0].get('license', {}).get('id', 'AGPL-3.0-or-later')
    chips = (f'<span class="cbom-chip">versión <b>{_htmlmod.escape(perfil["version"])}</b></span>'
             f'<span class="cbom-chip">licencia <b>{_htmlmod.escape(lic)}</b></span>'
             f'<span class="cbom-chip">FIPS 140-3 <b>no validado</b></span>'
             f'<span class="cbom-chip">activos <b>{len(comps)}</b></span>')
    al_dia = sha_real is not None and sha_real == sig.get('sha256_artefacto')
    cabeza = ('Firma <b>atada a este CBOM</b> (SHA-256 verificado)' if al_dia
              else 'Firma <b>NO corresponde a este CBOM</b> — SHA distinto, regenerar'
              if sha_real is not None
              else 'Firma <b>verificada</b>')
    firma = (f'{cabeza} · {_htmlmod.escape(sig["algoritmo"])} · '
             f'clave {_htmlmod.escape(sig.get("clave", "identidad-xiliux"))} '
             f'(huella {_htmlmod.escape(sig.get("huella_clave", ""))})<br>'
             f'SHA-256 {_htmlmod.escape(sig["sha256_artefacto"])}')
    return (f'<section class="cbom-perfil"><div class="cbom-head">'
            f'<h2>{_htmlmod.escape(nombre)}</h2><span class="cbom-eyebrow">{_htmlmod.escape(tag)}</span></div>'
            f'<div class="cbom-chips">{chips}</div>'
            f'<div class="cbom-verdict"><span class="cbom-badge">&#10003;</span><div><b>{_htmlmod.escape(claim)}</b>'
            f'<p>{_htmlmod.escape(sub)}</p></div></div>'
            f'<div class="cbom-tablewrap"><table><thead><tr><th>Algoritmo</th><th>Primitiva</th>'
            f'<th>OID</th><th>Resistencia cuántica</th></tr></thead>'
            f'<tbody>{"".join(filas)}</tbody></table></div>'
            f'<div class="cbom-sign">{firma}</div></section>')

def _leer_cbom(nombre):
    import pathlib, hashlib
    base = pathlib.Path(__file__).parent / 'assets' / 'cbom'
    crudo = (base / nombre).read_bytes()
    cbom = json.loads(crudo.decode('utf-8'))
    sig = json.loads((base / f'{nombre}.sig.json').read_text(encoding='utf-8'))
    # SHA-256 de los BYTES exactos del archivo servido: es sobre lo que se firmó
    # (Rust: `fs::read`). Cruzar contra `sig["sha256_artefacto"]` deja que la
    # página diga "atada a este CBOM" en vez de afirmar "verificada" a ciegas.
    sha_real = hashlib.sha256(crudo).hexdigest()
    return cbom, sig, sha_real

@app.get('/quipu/cbom')
def quipu_cbom():
    secciones = ''
    for nombre in ('cbom-quipu.json', 'cbom.json'):
        cbom, sig, sha_real = _leer_cbom(nombre)
        secciones += _cbom_seccion(cbom, sig, sha_real)
    body = (f'{_CBOM_CSS}<main class="wrap">'
            f'<p class="meta"><a href="/quipu">&larr; Quipu</a></p>'
            f'<h1>La radiografía criptográfica de Quipu</h1>'
            f'<p class="sub">Casi todos los inventarios criptográficos se hacen para <em>descubrir</em> qué migrar '
            f'antes de la computación cuántica. El de Quipu demuestra lo contrario: aquí no queda nada por migrar. '
            f'Cada primitiva, con su OID y su estado frente a la amenaza cuántica &mdash; firmado y verificable.</p>'
            f'{secciones}'
            f'<p style="color:#94a3b8;font-size:.9rem;margin-top:2rem">Un <b>CBOM</b> (Cryptography Bill of '
            f'Materials) es el inventario de los activos criptográficos de un software, en el formato abierto '
            f'<b>CycloneDX 1.6</b> de OWASP. Es la pieza central de la migración post-cuántica que empujan NIST '
            f'(FIPS 203/204/205), la NSA (CNSA 2.0) y la UE: no se puede migrar la criptografía que no se sabe que '
            f'se tiene. Generado por <code>quipu-cbom</code> y firmado con la propia firma híbrida de Quipu.</p>'
            f'</main>')
    head = _seo_head(
        'CBOM de Quipu — radiografía criptográfica post-cuántica firmada',
        'Inventario CycloneDX 1.6 de los algoritmos de Quipu: perfil CNSA 2.0 puro e híbrido, con sus OIDs, '
        'niveles de seguridad NIST y firma híbrida verificable. Cero primitivas cuánticamente vulnerables.',
        f'{DOMAIN}/quipu/cbom')
    return Response(content=_blog_page(head, body), media_type='text/html')


@app.get('/quipu')
def quipu_modelo():
    body = """<main class="wrap">
<h1>Quipu</h1>
<p class="sub">Criptografía post-cuántica para datos en reposo. Software libre bajo AGPL-3.0,
con licencia comercial para quien la necesita.</p>

<h2>Qué se cobra, exactamente</h2>
<p><strong>Quipu es libre y siempre lo será.</strong> Puede usarlo hoy sin pagarnos nada.
La única condición es publicar el código de lo que construya encima. Si eso no le sirve,
le vendemos la exención de esa obligación.</p>
<p>Dicho de otro modo: <strong>no se cobra por el uso, se cobra por el derecho a no
publicar</strong>. El copyleft no prohíbe cobrar — la licencia dice literalmente que puede
cobrarse cualquier precio o ninguno. Lo que restringe es el <em>secreto</em>, no el precio.</p>

<h2>Si puede cumplir el copyleft, no necesita comprarnos nada</h2>
<p>Un proyecto libre, uno académico o una entidad con política de software abierto usan
Quipu gratis, y nos interesa que lo hagan: son la razón de que el proyecto exista y de que
otros confíen en él. El cliente comercial es específicamente quien tiene código que no
puede o no quiere publicar.</p>

<h2>Dos cosas distintas que se venden</h2>
<div class="grid">
  <div class="card"><h2>Licencia comercial</h2>
    <p>Le exime del copyleft de red. Integre Quipu en su producto propietario o su SaaS sin
    publicar su código fuente.</p>
    <p class="sub">Es una concesión <em>adicional y paralela</em> a la AGPL, no una
    sustitución: conserva todos los derechos que la licencia libre concede a cualquiera.</p></div>
  <div class="card"><h2>Servidor OPRF gestionado</h2>
    <p>No tener que operar la infraestructura ni custodiar la clave. Disponibilidad,
    límite de tasa y rotación incluidos.</p>
    <p class="sub">Negocio distinto y complementario. Puede necesitar uno, el otro, los dos
    o ninguno.</p></div>
</div>

<h2>Qué hay dentro</h2>
<p>Cifrado híbrido <strong>X25519 + ML-KEM-1024</strong> y firma híbrida
<strong>Ed25519 + ML-DSA-87</strong> — los parámetros que exige el mandato CNSA 2.0 de la NSA —,
con opción de <strong>X-Wing-768 interoperable</strong> (borrador CFRG, conforme a sus vectores
oficiales) y de <strong>firma triple</strong> que suma SLH-DSA: tres esquemas, y las tres firmas
tienen que validar. Custodia de claves por umbral (Shamir), autopruebas de arranque con vectores
del RFC 5869, y un laboratorio de seguridad que se ataca a sí mismo.</p>
<p><strong>Modos que un cifrado normal no cubre:</strong> cifrado <em>discreto</em> (sin cabecera
en claro, indistinguible de bytes al azar), cifrado <em>perforable</em> (la clave se destruye al
abrir, con registro encadenado de cada apertura) y evaluación ciega online por VOPRF conforme a
la RFC 9497.</p>
<p><strong>Verificado, no solo afirmado.</strong> Su ML-KEM y su ML-DSA se comparan byte a byte,
en los tres niveles de seguridad, contra tres implementaciones independientes: la referencia C de
pq-crystals, libcrux (formalmente verificada) y AWS-LC (de producción). Coincidir con tres que no
se conocen entre sí es la prueba de que el estándar está bien implementado, no solo afirmado.</p>
<p>El código es auditable y se entrega a quien quiera auditarlo, con su firma y su
suma SHA-256. <strong>Desde agosto de 2026 no se distribuye por registros públicos</strong>
—ni crates.io, ni PyPI, ni npm, ni GitHub— y el motivo es la seguridad: los ataques
encadenados de ciberdelincuentes contra esas plataformas durante 2026 hicieron que
alojar ahí una librería de criptografía dejara de ser una decisión neutra. No cambia
la licencia ni el producto: sigue siendo AGPL-3.0 y sigue siendo gratis.
Se pide por <a href="/#contacto">el formulario de contacto</a> — <a href="/quipu/codigo">cómo pedirlo, qué llega y por qué se decidió así</a>.</p>

<p><a class="card" href="/quipu/precios" style="display:inline-block;margin-top:1rem">
Ver planes del servicio gestionado &rarr;</a></p>
</main>"""
    quipu_jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "SoftwareSourceCode",
        "name": "Quipu",
        "description": "Criptografía híbrida post-cuántica para datos en reposo: "
                       "X25519 + ML-KEM-1024 para claves y Ed25519 + ML-DSA-87 para "
                       "firmas, con perfil CNSA 2.0. Resistente al algoritmo de Shor.",
        "url": f"{DOMAIN}/quipu",
        # Apuntaba al repositorio de GitHub, vaciado el 2026-08-10: un dato
        # estructurado mandando al buscador a un repo con solo README y LICENSE.
        "codeRepository": f"{DOMAIN}/quipu/codigo",
        "programmingLanguage": ["Rust", "Python"],
        "license": "https://www.gnu.org/licenses/agpl-3.0.html",
        "keywords": "criptografía post-cuántica, ML-KEM, ML-DSA, cifrado híbrido, Rust, OPRF",
        "author": {"@type": "Person", "name": "Juan Carlos Isaza", "url": DOMAIN,
                   "sameAs": ["https://github.com/isazajuancarlos"]},
    }, ensure_ascii=False).replace("</", "<\\/")
    head = _seo_head(
        'Quipu — criptografía post-cuántica libre, con licencia comercial | Xiliux',
        'Quipu es software libre bajo AGPL-3.0: úselo sin pagar. La licencia comercial no '
        'vende el uso, vende la exención de publicar su código. Cifrado híbrido X25519 + '
        'ML-KEM-1024 y firma Ed25519 + ML-DSA-87.',
        f'{DOMAIN}/quipu', alternates=_QUIPU_ALT,
        jsonld=f'<script type="application/ld+json">{quipu_jsonld}</script>')
    return Response(content=_blog_page(head, body), media_type='text/html')


# --- CÓMO PEDIR EL CÓDIGO DE QUIPU (HTML de servidor, rastreable, bilingüe) ---
#
# Nace el 2026-08-11. El README público de quipu en GitHub dice que aquí están
# «la documentación, las mediciones y la forma de pedirlo», y hasta hoy eso era
# UN PÁRRAFO al final de /quipu, que es una página de modelo de negocio. Quien
# llega desde GitHub buscando el código aterrizaba en una página de precios.
#
# Y va en INGLÉS además de español porque quien más probablemente siga ese
# enlace no lee español: revisores de subvenciones (OTF), auditores y
# desarrolladores que evalúan la librería. El README de GitHub está en español.
#
# La decisión de retirada NO se justifica aquí de forma nueva: se explica con
# los mismos hechos que la sostienen (ataques de 2026 con nombre y fecha), y se
# dice sin adornar lo que la retirada NO consiguió — los artefactos ya
# publicados siguen descargables. Un canal de entrega que empieza ocultando eso
# no merece que nadie le confíe una librería de criptografía.

_CODIGO_ALT = (f'<link rel="alternate" hreflang="es" href="{DOMAIN}/quipu/codigo">'
               f'<link rel="alternate" hreflang="en" href="{DOMAIN}/en/quipu/code">'
               f'<link rel="alternate" hreflang="x-default" href="{DOMAIN}/quipu/codigo">')

_CODIGO_ES = """<main class="wrap">
<h1>Cómo pedir el código de Quipu</h1>
<p class="sub">Quipu es software libre bajo AGPL-3.0 y su código completo se entrega a
quien lo pida. Lo que cambió en agosto de 2026 no es la licencia ni la disponibilidad:
es el canal.</p>

<h2>Se pide por correo</h2>
<p>Pídalo por <a href="/#contacto">el formulario de contacto</a>.
Decir para qué lo quiere —evaluarlo, auditarlo, integrarlo, estudiarlo— ayuda a enviarle
lo que le sirve, pero <strong>no es un requisito ni una condición</strong>. No hay
formulario, no hay registro y no hay lista de espera.</p>

<h2>Qué recibe</h2>
<div class="grid">
  <div class="card"><h2>El código</h2>
    <p>El fuente completo de una versión publicada, anclado a su <em>commit</em> exacto.
    Nada retirado, nada ofuscado, sin «edición comercial» aparte.</p></div>
  <div class="card"><h2>La firma</h2>
    <p>Firma híbrida <strong>Ed25519 + ML-DSA-87</strong>, la clave pública y un
    verificador estático que no necesita red ni dependencias.</p></div>
  <div class="card"><h2>Los documentos</h2>
    <p>Especificación técnica, modelo de amenaza, pre-auditoría interna escrita y las
    notas de reproducibilidad.</p></div>
</div>
<p><strong>Sin NDA, sin restricción sobre lo que publique de lo que encuentre, sin
caducidad y sin coste.</strong> Si audita Quipu y encuentra un fallo, es suyo para
publicarlo.</p>

<h2>Por qué dejó de publicarse en los registros</h2>
<p>Desde agosto de 2026 el código de Quipu no se aloja en GitHub ni se distribuye por
crates.io, PyPI o npm. No es abandono, no es un incidente y no hubo ninguna intrusión:
es una decisión, y conviene decir en qué se basa.</p>
<p>Durante 2026 los registros de paquetes y las plataformas de código sufrieron ataques
de cadena de suministro <strong>encadenados y sistemáticos</strong> — el gusano
Shai-Hulud, ChainDrop el 4 de agosto, y una extensión de VS Code que se llevó varios
miles de repositorios privados. No son incidentes aislados y no hay motivo para creer
que paran.</p>
<p>El razonamiento no es «nos puede pasar a nosotros». Es más concreto:
<strong>trabajamos en seguridad</strong>, y que a un proveedor de criptografía le
extraigan el código desde la plataforma donde lo alojó no sería un incidente
operativo — sería un argumento en contra del producto. Un registro público mete además
un tercero de confianza obligatorio entre nosotros y usted: quien comprometa ese
registro, o la cuenta, puede entregarle un paquete manipulado con nuestro nombre.</p>

<h2>Lo que el canal directo mejora, y lo que no</h2>
<p><strong>Mejora la integridad.</strong> Un SHA-256 publicado junto al archivo protege
del error de copia y del transporte, no de un origen comprometido: quien controle el
servidor cambia el archivo <em>y</em> el hash. Con firma, comprometer el servidor deja
de bastar — la clave privada no vive en él. Y la firma es híbrida a propósito: quien
guarde hoy una entrega y tenga un computador cuántico mañana tampoco puede falsificarla
hacia atrás. Firmar con RSA una librería que se vende por ser post-cuántica sería
contradecirse por escrito.</p>
<p><strong>No mejora la confidencialidad de lo ya publicado, y no lo vamos a insinuar.</strong>
Los artefactos que estuvieron en crates.io y PyPI <em>siguen descargables con su código
fuente completo</em>: crates.io no permite borrar nunca, y el plazo de retirada de npm
caduca. La criptografía de Quipu es pública de forma permanente, que por lo demás es
como debe ser — un cifrado cuya seguridad dependa de que nadie vea el algoritmo no es
seguro. Lo que está en juego aquí es <em>qué instala usted</em>, no si el diseño se
conoce.</p>

<h2>El código, a pedido — y su modelo</h2>\n<p>quipu es <strong>AGPL-3.0</strong>: libre si publicas tu derivado. Para usarla <strong>sin</strong> publicar hay <strong>licencia comercial</strong> (a cotización); y si necesitas <strong>desarrollo a medida</strong> sobre ella, se cotiza por alcance. Se pide por <a href="/#contacto">el formulario de contacto</a>.</p>\n<p class="sub">La fuente completa —vendorizada para construirse sin red, con su firma híbrida Ed25519 + ML-DSA-87 y su verificador estático— se entrega a pedido a quien la audite, no por descarga pública.</p>\n\n<h2>La huella de la clave, aquí y no en el paquete</h2>
<p>Una firma solo sirve si la clave pública con la que se comprueba llega por un camino
que el atacante no controle. Si la clave viaja <em>dentro</em> del mismo envío que el
archivo que autentica, quien pueda sustituir el archivo sustituye también la clave y la
verificación pasa igual: es un círculo, y un círculo no prueba nada.</p>
<p>Por eso la huella está publicada aquí, en un sitio distinto del envío. Compruebe que
la clave que recibió tiene esta huella <strong>antes</strong> de verificar nada con ella:</p>
<pre class="huella"><code>SHA-256 de la clave pública de firma de Xiliux

  f64e 46b9 676f e72e 4f79 a9d1 3664 ebfe
  94f9 6119 eb26 b037 8631 16dd f3d2 7d7d

  tr -d '\n' &lt; CLAVE-PUBLICA.txt | sha256sum</code></pre>
<p class="sub">Si no coinciden, no verifique: escríbanos por otra vía y dígalo.</p>

<h2>Lo que no cambió</h2>
<ul>
<li>La licencia sigue siendo <strong>AGPL-3.0</strong>, y no va a cambiar.</li>
<li>Sigue siendo gratis. La <a href="/quipu">licencia comercial</a> exime del copyleft
de red a quien no puede publicar su código; no compra el acceso, que es de todos.</li>
<li>Se entrega a cualquiera que lo pida, no a una lista de aprobados.</li>
</ul>

<h2>Si es usted auditor</h2>
<p>Pídalo igual, dígalo en el correo y añadimos lo que necesite: la trazabilidad entre
la versión publicada y su <em>commit</em>, el histórico, y una sesión para recorrer la
parte del código que le interese. Una auditoría independiente es lo que más falta le
hace hoy a este proyecto; no la vamos a poner difícil.</p>

<p><a class="card" href="/quipu" style="display:inline-block;margin-top:1rem">
Volver a Quipu &rarr;</a></p>
</main>"""

_CODIGO_EN = """<main class="wrap">
<h1>How to request the Quipu source code</h1>
<p class="sub">Quipu is free software under AGPL-3.0 and the complete source is delivered
to anyone who asks. What changed in August 2026 is not the licence and not the
availability: it is the channel.</p>

<h2>Ask by email</h2>
<p>Ask via <a href="/#contacto">the contact form</a>.
Telling us what you want it for — to evaluate it, audit it, integrate it, study it —
helps us send what is useful to you, but it is <strong>not a requirement and not a
condition</strong>. There is no form, no sign-up and no waiting list.</p>

<h2>What you get</h2>
<div class="grid">
  <div class="card"><h2>The code</h2>
    <p>Complete source of a released version, anchored to its exact commit. Nothing
    held back, nothing obfuscated, no separate "commercial edition".</p></div>
  <div class="card"><h2>The signature</h2>
    <p>A hybrid <strong>Ed25519 + ML-DSA-87</strong> signature, the public key, and a
    static verifier that needs no network and no dependencies.</p></div>
  <div class="card"><h2>The documents</h2>
    <p>Technical specification, threat model, written internal pre-audit and the
    reproducible-build notes.</p></div>
</div>
<p><strong>No NDA, no restriction on publishing what you find, no expiry and no
cost.</strong> If you audit Quipu and find a flaw, it is yours to publish.</p>

<h2>Why it is no longer on the public registries</h2>
<p>Since August 2026 the Quipu source is not hosted on GitHub and is not distributed
through crates.io, PyPI or npm. This is not abandonment, not an incident, and there was
no breach: it is a decision, and it is worth stating what it rests on.</p>
<p>Through 2026 the package registries and code-hosting platforms were hit by
<strong>sustained, chained</strong> supply-chain attacks — the Shai-Hulud worm,
ChainDrop on 4 August, and a VS Code extension that exfiltrated several thousand private
repositories. These are not isolated incidents and there is no reason to believe they
stop.</p>
<p>The reasoning is not "it could happen to us". It is narrower than that: <strong>we
work in security</strong>, and a cryptography vendor having its code extracted from the
platform it chose to host it on would not be an operational incident — it would be an
argument against the product. A public registry also inserts a mandatory trusted third
party between us and you: whoever compromises that registry, or the account, can hand
you a tampered package carrying our name.</p>

<h2>What the direct channel improves, and what it does not</h2>
<p><strong>It improves integrity.</strong> A SHA-256 published next to the file protects
against copy errors and the transport, not against a compromised origin: whoever
controls the server changes the file <em>and</em> the hash. With a signature,
compromising the server is no longer enough — the private key does not live there. And
the signature is hybrid on purpose: someone who stores a delivery today and has a
quantum computer tomorrow still cannot forge it retroactively. Signing a library sold on
post-quantum grounds with RSA would be a contradiction in writing.</p>
<p><strong>It does not improve the confidentiality of what was already published, and we
are not going to imply otherwise.</strong> The artifacts that were on crates.io and PyPI
<em>remain downloadable with their full source</em>: crates.io never allows deletion,
and npm's unpublish window expires. Quipu's cryptography is permanently public — which
is how it should be anyway, since a cipher whose security depends on nobody seeing the
algorithm is not secure. What is at stake here is <em>what you install</em>, not whether
the design is known.</p>

<h2>The code, on request — and its model</h2>\n<p>quipu is <strong>AGPL-3.0</strong>: free if you publish your derivative. To use it <strong>without</strong> publishing there is a <strong>commercial license</strong> (on quote); and if you need <strong>bespoke development</strong> on top of it, it is quoted by scope. Ask via <a href="/#contacto">the contact form</a>.</p>\n<p class="sub">The full source —vendored to build offline, with its hybrid Ed25519 + ML-DSA-87 signature and its static verifier— is delivered on request to anyone auditing it, not by public download.</p>\n\n<h2>The key fingerprint, published here and not in the package</h2>
<p>A signature is only worth something if the public key it is checked against arrives by
a path the attacker does not control. If the key travels <em>inside</em> the same delivery
as the file it authenticates, whoever can substitute the file substitutes the key too and
verification passes anyway: that is a circle, and a circle proves nothing.</p>
<p>So the fingerprint is published here, on a channel separate from the delivery. Check
that the key you received has this fingerprint <strong>before</strong> you verify anything
with it:</p>
<pre class="huella"><code>SHA-256 of the Xiliux artifact-signing public key

  f64e 46b9 676f e72e 4f79 a9d1 3664 ebfe
  94f9 6119 eb26 b037 8631 16dd f3d2 7d7d

  tr -d '\n' &lt; CLAVE-PUBLICA.txt | sha256sum</code></pre>
<p class="sub">If they do not match, do not verify: contact us by another route and say so.</p>

<h2>What did not change</h2>
<ul>
<li>The licence is still <strong>AGPL-3.0</strong>, and it will not change.</li>
<li>It is still free. The <a href="/quipu">commercial licence</a> exempts from network
copyleft those who cannot publish their own code; it does not buy access, which belongs
to everyone.</li>
<li>It goes to anyone who asks, not to an approved list.</li>
</ul>

<h2>If you are an auditor</h2>
<p>Ask the same way, say so in the email, and we add whatever you need: the traceability
between the released version and its commit, the history, and a session walking through
whichever part of the code interests you. An independent audit is what this project most
needs right now; we are not going to make it difficult.</p>

<p><a class="card" href="/quipu" style="display:inline-block;margin-top:1rem">
Back to Quipu &rarr;</a></p>
</main>"""


def _codigo_jsonld(lang):
    return json.dumps({
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [{
            "@type": "Question",
            "name": ("How do I get the Quipu source code?" if lang == "en"
                     else "¿Cómo se consigue el código de Quipu?"),
            "acceptedAnswer": {"@type": "Answer", "text": (
                "Use the contact form. The complete source of a released version is "
                "delivered with a hybrid Ed25519 + ML-DSA-87 signature, the public key, a "
                "static verifier, the specification, the threat model and the internal "
                "pre-audit. No NDA, no cost, no expiry."
                if lang == "en" else
                "Escribiendo por el formulario de contacto. Se entrega el fuente completo de una "
                "versión publicada con su firma híbrida Ed25519 + ML-DSA-87, la clave "
                "pública, un verificador estático, la especificación, el modelo de amenaza "
                "y la pre-auditoría interna. Sin NDA, sin coste y sin caducidad.")},
        }, {
            "@type": "Question",
            "name": ("Why is Quipu no longer on GitHub, crates.io, PyPI or npm?" if lang == "en"
                     else "¿Por qué Quipu ya no está en GitHub, crates.io, PyPI ni npm?"),
            "acceptedAnswer": {"@type": "Answer", "text": (
                "A deliberate decision taken in August 2026 after the year's chained "
                "supply-chain attacks on the public registries. The licence (AGPL-3.0) and "
                "the availability of the code did not change; the delivery channel did."
                if lang == "en" else
                "Es una decisión de agosto de 2026, tras los ataques encadenados de cadena "
                "de suministro contra los registros públicos durante ese año. Ni la "
                "licencia (AGPL-3.0) ni la disponibilidad del código cambiaron; cambió el "
                "canal de entrega.")},
        }],
    }, ensure_ascii=False).replace("</", "<\\/")


@app.get('/quipu/codigo')
def quipu_codigo():
    head = _seo_head(
        'Cómo pedir el código de Quipu — se entrega firmado, a quien lo pida | Xiliux',
        'Quipu es AGPL-3.0 y su código completo se entrega por correo, firmado con '
        'Ed25519 + ML-DSA-87, sin NDA y sin coste. Por qué dejó de publicarse en '
        'GitHub, crates.io, PyPI y npm en agosto de 2026.',
        f'{DOMAIN}/quipu/codigo', alternates=_CODIGO_ALT,
        jsonld=f'<script type="application/ld+json">{_codigo_jsonld("es")}</script>')
    return Response(content=_blog_page(head, _CODIGO_ES), media_type='text/html')


@app.get('/en/quipu/code')
def quipu_codigo_en():
    head = _seo_head(
        'How to request the Quipu source code — signed, to anyone who asks | Xiliux',
        'Quipu is AGPL-3.0 and the complete source is delivered by email, signed with '
        'Ed25519 + ML-DSA-87, with no NDA and no cost. Why it left GitHub, crates.io, '
        'PyPI and npm in August 2026.',
        f'{DOMAIN}/en/quipu/code', lang='en', alternates=_CODIGO_ALT,
        jsonld=f'<script type="application/ld+json">{_codigo_jsonld("en")}</script>')
    return Response(content=_blog_page(head, _CODIGO_EN, lang='en'), media_type='text/html')


# --- QUIPU Y SERVICIOS EN INGLÉS (HTML de servidor) --------------------------
#
# Cierra lo que quedaba del embudo inglés. Hasta el 2026-08-12 existían `/en`,
# `/en/blog`, `/en/libraries/code` y `/en/quipu/code`, pero las dos páginas que
# de verdad venden —el producto Quipu y los servicios— solo estaban en español,
# así que el lector anglófono llegaba al final del recorrido y se topaba con el
# muro. Traducirlas es barato: son HTML de servidor y el patrón ya está montado.
#
# `/informes` NO se traduce, y es decisión razonada, no olvido: SIGER se vende a
# entidades colombianas por una obligación de reporte de la normativa
# colombiana. Una versión inglesa no tendría a quién hablarle, y una página que
# no le habla a nadie diluye la señal temática del dominio en vez de sumarla.

_QUIPU_ALT = (f'<link rel="alternate" hreflang="es" href="{DOMAIN}/quipu">'
              f'<link rel="alternate" hreflang="en" href="{DOMAIN}/en/quipu">'
              f'<link rel="alternate" hreflang="x-default" href="{DOMAIN}/quipu">')

_SERVICIOS_ALT = (f'<link rel="alternate" hreflang="es" href="{DOMAIN}/servicios">'
                  f'<link rel="alternate" hreflang="en" href="{DOMAIN}/en/services">'
                  f'<link rel="alternate" hreflang="x-default" href="{DOMAIN}/servicios">')

_QUIPU_EN = """<main class="wrap">
<h1>Quipu</h1>
<p class="sub">Post-quantum cryptography for data at rest. Free software under AGPL-3.0,
with a commercial licence for those who need one.</p>

<h2>What exactly is being charged for</h2>
<p><strong>Quipu is free and always will be.</strong> You can use it today without paying
us anything. The only condition is publishing the source of whatever you build on top of
it. If that does not work for you, we sell you an exemption from that obligation.</p>
<p>Put another way: <strong>we do not charge for use, we charge for the right not to
publish</strong>. Copyleft does not forbid charging &mdash; the licence says in so many
words that you may charge any price or none. What it restricts is <em>secrecy</em>, not
price.</p>

<h2>If you can comply with the copyleft, you need to buy nothing from us</h2>
<p>A free-software project, an academic one, or an organisation with an open-source policy
uses Quipu for free, and we want them to: they are the reason the project exists and the
reason anyone else trusts it. The commercial customer is specifically the one with code
they cannot or will not publish.</p>

<h2>Two different things are for sale</h2>
<div class="grid">
  <div class="card"><h2>Commercial licence</h2>
    <p>Exempts you from the network copyleft. Ship Quipu inside your proprietary product or
    your SaaS without publishing your source.</p>
    <p class="sub">It is an <em>additional and parallel</em> grant to the AGPL, not a
    replacement: you keep every right the free licence gives to anyone.</p></div>
  <div class="card"><h2>Managed OPRF server</h2>
    <p>Not having to run the infrastructure or hold the key. Availability, rate limiting and
    rotation included.</p>
    <p class="sub">A separate, complementary business. You may need one, the other, both or
    neither.</p></div>
</div>

<h2>What is inside</h2>
<p>Hybrid encryption <strong>X25519 + ML-KEM-1024</strong> and hybrid signatures
<strong>Ed25519 + ML-DSA-87</strong> &mdash; the parameters the NSA's CNSA 2.0 mandate
requires &mdash; with an <strong>interoperable X-Wing-768</strong> option (CFRG draft, conformant
to its official vectors) and a <strong>triple signature</strong> that adds SLH-DSA: three schemes,
and all three must verify. Threshold key custody (Shamir), start-up self-tests against RFC 5869
vectors, and a security lab that attacks the library itself.</p>
<p><strong>Modes a plain cipher does not cover:</strong> <em>discreet</em> encryption (no
cleartext header, indistinguishable from random bytes), <em>puncturable</em> encryption (the key
is destroyed on opening, with a hash-chained log of every open), and online blind evaluation by
VOPRF conformant to RFC 9497.</p>
<p><strong>Verified, not just asserted.</strong> Its ML-KEM and ML-DSA are compared byte for byte,
across all three security levels, against three independent implementations: the pq-crystals C
reference, libcrux (formally verified) and AWS-LC (production). Agreeing with three that do not
know each other is proof the standard is implemented, not just claimed.</p>
<p>The code is auditable and is delivered to anyone who wants to audit it, with its
signature and its SHA-256 checksum. <strong>Since August 2026 it is not distributed through
public registries</strong> &mdash; not crates.io, not PyPI, not npm, not GitHub &mdash; and
the reason is security: the chained supply-chain attacks against those platforms through
2026 made hosting a cryptography library there stop being a neutral decision. It changes
neither the licence nor the product: still AGPL-3.0, still free.
Ask via <a href="/#contacto">the contact form</a>
&mdash; <a href="/en/quipu/code">how to ask, what arrives, and why it was decided this way</a>.</p>

<p class="sub">The same delivery exists for the nine Apache-2.0 libraries:
<a href="/en/libraries/code">direct, signed download</a>.</p>

<p><a class="card" href="/quipu/precios" style="display:inline-block;margin-top:1rem">
See the managed service plans &rarr;</a></p>
</main>"""


@app.get('/en/quipu')
def quipu_modelo_en():
    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "SoftwareSourceCode",
        "name": "Quipu",
        "description": "Hybrid post-quantum cryptography for data at rest: X25519 + "
                       "ML-KEM-1024 for keys and Ed25519 + ML-DSA-87 for signatures, "
                       "under the CNSA 2.0 profile. Resistant to Shor's algorithm.",
        "url": f"{DOMAIN}/en/quipu",
        # Antes apuntaba al repositorio de GitHub, que está VACÍO desde el
        # 2026-08-10: un dato estructurado que manda al buscador —y al asistente
        # que lo lea— a un repositorio con solo README y LICENSE. Apunta a donde
        # el código se entrega de verdad.
        "codeRepository": f"{DOMAIN}/en/quipu/code",
        "programmingLanguage": ["Rust", "Python"],
        "license": "https://www.gnu.org/licenses/agpl-3.0.html",
        "inLanguage": "en",
        "keywords": "post-quantum cryptography, ML-KEM, ML-DSA, hybrid encryption, Rust, OPRF",
        "author": {"@type": "Person", "name": "Juan Carlos Isaza", "url": DOMAIN},
    }, ensure_ascii=False).replace("</", "<\\/")
    head = _seo_head(
        'Quipu — free post-quantum cryptography, with a commercial licence | Xiliux',
        'Quipu is free software under AGPL-3.0: use it without paying. The commercial '
        'licence does not sell usage, it sells the exemption from publishing your code. '
        'Hybrid X25519 + ML-KEM-1024 encryption and Ed25519 + ML-DSA-87 signatures.',
        f'{DOMAIN}/en/quipu', lang='en', alternates=_QUIPU_ALT,
        jsonld=f'<script type="application/ld+json">{jsonld}</script>')
    return Response(content=_blog_page(head, _QUIPU_EN, lang='en'), media_type='text/html')


# Servicios en inglés. Los precios SON los mismos que en español y se dicen: uno
# publicado en una lengua y escondido en la otra es la clase de asimetría que,
# el día que alguien la nota, cuesta más que el descuento que evitaba. Lo que sí
# cambia es el ORDEN — el sistema a la medida encabeza en vez de cerrar—, porque
# leer «desde $200» primero ancla la conversación en la tarifa, y ahí se compite
# con miles de perfiles genéricos en vez de con nadie.
_SERVICIOS_EN_ORDEN = (
    ("Custom system &mdash; Rust", "Quoted by scope",
     "Systems built to last: an axum + SQLx backend, server-rendered UI, post-quantum "
     "signing with Quipu, shipping as a single binary with one database file. It is what I "
     "run in production myself. Priced by number of requirements and their complexity."),
    ("AI integration with LLMs", "From $800 USD",
     "Claude, GPT and Gemini wired into a product that already exists, with the boring part "
     "done: cost ceilings, retries, failure paths, and an evaluation that does not flatter "
     "itself."),
    ("Prototype / MVP in Python", "From $500 USD",
     "Validate the idea fast (FastAPI, NiceGUI). It is the first rung: when the prototype "
     "proves its worth, it grows into the Rust system."),
    ("Scripts and automation", "From $200 USD",
     "Process automation, scraping and bots. Fast, measurable results: first value in days, "
     "not months."),
)

_PROCESO_EN = (
    ("1. We talk", "Tell me the problem by email. No commitment."),
    ("2. Proposal", "Scope, timeline and a closed price within 24&ndash;48 h."),
    ("3. Build", "Incremental deliveries and constant communication."),
    ("4. Delivery", "Deployment, documentation, source and initial support included."),
)


@app.get('/en/services')
def servicios_en():
    tarjetas = "".join(
        f'<div class="card"><h2>{t}</h2><p>{d}</p>'
        f'<div class="tags"><span class="tag">{p}</span></div></div>'
        for t, p, d in _SERVICIOS_EN_ORDEN)
    pasos = "".join(f'<div class="card"><h2>{t}</h2><p>{d}</p></div>' for t, d in _PROCESO_EN)
    body = (f'<main class="wrap"><h1>Services</h1>'
            f'<p class="sub">Rust systems, post-quantum cryptography, AI integration and '
            f'automation. You work directly with the person who writes the code &mdash; there '
            f'is no account manager in between.</p>'
            f'<div class="grid">{tarjetas}</div>'
            f'<h2>How I work</h2>'
            f'<p class="sub">Closed price agreed before anything starts. No surprises halfway '
            f'through. Correspondence in English or Spanish.</p>'
            f'<div class="grid">{pasos}</div>'
            f'<h2>And what I build for myself</h2>'
            f'<p class="sub">The best reference for how I work is what I keep in production: '
            f'<a href="/en/quipu">Quipu</a>, a post-quantum cryptography library in production '
            f'use, and nine Apache-2.0 libraries whose '
            f'<a href="/en/libraries/code">complete source is delivered signed</a> to anyone '
            f'who asks. Not demos.</p>'
            f'<div class="cta">'
            f'<a class="btn" href="/#contacto">'
            f'Request a quote</a>'
            f'<a href="/en">&larr; Back to the start</a></div></main>')
    head = _seo_head(
        'Services — Rust systems, post-quantum cryptography and AI integration | Xiliux',
        'Custom systems in Rust (axum + SQLx) that ship as a single offline binary, '
        'post-quantum cryptography, LLM integration and automation. Closed price agreed '
        'before the work starts.',
        f'{DOMAIN}/en/services', lang='en', alternates=_SERVICIOS_ALT)
    return Response(content=_blog_page(head, body, lang='en'), media_type='text/html')


# --- ENTREGA DE LAS MICRO-LIBRERÍAS (descarga directa, firmada) --------------
#
# Quipu ya tenía su entrega descargable (`/quipu/entrega/…`) y el SDK del OPRF
# su canal con token. Las NUEVE micro-librerías no tenían ninguna de las dos, y
# sin embargo el README de sus repositorios vacíos promete «el código se entrega
# a pedido» y remite aquí. El circuito se cortaba justo al llegar: xiliux.com no
# tenía dónde recibir a quien viniera a pedirlo.
#
# POR QUÉ DESCARGA DIRECTA Y NO TOKEN, al revés que el SDK. El token del SDK
# existe para saber a quién se le dio qué y poder cortarle el acceso. Aquí no
# protege nada: siete de las nueve siguen descargándose de PyPI pese al yank
# —medido el 2026-08-12: `pip download position-sizing==0.1.0` trae la rueda—,
# así que la confidencialidad no está en juego y una puerta con llave solo
# añadiría fricción al evaluador, que es exactamente a quien queremos convencer
# (directiva 11). Lo que sí está en juego es la INTEGRIDAD de lo que instale, y
# eso lo sostiene la firma híbrida, no el token.
ENTREGA_LIBS_DIR = os.path.join(ENTREGA_DIR, 'librerias')


def _libs_sumas():
    """Lee SHA256SUMS de la entrega y devuelve {nombre: sha256}.

    Es la FUENTE ÚNICA: la página, la lista de descargas y el filtro de la ruta
    salen todos de aquí. Un archivo que no esté en SHA256SUMS no se sirve —eso
    hace de lista blanca y cierra el recorrido de rutas de paso—, y un archivo
    que esté pero falte del disco se ve como falta en vez de como enlace roto.
    Si el archivo no existe, se devuelve vacío y la página lo DICE (directiva
    20): mejor una página que anuncia que no hay entrega que una que finge.
    """
    ruta = os.path.join(ENTREGA_LIBS_DIR, 'SHA256SUMS')
    if not os.path.exists(ruta):
        return {}
    out = {}
    with open(ruta, 'r', encoding='utf-8') as f:
        for linea in f:
            # El formato de `sha256sum` es <64 hex><espacio><' '|'*'><nombre>,
            # y el nombre PUEDE llevar espacios. Partir con `split()` descartaba
            # en silencio cualquier nombre con espacio —un artefacto legítimo
            # desapareciendo de la entrega sin decir por qué, directiva 20— y
            # metía el `*` del modo binario pegado al nombre.
            linea = linea.rstrip('\n')
            if len(linea) < 67 or linea[64] != ' ' or linea[65] not in ' *':
                continue
            suma = linea[:64]
            if any(c not in '0123456789abcdefABCDEF' for c in suma):
                continue
            out[linea[66:]] = suma.lower()
    return out


# Nombre visible y una línea de qué hace cada una, en los dos idiomas. Se indexa
# por el prefijo del tarball (`<lib>-<version>-<sha>.tar.gz`), que es lo que la
# herramienta de empaquetado produce.
LIBS_ENTREGA = {
    "position-sizing": ("Traduce un presupuesto de riesgo a una cantidad que el exchange acepta.",
                        "Turns a risk budget into a quantity the exchange will accept."),
    "ccxt-resilience": ("Endurece un cliente ccxt contra los falsos positivos de Cloudflare.",
                        "Hardens a legitimate ccxt client against Cloudflare false positives."),
    "honest-eval": ("Dos primitivas para no mentirte en un backtest.",
                    "Two primitives that stop a backtest from flattering itself."),
    "hysteresis-state": ("Máquina de estados con histéresis: anti-flapping para clasificadores ruidosos.",
                         "Hysteresis state machine: anti-flapping for noisy classifiers."),
    "fanout-broadcast": ("Reparte a muchos destinos aislando el fallo de cada uno.",
                         "Fans out to many sinks, isolating each one's failure."),
    "dotkey-i18n": ("i18n por clave con puntos sobre JSON, sin gettext.",
                    "Dot-key i18n over plain JSON, without gettext."),
    "tumbaga": ("Cliente OPRF y cadena de avance sobre el protocolo RFC 9497.",
                "OPRF client and ratchet chain over the RFC 9497 protocol."),
    "chibcha": ("Constantes legislativas colombianas con la norma que las fija.",
                "Colombian statutory constants, each with the rule that sets it."),
    "mirilla": ("Conduce un Chromium sin cabeza por CDP sobre una tubería, sin npm.",
                "Drives headless Chromium over CDP on a pipe. No port, no npm."),
}

_LIBS_ALT = (f'<link rel="alternate" hreflang="es" href="{DOMAIN}/librerias/codigo">'
             f'<link rel="alternate" hreflang="en" href="{DOMAIN}/en/libraries/code">'
             f'<link rel="alternate" hreflang="x-default" href="{DOMAIN}/librerias/codigo">')


def _libs_filas(lang):
    """Filas de la tabla, derivadas de SHA256SUMS + el disco."""
    sumas = _libs_sumas()
    filas = []
    for nombre, suma in sorted(sumas.items()):
        if not nombre.endswith('.tar.gz'):
            continue
        # `<lib>-<version>-<sha>.tar.gz` → lib, version, sha
        base = nombre[:-len('.tar.gz')]
        trozos = base.rsplit('-', 2)
        if len(trozos) != 3:
            continue
        lib, version, sha = trozos
        desc = LIBS_ENTREGA.get(lib, ("", ""))[1 if lang == 'en' else 0]
        ruta = os.path.join(ENTREGA_LIBS_DIR, nombre)
        tam = os.path.getsize(ruta) if os.path.exists(ruta) else 0
        firmado = os.path.exists(ruta + '.firma')
        filas.append({"lib": lib, "version": version, "sha": sha, "desc": desc,
                      "nombre": nombre, "tam": tam, "firmado": firmado})
    return filas


def _libs_cuerpo(lang):
    filas = _libs_filas(lang)
    en = lang == 'en'
    if not filas:
        # Directiva 20: sin artefactos NO se pinta una tabla vacía que parezca
        # una entrega; se dice que no la hay y se ofrece el correo.
        aviso = ("The signed delivery is being rebuilt. Write to "
                 f'<a href="/#contacto">the contact form</a> and it goes out the same day.'
                 if en else
                 "La entrega firmada se está rehaciendo. Escriba a "
                 f'<a href="/#contacto">el formulario de contacto</a> y sale el mismo día.')
        return f'<main class="wrap"><h1>{"Source code" if en else "El código"}</h1><p class="sub">{aviso}</p></main>'

    sin_firma = [f for f in filas if not f["firmado"]]
    tarjetas = []
    for f in filas:
        kb = f"{f['tam'] / 1024:.0f} kB"
        # Escapado también dentro del href: los otros cuatro campos de la misma
        # tarjeta sí lo estaban, y esa inconsistencia es la que sobrevive — el
        # día que la fuente deje de ser un archivo del propio servidor, la
        # única defensa habría desaparecido sin que nadie lo notara.
        _n = _htmlmod.escape(f["nombre"], quote=True)
        firma = (f'<a href="/librerias/entrega/{_n}.firma">.firma</a>'
                 if f["firmado"] else
                 ('<span class="tag">signature pending</span>' if en
                  else '<span class="tag">firma pendiente</span>'))
        tarjetas.append(
            f'<div class="card"><h2>{_htmlmod.escape(f["lib"])} {_htmlmod.escape(f["version"])}</h2>'
            f'<p>{_htmlmod.escape(f["desc"])}</p>'
            f'<p style="font-family:monospace;font-size:.75rem;color:#64748b;word-break:break-all">'
            f'{_htmlmod.escape(f["sha"])}</p>'
            f'<div class="tags"><span class="tag">{kb}</span></div>'
            f'<a href="/librerias/entrega/{_n}">'
            f'{"Download" if en else "Descargar"} .tar.gz</a> &nbsp; {firma}</div>')

    pendiente = ''
    if sin_firma:
        pendiente = (
            f'<p class="sub"><strong>{len(sin_firma)} of {len(filas)}</strong> are not signed yet. '
            f'The tarball and its SHA-256 are final; the hybrid signature is added in a second '
            f'step, with the key. Ask and it goes out signed the same day.</p>' if en else
            f'<p class="sub"><strong>{len(sin_firma)} de {len(filas)}</strong> todavía no están '
            f'firmadas. El tarball y su SHA-256 son definitivos; la firma híbrida se añade en un '
            f'segundo paso, con la clave. Pídala y sale firmada el mismo día.</p>')

    if en:
        intro = (
            '<h1>The source code of the libraries</h1>'
            '<p class="sub">Nine Apache-2.0 libraries, complete source, direct download. '
            'No sign-up, no NDA, no cost, no expiry.</p>'
            '<div class="prose"><h2>Why it is not on GitHub</h2>'
            '<p>Since August 2026 this code is not hosted on GitHub or published to a package '
            'registry. It is not abandonment: through 2026 the registries and code platforms took '
            'chained supply-chain attacks, and hosting cryptography and evidence-custody tooling '
            'there stopped being a neutral decision. The source did not disappear &mdash; it is '
            'right here, and the delivery is signed.</p>'
            '<h2>How to verify what you download</h2>'
            '<p><strong>Verify the manifest first, then the files against it.</strong> That order '
            'is the whole point: a signature over a tarball proves those bytes came from this key, '
            'but <em>not</em> that they are the artifact you asked for. <code>SHA256SUMS</code> is '
            'what ties each name to its contents, so it is the file that has to be signed.</p>'
            '<pre><code>chmod +x verificar-firma\n'
            './verificar-firma verificar "$(cat CLAVE-PUBLICA.txt)" \\\n'
            '    SHA256SUMS SHA256SUMS.firma      # 1. the manifest is authentic\n'
            'sha256sum -c SHA256SUMS              # 2. every file matches it</code></pre>'
            '<p>Step 1 prints <code>FIRMA VALIDA</code> and exits 0; step 2 prints <code>OK</code> '
            'for every line. The signature is hybrid &mdash; Ed25519 <em>and</em> ML-DSA-87 &mdash; '
            'and validates only if both do, so whoever stores these files today and owns a quantum '
            'computer tomorrow still cannot forge a past delivery. The verifier is a static Linux '
            'x86-64 binary: no dependencies, no network.</p>'
            '<p>Each tarball also carries its own <code>.firma</code>, handy for checking a single '
            'file &mdash; but on its own it does not tell you the file is the one you named. Use '
            'the manifest.</p>'
            '<p><strong>What this does not cover, said plainly:</strong> whoever controls this '
            'server can still serve you a <em>previous</em>, genuinely signed release instead of '
            'the current one. Detached signatures cannot stop a rollback on their own. If that '
            'matters to you, ask for the checksums by email and compare.</p>'
            '<p><strong>Check the key against a second channel.</strong> A public key that travels '
            'only inside the package it authenticates proves nothing. The same fingerprint is '
            'published at <a href="/en/quipu/code">/en/quipu/code</a>.</p></div>')
        pie = (f'<div class="cta"><a class="btn" href="/librerias/entrega/SHA256SUMS">SHA256SUMS</a>'
               f'<a href="/librerias/entrega/CLAVE-PUBLICA.txt">Public key</a>'
               f'<a href="/librerias/entrega/verificar-firma">Verifier (static, 1.3 MB)</a>'
               f'<a href="/#contacto">Ask for another format</a></div>')
    else:
        intro = (
            '<h1>El código de las librerías</h1>'
            '<p class="sub">Nueve librerías Apache-2.0, fuente completo, descarga directa. '
            'Sin registro, sin NDA, sin coste y sin caducidad.</p>'
            '<div class="prose"><h2>Por qué no está en GitHub</h2>'
            '<p>Desde agosto de 2026 este código no se aloja en GitHub ni se publica en un registro '
            'de paquetes. No es abandono: a lo largo de 2026 los registros y las plataformas de '
            'código sufrieron ataques encadenados de cadena de suministro, y alojar ahí herramientas '
            'de criptografía y de custodia de evidencia dejó de ser una decisión neutra. El código no '
            'desapareció &mdash; está aquí, y la entrega va firmada.</p>'
            '<h2>Cómo verificar lo que descarga</h2>'
            '<p><strong>Verifique primero el manifiesto, y después los archivos contra él.</strong> '
            'Ese orden es el punto entero: una firma sobre un tarball prueba que esos bytes salieron '
            'de esta clave, pero <em>no</em> que sean el artefacto que usted pidió. Lo que ata cada '
            'nombre a su contenido es <code>SHA256SUMS</code>, así que es ese el archivo que hay que '
            'firmar.</p>'
            '<pre><code>chmod +x verificar-firma\n'
            './verificar-firma verificar "$(cat CLAVE-PUBLICA.txt)" \\\n'
            '    SHA256SUMS SHA256SUMS.firma      # 1. el manifiesto es auténtico\n'
            'sha256sum -c SHA256SUMS              # 2. cada archivo coincide con él</code></pre>'
            '<p>El paso 1 imprime <code>FIRMA VALIDA</code> y sale con 0; el paso 2 dice que la suma '
            'coincide en cada línea. La firma es híbrida &mdash; Ed25519 <em>y</em> ML-DSA-87 &mdash; '
            'y valida solo si las dos validan, así que quien guarde hoy estos archivos y tenga un '
            'computador cuántico mañana sigue sin poder falsificar una entrega pasada. El verificador '
            'es un binario estático de Linux x86-64: sin dependencias y sin red.</p>'
            '<p>Cada tarball lleva además su propio <code>.firma</code>, cómodo para comprobar un '
            'archivo suelto &mdash; pero por sí solo no le dice que ese archivo sea el que usted '
            'nombró. Use el manifiesto.</p>'
            '<p><strong>Lo que esto NO cubre, dicho sin adornos:</strong> quien controle este '
            'servidor todavía puede servirle una entrega <em>anterior</em>, legítimamente firmada, '
            'en vez de la actual. Una firma separada no impide por sí sola una vuelta atrás. Si eso '
            'le importa, pida las sumas por correo y compare.</p>'
            '<p><strong>Contraste la clave por un segundo canal.</strong> Una clave pública que viaja '
            'solo dentro del paquete que autentica no prueba nada. La misma huella está publicada en '
            '<a href="/quipu/codigo">/quipu/codigo</a>.</p></div>')
        pie = (f'<div class="cta"><a class="btn" href="/librerias/entrega/SHA256SUMS">SHA256SUMS</a>'
               f'<a href="/librerias/entrega/CLAVE-PUBLICA.txt">Clave pública</a>'
               f'<a href="/librerias/entrega/verificar-firma">Verificador (estático, 1,3 MB)</a>'
               f'<a href="/#contacto">Pedir otro formato</a></div>')

    return (f'<main class="wrap">{intro}'
            f'<h2 style="margin:2.5rem 0 1rem;color:#fff">'
            f'{"The nine libraries" if en else "Las nueve librerías"}</h2>{pendiente}'
            f'<div class="grid">{"".join(tarjetas)}</div>{pie}</main>')


@app.get('/librerias/codigo')
def librerias_codigo():
    head = _seo_head(
        'El código de las nueve librerías — descarga directa y firmada | Xiliux',
        'Fuente completo de las nueve micro-librerías Apache-2.0 de Xiliux, en descarga '
        'directa y firmado con Ed25519 + ML-DSA-87. Sin registro, sin NDA y sin coste. '
        'Por qué dejó de publicarse en GitHub y en PyPI en agosto de 2026.',
        f'{DOMAIN}/librerias/codigo', alternates=_LIBS_ALT)
    return Response(content=_blog_page(head, _libs_cuerpo('es')), media_type='text/html')


@app.get('/en/libraries/code')
def librerias_codigo_en():
    head = _seo_head(
        'The source of the nine libraries — direct, signed download | Xiliux',
        'Complete source of the nine Apache-2.0 micro-libraries by Xiliux, direct download, '
        'signed with Ed25519 + ML-DSA-87. No sign-up, no NDA, no cost. Why it left GitHub '
        'and PyPI in August 2026.',
        f'{DOMAIN}/en/libraries/code', lang='en', alternates=_LIBS_ALT)
    return Response(content=_blog_page(head, _libs_cuerpo('en'), lang='en'), media_type='text/html')


@app.get('/librerias/entrega/{nombre}')
def librerias_entrega(nombre: str):
    """Sirve un archivo de la entrega. LISTA BLANCA: solo lo que aparece en
    SHA256SUMS, más el propio SHA256SUMS y los `.firma` de lo listado.

    El filtro no es una comprobación de `..`: es que el nombre pedido tenga que
    coincidir EXACTAMENTE con una entrada del manifiesto. Un nombre que no está
    no se sirve, y da igual cómo esté escrito."""
    # UNA sola fuente: el manifiesto. La versión anterior añadía por su cuenta
    # `<tarball>.firma`, y eso hacía servible una firma que NO figurara en
    # SHA256SUMS —lo único descargable sin cobertura de integridad—. Ahora las
    # firmas están listadas, así que la regla sintética sobraba y se fue.
    # `SHA256SUMS.firma` es la excepción inevitable: un manifiesto no puede
    # contener su propia suma.
    sumas = _libs_sumas()
    permitidos = set(sumas) | {'SHA256SUMS', 'SHA256SUMS.firma'}
    if nombre not in permitidos:
        return Response(content='no encontrado', media_type='text/plain', status_code=404)
    ruta = os.path.join(ENTREGA_LIBS_DIR, nombre)
    # Contención por ruta REAL: un enlace simbólico dentro del directorio de
    # entrega que apunte fuera y esté listado en el manifiesto se serviría. Es
    # post-compromiso, y por eso mismo cuesta una línea cerrarlo.
    base = os.path.realpath(ENTREGA_LIBS_DIR)
    if not os.path.realpath(ruta).startswith(base + os.sep):
        return Response(content='no encontrado', media_type='text/plain', status_code=404)
    if not os.path.exists(ruta):
        return Response(content='no encontrado', media_type='text/plain', status_code=404)
    tipo = ('application/gzip' if nombre.endswith('.tar.gz')
            else 'application/octet-stream' if nombre in ('verificar-firma',) or nombre.endswith('.firma')
            else 'text/plain; charset=utf-8')
    return FileResponse(ruta, media_type=tipo, filename=nombre)


# --- INICIO EN INGLÉS (HTML de servidor, rastreable) -------------------------
#
# POR QUÉ EXISTE. Hasta el 2026-08-12 la sección inglesa era un CALLEJÓN SIN
# SALIDA, medido en vivo con curl ese día: 7 artículos y `/en/quipu/code`
# servían inglés, pero los cuatro enlaces de su propia barra —Home, Contact,
# Quipu, y el pie— caían en páginas en español, y `/en` daba **404**. El lector
# anglófono que llega por una propuesta de Upwork o por una búsqueda en inglés
# lee el artículo y, al primer clic, se topa con un idioma que no habla. Todo el
# trabajo del Tier 3 moría ahí.
#
# NO ES UNA TRADUCCIÓN DE `/`, y es deliberado. La home española vende scripts y
# MVPs «desde $200 USD» a pymes latinoamericanas; puesta en inglés, esa cifra
# ancla la conversación en la tarifa y compite con miles de perfiles genéricos
# —que es justo el cribado que un marketplace de talento aplica primero—. Esta
# página vende lo que NO es genérico: criptografía post-cuántica, sistemas en
# Rust, y la evidencia MEDIDA, incluida la que deja mal al autor. Es la
# directiva 11 —la prueba de profundidad técnica— puesta donde el comprador
# anglófono la ve sin leer una línea de código.
_HOME_ALT = (f'<link rel="alternate" hreflang="es" href="{DOMAIN}/">'
             f'<link rel="alternate" hreflang="en" href="{DOMAIN}/en">'
             f'<link rel="alternate" hreflang="x-default" href="{DOMAIN}/">')

# Las tres piezas de evidencia. Van como DATO y no incrustadas en el HTML para
# que el JSON-LD y el cuerpo salgan de la MISMA fuente: si mañana cambia un
# titular, no puede quedar uno viejo en el schema y otro nuevo en la página.
_HOME_EN_PRUEBAS = (
    ("Testing", "/en/blog/banco-solo-de-negativos-no-discrimina",
     "My detector was blind across 1,029 of 6,309 lines &mdash; and its three tests stayed green",
     "A bench made only of negatives passes with the right rule and with a blind one: a clean "
     "file returns nothing either way. How to build the pair that tells them apart."),
    ("Verification", "/en/blog/un-negativo-solo-vale-si-el-camino-llego-a-ejecutarse",
     "I said no data was leaving. On the first good run, two records left",
     "A zero is indistinguishable from a path that never ran. What a positive control is, "
     "and why you look for it after the first success, not after the failures."),
    ("Cryptography", "/en/quipu/code",
     "Quipu &mdash; hybrid X25519 + ML-KEM-1024 and Ed25519 + ML-DSA-87",
     "Post-quantum encryption in pure Rust, CNSA 2.0 profile, running in production. "
     "AGPL-3.0: the complete source is delivered signed, by email, to anyone who asks."),
    ("Security research", "/en/blog/ocho-vulnerabilidades-authz-divulgadas-2026-11",
     "Eight access-control flaws, disclosed in a day &mdash; four with a GHSA advisory, one critical",
     "Whitebox reasoning about the code and execution-confirmed, not scanning. Eight broken "
     "invariants in OSS, reported through official channels; throwing away the false positives "
     "is what separates signal from noise."),
)

# Preguntas frecuentes en inglés. Mismo patrón answer-first + FAQPage que el
# resto del sitio (Tier 1). La tercera responde ANTES de que la formulen la
# objeción que se lleva el visitante al ver los repositorios vacíos de GitHub:
# no se oculta, se explica.
_HOME_EN_FAQ = (
    ("Do you take clients outside Colombia?",
     "Yes. The work is remote and the correspondence can be in English or Spanish. Scope, "
     "timeline and a fixed price are agreed before anything starts, and you talk to the "
     "person who writes the code &mdash; there is no account manager in between."),
    ("Do I get the source code?",
     "Yes. Client work is delivered with its source. Quipu is AGPL-3.0 and its complete "
     "source is delivered on request, signed with Ed25519 + ML-DSA-87, with no NDA and no cost."),
    ("Why is the code no longer on GitHub, crates.io, PyPI or npm?",
     "It was withdrawn in August 2026, on purpose. The work is security software &mdash; "
     "post-quantum cryptography and clinical records under Colombian data-protection law "
     "&mdash; and the 2026 registry supply-chain attacks made a public package a liability "
     "rather than a shop window. The source did not disappear: it is delivered signed, by "
     "email, to whoever asks for it."),
)


def _home_en_jsonld():
    """ProfessionalService + FAQPage, derivados de las MISMAS tuplas que el
    cuerpo. `&mdash;` es una entidad HTML: en JSON-LD hay que servir el carácter,
    o el asistente que lo lea cita el literal."""
    def texto(s):
        return s.replace("&mdash;", "—")
    servicio = {
        "@context": "https://schema.org",
        "@type": "ProfessionalService",
        "name": "Xiliux",
        "url": f"{DOMAIN}/en",
        "logo": SOCIAL_IMAGE,
        "image": SOCIAL_IMAGE,
        "inLanguage": "en",
        "description": "Post-quantum cryptography and Rust systems for work where being "
                       "wrong is expensive, by Juan Carlos Isaza.",
        "founder": {"@type": "Person", "name": "Juan Carlos Isaza"},
        "address": {"@type": "PostalAddress", "addressLocality": "Medellín",
                    "addressCountry": "CO"},
        "areaServed": {"@type": "Place", "name": "Worldwide"},
        "availableLanguage": ["en", "es"],
        "knowsAbout": ["Post-quantum cryptography", "ML-KEM", "ML-DSA", "CNSA 2.0", "Rust",
                       "axum", "SQLx", "SQLite", "Software verification", "LLM integration"],
        "contactPoint": {"@type": "ContactPoint", "contactType": "Sales",
                         "email": CONTACT_EMAIL, "availableLanguage": ["en", "es"]},
    }
    faq = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": texto(q),
             "acceptedAnswer": {"@type": "Answer", "text": texto(a)}}
            for q, a in _HOME_EN_FAQ
        ],
    }
    return (f'<script type="application/ld+json">{json.dumps(servicio, ensure_ascii=False)}</script>'
            f'<script type="application/ld+json">{json.dumps(faq, ensure_ascii=False)}</script>')


def _home_en_body(ok=None):
    banner = ""
    if ok == "mensaje":
        banner = '<div class="ok-banner">✓ Message sent. I&rsquo;ll get back to you soon.</div>'
    elif ok == "error":
        banner = '<div class="ok-banner err">Could not send. Please reload and try again.</div>'
    pruebas = "".join(
        f'<a class="card" href="{href}"><time>{etiqueta}</time>'
        f'<h2>{titulo}</h2><p>{resumen}</p></a>'
        for etiqueta, href, titulo, resumen in _HOME_EN_PRUEBAS)
    faq = "".join(
        f'<h3>{q}</h3><p>{a}</p>' for q, a in _HOME_EN_FAQ)
    correo = _htmlmod.escape(CONTACT_EMAIL)
    return f"""<main class="wrap home">
<h1>Software that has to hold up, in Rust</h1>
<p class="sub">I&rsquo;m Juan Carlos Isaza. I build post-quantum cryptography and Rust systems
for work where being wrong is expensive &mdash; and I publish the measurements, including the
ones that make me look bad.</p>

<h2>Evidence, not adjectives</h2>
<p>Anyone can write &ldquo;rigorous&rdquo; on a profile. These are three things I measured on
my own code and wrote up in full, defect included:</p>
<div class="grid">{pruebas}</div>

<h2>What I build</h2>
<div class="grid">
  <div class="card"><h2>Post-quantum cryptography</h2>
    <p>Hybrid key exchange and signatures (X25519 + ML-KEM-1024, Ed25519 + ML-DSA-87) under the
    CNSA 2.0 profile, in pure Rust. Migration paths that stay compatible with what you already
    have deployed.</p>
    <div class="tags"><span class="tag">Rust</span><span class="tag">ML-KEM</span><span class="tag">ML-DSA</span></div></div>
  <div class="card"><h2>Systems that ship as one binary</h2>
    <p>axum + SQLx + SQLite, server-rendered UI, no Node build step. One executable and one
    database file per install: it runs offline, on the client&rsquo;s own machine, and it does
    not rot between visits.</p>
    <div class="tags"><span class="tag">axum</span><span class="tag">SQLx</span><span class="tag">htmx</span></div></div>
  <div class="card"><h2>Regulated environments</h2>
    <p>Software whose failure has a legal cost, not just a technical one: statutory reporting
    deadlines, audit trails that survive scrutiny, and clinical records handled under Colombia&rsquo;s
    Law 1581 as special-category data.</p>
    <div class="tags"><span class="tag">Audit trail</span><span class="tag">Compliance</span></div></div>
  <div class="card"><h2>AI integration</h2>
    <p>LLMs (Claude, GPT, Gemini) wired into a product that already exists, with the boring part
    done: cost ceilings, retries, failure paths, and an evaluation that does not flatter itself.</p>
    <div class="tags"><span class="tag">LLM</span><span class="tag">Evaluation</span></div></div>
  <div class="card"><h2>Educational software</h2>
    <p>chimini: a free, open periodic-table lab that runs in the browser —fuse elements and
    explore chemistry and nuclear energy with real scientific data. Offline, in Rust.
    <a href="https://chimini.xiliux.com">Play it &rarr;</a></p>
    <div class="tags"><span class="tag">Rust</span><span class="tag">Education</span><span class="tag">Open source</span></div></div>
</div>

<h2>How I work</h2>
<p>Scope, timeline and a <strong>fixed price agreed before anything starts</strong>. You talk to
the person who writes the code &mdash; there is no account manager in between. Delivery includes
the source, documentation and initial support.</p>

<h2>Questions I get asked</h2>
<div class="prose">{faq}</div>

<section id="contact">
<h2>Let&rsquo;s talk</h2>
{banner}
<p>Tell me about your project. Scope, timeline and a <strong>fixed price agreed before anything
starts</strong>, and you talk to the person who writes the code &mdash; no middlemen.</p>
<form class="lead-form" method="post" action="/en/contacto" accept-charset="utf-8">
  <input type="text" name="nombre" placeholder="Name" required autocomplete="name">
  <input type="email" name="email" placeholder="Email" required autocomplete="email">
  <textarea name="mensaje" placeholder="Message" required rows="4"></textarea>
  <input type="text" name="web" class="hp" tabindex="-1" autocomplete="off" aria-hidden="true">
  <input type="hidden" name="ts" value="{token_tiempo()}">
  <button type="submit">Send</button>
</form>
</section>

<div class="cta">
  <a href="/en/blog">Read the technical articles &rarr;</a>
</div>
</main>"""


# ==================== PORTADA ESPAÑOLA — SSR (rastreable) ====================
# La portada `/` era @ui.page (NiceGUI): Google veía ~27 palabras porque el
# cuerpo llega por WebSocket. Esta versión la sirve como HTML de servidor, igual
# que `/en`, /servicios, /informes. Los dos formularios (contacto y lead magnet)
# pasan a <form> HTML → @app.post con patrón PRG, reusando valid_email/save_lead
# y un cooldown por IP (el rate_ok de sesión no existe fuera de NiceGUI).

# Cooldown por IP para los POST de formulario (anti-relay; la causa es la misma
# que el rate_ok de sesión: no convertir el envío de correo en un relay abierto).
_ip_cooldown = {}
def rate_ok_ip(ip, key, seconds=30):
    now = time.time()
    k = (ip, key)
    if now - _ip_cooldown.get(k, 0) < seconds:
        return False
    _ip_cooldown[k] = now
    # Poda: sin esto el dict crece sin tope (cada IP nueva —p. ej. una oleada de
    # spam desde muchas IPs— deja una entrada que nunca se borra). Se limpian las
    # más viejas que 1 h cuando el dict se hace grande.
    if len(_ip_cooldown) > 2048:
        viejo = now - 3600
        for kk in [kk for kk, t in _ip_cooldown.items() if t < viejo]:
            del _ip_cooldown[kk]
    return True


# --- Trampa de tiempo firmada para los formularios SSR ---
# Un bot rellena y envía en milisegundos; un humano tarda segundos. La marca de
# tiempo va en un campo oculto FIRMADO con APP_SECRET (HMAC-SHA256), así no se
# puede forjar ni reusar: se rechaza lo instantáneo (bot) y lo rancio (página
# abierta hace horas). Es la capa que el honeypot no cubre: un bot que ignora el
# campo 'web' pero envía al instante cae aquí.
_TS_MIN_SEG = 2
_TS_MAX_SEG = 2 * 3600

def token_tiempo():
    ts = str(int(time.time()))
    firma = hmac.new(APP_SECRET.encode(), ts.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{ts}.{firma}"

def token_tiempo_estado(token):
    """'ok' | 'bot' (instantáneo o firma inválida) | 'rancio' (página muy vieja)."""
    try:
        ts_str, firma = token.split(".", 1)
        esperada = hmac.new(APP_SECRET.encode(), ts_str.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(firma, esperada):
            return "bot"
        edad = time.time() - int(ts_str)
        if edad < _TS_MIN_SEG:
            return "bot"
        if edad > _TS_MAX_SEG:
            return "rancio"
        return "ok"
    except Exception:
        return "bot"

def _enviar_correo(destino, asunto, cuerpo):
    """Envío SMTP síncrono (se llama dentro de asyncio.to_thread). Devuelve
    True/False; nunca lanza. Misma cuenta Zoho que los formularios NiceGUI."""
    # CR/LF/NUL en el destino o el asunto = intento de inyección de cabeceras
    # (un Bcc a un tercero, un From falso). Se rechaza ANTES de construir el
    # mensaje. El CUERPO no se revisa: ahí los saltos de línea son legítimos.
    if any(c in destino or c in asunto for c in ('\r', '\n', '\x00')):
        print("RECHAZADO: inyeccion de cabecera en correo SSR")
        return False
    try:
        s = smtplib.SMTP_SSL('smtp.zoho.com', 465)
        s.login('contacto@xiliux.com', EMAIL_PWD)
        m = MIMEMultipart()
        m['From'] = 'contacto@xiliux.com'
        m['To'] = destino
        m['Subject'] = asunto
        m.attach(MIMEText(cuerpo, 'plain'))
        s.send_message(m)
        s.quit()
        return True
    except Exception as e:
        print(f"ERROR SMTP (SSR): {type(e).__name__}: {str(e)}")
        return False

# Las tres pruebas (mismo patrón que _HOME_EN_PRUEBAS: dato único → cuerpo).
_HOME_PRUEBAS = (
    ("Pruebas", "/blog/banco-solo-de-negativos-no-discrimina",
     "Mi detector estaba ciego en 1.029 de 6.309 líneas &mdash; y sus tres pruebas seguían en verde",
     "Un banco hecho solo de negativos pasa con la regla buena y con una ciega: un archivo limpio "
     "no devuelve nada en los dos casos. Cómo construir la pareja que las distingue."),
    ("Verificación", "/blog/un-negativo-solo-vale-si-el-camino-llego-a-ejecutarse",
     "Dije que no salían datos. Al primer envío bueno, salieron dos",
     "Un cero es indistinguible de un camino que nunca se ejecutó. Qué es un positivo de control, "
     "y por qué se busca DESPUÉS del primer éxito, no tras los fallos."),
    ("Criptografía", "/quipu/codigo",
     "Quipu &mdash; híbrido X25519 + ML-KEM-1024 y Ed25519 + ML-DSA-87",
     "Cifrado post-cuántico en Rust puro, perfil CNSA 2.0, en producción. AGPL-3.0: el código "
     "completo se entrega firmado, por correo, a quien lo pida."),
    ("Investigación de seguridad", "/blog/ocho-vulnerabilidades-authz-divulgadas-2026-11",
     "Ocho fallos de control de acceso, divulgados en un día &mdash; cuatro con aviso GHSA, uno crítico",
     "Razonamiento whitebox sobre el código y confirmación por ejecución, no escaneo. Ocho "
     "invariantes rotas en OSS, reportadas por canal oficial; la refutación de los falsos "
     "positivos es lo que separa la señal del ruido."),
)

def _home_jsonld():
    """ProfessionalService + FAQPage, de las MISMAS tuplas que el cuerpo."""
    servicio = {
        "@context": "https://schema.org", "@type": "ProfessionalService",
        "name": "Xiliux", "url": f"{DOMAIN}/", "logo": SOCIAL_IMAGE, "image": SOCIAL_IMAGE,
        "inLanguage": "es",
        "description": "Desarrollo Full Stack en Python y Rust, con criptografía post-cuántica e "
                       "IA, por Juan Carlos Isaza. Del prototipo en Python al sistema a la medida "
                       "en Rust: un solo binario, sin Node, corre offline.",
        "founder": {"@type": "Person", "name": "Juan Carlos Isaza"},
        "address": {"@type": "PostalAddress", "addressLocality": "Medellín", "addressCountry": "CO"},
        "areaServed": {"@type": "Place", "name": "Worldwide"},
        "availableLanguage": ["es", "en"],
        "knowsAbout": ["Python", "Rust", "axum", "SQLx", "NiceGUI", "Criptografía post-cuántica",
                       "ML-KEM", "ML-DSA", "Integración de IA", "LLM", "Automatización"],
        "contactPoint": {"@type": "ContactPoint", "contactType": "Sales",
                         "email": CONTACT_EMAIL, "availableLanguage": ["es", "en"]},
    }
    faq = {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": q,
                        "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQS],
    }
    return (f'<script type="application/ld+json">{json.dumps(servicio, ensure_ascii=False)}</script>'
            f'<script type="application/ld+json">{json.dumps(faq, ensure_ascii=False)}</script>')

def _home_body(ok=None):
    correo = _htmlmod.escape(CONTACT_EMAIL)
    banner = ""
    if ok == "mensaje":
        banner = ('<div class="ok-banner">✓ Mensaje enviado. Te respondo pronto.</div>')
    elif ok == "guia":
        banner = ('<div class="ok-banner">✓ Revisa tu correo: te envié el enlace de la guía.</div>')
    elif ok == "error":
        banner = ('<div class="ok-banner err">No se pudo enviar. Escríbeme directo a '
                  f'<a href="mailto:{correo}">{correo}</a>.</div>')

    pruebas = "".join(
        f'<a class="card" href="{href}"><time>{etiqueta}</time><h2>{titulo}</h2><p>{resumen}</p></a>'
        for etiqueta, href, titulo, resumen in _HOME_PRUEBAS)

    servicios = ""
    for s in SERVICES:
        cta_url = s.get("cotizar_url") or "/#contacto"
        cta_txt = "Cotizar →" if s.get("cotizar_url") else "Escríbeme →"
        pop = '<span class="tag">Popular</span>' if s.get("popular") else ''
        servicios += (
            f'<div class="card"><h2>{_htmlmod.escape(s["title"])}</h2>'
            f'<p>{_htmlmod.escape(s["desc"])}</p>'
            f'<div class="tags"><span class="tag">{_htmlmod.escape(s["price_label"])}</span>{pop}</div>'
            f'<a href="{cta_url}">{cta_txt}</a></div>')

    productos = (
        '<div class="card"><h2>SIGER — informes de obligatorio cumplimiento</h2>'
        '<p>Sistema de monitoreo y seguimiento de informes de obligatorio cumplimiento para '
        'entidades públicas y empresas: trazabilidad completa, firma post-cuántica de entregas e '
        'instalación en su propio servidor.</p><a href="/informes">Ver SIGER →</a></div>'
        '<div class="card"><h2>Quipu — criptografía post-cuántica</h2>'
        '<p>Cifrado y firma híbridos (X25519 + ML-KEM-1024, Ed25519 + ML-DSA-87, con opción de '
        'X-Wing interoperable y firma triple) en Rust puro, perfil CNSA 2.0, corriendo en '
        'producción — y verificado byte a byte contra tres implementaciones independientes. '
        'Servicio gestionado de endurecimiento de contraseñas (OPRF) por suscripción.</p>'
        '<a href="/quipu">Ver Quipu →</a> <a href="/quipu/cbom" style="margin-left:10px">Radiografía CBOM →</a></div>'
        '<div class="card"><h2>tunjo — sellado de evidencia digital</h2>'
        '<p>Sella evidencia digital y levanta el acta de cadena de custodia con firma triple '
        'post-cuántica (Ed25519 + ML-DSA-87 + SLH-DSA, sobre Quipu), siguiendo el método que la '
        'Corte Suprema fijó en SP248-2025. El verificador es <strong>público</strong>: cualquiera '
        'comprueba la integridad y la firma de un acta en su propio navegador (WebAssembly), gratis '
        'y sin instalar nada. Hecho en Rust.</p>'
        '<a href="/verificar/">Verificar un acta →</a> '
        '<a href="https://tunjo.xiliux.com" rel="noopener" style="margin-left:10px">Servicio de sellado →</a></div>'
        '<div class="card"><h2>Sistemas a la medida en Rust</h2>'
        '<p>Inventario con kardex y facturación electrónica; historia clínica con RIPS/FEV-RIPS, '
        'interoperable con la historia clínica nacional (HL7 FHIR, Resolución 1888 de 2025) y con '
        'el ciclo de retención por habeas data cerrado; y más: backend en Rust (axum + SQLx sobre '
        'SQLite), interfaz maud + htmx, un solo binario que corre offline. Se cotiza por alcance.</p>'
        '<a href="/cotizador">Estimar mi proyecto →</a></div>'
        '<div class="card"><h2>chimini — laboratorio de química, libre y abierto</h2>'
        '<p>Un juego educativo que corre en el navegador sin instalar: fusiona elementos de la '
        'tabla periódica y explora la química y la energía nuclear con datos científicos reales. '
        'Software libre, funciona offline, hecho en Rust. Una muestra de lo que construimos.</p>'
        '<a href="https://chimini.xiliux.com">Jugar →</a> '
        '<a href="/blog/chimini-tabla-periodica-jugable-fusion-elementos" style="margin-left:10px">Leer más →</a></div>'
        '<div class="card"><h2>agua — balance hídrico y ENSO</h2>'
        '<p>Simulador de balance hídrico regional con datos reales del IDEAM (2003–2026, 33 '
        'departamentos) y un optimizador de malla hídrica. Corre en el navegador, hecho en Rust. '
        'Otra muestra de lo que construimos.</p>'
        '<a href="https://agua.xiliux.com">Ver la demo →</a></div>'
        '<div class="card"><h2>Validador FEV-RIPS — pre-vuelo</h2>'
        '<p>Revisa un FEV-RIPS contra los campos de la Resolución 948 de 2026 antes de enviarlo al '
        'Mecanismo Único de Validación de MinSalud: campo faltante, campo no permitido, estructura. '
        'Convierte la plantilla oficial de Excel a JSON. Hecho en Rust.</p>'
        '<a href="https://rips.xiliux.com">Probar →</a></div>')

    proceso = "".join(
        f'<div class="card"><h2>{_htmlmod.escape(titulo)}</h2><p>{_htmlmod.escape(desc)}</p></div>'
        for _icon, titulo, desc in PROCESS)

    faq = "".join(f'<h3>{_htmlmod.escape(q)}</h3><p>{_htmlmod.escape(a)}</p>' for q, a in FAQS)

    return f"""<main class="wrap home">
{banner}
<h1>Software que tiene que resistir, en Python y Rust</h1>
<p class="sub">Soy Juan Carlos Isaza. Del prototipo en Python al sistema a la medida en Rust
&mdash;un solo binario, sin Node, corre offline&mdash;, con criptografía post-cuántica e IA.
Y publico las mediciones, incluidas las que me dejan mal.</p>

<h2>Evidencia, no adjetivos</h2>
<p>Cualquiera escribe &ldquo;riguroso&rdquo; en un perfil. Estas son tres cosas que medí sobre mi
propio código y escribí enteras, con el defecto incluido:</p>
<div class="grid">{pruebas}</div>

<h2>Servicios</h2>
<div class="grid">{servicios}</div>

<h2>Productos en producción</h2>
<div class="grid">{productos}</div>

<h2>Cómo trabajo</h2>
<div class="grid">{proceso}</div>

<section id="recursos">
<h2>Recurso gratuito: Guía de Automatización con IA</h2>
<p>Descarga gratis mi guía con 5 casos de uso reales de automatización con IA aplicados a
negocios. Te llega por correo.</p>
<form class="lead-form" method="post" action="/recursos" accept-charset="utf-8">
  <input type="text" name="nombre" placeholder="Nombre" required autocomplete="name">
  <input type="email" name="email" placeholder="Email" required autocomplete="email">
  <input type="text" name="web" class="hp" tabindex="-1" autocomplete="off" aria-hidden="true">
  <input type="hidden" name="ts" value="{token_tiempo()}">
  <button type="submit">Quiero la guía</button>
</form>
</section>

<h2>Preguntas frecuentes</h2>
<div class="prose">{faq}</div>

<section id="contacto">
<h2>Hablemos</h2>
<p>Cuéntame tu idea. Alcance, tiempos y precio cerrado antes de empezar, y hablas con la persona
que escribe el código &mdash; sin intermediarios.</p>
<form class="lead-form" method="post" action="/contacto" accept-charset="utf-8">
  <input type="text" name="nombre" placeholder="Nombre" required autocomplete="name">
  <input type="email" name="email" placeholder="Email" required autocomplete="email">
  <textarea name="mensaje" placeholder="Mensaje" required rows="4"></textarea>
  <input type="text" name="web" class="hp" tabindex="-1" autocomplete="off" aria-hidden="true">
  <input type="hidden" name="ts" value="{token_tiempo()}">
  <button type="submit">Enviar</button>
</form>
</section>

<div class="cta">
  <a href="/blog">Lee los artículos técnicos &rarr;</a>
</div>
</main>"""

# Topes de longitud por campo (bytes de texto). Un correo de contacto legítimo
# cabe de sobra; lo que excede es un bot o un intento de abuso.
_LIMITES = {"nombre": 100, "email": 254, "mensaje": 5000, "web": 100}

async def _procesar_formulario(request, honeypot_key, requeridos, cooldown_key):
    """Valida un POST de formulario SSR. Devuelve (datos, error_str|None).
    error_str: 'spam' (honeypot, descartar en silencio), 'faltan', 'email',
    'rate'. La validación es la misma que la de los formularios NiceGUI."""
    form = await request.form()
    datos = {k: (form.get(k) or "").strip() for k in requeridos + ["web"]}
    # 1) Honeypot: campo oculto que solo un bot rellena.
    if datos.get("web"):
        return datos, "spam"
    # 2) Trampa de tiempo firmada: instantáneo o forjado = bot; muy viejo = rancio.
    estado_ts = token_tiempo_estado(form.get("ts") or "")
    if estado_ts == "bot":
        return datos, "spam"
    if estado_ts == "rancio":
        return datos, "rancio"
    # 3) Topes de longitud: un POST gigante es abuso, no una consulta.
    if any(len(v) > _LIMITES.get(k, 5000) for k, v in datos.items()):
        return datos, "spam"
    # 4) Requeridos y formato.
    if not all(datos.get(k) for k in requeridos):
        return datos, "faltan"
    if "email" in requeridos and not valid_email(datos["email"]):
        return datos, "email"
    # 4.5) Filtro de CONTENIDO: tokens aleatorios + correo desechable. Caza el
    #      spam de formulario bien formado que pasó honeypot/tiempo/cooldown
    #      (patrón medido 2026-11-08). Se descarta en silencio como el honeypot.
    if antispam.es_spam_contenido(datos.get("nombre", ""), datos.get("email", ""), datos.get("mensaje", "")):
        return datos, "spam"
    # 5) Cooldown por IP (anti-relay).
    ip = request.client.host if request.client else "?"
    if not rate_ok_ip(ip, cooldown_key, 30):
        return datos, "rate"
    return datos, None

@app.post('/contacto')
async def contacto_post(request: Request):
    datos, err = await _procesar_formulario(request, "web", ["nombre", "email", "mensaje"], "contact_ts")
    if err == "spam":
        return RedirectResponse('/?ok=mensaje#contacto', status_code=303)  # bot: fingir éxito
    if err:
        return RedirectResponse('/?ok=error#contacto', status_code=303)
    ok = await asyncio.to_thread(
        _enviar_correo, 'contacto@xiliux.com', f"Web: {datos['nombre']}",
        f"De: {datos['nombre']} ({datos['email']})\n\n{datos['mensaje']}")
    return RedirectResponse('/?ok=mensaje#contacto' if ok else '/?ok=error#contacto', status_code=303)

@app.post('/en/contacto')
async def contacto_en_post(request: Request):
    datos, err = await _procesar_formulario(request, "web", ["nombre", "email", "mensaje"], "contact_ts")
    if err == "spam":
        return RedirectResponse('/en?ok=mensaje#contact', status_code=303)  # bot: fingir éxito
    if err:
        return RedirectResponse('/en?ok=error#contact', status_code=303)
    ok = await asyncio.to_thread(
        _enviar_correo, 'contacto@xiliux.com', f"Web EN: {datos['nombre']}",
        f"From: {datos['nombre']} ({datos['email']})\n\n{datos['mensaje']}")
    return RedirectResponse('/en?ok=mensaje#contact' if ok else '/en?ok=error#contact', status_code=303)

@app.post('/recursos')
async def recursos_post(request: Request):
    datos, err = await _procesar_formulario(request, "web", ["nombre", "email"], "lead_ts")
    if err == "spam":
        return RedirectResponse('/?ok=guia#recursos', status_code=303)
    if err:
        return RedirectResponse('/?ok=error#recursos', status_code=303)
    save_lead(datos['nombre'], datos['email'])
    ok = await asyncio.to_thread(
        _enviar_correo, datos['email'], "🎁 Tu Guía - Xiliux",
        f"Hola {datos['nombre']},\n\nDescarga: {DOMAIN}/guia_automatizacion.pdf\n\nSaludos,\nXiliux")
    return RedirectResponse('/?ok=guia#recursos' if ok else '/?ok=error#recursos', status_code=303)

# Portada española: HTML de servidor (rastreable), reemplaza la antigua @ui.page.
@app.get('/')
def home_es(request: Request):
    ok = request.query_params.get('ok')
    head = _seo_head(
        'Xiliux — Python y Rust · Cripto post-cuántica, MVPs e IA',
        'Desarrollo Full Stack en Python y Rust, con IA. Del prototipo en Python al sistema a la '
        'medida en Rust —un solo binario, sin Node, corre offline— que resiste. Scripts desde '
        '$200, MVPs desde $500, IA desde $800; sistemas a la medida a cotización.',
        f'{DOMAIN}/', alternates=_HOME_ALT, jsonld=_home_jsonld())
    return Response(content=_blog_page(head, _home_body(ok), lang='es'), media_type='text/html')


@app.get('/en')
def home_en(request: Request):
    ok = request.query_params.get('ok')
    head = _seo_head(
        'Xiliux — post-quantum cryptography and Rust systems | Juan Carlos Isaza',
        'Post-quantum cryptography (ML-KEM, ML-DSA, CNSA 2.0) and Rust systems that ship as a '
        'single offline binary, for work where being wrong is expensive. Written up with the '
        'measurements, defects included.',
        f'{DOMAIN}/en', lang='en', alternates=_HOME_ALT, jsonld=_home_en_jsonld())
    return Response(content=_blog_page(head, _home_en_body(ok), lang='en'), media_type='text/html')


# `/en/` con barra: FastAPI no la resuelve sola cuando la ruta se declara sin
# ella, y teclear la barra es lo normal. Redirección permanente para no partir
# la señal de indexación en dos URLs (directiva 20: el 404 silencioso era lo que
# había).
@app.get('/en/')
def home_en_barra():
    return RedirectResponse(f'{DOMAIN}/en', status_code=301)


# --- INFORMES: PÁGINA DE PRODUCTO (HTML de servidor, rastreable) ---
#
# Nace del paso por la Secretaría de Salud de Medellín, donde el sistema se
# llamaba "Subsistema de monitoreo y seguimiento informes de obligatorio
# cumplimiento". Esa es la terminología con la que las entidades lo buscan.
#
# El producto se llama SIGER, y por eso encabeza la página. Pero el TÍTULO y
# la descripción conservan la frase larga: nadie busca "SIGER" en un buscador,
# y cambiarla por la marca habría tirado el posicionamiento que ya está hecho.
# Marca arriba, descriptor detrás. La RUTA no se toca por lo mismo.

@app.get('/informes')
def informes_producto():
    body = """<main class="wrap">
<h1>SIGER</h1>
<p class="sub">Monitoreo y seguimiento de informes de obligatorio cumplimiento.
Para entidades y empresas que responden por reportes con plazo.</p>

<h2>El problema</h2>
<p>Una entidad tiene decenas de obligaciones de reporte con fundamento legal, cada una con
su plazo, su responsable y su destinatario. Hoy el seguimiento se lleva en hojas de cálculo
y en la memoria de quien está a cargo. Cuando esa persona cambia de puesto, el conocimiento
se va con ella — y el informe que no salió no se descubre hasta que lo pregunta un ente de
control.</p>
<p>Lo desarrollamos con calendario en mano en
<a href="/blog/como-no-perder-un-reporte-obligaciones-recurrentes">cómo no perder un reporte
de obligaciones recurrentes</a>: por qué los recordatorios fallan y qué hay que calcular en
su lugar.</p>

<h2>Qué hace</h2>
<div class="grid">
  <div class="card"><h2>Reglas, no recordatorios</h2>
    <p>Las obligaciones se definen una vez con su periodicidad y su regla de cálculo. El
    sistema genera los pendientes solo, con los festivos colombianos ya contemplados.</p></div>
  <div class="card"><h2>Trazabilidad completa</h2>
    <p>Quién entregó, cuándo, qué archivo y qué se modificó después. Auditoría de todos los
    cambios, no solo del resultado.</p></div>
  <div class="card"><h2>Portal para terceros</h2>
    <p>Los sujetos obligados a reportarle a usted entregan por su propio acceso, sin correos
    ni archivos sueltos.</p></div>
  <div class="card"><h2>El calendario se siembra desde SECOP II</h2>
    <p>Una foto de sus contratos en SECOP II genera las obligaciones y su periodicidad de una
    sola pasada, en vez de cargarlas a mano contrato por contrato: el sistema arranca con el
    calendario ya poblado.</p></div>
  <div class="card"><h2>Firma post-cuántica</h2>
    <p>Cada entrega puede firmarse con <a href="/quipu">Quipu</a>: se detecta si el
    documento fue alterado después de entregado, y la firma resiste a un computador
    cuántico.</p></div>
</div>

<h2>Véalo funcionando</h2>
<p>Hay una demostración pública, con datos ficticios, en
<a href="https://informes.xiliux.com/" rel="noopener">informes.xiliux.com</a>. Entre con
<code>operador@co.co</code> / <code>operador</code> para el uso diario, o con
<code>admin@co.co</code> / <code>admin</code> para ver la administración.</p>
<p>No es una maqueta: las obligaciones que verá las genera el mismo motor de reglas que
usa una instalación real, con sus fechas calculadas desde hoy y el calendario de festivos
colombianos. Encontrará entregas cumplidas, extemporáneas, incumplidas y vencidas sin
registrar, porque es lo que enseña de qué sirve el sistema. Los datos se regeneran cada
noche, así que puede tocar lo que quiera.</p>

<h2>Funciona donde su entidad pueda instalarlo</h2>
<p>El mismo sistema en tres modalidades, según lo que permita su política de datos:</p>
<div class="grid">
  <div class="card"><h2>En su servidor</h2>
    <p>Dentro de su red, sin salir a internet. Los datos no salen de su infraestructura —
    y eso es un argumento, no una limitación.</p></div>
  <div class="card"><h2>Aislado por completo</h2>
    <p>Instalación air-gapped, sin conexión ni siquiera para instalarlo. Se traslada en un
    medio extraíble.</p></div>
  <div class="card"><h2>Hospedado</h2>
    <p>Nosotros lo operamos. Sin servidores que administrar.</p></div>
</div>

<h2>Cómo se cobra</h2>
<p>En servidor propio, <strong>licencia perpetua</strong> más mantenimiento y actualizaciones
anual. Perpetua de verdad: si deja de renovar el mantenimiento, el sistema
<strong>sigue funcionando</strong> con la última versión recibida. La validación de licencia
es local y <strong>no caduca</strong> — un sistema aislado no puede depender de que alcance
un servidor nuestro para seguir operando.</p>
<p>El mantenimiento no es soporte: es <strong>adecuación normativa</strong>. Los plazos, los
festivos y los requisitos de reporte cambian, y el software se degrada solo si nadie lo
actualiza.</p>

<h2>Hablemos</h2>
<p>El precio depende de cuántas obligaciones administra y de la modalidad de instalación,
no de una lista fija. <a href="/#contacto">Escríbanos</a> y lo conversamos.</p>
</main>"""
    head = _seo_head(
        'SIGER — monitoreo y seguimiento de informes de obligatorio cumplimiento | Xiliux',
        'SIGER, sistema de monitoreo y seguimiento de informes de obligatorio cumplimiento para '
        'entidades públicas y empresas. Instalación en su servidor, air-gapped u hospedado. '
        'Trazabilidad completa y firma post-cuántica de entregas.',
        f'{DOMAIN}/informes')
    return Response(content=_blog_page(head, body), media_type='text/html')


@ui.page('/privacidad')
def privacy_page():
    ui.dark_mode().enable()
    ui.colors(primary='#6366f1', secondary='#06b6d4', accent='#8b5cf6', dark='#0f172a')
    ui.page_title('Política de privacidad | Xiliux')
    # Sin los datos del responsable, la política es un borrador: no se indexa.
    robots = "index, follow" if privacy_ready() else "noindex, nofollow"
    ui.add_head_html(f'''<html lang="es">
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="description" content="Cómo trata Xiliux los datos personales de los suscriptores del servicio Quipu OPRF: qué se recoge, para qué, con quién se comparte y qué no se recoge nunca." />
<link rel="canonical" href="{DOMAIN}/privacidad" />
<meta name="robots" content="{robots}" />
<link rel="icon" type="image/png" href="/logo.png">
<meta name="theme-color" content="#0f172a">
<style>.glass {{ background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(12px); }}</style>
''')
    blog_header()
    with ui.column().classes('w-full min-h-screen bg-slate-950 text-slate-200 items-center pt-24 pb-20 px-4'):
        with ui.column().classes('max-w-3xl w-full'):
            ui.html('<h1 class="text-4xl md:text-5xl font-bold text-white mb-2">Política de privacidad</h1>', sanitize=False)
            ui.html(f'<p class="text-slate-500 text-sm mb-8">Vigente desde el {PRIVACY_VIGENCIA}.</p>', sanitize=False)

            if not privacy_ready():
                with ui.card().classes('bg-amber-950/40 border border-amber-700 rounded-xl p-4 mb-8 w-full'):
                    ui.html('<p class="text-amber-300 text-sm"><strong>Borrador sin publicar.</strong> '
                            'Faltan los datos del responsable del tratamiento. Esta página no se '
                            'indexa ni aparece en el sitemap hasta que se completen en el <code>.env</code>.</p>',
                            sanitize=False)

            _priv_p('Esta política explica cómo Xiliux trata los datos personales de quienes '
                    'contratan el servicio <strong>Quipu OPRF Hardening</strong>. Es específica y corta '
                    'a propósito: el servicio recoge muy pocos datos, y conviene que se vea.')

            _priv_h2('1. Responsable')
            if privacy_ready():
                _priv_p(f'<strong>{PRIVACY_RAZON_SOCIAL}</strong> (identificación {PRIVACY_IDENT}), '
                        f'con dirección en {PRIVACY_DIRECCION}. '
                        f'Contacto: <a href="/#contacto" class="text-cyan-400 hover:underline">el formulario de contacto</a>.')
            else:
                _priv_p('<em class="text-amber-400">[Pendiente: razón social, identificación y dirección '
                        'registrada del responsable.]</em> '
                        f'Contacto: <a href="/#contacto" class="text-cyan-400 hover:underline">el formulario de contacto</a>.')

            _priv_h2('2. Qué datos tratamos, y de dónde salen')
            _priv_p('Xiliux <strong>no te pide datos directamente para contratar</strong>. Todo lo que '
                    'tratamos nos lo entrega PayPal cuando confirma tu suscripción:')
            ui.html('''<ul class="text-slate-300 leading-relaxed mb-4 list-disc pl-6 space-y-1">
<li><strong>Tu correo electrónico</strong> — para enviarte la API key y comunicarte cambios del servicio.</li>
<li><strong>El plan contratado</strong> (beta, starter o pro) y el identificador de tu suscripción en PayPal — para saber qué cuota te corresponde y desactivar el acceso si cancelas.</li>
<li><strong>El prefijo de tu API key</strong> — un fragmento que identifica la clave sin permitir usarla.</li>
<li><strong>El uso del servicio</strong>: número de evaluaciones por periodo y fecha del último uso — para aplicar la cuota de tu plan.</li>
</ul>''', sanitize=False)
            _priv_p('<strong>No tratamos datos de pago.</strong> Tu tarjeta, tu saldo y tu identidad '
                    'financiera los procesa PayPal; Xiliux no los ve ni los recibe.')

            _priv_h2('3. Lo que no tratamos nunca, y por qué no podríamos')
            _priv_p('El servicio Quipu OPRF endurece contraseñas. Aun así, '
                    '<strong>el servidor no ve jamás las contraseñas de tus usuarios</strong>, ni los '
                    'secretos que se derivan de ellas. Esto no es una promesa: es cómo está construido.')
            _priv_p('El protocolo es un VOPRF verificable conforme a la '
                    '<a href="https://www.rfc-editor.org/rfc/rfc9497.html" class="text-cyan-400 hover:underline" '
                    'target="_blank" rel="noopener">RFC&nbsp;9497</a>. Tu servidor <em>ciega</em> el dato '
                    'antes de enviarlo; el nuestro lo evalúa sin poder aprender ni la entrada ni el '
                    'resultado, y devuelve una prueba criptográfica de que usó la clave correcta. '
                    'Si alguien comprometiera nuestra infraestructura por completo, ahí no habría '
                    'contraseñas que robar, porque nunca llegaron.')
            _priv_p('Tampoco guardamos tu API key: solo un hash. Por eso, si la pierdes, no podemos '
                    'devolvértela — emitimos una nueva.')

            _priv_h2('4. Para qué los usamos')
            _priv_p('Únicamente para prestar el servicio que contrataste: emitir tu clave, aplicar la '
                    'cuota de tu plan, atender tus solicitudes y desactivar el acceso cuando cancelas. '
                    '<strong>No hacemos perfilado, ni publicidad, ni decisiones automatizadas sobre ti, '
                    'y no vendemos ni cedemos tus datos a nadie.</strong>')

            _priv_h2('5. Con quién se comparten')
            ui.html(f'''<ul class="text-slate-300 leading-relaxed mb-4 list-disc pl-6 space-y-1">
<li><strong>PayPal</strong> — procesa el cobro y es quien nos entrega tu correo. Se rige por su propia política.</li>
<li><strong>Zoho Mail</strong> — transporta los correos que te enviamos, incluido el que contiene tu API key.</li>
</ul>''', sanitize=False)
            _priv_p('Nadie más. Los datos se alojan en un servidor propio; no hay analítica de terceros '
                    'ni rastreadores en las páginas del servicio.')

            _priv_h2('6. Cuánto tiempo los conservamos')
            if PRIVACY_RETENCION:
                _priv_p(f'Conservamos tus datos {PRIVACY_RETENCION}. Cumplido ese plazo se suprimen.')
            else:
                _priv_p('<em class="text-amber-400">[Pendiente: definir el plazo de conservación y el '
                        'criterio — obligaciones comerciales y tributarias frente a minimización.]</em>')

            _priv_h2('7. Tus derechos')
            _priv_p('Puedes solicitar el acceso, la corrección, la actualización o la supresión de tus '
                    'datos, así como revocar la autorización, escribiendo a '
                    f'<a href="/#contacto" class="text-cyan-400 hover:underline">el formulario de contacto</a>. '
                    'Responderemos en los plazos que fija la ley aplicable.')
            _priv_p('Ten en cuenta que <strong>suprimir tus datos implica cancelar el servicio</strong>: '
                    'tu correo es lo que vincula tu suscripción con tu clave.')

            _priv_h2('8. Seguridad')
            _priv_p('Todo el tráfico va cifrado con TLS. Las API keys se guardan hasheadas, nunca en '
                    'claro. El acceso administrativo al servidor exige un token propio. Aun así, '
                    'conviene ser honestos sobre un punto: <strong>tu API key te llega por correo '
                    'electrónico</strong>, que es un canal que no controlamos de extremo a extremo. '
                    'Guárdala como un secreto y rótala si sospechas que se expuso.')

            _priv_h2('9. Cambios')
            _priv_p('Si esta política cambia de forma relevante, actualizaremos la fecha de vigencia y '
                    'avisaremos por correo a los suscriptores activos antes de que aplique.')

    blog_footer()

# --- PRECIOS: SERVICIO GESTIONADO QUIPU OPRF ---
@ui.page('/quipu/precios')
def quipu_pricing_page():
    ui.dark_mode().enable()
    ui.colors(primary='#6366f1', secondary='#06b6d4', accent='#8b5cf6', dark='#0f172a')
    ui.page_title('Planes — Quipu OPRF gestionado | Xiliux')
    ui.add_head_html(f'''<html lang="es">
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="description" content="Servicio gestionado de endurecimiento de contraseñas con VOPRF de Quipu: rate-limit online que hace imposible el brute-force offline. Suscripción mensual." />
<link rel="canonical" href="{DOMAIN}/quipu/precios" />
<meta name="robots" content="index, follow, max-image-preview:large" />
<link rel="icon" type="image/png" href="/logo.png">
<meta name="theme-color" content="#0f172a">
<meta property="og:title" content="Quipu OPRF — servicio gestionado" />
<meta property="og:description" content="Endurecimiento de contraseñas con VOPRF. Suscripción mensual." />
<meta property="og:image" content="{SOCIAL_IMAGE}" />
<meta property="og:url" content="{DOMAIN}/quipu/precios" />
<style>.glass {{ background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(12px); }}</style>
''')
    blog_header()
    ready = quipu_sales.sales_ready()
    with ui.column().classes('w-full min-h-screen bg-slate-950 text-slate-200 items-center pt-24 pb-20 px-4'):
        ui.html('<div class="max-w-2xl w-full mb-8 rounded-xl border border-amber-500/40 bg-amber-500/10 text-amber-300 px-5 py-3 text-sm text-center">⚠️ Servicio en <b>BETA</b> (pre-auditoría externa). Ideal para evaluar e integrar; evita datos críticos de producción hasta la auditoría.</div>', sanitize=False)
        ui.html('<h1 class="text-4xl md:text-5xl font-bold text-white mb-3 text-center">Quipu OPRF — servicio gestionado</h1>', sanitize=False)
        ui.html('<p class="text-slate-400 mb-3 text-center max-w-2xl">Endurecimiento de contraseñas con VOPRF: un servidor con rate-limit online que hace <b>imposible el brute-force offline</b>. Nosotros lo hospedamos; tú consumes la API con tu key.</p>', sanitize=False)
        ui.html('<p class="text-slate-500 mb-12 text-center text-sm">Cobro mensual · cancela cuando quieras · la API key llega a tu email al suscribirte.</p>', sanitize=False)

        with ui.grid().classes('grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl w-full'):
            for plan in quipu_sales.PLANS:
                border = 'border-cyan-500' if plan.get('popular') else 'border-slate-700'
                with ui.card().classes(f'bg-slate-800 border {border} p-6 rounded-2xl flex flex-col'):
                    if plan.get('popular'):
                        ui.html('<div class="text-xs font-bold tracking-widest text-cyan-400 mb-2">MÁS POPULAR</div>', sanitize=False)
                    ui.html(f'<div class="text-2xl font-bold text-white">{plan["name"]}</div>', sanitize=False)
                    ui.html(f'<div class="text-slate-400 text-sm mb-4">{plan["desc"]}</div>', sanitize=False)
                    ui.html(f'<div class="text-4xl font-extrabold text-white">${plan["price"]}<span class="text-base font-medium text-slate-400">/mes</span></div>', sanitize=False)
                    ui.html(f'<div class="text-cyan-400 text-sm font-semibold mt-1 mb-4">{plan["quota"]} evaluaciones/mes</div>', sanitize=False)
                    feats = "".join(f'<li class="flex items-start gap-2 text-slate-300 text-sm mb-2"><span class="text-green-400">✓</span>{f}</li>' for f in plan["features"])
                    ui.html(f'<ul class="mb-6 flex-1">{feats}</ul>', sanitize=False)
                    if ready and quipu_sales.plan_paypal_id(plan):
                        ui.html(f'<div id="paypal-{plan["key"]}" class="min-h-[45px]"></div>', sanitize=False)
                    else:
                        ui.html('<div class="text-center text-slate-500 text-sm border border-slate-700 rounded-lg py-3">Próximamente — <a href="/#contacto" class="text-cyan-400 underline">avísame</a></div>', sanitize=False)

        ui.html('''<div class="max-w-3xl w-full mt-16">
  <h2 class="text-2xl font-bold text-white mb-2 text-center">Cómo se integra</h2>
  <p class="text-slate-400 text-sm mb-6 text-center">Django, con el hasher de contraseñas de siempre. Los usuarios existentes migran solos al entrar: sin script, sin reseteo.</p>
  <pre class="bg-slate-900 border border-slate-700 rounded-xl p-5 text-sm text-slate-300 overflow-x-auto"><code># El SDK se entrega junto con tu API key
# (Apache-2.0, sin la AGPL del núcleo)</code></pre>
  <pre class="bg-slate-900 border border-slate-700 rounded-xl p-5 text-sm text-slate-300 overflow-x-auto mt-3"><code># settings.py
PASSWORD_HASHERS = [
    "quipu_oprf_django.hashers.OprfArgon2PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",   # migración
]

QUIPU_OPRF = {
    "BASE_URL":   "https://oprf.xiliux.com",
    "API_KEY":    os.environ["QUIPU_OPRF_API_KEY"],   # llega a tu email
    "PUBLIC_KEY": os.environ["QUIPU_OPRF_PUBKEY"],    # fíjala fuera de banda
}</code></pre>
  <p class="text-slate-500 text-xs mt-4 text-center">El SDK es <b>Apache-2.0</b>: no arrastra la AGPL del núcleo a tu servidor de autenticación.
  Conforme a <a href="https://www.rfc-editor.org/rfc/rfc9497.html" class="text-cyan-400 underline">RFC 9497</a> (VOPRF, ristretto255-SHA512), verificado contra los vectores oficiales.</p>
  <p class="text-slate-500 text-xs mt-2 text-center">¿Otro stack? Las primitivas se piden por <a href="/#contacto" class="text-cyan-400 underline">el formulario de contacto</a>, y el protocolo es el estándar <b>RFC 9497</b>: cualquier cliente conforme interopera.</p>
</div>''', sanitize=False)

        ui.html('<p class="text-slate-500 text-xs mt-10 text-center max-w-2xl">¿Prefieres auto-hospedar? Quipu sigue siendo software libre (AGPL-3.0). Desde agosto de 2026 el código no se publica en registros ni en GitHub, por seguridad: se entrega a pedido por <a href="/#contacto" class="text-cyan-400 underline">el formulario de contacto</a>, con firma y SHA-256.</p>', sanitize=False)

    if ready:
        first = quipu_sales.PLANS[0]["key"]
        renders = "".join(quipu_sales.button_script(p) for p in quipu_sales.PLANS if quipu_sales.plan_paypal_id(p))
        ui.add_body_html(f'''
<script src="{quipu_sales.paypal_sdk_url()}"></script>
<script>
(function wait(){{
  if(!window.paypal || !document.getElementById('paypal-{first}')){{ return setTimeout(wait, 300); }}
  {renders}
}})();
</script>
''')
    blog_footer()


# --- GRACIAS (retorno de PayPal tras suscribirse) ---
@ui.page('/quipu/gracias')
def quipu_thanks_page():
    ui.dark_mode().enable()
    ui.colors(primary='#6366f1', secondary='#06b6d4', accent='#8b5cf6', dark='#0f172a')
    ui.page_title('¡Gracias por suscribirte! | Xiliux')
    ui.add_head_html(f'''<html lang="es">
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, follow" />
<link rel="icon" type="image/png" href="/logo.png">
<style>.glass {{ background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(12px); }}</style>
''')
    blog_header()
    with ui.column().classes('w-full min-h-screen bg-slate-950 text-slate-200 items-center justify-center pt-24 pb-20 px-4 text-center'):
        ui.html('<div class="text-6xl mb-4">🎉</div>', sanitize=False)
        ui.html('<h1 class="text-3xl md:text-4xl font-bold text-white mb-4">¡Suscripción activada!</h1>', sanitize=False)
        ui.html('<p class="text-slate-400 max-w-xl mb-2">Estamos generando tu <b>API key</b>. Te llegará por email en unos instantes (revisa spam).</p>', sanitize=False)
        ui.html('<p class="text-slate-500 max-w-xl text-sm mb-8">Guárdala bien: por seguridad no se vuelve a mostrar.</p>', sanitize=False)
        ui.link('Cómo usar tu API key →', '/quipu').classes('no-underline bg-cyan-600 text-white rounded-full px-6 py-3 font-semibold hover:bg-cyan-500')
    blog_footer()


if __name__ in {"__main__", "__mp_main__"}:
    # Contrasta lo que anunciamos contra lo que PayPal cobra y lo que el servidor
    # OPRF concede. Si no cuadra, `sales_ready()` pasa a False y la página de
    # precios muestra "Próximamente" en vez de un botón que cobraría de más o
    # entregaría de menos. Una consulta de red al arrancar, no por petición.
    quipu_sales.comprobar_catalogo_al_arrancar()

    # host='127.0.0.1' y no '0.0.0.0' (2026-08-11). Escuchando en todas las
    # interfaces, el sitio era alcanzable en http://192.99.42.108:8080 SALTÁNDOSE
    # nginx entero: sin TLS, sin HSTS, sin CSP y sin las cabeceras de seguridad.
    # No era teórico — el log del servidor tiene sondeos contra esa IP y ese
    # puerto. nginx hace proxy_pass a 127.0.0.1:8080, así que atarlo a loopback
    # no cambia nada de lo que el mundo ve por el dominio; solo cierra la puerta
    # de atrás.
    ui.run(title='Xiliux — Python y Rust · Cripto post-cuántica e IA', favicon='🚀', host='127.0.0.1', port=8080, reload=False, show=False, storage_secret=APP_SECRET)