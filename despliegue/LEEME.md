# despliegue/ — la constancia del vhost de xiliux.com

`xiliux.com.nginx` es **copia EXACTA, byte a byte**, de
`/etc/nginx/sites-available/xiliux` en el VPS, traída el 2026-08-19 con `scp`.
Que sea exacta es el punto: así comparar es un `diff` y no un juicio.

```sh
scp debian@192.99.42.108:/etc/nginx/sites-available/xiliux /tmp/vivo
diff /tmp/vivo /mnt/data/portafolio/despliegue/xiliux.com.nginx && echo "sin deriva"
```

**No es el origen.** Nada despliega desde aquí: el origen sigue siendo el
servidor. Mientras siga así, esta copia envejece en cuanto alguien edite en
caliente —que, según `conocimiento/despliegue/VPS.md`, pasa más de lo que uno
cree—. Lo que sí resuelve es lo que no había: algo con qué comparar, y una
copia si la máquina se pierde. Es el hallazgo 2 de la auditoría #V3.

La aplicación es el proceso NiceGUI de `main.py`, en `127.0.0.1:8080`.

## Por qué este vhost NO lleva `limit_req` — y la corrección de cómo se midió

Se propuso ponerle un freno (hallazgo 3 de la auditoría #V3). **No se pone**, y
el motivo bueno no es el que escribí primero.

**Lo que escribí y NO se sostiene:** «en 24 h el tráfico de xiliux.com y
abogadoisaza.com fue de 657 segundos con 1 petición, 59 con 2 y cuatro por
encima de 3». Esa cifra salió de un `grep` por el nombre del dominio sobre el
`access.log`, y **el `access.log` usa el formato `combined`, que no guarda el
host pedido** (comprobado el 2026-08-19 leyendo `log_format` en `nginx.conf`).
Lo que el `grep` casaba era el campo *referer* — o sea el barrido de WordPress,
que se autorrefiere. Medí una cosa y afirmé otra.

**El motivo que sí se sostiene, y es más fuerte:** no se puede fijar un umbral
por dominio porque **hoy no se puede medir el tráfico por dominio**. Poner un
`limit_req` con un número que no se puede probar contra el cliente legítimo es
cerrar por si acaso. Y lo que se quería frenar tiene ya su herramienta:

- el barrido son **2 067 peticiones `.php` en 24 h**, y todas se llevan un 404,
  un 301 o un 444 — esta máquina **no tiene PHP instalado**, así que no hay a
  qué llegar y servir esos 404 no cuesta nada;
- desde el 2026-08-19 la jaula `nginx-botsearch` de fail2ban **sí los caza**
  (antes casaba 12 líneas de 2 345; ahora, 2 342), que es la herramienta
  adecuada: banea al que insiste en vez de estrechar a todo el mundo.

**Y desde el 2026-08-19 ese número SÍ se puede medir**: `nginx.conf` lleva
`$host` en el `log_format`. La decisión sobre el freno se puede rehacer con
datos cuando haya unos días de registro con el formato nuevo — hoy no los hay,
y con eso a la vista sigue sin ponerse. (El `sdk.log` de este mismo vhost es la
excepción: no nombra formato, así que sigue sin host. Ahí da igual, porque solo
lo escribe xiliux.com.)

## `location /verificar/` — copia propia del verificador de tunjo (2026-10-12)

`xiliux.com/verificar/` sirve, **estático por nginx** (no por la app), una copia
del kit del verificador WASM de tunjo. Es la «copia propia» de la decisión 0009:
anuncia la herramienta GRATIS en el lado Xiliux **sin enlazar a la marca jurídica**
(el mismo kit también vive en `verificar.abogadoisaza.com`, pero las dos copias no
se enlazan entre sí). El vhost apunta `alias /var/www/xiliux-verificar/` y **no
lleva `add_header`** a propósito, para heredar la CSP del vhost —que con
`script-src ... 'unsafe-eval'` deja correr el WASM— y servir `.wasm` como
`application/wasm` (está en `mime.types`).

**El origen del kit es `/mnt/data/tunjo/sitio/`** (no este repo). Re-subir la copia
cuando el kit cambie (desde `tunjo/sitio/`, lista blanca segura = rastreados ∪
artefactos del build, para no publicar un `*.clave`/`acta*.json` git-ignored):

```bash
cd /mnt/data/tunjo/sitio && bash ../verificador-wasm/construir.sh
M=$(mktemp -d)
while IFS= read -r r; do mkdir -p "$M/$(dirname "$r")"; cp "$r" "$M/$r"; done \
  < <(git ls-files -- index.html app.js xiliux-logo.webp verificador ejemplo)
for a in verificador/verificador_wasm.js verificador/verificador_wasm_bg.wasm; do cp "$a" "$M/$a"; done
tar -C "$M" -cf - . | ssh debian@192.99.42.108 '
  set -e; D=/var/www/xiliux-verificar
  sudo rm -rf $D.nueva && sudo mkdir -p $D.nueva && sudo tar -C $D.nueva -xf - --no-same-owner
  sudo chown -R root:root $D.nueva && sudo find $D.nueva -type f -exec chmod 0644 {} + && sudo find $D.nueva -type d -exec chmod 0755 {} +
  sudo rm -rf $D && sudo mv $D.nueva $D'
rm -rf "$M"
```
Verificar: `curl -s -o /dev/null -w '%{http_code} %{content_type}\n' https://xiliux.com/verificar/verificador/verificador_wasm_bg.wasm` → `200 application/wasm`.
