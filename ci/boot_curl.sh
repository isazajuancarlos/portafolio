#!/usr/bin/env bash
# CI de portafolio: arranca el binario real y le habla como el mundo (D28).
# portafolio no tiene banco de pruebas; esta es su verificación real. Se corre
# con `verde_local.py portafolio` (lee el `run:` que lo invoca desde ci.yml) o
# directo con `bash ci/boot_curl.sh`. Sale != 0 si algo falla.
set -euo pipefail
cd "$(dirname "$0")/.."
BASE="http://127.0.0.1:8080"

# El binario ata 8080 en duro. Si algo lo ocupa, no lo matamos a ciegas: fallamos
# claro. En un entorno de CI limpio el puerto está libre.
if ss -ltn 2>/dev/null | grep -q ':8080 '; then
  echo "FALLO: el puerto 8080 está ocupado; libéralo antes de correr el CI"; exit 1
fi

.venv/bin/python main.py >/tmp/ci_portafolio_srv.log 2>&1 &
SRV=$!
trap 'kill "$SRV" 2>/dev/null || true' EXIT

# esperar al puerto con TOPE (D39: ningún until sin límite)
fin=$(( $(date +%s) + 40 ))
until curl -sf -o /dev/null "$BASE/"; do
  if [ "$(date +%s)" -gt "$fin" ]; then
    echo "FALLO: el servidor no abrió en 40 s"; cat /tmp/ci_portafolio_srv.log; exit 1
  fi
  sleep 1
done

fail=0
# Cuenta palabras del CUERPO VISIBLE: quita el CONTENIDO de <script>/<style>
# (si no, el texto del JSON-LD se cuela y una página client-render con JSON-LD
# gordo pasaría el umbral — mediría el códec, no el cuerpo, directiva 16).
palabras_en() {
  curl -s "$BASE$1" | .venv/bin/python -c \
"import sys,re,html; h=sys.stdin.read(); b=re.sub(r'<(script|style)\b[^>]*>.*?</\1>',' ',h,flags=re.S|re.I); print(len(html.unescape(re.sub(r'<[^>]+>',' ',b)).split()))"
}

echo "== rutas (200) =="
for u in / /blog /en /informes /servicios /quipu /cotizador /quipu/precios /project/1 /privacidad; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE$u")
  if [ "$code" = 200 ]; then echo "  ok  $u"; else echo "  FALLO $u -> $code"; fail=1; fi
done

echo "== la portada sirve contenido, no la cáscara WebSocket (guarda la regresión de las 27 palabras) =="
p=$(palabras_en /)
echo "  palabras en / : $p"
if [ "$p" -lt 200 ]; then echo "  FALLO: portada con $p palabras (<200): regresión a client-render"; fail=1; fi

echo "== formularios y sitemap =="
if [ "$(curl -s "$BASE/" | grep -c 'class="lead-form"')" -ge 2 ]; then echo "  ok  2 formularios"; else echo "  FALLO: faltan formularios en /"; fail=1; fi
if curl -s "$BASE/sitemap.xml" | grep -q '<loc>https://xiliux.com/</loc>'; then echo "  ok  sitemap incluye la portada"; else echo "  FALLO: sitemap sin la portada"; fail=1; fi

echo "== regresión de seguridad: la inyección de cabeceras se rechaza (sin enviar correo) =="
inj=$(curl -s -o /dev/null -w '%{redirect_url}' -X POST "$BASE/contacto" \
  --data-urlencode $'nombre=x\r\nBcc: t@t.com' --data-urlencode 'email=a@b.com' --data-urlencode 'mensaje=x')
case "$inj" in
  *ok=error*) echo "  ok  inyección rechazada" ;;
  *) echo "  FALLO: inyección de cabecera NO rechazada ($inj)"; fail=1 ;;
esac

if [ "$fail" -eq 0 ]; then echo "VERDE"; else echo "ROJO"; fi
exit "$fail"
