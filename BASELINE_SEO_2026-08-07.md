# Baseline SEO/AEO — 2026-08-07

Punto de partida ANTES de que el Tier 1 (capa AEO/GEO) haga efecto. Sirve para
**decidir a las 8–12 semanas** si el motor tipo-Soro merece convertirse en
producto. Sin esto, "analizar en base a resultados" no tiene con qué comparar.

**Checkpoint de decisión: ~2026-10-16** (10 semanas). Ese día se re-miden los
mismos números de abajo y se decide.

## Lo que YA está desplegado (on-site, medido hoy)

| Señal | Estado |
|---|---|
| `/llms.txt` (AEO/GEO) | ✅ vivo |
| robots.txt con bienvenida a crawlers de IA | ✅ vivo |
| JSON-LD `TechArticle` + autor E-E-A-T (`sameAs`) | ✅ vivo |
| `FAQPage` + answer-first en 5 posts de cripto | ✅ vivo |
| `SoftwareSourceCode` en `/quipu` | ✅ vivo |
| URLs indexables (sitemap) | **24** |
| GA4 | ✅ vivo (`G-D9MF2QNT8M`) |

## Estado de VISIBILIDAD hoy (el baseline que importa)

- **Orgánica para los 5 términos de cripto PQ:** efectivamente **CERO**. Una
  búsqueda de "criptografía post-cuántica Rust cifrado híbrido" no devuelve
  xiliux/quipu — dominan Wikipedia y papers académicos.
- **Citación en asistentes de IA (ChatGPT/Perplexity/Claude):** no citado
  (recién desplegado; los crawlers de IA aún no han pasado tras el robots nuevo).
- **Referrers:** ~0 (medido antes: el repo público de Quipu tuvo 17 visitas / 0
  referrers en 14 días).

## Search Console — CONFIRMADO por captura (2026-08-07 11:46)

GSC **sí está verificado y con datos** (vía la cuenta de GA — por eso la etiqueta
no está en el HTML). Corrige el "hueco #1" que sospeché. Números leídos de la
Descripción general:

- **Páginas indexadas: 24** (las 24 del sitemap → cobertura COMPLETA). El salto a
  24 ocurrió ~2026-07-07.
- **Páginas no indexadas: 3 — REVISADO (captura 11:50), benigno.** Son las
  variantes de la portada que redirigen a la canónica `https://xiliux.com/`:
  `https://www.xiliux.com/`, `http://xiliux.com/`, `http://www.xiliux.com/`.
  Google las excluye a propósito (301 → canónica). **Correcto, cero acción.**
- **Clics totales (búsqueda web, ~3 meses): 1.** Un pico el 18-may, plano (0)
  desde entonces.
- Impresiones / posición media: pendiente de leer en Rendimiento → Informe
  completo (la Descripción general no las muestra).

**Lectura:** la indexación técnica está RESUELTA — el cuello no es que Google no
te vea, es **autoridad y demanda** (1 clic en 3 meses). Es exactamente el
problema que atacan el Tier 1 (AEO) y el Tier 2/3 (contenido, clusters, inglés),
no la parte técnica, que ya está.

## Números a ANOTAR HOY (para comparar en octubre)

De la captura de hoy quedan fijados: **indexadas 24, no indexadas 3, clics ~1.**
Falta apuntar (yo no accedo a tu cuenta):

**En Search Console** (Rendimiento, últimos 28 días):
- Impresiones totales: `____`
- Posición media: `____`

**En GA4** (Adquisición, últimos 28 días):
- Sesiones totales: `____`
- Sesiones por Organic Search: `____`
- Sesiones/fuente de Referral: `____`

**Acción pendiente:** ver cuáles son las **3 páginas no indexadas** y si alguna
debería estarlo. Y enviar/confirmar el sitemap (`/sitemap.xml`) en GSC.

## Qué se re-mide en el checkpoint (2026-10-16)

Los mismos: impresiones/clics/posición/indexadas (GSC), sesiones orgánicas y
referrers (GA4), y **una prueba manual de citación**: preguntar a ChatGPT y
Perplexity por los 5 temas de cripto y ver si citan xiliux.com.

**Regla de decisión (recordatorio):** el portafolio valida el MOTOR, no el
mercado. Si el motor mueve estos números en un sitio real, la pregunta del
producto pasa a ser la repetibilidad en nichos ajenos. Si no los mueve, el
producto no tiene base y el aprendizaje costó poco.
