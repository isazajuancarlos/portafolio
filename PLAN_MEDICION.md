# Plan de medición — Tier 1 (AEO/GEO) + Tier 3 (bilingüe)

Doc **vivo** (el snapshot con fecha es `BASELINE_SEO_2026-08-07.md`). Aterriza lo
que al baseline le falta para que el checkpoint del **2026-10-16** sea
*ejecutable*: las **queries objetivo** exactas, los **umbrales de éxito**
numéricos, y la **plantilla de captura** de los números que solo salen de
GSC/GA4. Sin esto, «analizar en base a resultados» no tiene con qué comparar ni
regla para decidir (directiva 30).

## Verificación técnica en vivo — 2026-08-09 (2 días tras el despliegue)

Medido con `curl` al dominio y logs de nginx del VPS (solo lectura). Es la **capa
1**: prueba que el cambio se desplegó y es consumible, NO que funcione.

| Señal | Resultado | Lectura |
|---|---|---|
| hreflang recíproco ES↔EN | ✅ ES→EN y EN→ES, con `x-default`→ES | bien montado; el error clásico (no recíproco → Google lo ignora) NO está |
| canonical por versión | ✅ cada una a sí misma | no se colapsan las dos en una |
| URLs EN | ✅ 6 en HTTP 200, en sitemap (30 total, era 24) | pilar `/en/blog` + 5 de cripto |
| crawlers IA rastreando | ✅ cientos/bot: Meta, ClaudeBot, GPTBot, Amazonbot, OAI-SearchBot, Perplexity; decenas de Google-Extended, Applebot, CCBot, Bytespider (vs 357 Googlebot) | el `robots.txt` de bienvenida no los bloquea |
| `/llms.txt` consumido por IA real | ⚠️ **0** — solo escáneres y `curl`; primeros hits daban 404 | apuesta a futuro, hoy no mueve nada; lo que se consume es el HTML con JSON-LD |

**Pendiente técnico (decisión aparte, NO de paso):** los slugs EN están en
español (`/en/blog/que-es-criptografia-post-cuantica`). No está roto; se pierde la
keyword en inglés en la URL. Traducirlos rompe URLs ya indexadas (→ 301), así que
es decisión con coste, no arreglo.

## Queries objetivo — se mide ESTO, no el sitio entero

«Impresiones totales» mezcla el portafolio con el ruido del dominio. Las queries
salen de los títulos y las FAQ de los 17 posts (lo que el contenido declaró
perseguir). **Foco del checkpoint = el cluster cripto PQ** (el único bilingüe y
el que el baseline ya eligió); el resto es cobertura secundaria.

### Cluster CRÍPTO PQ — bilingüe, es el que decide (head queries)

| post | query ES | query EN |
|---|---|---|
| que-es-criptografia-post-cuantica | criptografía post-cuántica | what is post-quantum cryptography |
| cifrado-hibrido-clasico-post-cuantico | cifrado híbrido post-cuántico | hybrid post-quantum encryption |
| sellar-evidencia-digital-firma-post-cuantica | sellar evidencia digital | post-quantum timestamp digital evidence |
| te-roban-la-base-de-datos… | proteger contraseñas si roban la base | password hashing after database breach |
| quipu-cifrado-multilenguaje | cifrado post-cuántico rust python | post-quantum encryption library rust |

### Clusters secundarios (solo ES) — cobertura, no deciden

- **Trading**: `position sizing riesgo bot` · `errores backtest overfitting` · `ccxt 403 cloudflare` · `histéresis flapping clasificador`
- **Python/IA**: `integrar LLM en python` · `qué es RAG` · `nicegui web app python` · `automatizar tareas python` · `MVP python 2 semanas`
- **Infra**: `fan-out notificaciones aislar fallo` · `i18n sin gettext json`
- **Legal**: `no perder obligaciones recurrentes reporte`

## Umbrales de éxito — checkpoint 2026-10-16 (PROPUESTA, ajústalos)

La regla del baseline —«si el motor mueve estos números»— sin número se
racionaliza después. Se fija ANTES de medir (directiva 16). Base de partida: 1
clic / 3 meses, indexación técnica ya completa.

**DUROS — bilingüe (los más fiables, se mueven en semanas):**
- Indexación: **6/6** URLs EN indexadas en GSC.
- hreflang: **0 errores** en GSC → Internacional.
- Impresiones EN: **≥1** URL EN con >0 impresiones para una query en inglés desde país anglófono.

**LEADING — AEO (señal temprana, no resultado):**
- Referrals de dominios IA en GA4 (`chatgpt.com`, `perplexity.ai`, `gemini.google.com`): de 0 → **≥1** sesión.
- Google AI Overview: aparecer en **≥1** de las 5 head queries (con o sin cita).
- Structured data: **0 errores** en Rich Results Test (TechArticle + FAQPage).

**RESULTADO — SEO clásico (ruidoso a esta base, es contexto):**
- Posición media <30 para **≥2** de las 5 head queries.
- Clics 1 → ≥10 (informativo, no decisorio).

**CUALITATIVO — citación IA (protocolo obligatorio, si no es anécdota):**
- Mismas 15 preguntas literales en ChatGPT/Perplexity/Claude, **búsqueda web
  activada** y **sesión limpia** (sin haberles dado la URL antes), sí/no cita
  xiliux + captura, **3 repeticiones**. Éxito = **≥1** cita.

### Regla de decisión cuantificada (propuesta)

El motor **movió señal** (→ evaluar repetibilidad como producto) si se cumple:

> **6/6 EN indexadas Y ≥1 EN con impresiones** (el bilingüe capta demanda),
> **Y** al menos UNA señal AEO real (≥1 referral IA **o** ≥1 AI Overview con
> inclusión **o** ≥1 citación de protocolo).

Si el bilingüe no indexa/no capta impresión **y** la AEO da 0 en todo → el motor
no movió nada medible en 10 semanas → el producto no tiene base todavía, y el
aprendizaje costó poco (que es lo que el baseline dijo querer).

**Lo que NO cabe en la ventana, dicho para no leer un cero como fracaso:** la
citación-por-ENTRENAMIENTO de los LLM (corte de conocimiento anterior al 07-ago)
tarda meses o años. En octubre solo se mide **búsqueda web + AI Overviews**.

## Plantilla de captura — SOLO Juan (no accedo a GSC/GA4)

**Apuntar HOY** (línea base, o el checkpoint compara contra vacío):

GSC → Rendimiento, últimos 28 días:
- Impresiones totales: `____`  · Posición media: `____`

GA4 → Adquisición, últimos 28 días:
- Sesiones totales: `____` · Organic Search: `____` · Referral: `____`
- Referrals de dominios IA (chatgpt/perplexity/gemini): `____`

Por cada head query (GSC → filtro por consulta):
- `criptografía post-cuántica` → impresiones `____` pos `____`
- `what is post-quantum cryptography` → impresiones `____` pos `____`
- (… las 10, ES y EN)

## Leading indicators semanales (para no llegar a octubre a ciegas)

Dos números que hoy no vigila nadie y que se mueven antes que los clics:
1. hits de crawler IA por bot (logs nginx del VPS).
2. referrals desde dominios de IA (GA4 o `Referer` en logs).

Pendiente de montar como script de lectura (Rust, directiva 38) si se decide.
