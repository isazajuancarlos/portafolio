# Plan de palabras clave por cluster — 2026-08-31

Derivado de los datos REALES de Search Console (últimos 3 meses): **1 clic, 189
impresiones, posición media 17,8**. El cuello no es técnico (indexación limpia,
SEO técnico completo) sino **demanda + autoridad**, y sobre todo que el contenido
apunta a formulaciones que casi nadie teclea.

> **AVISO DE HONESTIDAD (D16/D20):** aquí NO hay cifras de volumen de búsqueda.
> No las puedo medir —requieren el Planificador de Palabras Clave de Google Ads,
> que es tu cuenta—. Lo que sigue son **candidatos razonados** de cómo se busca
> de verdad cada tema; el volumen lo pones tú pegando estas frases en el
> Planificador. Inventar un número sería peor que no darlo.

## Cómo se usa

1. Pega la columna «consulta candidata» en el Planificador (una tanda por
   cluster).
2. Ordena por volumen y por competencia.
3. Donde haya volumen y ya tengas post → ajusta el `title`/`description` para que
   ARRANQUEN con esa formulación (no rellenar el cuerpo: padear penaliza).
4. Donde haya volumen y NO tengas post → es un hueco de contenido (post nuevo o
   versión EN).

---

## Lo que GSC ya confirma (demanda real hoy, aunque diminuta)

Las únicas consultas con impresiones son de **herramienta**, no de tu
diferenciador:

| Consulta real | Impr. | Posición | Post |
|---|---|---|---|
| nicegui | 11 | **7,2** | nicegui-web-app-python-sin-javascript |
| ccxt | 10 | 22,2 | por-que-tu-bot-recibe-403-de-cloudflare-ccxt |
| gettext i18n / i18n gettext | 5 | 16–22 | i18n-minima-sin-gettext |
| rust htmx | 2 | 49 | (mención suelta) |

`nicegui` a 7,2 es lo único a pie de página 1. Ninguna consulta de cripto, firma,
cadena de custodia o evidencia digital aparece: **cero impresiones** en tu moat.

---

## cripto-postcuantica (7 posts, 6 con EN) — el moat, hoy sin demanda ES

El término cabeza «criptografía post-cuántica» lo dominan Wikipedia/IBM/Cloudflare
(verificado: fuera del top 30). No se pelea de frente. Se entra por **cola larga
con intención**:

| Consulta candidata (intención) | Estado | Acción |
|---|---|---|
| `harvest now decrypt later qué es` | cubierto (que-es-criptografia) | subir el término al `title`/H2 |
| `migrar a criptografía post-cuántica` | parcial | post/CTA de servicio de migración |
| `ML-KEM ML-DSA ejemplo` / `NIST PQC estándares` | parcial | reforzar en el post «qué es» |
| `cifrado híbrido X25519 ML-KEM` | cubierto (cifrado-hibrido) | ya bien; empujar EN |
| `Argon2id proteger contraseñas` | cubierto (te-roban-la-bd) | ya bien |
| **inglés**: `post-quantum migration Rust`, `hybrid encryption X25519 Kyber` | EN existe | prioridad: EN tiene MÁS mercado que ES aquí |

**Determinación del cluster:** el mercado ES de PQC es pequeño; el valor está en
**inglés** y en la intención comercial («migrar», «servicio»), no en la
definición.

## trading-algoritmico (5 posts, 0 con EN) — demanda REAL y ya entrando

Es el cluster con demanda medida (ccxt 10 impr). Es «how-to» de nicho, poca
competencia:

| Consulta candidata | Estado | Acción |
|---|---|---|
| `ccxt 403 cloudflare` / `bot trading 403 cloudflare` | **cubierto, pos 22** | **EN** (el trading algo se busca sobre todo en inglés) |
| `dimensionar posición trading riesgo` / `position sizing sin apalancamiento` | cubierto | EN |
| `backtest sesgo look-ahead` / `por qué mi backtest miente` | cubierto | reforzar título |
| `histéresis señal que parpadea` | cubierto | nicho, ok |

**Determinación:** este cluster es el que YA convierte impresión en posición
decente. **Traducir los 5 a EN es la acción de mayor ROI medido** de todo el
plan: mercado grande, competencia baja, y ya rankeas en ES. Hoy 0 tienen EN.

## python-ia (5 posts, 0 con EN) — demanda de herramienta, funnel a MVP

Aquí está `nicegui` (pos 7,2, lo más cerca de tráfico real):

| Consulta candidata | Estado | Acción |
|---|---|---|
| `nicegui tutorial` / `nicegui vs streamlit` / `web app python sin javascript` | **cubierto, pos 7,2** | EN + enlazar al servicio de MVP |
| `crear MVP en python` / `mvp 2 semanas` | cubierto | enlazar a `/cotizador` y `/servicios` |
| `integrar LLM en python` / `RAG con tus datos` | cubierto | EN (mercado grande) |
| `automatizar tareas con bot python` | cubierto (bot-python, pos «bot automatizador» 53) | mejorar |

**Determinación:** el post de nicegui es tu mejor activo de captación. Traducir a
EN y **enlazarlo a `/servicios` + `/cotizador`** convierte su tráfico (el único
que casi llega) en leads.

## libs-fiables (12 posts, 6 con EN) — el cluster más grande y el de menos demanda comercial

Son lecciones de ingeniería (el bucle que se encuentra a sí mismo, el nieto que
hereda la tubería, banco solo de negativos…). Excelentes como prueba de
profundidad (D11), pero **casi nadie los busca**: no mapean a un comprador.

**Determinación:** NO invertir en SEO de captación aquí. Su función es
**autoridad/E-E-A-T** —demuestran rigor—, y para eso ya sirven. Dejarlos como
están.

## legaltech (1 post) — EL HUECO, y es tu diferenciador

Solo 1 post (`como-no-perder-un-reporte`). Y sin embargo es donde tu identidad
doble (abogado + programador) no tiene competencia. El post
`un-hash-no-es-una-cadena-de-custodia` (en cripto) es #1 mundial para su frase.

| Consulta candidata (intención jurídico-técnica) | Estado | Acción |
|---|---|---|
| `cadena de custodia digital` / `valor probatorio del hash` | 1 post relacionado | **post nuevo dedicado** |
| `evidencia digital admisibilidad` / `integridad prueba electrónica` | hueco | post nuevo |
| `firma electrónica vs firma digital validez` | hueco | post nuevo |
| `Ley 1581 tratamiento de datos software` | hueco | post nuevo (nicho Colombia, competencia baja) |

**Determinación:** este es el cluster con MEJOR relación diferenciación/competencia
de todo el sitio, y está casi vacío. Es donde 2-3 posts nuevos rendirían más que
20 en libs-fiables. **Ojo D-identidad:** va en el blog de Xiliux (software) como
contenido TÉCNICO sobre evidencia/firma, sin cruzar a la práctica jurídica ni
enlazar a `juancarlosisaza`.

---

## Prioridad global (por ROI, no por esfuerzo)

1. **Traducir a EN los clusters trading-algoritmico (5) y python-ia (5)** —
   mercado grande, competencia baja, YA rankeas en ES. Mayor ROI medido.
2. **2-3 posts nuevos de legaltech** (cadena de custodia, evidencia digital, Ley
   1581) — diferenciador sin competencia, cluster casi vacío.
3. **Enlazar los how-to que traen impresiones → `/servicios` y `/cotizador`** —
   convierte el poco tráfico en leads.
4. **Autoridad (off-page)**: lo que ningún ajuste de código arregla. Backlinks
   de calidad (menciones en foros técnicos, dev.to, HN cuando encaje). Es el
   techo real de un dominio joven; el contenido sin enlaces tarda 6-12 meses.

## Lo técnico (ya hecho o determinado)

- **Sitemap**: se añadieron `/cotizador` y `/quipu/precios` (faltaban). Pendiente
  desplegar. Reenviado en GSC para refrescar la lectura (era del 20-jul).
- **Portada client-rendered**: `/` sirve 27 palabras en el HTML crudo (NiceGUI
  por WebSocket). Es la debilidad técnica de fondo, pero su arreglo es una
  **portada SSR** —reescritura de la página que cobra—, decisión aparte, no un
  retoque.
