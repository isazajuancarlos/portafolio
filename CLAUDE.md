# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Configuración general: `~/.claude/CLAUDE.md`** — reglas que no se rompen,
> las directivas numeradas y las máquinas montadas. Se carga en toda sesión y
> **no se copia aquí**; este archivo lleva SOLO lo propio del portafolio.
>
> **Esta instancia se arranca desde esta carpeta**: `cd /mnt/data/portafolio && claude`.
> Desde el 2026-08-01 no se trabajan varios proyectos desde una sola sesión.
>
> Xiliux y la identidad jurídica van **separadas**: distinto dominio, distinta
> estética, sin enlaces cruzados. Y no se vende software a clientes de asesoría.

## Qué es esto

`xiliux.com`: el escaparate comercial de Xiliux. No es solo un portafolio — es el
**canal de venta**: describe los productos (Informes, Inventario, Salud, Quipu,
tunjo, guaca), capta contactos, y **cobra suscripciones del servicio gestionado
Quipu OPRF por PayPal aprovisionando la clave automáticamente**.

Stack: **NiceGUI 3.6.1** (sobre FastAPI/Quasar) + `python-dotenv` + `markdown2`.
Todo el sitio vive en **`main.py` (~2.300 líneas)** más dos módulos de venta.
Datos en JSON planos; no hay base de datos ni ORM.

## Arquitectura: DOS motores de render en el mismo proceso

Es lo primero que hay que entender, y no se ve leyendo una sola función.

| | `@ui.page(...)` (NiceGUI) | `@app.get(...)` (FastAPI, HTML de servidor) |
|---|---|---|
| Rutas | `/project/{id}`, `/privacidad`, `/quipu/precios`, `/quipu/gracias` | **`/` (portada, desde 2026-08-31)**, **`/en`**, `/blog`, `/blog/{slug}`, **`/en/blog`, `/en/blog/{slug}`**, `/en/quipu/code`, `/servicios`, `/quipu`, `/informes`, `/cotizador`, `/llms.txt`, y los POST `/contacto` y `/recursos` (formularios) |
| Cómo llega al navegador | Vue/Quasar por **WebSocket** tras cargar JS | cadena HTML ya construida, **sin JS** |
| Lo ve Google | **No** el contenido, solo el `ui.add_head_html()` | Sí, entero |
| Se estiliza con | clases Tailwind/Quasar en `.classes()` | `_BLOG_CSS`, una hoja embebida en el `<head>` |

**El motivo es SEO**: NiceGUI renderiza en el cliente y el rastreador no ve nada,
así que **todo lo que tiene que posicionar se sirve como HTML de servidor**. Si
añades una página cuyo objetivo es tráfico orgánico, va por `@app.get` usando
`_seo_head()` + `_nav_html()` + `_footer_html()` + `_blog_page()`; si es
interactiva (formularios, estado de sesión), va por `@ui.page`.

**El render del blog es BILINGÜE y de FUENTE ÚNICA (Tier 3, 2026-08-07):**
`_render_post(post, lang)` genera el mismo artículo en ES (`/blog/{slug}`) o EN
(`/en/blog/{slug}`) cambiando solo la fuente de los campos y las etiquetas
(`_LBL`); añade `hreflang` es/en/x-default cuando el post trae versión en el otro
idioma. `_seo_head`, `_nav_html`, `_footer_html` y `_blog_page` aceptan `lang`.
### `/en` — la puerta inglesa (2026-08-12)

Hasta ese día la sección inglesa era un **callejón sin salida**, medido en vivo:
7 artículos y `/en/quipu/code` servían inglés, pero los enlaces de su propia
barra —Home, Contact, Quipu— y el **botón de conversión de cada artículo**
(`/#contacto`) caían en páginas en español, y `/en` daba **404**. El lector
anglófono salía del idioma al primer clic; todo el Tier 3 moría ahí.

`/en` **NO es la traducción de `/`**, y es deliberado. La home española vende
scripts y MVPs «desde $200 USD» a pymes latinoamericanas; en inglés esa cifra
ancla la conversación en la tarifa y compite con miles de perfiles genéricos.
`/en` vende lo que no es genérico —cripto post-cuántica, sistemas en Rust— y la
**evidencia medida**, con las tres piezas en `_HOME_EN_PRUEBAS` y las FAQ en
`_HOME_EN_FAQ`, que son la fuente única del cuerpo *y* del JSON-LD.

El destino del botón de cada artículo es ahora un dato por idioma
(`_LBL[lang]["cta_href"]`): ES → `/#contacto`, EN → `/en`.

Un `/en/blog/{slug}` sin traducción hace **302 a la versión ES** (no 404). Los
clusters (`CLUSTERS`/`CLUSTERS_EN`) agrupan el índice y alimentan el "Sigue
leyendo"/"Keep reading" entre hermanos.

**Las rutas FastAPI se registran ANTES que las páginas NiceGUI** en el archivo, y
ese orden importa. `ui.run()` al final **bloquea**: todo el montaje ocurre antes.

## Mapa de `main.py`

> **Las líneas se corrieron ~+300 tras la expansión SEO del 2026-08-07** (Tier
> 1-3). Los rangos de abajo son orientativos; para ubicar algo, `grep` por el
> nombre de la función, no por el número.

| Líneas aprox. | Qué hay |
|---|---|
| 1–75 | imports, `BASE_DIR`, rutas de ficheros, secretos del `.env`, datos de contacto y privacidad |
| 84–390 | **el contenido es DATOS, no marcado**: `SERVICES`, `PROCESS`, `FAQS`, `*_FEATURES`, `*_TAGS`, `*_LINKS`, `NAV_ANCLAS`, `OSS_LIBS`, `SPONSORS`. Editar la web es casi siempre editar una de estas listas |
| 394–425 | `load_projects` / `save_projects` / `save_lead` (JSON) |
| 426 | `ProxyHeadersMiddleware` con `trusted_hosts=["127.0.0.1"]` — **no lo pongas en `"*"`**: el cliente falsearía su IP por cabecera |
| 429–480 | SEO y estáticos: `robots.txt` (**da la bienvenida a crawlers de IA**: GPTBot/ClaudeBot/PerplexityBot…), `sitemap.xml` (proyectos + posts ES **y EN**), **`/llms.txt`** (índice AEO curado, derivado de `OSS_LIBS`/`posts_data`), logo, favicon, PDF, manifest |
| 483–495 | **webhook de PayPal**: verifica firma ANTES de aprovisionar, luego `quipu_sales.handle_event` |
| 498–541 | helpers: `valid_email`, `rate_ok` (cooldown antimspam por sesión), blog (`load_posts`, `markdown_to_plain`) |
| 544–683 | `/project/{id}` (NiceGUI) |
| 686–855 | blog SSR **bilingüe**: `_BLOG_CSS`, `_ga_snippet`, `_seo_head`(lang/alternates), `_nav_html`/`_footer_html`/`_blog_page`(lang), `CLUSTERS`/`CLUSTERS_EN`, `_LBL`, `_blog_card`(lang), `_render_post(post,lang)`, y las rutas `/blog`, `/blog/{slug}`, `/en/blog`, `/en/blog/{slug}` |
| 874–1410 | páginas de producto SSR: `/servicios`, `/cotizador` (HTML autocontenido en `COTIZADOR_HTML`), `/quipu`, `/informes` |
| 1411–1626 | `/privacidad`, `/quipu/precios`, `/quipu/gracias` (NiceGUI) |
| (portada) | **`/` es SSR desde 2026-08-31**: `_home_body()`/`_home_jsonld()`/`_HOME_PRUEBAS`, servida por `@app.get('/')` con `_blog_page`. La antigua `main_page()` (@ui.page, ~750 líneas) **se retiró**: servía ~27 palabras en el HTML crudo (cuerpo por WebSocket) y Google casi no veía la página que vende. Los 2 formularios (contacto, lead magnet) pasaron a `<form>`→`@app.post` (`/contacto`, `/recursos`) con `_procesar_formulario` + cooldown por IP `rate_ok_ip` + guardián de inyección de cabeceras en `_enviar_correo` |

**La portada ya NO tiene splash ni secciones NiceGUI.** El SSR mantiene hero,
pruebas, servicios (de `SERVICES`), productos, proceso (de `PROCESS`), lead
magnet, FAQ (de `FAQS`) y contacto. El detalle de cada producto vive en su propia
página (`/informes`, `/quipu`, `/cotizador`), enlazada desde la portada.

## Ejecutar

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python main.py          # http://0.0.0.0:8080
```

`requirements.txt` fija `nicegui==3.6.1`, `python-dotenv==1.2.1`,
`markdown2==2.5.4`. **`markdown2` falta con facilidad** y no se nota hasta el
arranque: un despliegue limpio sin él muere con `ModuleNotFoundError`.

No hay pruebas ni linter. El único diagnóstico es `python test_smtp.py`, que
comprueba credenciales de Zoho y manda un correo de prueba.

`reload=False` está fijado en `ui.run()`: **hay que reiniciar el proceso** para
ver un cambio, no basta recargar la página.

## Despliegue

> El detalle completo —incluido cómo desplegar los otros proyectos del mismo
> servidor— está en `/mnt/data/conocimiento/despliegue/VPS.md`.

```
ssh debian@192.99.42.108           # por clave, sin contraseña
servicio   xiliux.service          # WorkingDirectory=/home/debian/portafolio
puerto     8080                    # nginx delante, xiliux.com y www.xiliux.com
```

```bash
D=/home/debian/portafolio
ssh debian@192.99.42.108 "cd $D && cp -a main.py main.py.bak-\$(date +%Y%m%d-%H%M%S)"  # 1. red
scp debian@192.99.42.108:$D/main.py /tmp/remoto.py && diff main.py /tmp/remoto.py | grep '^>'  # 2. ¿el remoto tiene algo que yo no?
scp main.py debian@192.99.42.108:$D/main.py                                            # 3. subir
ssh debian@192.99.42.108 "sudo -n systemctl restart xiliux && sleep 10 && journalctl -u xiliux -n 15 --no-pager"
```

Si el cambio toca el blog, los planes o las dependencias, sube también
`blog_posts.json`, `quipu_sales.py` o `requirements.txt` (y ahí sí, `pip install
-r` en el servidor antes de reiniciar).

**Y después, siempre, `curl` contra el dominio.** `systemctl is-active` no prueba
que se esté sirviendo lo nuevo: `Restart=always` relanza el servicio con la
versión anterior si la nueva revienta, y el `restart` sale 0 igual. Hay que
comprobar que lo nuevo aparece **y que lo viejo sigue en pie**:

```bash
curl -s https://xiliux.com/ | grep -c "<algo del cambio nuevo>"
for u in /informes /cotizador /blog /servicios /quipu /quipu/precios; do
  printf '%-18s %s\n' "$u" "$(curl -s -o /dev/null -w '%{http_code}' https://xiliux.com$u)"
done
```

Volver atrás: `cp -a main.py.bak-<marca> main.py` y reiniciar.

**El `.env` del servidor NO se sobrescribe desde local**: tiene las credenciales
de producción (SMTP de Zoho, PayPal, tokens del OPRF). Si falta una variable, se
edita allá.

## Venta de Quipu OPRF (`quipu_sales.py`, `paypal_setup.py`)

El único camino del sitio que **cobra dinero y entrega un producto**, así que es
donde un error sale caro.

- `paypal_setup.py` — se corre **a mano y una vez**: crea el producto y los tres
  planes en PayPal e imprime los `P-XXXX` que van al `.env`.
- `quipu_sales.py` — `PLANS` (lo que se anuncia), token de PayPal,
  `verify_webhook`, `oprf_issue_key` / `oprf_deactivate` contra el servidor OPRF,
  `subscriptions.json`, y el correo con la clave al cliente.
- `main.py` solo expone `/quipu/precios`, `/quipu/gracias` y `/paypal/webhook`.

**La invariante que sostiene todo esto**: lo *anunciado* (`PLANS`), lo *cobrado*
(los planes de PayPal) y lo *concedido* (`/v1/plans` del servidor OPRF) son tres
copias del mismo dato en tres sistemas. `comprobar_catalogo_al_arrancar()` las
contrasta **al arrancar el proceso**; si discrepan, `sales_ready()` pasa a `False`
y la página de precios muestra *«Próximamente»* en vez de un botón. Ya se
descuadró dos veces en un día (49 USD anunciados / 79 cobrados; 250.000
evaluaciones vendidas / 100.000 concedidas). **No debilitar esa comprobación:**
una tienda cerrada cuesta una venta, cobrar de más cuesta el cliente. Ojo con la
asimetría deliberada: *no poder comprobar* (red caída) avisa y sigue; un
desacuerdo **confirmado** bloquea.

Si cambias un precio o una cuota, cámbialo en los **tres** sitios o el sitio se
cierra solo al reiniciar — que es justo lo que tiene que pasar.

## Variables de entorno

Plantilla completa y comentada en **`.env.example`**. La regla de diseño que hay
que respetar al añadir una nueva: **cada CTA aparece SOLO si su variable está
definida** — sin `WHATSAPP_NUMBER` no hay botón de WhatsApp, sin `STRIPE_MVP` no
hay botón «Reservar», sin los datos de `PRIVACY_*` (`privacy_ready()`) la página
de privacidad no se publica como definitiva. Nada de valores de relleno.

Obligatorias: `APP_SECRET` (cifra la sesión; sin él las sesiones fallan) y
`PASSWORD` (SMTP de Zoho). `ADMIN_PASSWORD` sigue en `.env.example` pero **ya no
la usa nadie**: el panel de administración se retiró del código.

## Datos y estado

| Fichero | Qué es | ¿Versionado? |
|---|---|---|
| `portfolio_data.json` | proyectos que salen en la portada y `/project/{id}` | no |
| `blog_posts.json` | artículos: `slug`, `title`, `description`, `date`, `tags`, `cover`, `body` (Markdown), y desde el 2026-08-07 los campos **opcionales dirigidos por datos**: `answer` (answer-first), `faq` (lista `{q,a}` → FAQPage), `cluster` (id de racimo temático), `en` (`{title,description,answer,faq,body}` para la versión inglesa) | **sí** |
| `subscriptions.json` | suscripciones activas de Quipu OPRF | no |
| `leads.json` | contactos del lead magnet — **PII**, gitignored | nunca |
| `.nicegui/` | almacenamiento de sesión de NiceGUI — gitignored | nunca |

`portfolio_data.json` y `blog_posts.json` se cargan **una vez al arrancar**
(`projects_data`, `posts_data`). Editarlos en caliente no cambia nada hasta
reiniciar el servicio.

**`blog_posts.json` SÍ está versionado** —corregido el 2026-08-05; esta tabla
decía que no—. Se comprueba con `git ls-files --error-unmatch blog_posts.json`,
que lo devuelve. La distinción importa: un artículo corregido entra por commit y
viaja con el repositorio, mientras que `portfolio_data.json` y
`subscriptions.json` viven solo en el servidor y hay que subirlos aparte.

**Trampa del markdown de los artículos, medida el 2026-08-05**: el cuerpo va
envuelto a ~80 columnas, y una línea de continuación que empiece por `+`, `-` o
`*` markdown la lee como **viñeta**. Partió en dos la frase de la firma triple en
`sellar-evidencia-digital-firma-post-cuantica` y rompió el argumento central del
texto sin que nada fallara. La regla que lo caza sobre el HTML servido —y que
discrimina, 1 de 17 antes y 0 de 17 después— es «un `<p>` que no cierra frase
(ni `.` `:` `?` `!` `;`) seguido inmediatamente de `<ul>`». Al añadir o editar un
artículo, córrela contra el proceso real antes de desplegar.

## Trampas de NiceGUI que ya han mordido aquí

1. **`ui.html()` exige `sanitize=`** explícito. `sanitize=False` para el HTML que
   escribimos nosotros; `sanitize=True` para cualquier cosa de un usuario.
2. **Rutas anidadas y clics**: una tarjeta clicable que contiene botones necesita
   `.on('click.stop', ...)` en los botones, o el clic navega en vez de actuar.
3. **Rutas absolutas siempre** (`BASE_DIR`): bajo systemd el `cwd` no es el que
   crees.
4. ~~El **splash** de la portada~~ **RETIRADO el 2026-08-31** al pasar `/` a SSR:
   ya no hay splash ni `splash_seen`. Si se quiere de vuelta, va como CSS puro
   sobre la portada SSR, no como elemento NiceGUI.
5. **`rate_ok()` antes de cada envío de correo** (y `rate_ok_ip()` en los POST
   SSR `/contacto` y `/recursos`, que no tienen sesión NiceGUI). Los dos
   formularios (contacto y
   lead magnet) mandan correo por `smtplib.SMTP_SSL('smtp.zoho.com', 465)`; sin
   cooldown se convierten en un relay y se quema la reputación del dominio.

   **Capa de CONTENIDO (2026-11-08), `antispam.py`:** honeypot + trampa de tiempo
   + cooldown cazan al bot naive, pero NO el spam de **tokens aleatorios** que
   llega con un formulario bien formado y un **correo desechable**
   (medido: `NATREGTEGH1610646NEHTYHYHTR` desde `@notlettersmail.com`).
   `antispam.es_spam_contenido(nombre, email, mensaje)` lo filtra por contenido
   (dominio desechable + token alfanumérico aleatorio ≥18), con **sesgo a dejar
   pasar** (D21: un falso positivo pierde un lead real). Se llama dentro de
   `_procesar_formulario` y se descarta en silencio como el honeypot. Pareja
   roja/verde en `test_antispam.py` (`python test_antispam.py`, 9/9).
6. **FastAPI NO añade `HEAD` cuando registras un `GET`.** Starlette sí lo hace en
   su `Route`; `APIRoute` de FastAPI no, y NiceGUI monta sus páginas por ahí.
   Consecuencia medida contra producción el 2026-08-05: **diez de once rutas
   devolvían `405 Method Not Allowed` al `HEAD`** —todas menos `/favicon.ico`—.
   Un monitor de disponibilidad sondea con `HEAD`, así que veía caída la página
   que cobra; y `/robots.txt` y `/sitemap.xml` también daban 405 a un rastreador
   que los pida así, en un sitio cuyo propósito es posicionar.

   Lo cierra el middleware `HeadComoGet` (`main.py`, junto al de proxy), que
   convierte el `HEAD` en `GET` y devuelve la respuesta sin cuerpo. Va como
   regla y no como `@app.head('/')` porque la causa es del framework y alcanza a
   TODAS las rutas, incluidas las que se escriban mañana. **No se arregla en
   nginx**: si nginx contesta el `HEAD`, el monitor recibe 200 aunque el proceso
   esté muerto, y entonces «sano» y «muerto» se ven igual — que es justo lo que
   el monitor existe para distinguir.

   Al tocar esto, la prueba es la pareja: sin el middleware el `HEAD` tiene que
   volver a 405 (comprobado), y `/favicon.ico` en 200 en los dos casos es el
   control de que el arnés no está diciendo lo mismo a todo.

## SEO

Es el propósito de media base de código, no un adorno. Base: HTML semántico con
un solo `<h1>` por página, navegación con `<a href>` reales (no JS), Open Graph +
Twitter Cards, JSON-LD (`ProfessionalService`, `Person`, `CreativeWork`,
`FAQPage`, `BreadcrumbList`), `sitemap.xml` dinámico con namespace de imágenes,
`robots.txt`, PWA (`manifest.json`), GA4 y verificación de Search Console (GSC ya
verificado vía la cuenta de GA), y `logo.webp` (18 KB frente a 257 KB del PNG).

**Capa AEO/GEO + bilingüe (Tier 1-3, 2026-08-07)** — el trabajo que abrió el moat
de cripto al buscador y a los asistentes de IA:

- **AEO/GEO:** `/llms.txt` (índice curado para ChatGPT/Claude/Perplexity),
  `robots.txt` que da la **bienvenida a crawlers de IA**, y en los artículos
  `TechArticle` (no `BlogPosting`) + autor `Person` con `sameAs` (E-E-A-T) +
  **answer-first** y **`FAQPage`** dirigidos por datos (campos `answer`/`faq`).
  `SoftwareSourceCode` en `/quipu`.
- **Clusters + enlazado interno:** campo `cluster` en cada post; `/blog` agrupa
  por racimo y cada artículo enlaza a sus hermanos ("Sigue leyendo").
- **Bilingüe + hreflang:** el 2026-08-31 se tradujeron los clusters de
  **trading (5) y python-IA (5)** además de los de cripto, y nacieron 2 posts de
  **legaltech** (cadena de custodia, sellado de tiempo) ya bilingües. **25 de 32
  posts tienen versión inglesa** (`/en/blog/...`, campo `en`), con `hreflang`
  es/en/x-default. La decisión de traducir se adelantó al checkpoint por los
  datos de GSC (ver abajo). El baseline está en `BASELINE_SEO_2026-08-07.md`; las
  **queries objetivo, los umbrales de éxito y la plantilla de captura** están en
  `PLAN_MEDICION.md`, y el plan de palabras clave por cluster derivado de GSC en
  `PLAN_PALABRAS_CLAVE_2026-08-31.md`.
- **Diagnóstico GSC (2026-08-31):** 1 clic / 189 impresiones / posición 17,8 en
  3 meses. Indexación LIMPIA (35 indexadas, 7 excluidas correctamente). El cuello
  **no es técnico** sino demanda + autoridad, y que el contenido apunta a
  formulaciones que casi nadie teclea. **Pendiente técnico real: la portada `/`
  es NiceGUI (client-rendered) y sirve ~27 palabras en el HTML crudo** —Googlebot
  puede no establecer el WebSocket y ver casi nada—; el arreglo es inyectar el
  hero en el HTML inicial (`ui.add_body_html` que sobreviva a la hidratación),
  probado contra Googlebot, NO un `<noscript>` (Googlebot ejecuta JS). Es una
  reescritura de la página que vende: va como tarea aparte, tocada con red.

**Todos los 17 posts tienen `answer` + `faq`.** Los cuerpos NO se expanden a la
fuerza: los posts son concisos pero completos; padear penaliza (Google 2026).

Al tocar un artículo, lo que se conserva: **canónico correcto**, un único `<h1>`,
`alt` con palabras clave, alta en `sitemap()` si es nueva, y —si lleva versión
EN— el par `hreflang` en las dos. Un post nuevo del moat nace con `answer`,
`faq` y `cluster`; la traducción es opcional (campo `en`).

`SEO_SETUP.md` tiene el paso a paso de Google Analytics y Search Console.

## Regenerar los iconos desde `logo.png`

```python
from PIL import Image
img = Image.open('logo.png')
img.save('favicon.ico', format='ICO', sizes=[(16,16), (32,32), (48,48)])
img.save('logo.webp', format='WEBP', quality=85)
```

`logo_original_backup.png` es el maestro de 2048×2048.
