# BORRADOR — bloque de anclaje para /informes

Para revisión de Juan. **No desplegado.** Va en `main.py`, dentro de
`informes_producto()`, justo **antes** de la sección `<h2>Hablemos</h2>`.

Las cifras salen de `informes/analisis_precios_secop.py` sobre SECOP II
(dataset `jbjy-vk9h`), universo completo. Ver `informes/ANCLAJE_PRECIOS.md`.

---

## Por qué este bloque, y por qué ahí

La página describe muy bien QUÉ hace el producto y CÓMO se cobra, pero no da
ninguna **referencia de valor**. Un comprador público que lee «el precio depende
de cuántas obligaciones administra» no tiene con qué comparar, y lo que hace
entonces es compararlo con cero — con seguir en la hoja de cálculo.

El anclaje correcto no es otro software: es **lo que la entidad ya paga hoy**
por resolver el mismo problema a mano.

## Lo que NO propongo poner, y merece explicación

Medí que el **85% de estas compras entra por contratación directa**, exenta de
RUP por el artículo 6 de la Ley 1150 de 2007. Es un dato útil y verdadero.

**No va en la página pública.** Decirle a una entidad por qué modalidad debería
contratar es orientación en contratación estatal, y eso es asesoría — justo la
línea que la práctica jurídica y Xiliux mantienen separada. Ese dato sirve en
una conversación comercial, donde se responde a una pregunta concreta de la
entidad, no como argumento de venta en una página de producto.

---

## El bloque

```html
<h2>Cuánto cuesta, comparado con qué</h2>
<p>Hoy ese seguimiento lo hace una persona. En la contratación pública
colombiana, un profesional contratado para el monitoreo y seguimiento de
informes cuesta una <strong>mediana de $54,8 millones al año</strong> — medido
sobre 3.360 contratos reales de SECOP&nbsp;II, normalizados a doce meses.</p>

<p><strong>La licencia perpetua más completa de Informes cuesta lo mismo que uno
de esos años.</strong> Y es perpetua: al año siguiente ya no vuelve a pagarse.</p>

<p>No sustituye a esa persona — sigue haciendo falta quien decida, revise y
responda. Le quita el trabajo que no debería estar haciendo: rastrear treinta
vencimientos en una hoja de cálculo y acordarse de todos.</p>

<p class="fuente">Fuente: SECOP&nbsp;II, datos abiertos de Colombia Compra
Eficiente. Análisis reproducible; las cifras se recalculan contra la fuente y no
están escritas a mano.</p>
```

---

## Tres decisiones de redacción que quiero justificar

**1. Se cita la fuente y el número de contratos.** Un comprador público conoce
SECOP y puede comprobarlo. Una cifra sin origen, en cambio, se lee como
argumento de vendedor y resta en vez de sumar.

**2. Se dice explícitamente que NO sustituye a la persona.** Es verdad, y además
es lo que evita la objeción más previsible: quien lea que un software reemplaza
a su analista deja de leer. Reconocer el límite hace creíble lo que sí hace.

**3. No se publican los precios.** La página ya decide no listarlos y me parece
correcto: con un anclaje y sin lista, el precio se conversa desde una referencia
que el comprador acepta, en vez de anclarse en el número más bajo de una tabla.

---

## Si prefieres una versión más corta

```html
<h2>Cuánto cuesta, comparado con qué</h2>
<p>Un profesional contratado en Colombia para el seguimiento de informes de
obligatorio cumplimiento cuesta una <strong>mediana de $54,8 millones al año</strong>
(3.360 contratos de SECOP&nbsp;II). <strong>La licencia perpetua de Informes
cuesta lo mismo que uno de esos años</strong>, y no se vuelve a pagar.</p>
```
