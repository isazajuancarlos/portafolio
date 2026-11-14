"""Alta ÚNICA de los planes de suscripción en PayPal.

Crea un Product y un Billing Plan mensual por cada plan de `quipu_sales.PLANS`,
e imprime los IDs (P-XXXX) que debes pegar en el .env como PAYPAL_PLAN_*.

Uso (con las credenciales ya en el .env):
    python paypal_setup.py

Requiere PAYPAL_CLIENT_ID / PAYPAL_SECRET / PAYPAL_ENV. Ejecútalo una sola vez
(o de nuevo si cambias precios: creará planes nuevos y tendrás que actualizar los
IDs en el .env; los planes viejos se pueden desactivar desde el panel de PayPal).
"""

import sys

from dotenv import load_dotenv

load_dotenv()

import quipu_sales as qs  # noqa: E402  (tras load_dotenv para leer el .env)


def _post(path, token, payload, extra_headers=None):
    headers = {"Authorization": f"Bearer {token}"}
    if extra_headers:
        headers.update(extra_headers)
    return qs._http_json("POST", f"{qs.PAYPAL_API}{path}", headers=headers, data=payload)


def main():
    if not (qs.PAYPAL_CLIENT_ID and qs.PAYPAL_SECRET):
        sys.exit("Faltan PAYPAL_CLIENT_ID / PAYPAL_SECRET en el .env")
    print(f"Entorno PayPal: {qs.PAYPAL_ENV}  ({qs.PAYPAL_API})")

    token = qs._paypal_token()
    if not token:
        sys.exit("No se pudo obtener token de PayPal (revisa credenciales/entorno).")

    # 1) Producto (uno para todo el servicio).
    status, prod = _post(
        "/v1/catalogs/products",
        token,
        {
            "name": "Quipu OPRF Hardening",
            "description": "Endurecimiento de contraseñas con VOPRF (rate-limit online).",
            "type": "SERVICE",
            "category": "SOFTWARE",
        },
    )
    if status not in (200, 201):
        sys.exit(f"Error creando el producto: {status} {prod}")
    product_id = prod["id"]
    print(f"Producto creado: {product_id}\n")

    # 2) Un plan mensual por cada tier.
    print("Pega esto en tu .env:\n")
    for plan in qs.PLANS:
        status, res = _post(
            "/v1/billing/plans",
            token,
            {
                "product_id": product_id,
                "name": f"Quipu OPRF — {plan['name']}",
                "description": f"{plan['quota']} evaluaciones/mes",
                "billing_cycles": [
                    {
                        "frequency": {"interval_unit": "MONTH", "interval_count": 1},
                        "tenure_type": "REGULAR",
                        "sequence": 1,
                        "total_cycles": 0,  # 0 = indefinido
                        "pricing_scheme": {
                            "fixed_price": {
                                "value": plan["price"],
                                "currency_code": "USD",
                            }
                        },
                    }
                ],
                "payment_preferences": {
                    "auto_bill_outstanding": True,
                    "setup_fee_failure_action": "CONTINUE",
                    "payment_failure_threshold": 2,
                },
            },
            extra_headers={"Prefer": "return=representation"},
        )
        if status not in (200, 201):
            print(f"  ⚠ {plan['name']}: error {status} {res}")
            continue
        print(f"  {plan['plan_env']}={res['id']}")

    print("\nListo. Luego crea el webhook en developer.paypal.com apuntando a")
    print("  https://xiliux.com/paypal/webhook")
    print("suscrito a los eventos BILLING.SUBSCRIPTION.* y copia su ID en")
    print("  PAYPAL_WEBHOOK_ID=...")


if __name__ == "__main__":
    main()
