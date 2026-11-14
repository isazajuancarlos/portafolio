# Inventario de datos personales — Xiliux / Quipu OPRF

Levantado del código el 2026-07-17. **Son los hechos técnicos, no la política**:
la redacción legal, la base de licitud y los plazos los pone Juan.

Existe por dos razones que aparecieron el mismo día: LinkedIn exige una política
de privacidad publicada para dar acceso a la Community Management API, y el
portafolio empezó a tratar datos personales en cuanto se crearon los planes de
PayPal.

## Qué se trata, dónde y quién lo escribe

### 1. `subscriptions.json` — VPS, plano de control (portafolio)

Escrito por `quipu_sales._record_sub()`, disparado por el webhook de PayPal.

| Campo | Contenido | Personal |
|---|---|---|
| *clave* | `sub_id` de PayPal | Identificador indirecto |
| `email` | Email del suscriptor, **lo entrega PayPal** | **Sí** |
| `plan` | `beta` / `starter` / `pro` | No, pero perfila |
| `prefix` | Prefijo de la API key (no el secreto) | No |
| `active` | Bool | No |

### 2. SQLite del `quipu-oprf-server` — VPS, plano de datos

Esquema en `crates/quipu-oprf-server/src/store.rs`.

| Tabla | Campos | Personal |
|---|---|---|
| `customer` | `id`, `email`, `plan`, `provider_ref`, `created_at` | **Sí — el email** |
| `api_key` | `prefix`, `key_hash`, `active`, `quota_monthly`, `expires_at`, `created_at`, `last_used_at`, `revoked_at` | `last_used_at` revela actividad |
| `usage` | `key_id`, `period`, `count` | Volumen de uso por cliente |

**El email está duplicado en los dos almacenes.** Un borrado tiene que tocar
ambos, y hoy no hay ningún camino que lo haga.

### 3. Terceros

| Tercero | Qué ve | Por qué |
|---|---|---|
| **PayPal** | Datos de pago completos. Es el **origen** del email. | Cobra la suscripción |
| **Zoho** (`smtp.zoho.com`) | El email del cliente y **la API key en claro**, en tránsito | Envía la key recién emitida |

## Lo que NO se trata, y es el argumento del producto

**El servidor OPRF no ve nunca las contraseñas de los usuarios finales de un
cliente, ni los secretos endurecidos.** No es una promesa de política: es la
construcción. El cliente ciega el elemento antes de enviarlo (RFC 9497,
ristretto255-SHA512); el servidor lo evalúa sin aprender ni la entrada ni la
salida. Aunque el VPS estuviese comprometido entero, ahí no hay contraseñas que
robar.

Tampoco se guarda el secreto de la API key: `api_key.key_hash` es un hash. Por
eso una key perdida no se recupera, se reemite.

## Huecos, para que la política no mienta

Ninguno es un fallo del código: son decisiones que nadie ha tomado todavía.

1. **No hay plazo de conservación.** Ni en `subscriptions.json` ni en SQLite.
   Un cliente que cancele en 2026 sigue con su email en los dos en 2030.
2. **No hay camino de supresión.** Cancelar marca `active = false`
   (`_mark_inactive`); no borra nada. Desactivar ≠ suprimir.
3. **No hay base de licitud declarada** en ninguna parte de la web.
4. **La API key viaja en claro por email.** Es la práctica común, pero conviene
   decirlo en vez de que se descubra.
5. **`subscriptions.json` no está cifrado** en el VPS y contiene los emails de
   todos los suscriptores en un fichero plano.

## Pendiente

- Publicar `/privacidad` en xiliux.com (no existe la ruta; `main.py` solo define
  `/`, `/blog`, `/blog/{slug}`, `/project/{p_id}`, `/quipu/precios`,
  `/quipu/gracias`).
- Decidir plazo de conservación e implementar la supresión en **los dos**
  almacenes.
- Sin `/privacidad` publicada, la solicitud de Community Management API de
  LinkedIn se rechaza — y LinkedIn no deja reintentar con la misma app.
