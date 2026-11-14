# Venta del servicio Quipu OPRF (capa de ventas)

Cómo el portafolio cobra y aprovisiona el servicio **Quipu OPRF Hardening**.
El portafolio es el **plano de control** (cobra, emite y revoca keys); el
`quipu-oprf-server` desplegado en el VPS es el **plano de datos** (evalúa).
Se comunican por una sola costura: la API `/admin/*` del servidor.

Diseño del servidor: `quipu/docs/quipu-oprf-server-plan.md`.

## Estado (2026-07-21) — EN VIVO

**Se pasó a Live el 2026-07-19.** Verificado el 2026-07-21 contra la web en
producción: `xiliux.com/quipu/precios` devuelve 200, carga el SDK de PayPal con
client-id real, tiene dos IDs de plan de producción y renderiza los botones.
Cero menciones de *sandbox*.

Precios reales: **79 USD** (starter, 250 000 evaluaciones/mes) y **299 USD**
(pro, 1 500 000). El tramo de 9 USD se retiró al pasar a Live.

`quipu-oprf-django` 0.1.0 está publicado en PyPI, así que la cadena está
completa: un cliente puede `pip install`, suscribirse y recibir su API key.

**Lo que falta ya no es fontanería: son clientes.** El blog tiene 15 entradas y
CERO menciones de OPRF, VOPRF o «contraseña» — el único producto con vía de
cobro no tiene contenido que lleve a él.

<!-- Lo de abajo es el estado del 2026-07-17 y se conserva por contexto
     histórico. NO refleja la realidad actual. -->

## Estado histórico (2026-07-17)

| Pieza | Estado |
|---|---|
| `quipu-oprf-server` en el VPS | **Vivo** — `https://oprf.xiliux.com/healthz` → 200 |
| Clave pública fijada | `88b623ccc00c9eac39f8e02a0f41851535dc2e196ed9836cad00f77644af214b` |
| Cliente instalable | **Sí, desde el 2026-07-17**: `pip install quipu-oprf-django` (Apache-2.0, arrastra `quipu-voprf` 0.2.1, NO el núcleo AGPL) |
| Conformidad | **RFC 9497** (ristretto255-SHA512), verificado contra los vectores del Apéndice A.1.2 |
| Capa de ventas (este repo) | Construida, probada en local, **sin credenciales de PayPal** |
| Página `/quipu/precios` | Muestra "Próximamente" hasta que `sales_ready()` sea True |

Fase de negocio: **beta**. La GA comercial espera la auditoría externa.

## El flujo

```
cliente en /quipu/precios
   └─> botón de Suscripción PayPal (SDK, intent=subscription)
        └─> PayPal cobra
             └─> webhook firmado -> POST /paypal/webhook
                  ├─ verify_webhook()  (firma verificada CONTRA LA API DE PAYPAL)
                  └─ handle_event()
                       ├─ ACTIVATED -> POST /admin/keys -> API key -> email al cliente
                       └─ CANCELLED/SUSPENDED/EXPIRED -> /admin/keys/<prefix>/deactivate
```

**El webhook no se fía del cuerpo del POST.** Sin firma válida devuelve 400 y no
aprovisiona nada; si no, cualquiera podría regalarse una API key con un `curl`.

## Los archivos

| Archivo | Rol |
|---|---|
| `quipu_sales.py` | Toda la lógica: planes, verificación de webhook, aprovisionamiento, email |
| `paypal_setup.py` | Alta **única** del producto + los 3 planes en PayPal; imprime los `PAYPAL_PLAN_*` |
| `main.py` | `@app.post('/paypal/webhook')`, `@ui.page('/quipu/precios')`, `@ui.page('/quipu/gracias')`, CTA en la sección Quipu |
| `subscriptions.json` | Mapa `sub_id -> {email, plan, prefix, active}`. **Necesario para poder desactivar al cancelar** (PayPal solo manda el sub_id). No versionar. |

`PLANS` en `quipu_sales.py` es la **única fuente de verdad**: alimenta la página,
el alta en PayPal y el mapeo webhook→plan. Las cuotas deben cuadrar con
`plans.rs` del servidor. Los precios (9/49/199 USD) son **placeholders**.

## Puesta en marcha

Falta solo la parte de PayPal (el servidor ya está desplegado).

1. **App en developer.paypal.com** → Client ID + Secret.
2. **Rellena el `.env`** (ver `.env.example`):
   ```
   PAYPAL_ENV=sandbox          # sandbox hasta validar el flujo entero
   PAYPAL_CLIENT_ID=...
   PAYPAL_SECRET=...
   OPRF_SERVER_URL=https://oprf.xiliux.com
   OPRF_ADMIN_TOKEN=...        # el QUIPU_OPRF_ADMIN_TOKEN del servidor
   ```
3. **Ajusta los precios** en `quipu_sales.PLANS` ANTES del paso 4 (el precio del
   plan de PayPal queda congelado al crearlo; cambiarlo obliga a crear planes nuevos).
4. `python paypal_setup.py` → copia los `PAYPAL_PLAN_*` que imprime al `.env`.
5. **Webhook** en PayPal → `https://xiliux.com/paypal/webhook`, eventos
   `BILLING.SUBSCRIPTION.*` → su ID va a `PAYPAL_WEBHOOK_ID`.
6. Despliega. La página pasa sola de "Próximamente" a botones de pago
   (`sales_ready()` = hay `PAYPAL_CLIENT_ID` + `OPRF_SERVER_URL` + `OPRF_ADMIN_TOKEN`).

Valida en **sandbox** de punta a punta (suscribirse → recibir el email con la key
→ cancelar → confirmar que la key queda inactiva) antes de `PAYPAL_ENV=live`.

## Notas de operación

- **Sin dependencias nuevas**: `urllib` (stdlib, con TLS) + el SMTP de Zoho que ya usa el portafolio.
- **Idempotencia**: `handle_event` sale si `get_sub(sub_id)` ya existe. PayPal
  reintenta los webhooks; sin esto, un reintento emitiría una segunda key.
- **Si el email falla**, la key ya está emitida y registrada: se recupera de
  `subscriptions.json` (el `prefix`, no el secreto — el secreto no se vuelve a
  mostrar, ni el servidor lo guarda). Habría que emitir una key nueva.
- **Desactivar ≠ revocar**: cancelar una suscripción desactiva (reversible).
- La clave OPRF `k` del servidor **no rota nunca**: rotarla invalida todos los
  secretos endurecidos de todos los clientes. Las API keys sí rotan libremente.

## Pendiente

- **Validar el flujo completo en sandbox** (nunca se ha ejecutado contra PayPal
  real). **Es lo único que ya bloquea el dinero**: el producto existe y es
  consumible; lo que no existe es un cobro que haya completado alguna vez.
- Decidir precios definitivos.
- **Express y Go siguen sin publicar** y siguen AGPL: sus paquetes empaquetan
  `libquipu_capi` con las 12 funciones del núcleo. Necesitan un C ABI solo-VOPRF
  y sus paquetes aparte. No bloquean la primera venta: Django ya es un producto
  completo.
- Mientras tanto el cliente usa **los bindings directamente**, y ese camino
  llevaba un defecto real hasta el 2026-07-16: `oprfHarden` (Node) y `OprfHarden`
  (Go) pedían la clave pública al servidor si el cliente la omitía. Eso vuelve
  decorativa la prueba DLEQ — el servidor entrega la clave contra la que se le
  verifica — y encima Go no tenía timeout, así que una red muda colgaba un login
  para siempre. Corregido: la clave es obligatoria y hay dos errores distintos
  (no disponible = reintenta; rechazado = investiga). **Sin publicar todavía**,
  así que un cliente que instale desde npm/Go hoy se lleva la versión con el
  defecto. Si ya hay alguno, hay que avisarle al publicar.
