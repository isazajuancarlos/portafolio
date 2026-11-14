# Clúster Negocios Digitales — material para Xiliux

Preparado el 2026-07-22 para la invitación de la Cámara de Comercio de Medellín:
formulario de caracterización + espacio de relacionamiento con presentación de
portafolio (~20 min).

**Todo lo que va aquí está comprobado contra los servicios reales**, no citado de
memoria. Lo verificado, con fecha:

| Afirmación | Comprobación |
|---|---|
| `oprf.xiliux.com` está en producción | `/healthz` → 200 `ok`; `/v1/public-key` y `/v1/plans` responden |
| `quipu-crypto` publicado | PyPI, versión **0.9.1** |
| `quipu-voprf` publicado | PyPI, versión **0.2.1** |
| `xiliux.com` en línea | 200, con `/quipu`, `/informes`, `/servicios` y `/blog` |
| Planes del OPRF | starter 250 000 evaluaciones/mes · 79 USD; pro 1 500 000 · 299 USD |

> Si algo de esto cambia antes de la reunión, **vuelve a comprobarlo**. Decir en
> una sala lo que no se sostiene con una URL cuesta más que no decirlo.

---

## 0. Lo que te va a frenar en el formulario

**Xiliux no es persona jurídica.** Es marca, no sociedad. Cuando el formulario
pida razón social y NIT:

- **Razón social**: tu nombre como persona natural, `Juan Carlos Isaza`.
- **Nombre comercial / marca**: `Xiliux`.
- **NIT**: tu RUT como persona natural.

No lo dejes en blanco ni inventes una sociedad. Un clúster que te registra como
empresa inexistente te lo va a preguntar en el primer contrato, y esa
conversación es peor tenerla después.

**El NIT lleva dígito de verificación.** Es la cédula más el DV del RUT
(`1.234.567-8`), no el número pelado: muchos formularios lo validan, y el DV es
lo que distingue «cédula» de «NIT» para quien lo procesa.

**Si el formulario trae dos campos**, no repitas Xiliux en los dos: razón social
el nombre propio, nombre comercial Xiliux. Si solo hay uno, va **Xiliux** — es
lo que queda en el directorio.

**El cruce que van a hacer**: la Cámara comprueba el NIT contra su matrícula
mercantil. Si Xiliux no está matriculado como establecimiento de comercio, el
nombre no coincidirá con nada en su registro y lo preguntarán en el seguimiento.
La respuesta es sencilla —se opera como persona natural bajo la marca Xiliux—,
pero conviene tenerla preparada y no improvisarla.

Consecuencia normal de todo esto: la factura y el contrato dirán *Juan Carlos
Isaza Arenas* mientras el directorio dice *Xiliux*.

Si el formulario **exige** persona jurídica y no admite persona natural, eso es
una decisión de negocio —constituir o no— que no se toma llenando un formulario.
Escríbeles y pregunta; los clústeres suelen admitir persona natural.

---

## 1. Respuestas del formulario

Los formularios de caracterización de clúster piden casi siempre estos campos.
Ajusta el orden al que te salga.

### Cargo
> Fundador

Ni «Gerente» —chirría en cuanto alguien mira que no hay persona jurídica— ni,
sobre todo, **«Abogado»**: es el reflejo natural al rellenar un formulario, y en
ese directorio te clasifica de forma permanente en la casilla equivocada. Si
prefieres que Xiliux se lea como firma de servicios y no como producto propio,
«Director»; pero entonces, consistente en toda la presentación.

### Sector / actividad
> Desarrollo de software a la medida y productos propios de infraestructura
> criptográfica y cumplimiento normativo.

### Código CIIU
> **6201** — Actividades de desarrollo de sistemas informáticos
> (planificación, análisis, diseño, programación, pruebas).

Si admite varios: `6201` principal, más `5820` (edición de software) y `6311`
(procesamiento y hosting) como secundarios — son Quipu/**SIGER** y el OPRF.

`5820` **solo** sería el principal si el negocio fuera licenciar producto
empaquetado. Hoy no lo es: **SIGER** no tiene primer cliente y el OPRF es
suscripción. Describiría la empresa que quieres ser, no la que eres, y en un
directorio eso trae las conversaciones equivocadas.

**Manda el RUT.** Si la actividad económica principal registrada allí es otra de
esta lista, va esa: la Cámara cruza el registro igual que con el NIT, y una
discrepancia hay que explicarla.

### ¿A qué se dedica la empresa? (descripción corta)
> Xiliux construye software donde el error es caro: criptografía post-cuántica y
> sistemas de cumplimiento de obligaciones de reporte. Trabajamos sobre producto
> propio y sobre desarrollo a la medida para entidades que necesitan que el dato
> sea correcto y demostrable, no solo que la pantalla funcione.

### ¿Cuáles son sus principales productos/servicios?

**El orden es el mismo que el de la presentación: primero lo que CONECTA,
después lo que impresiona.** Quien lee esto en la Cámara es quien decide con
quién te sientan. Abriendo con criptografía post-cuántica te clasifican como
caso raro y no te sientan con nadie; abriendo con «desarrollo a la medida» te
meten en el montón con doscientas fábricas de software. **SIGER** es lo único
que hace las dos cosas: todos tienen el problema y casi nadie la solución.

**Versión corta**, si la caja es pequeña:

> Sistemas de cumplimiento de obligaciones de reporte: **SIGER** programa,
> vigila y audita lo que una entidad debe entregar —qué, cuándo vence, quién
> responde y si se cumplió—, calculando los plazos contra el calendario legal.
> Desarrollo de software a la medida para entidades donde el dato tiene que ser
> correcto y demostrable. Y producto propio de criptografía post-cuántica
> (Quipu, publicado en PyPI) con un servicio de derivación de claves en la nube
> conforme al RFC 9497.

**Versión larga**, si es un cuadro amplio:

**1. SIGER — cumplimiento de obligaciones de reporte.**
> Programa, vigila y audita las obligaciones periódicas de una organización: qué
> se debe entregar, cuándo vence, quién responde y si se cumplió. Calcula los
> vencimientos contra el calendario legal —días hábiles, festivos, plazos de
> gracia— y deja constancia firmada de cada entrega.

**2. Desarrollo de software a la medida.**
> Aplicaciones, integraciones y automatización para entidades donde el error es
> caro: se entrega lo que está comprobado, y se dice qué no lo está.

**3. Quipu — criptografía post-cuántica.**
> Producto propio en Rust, con enlaces para Python, Node, Go y C. Combina
> algoritmos clásicos con los estandarizados por el NIST frente a computación
> cuántica (ML-KEM-1024, ML-DSA-87), el mismo mandato que exige la CNSA 2.0 de
> Estados Unidos. Software libre (AGPL-3.0) con licencia comercial disponible;
> distribuido en PyPI.

**4. Quipu OPRF — servicio en la nube.**
> Derivación de claves conforme al RFC 9497, en producción en
> `oprf.xiliux.com`, por suscripción mensual. Permite endurecer contraseñas y
> credenciales sin que el servidor conozca nunca el dato del cliente.

### Sectores con mayor experiencia / donde comercializa

> **Salud.** Sistemas de información clínica y reporte regulatorio: historia
> clínica electrónica, gestión de citas y pacientes, y generación de RIPS con
> trazabilidad de auditoría conforme a la Ley 1581 de 2012, sobre arquitectura
> multi-institucional.
>
> **Sector público y entidades territoriales.** Administración de las
> obligaciones periódicas de reporte de una entidad pública: el catálogo
> completo de informes, sus responsables, sus vencimientos y su cumplimiento
> frente a entes de control.
>
> **Transversal a cualquier sector regulado.** Toda organización con reportes
> recurrentes a superintendencias, ministerios, casas matrices o clientes.
>
> En comercialización activa: el servicio Quipu OPRF por suscripción y el
> desarrollo a la medida.

Los dos sectores son los únicos sostenibles con algo delante: salud lo respalda
un sistema construido (RIPS, CIE-11, aislamiento por institución) y público lo
respalda la base real de la que salió **SIGER** —399 obligaciones de una
entidad que opera—.

La última línea separa **experiencia** de **comercialización** a propósito:
**SIGER** no tiene primer cliente privado, y «comercializando en salud» sería
adelantar un hecho. Si preguntan, «está construido y busco el primero» deja
mejor parado que una media verdad que se cae en la segunda pregunta.

**Fuera de la lista, a propósito:** financiero (es el alfa, no se vende: listarlo
trae reuniones donde no hay nada que enseñar) y jurídico. Este último es el
tentador, porque «salud + regulación + cumplimiento» pide decir que eres
abogado — y en esa sala eso te convierte en consultor, no en proveedor.

Un sector listado es un sector donde te van a sentar. Ninguno donde haya que
improvisar.

### ¿Cuál es tu interés en acercarte a nosotros?

Es el campo que decide **con quién te sientan**: los demás describen, este pide.
«Networking y sinergias» —lo que escribe todo el mundo— lleva a la mesa
genérica.

> Tengo un producto construido y busco las primeras organizaciones que lo pongan
> a prueba. **SIGER** administra las obligaciones periódicas de reporte —lo que
> hoy vive repartido entre hojas de cálculo, correos y la memoria de alguien— y
> calcula los vencimientos contra el calendario legal. No hay empresa en el
> clúster que no tenga ese problema; me interesa encontrar dos o tres que
> quieran resolverlo bien.
>
> En la otra dirección: opero como equipo pequeño y muy especializado, así que
> no compito con las firmas de desarrollo grandes de la región — puedo
> complementarlas. Aporto profundidad en criptografía, cumplimiento normativo y
> arquitectura de datos en los proyectos donde eso decide el resultado, y busco
> justamente esas alianzas.
>
> También puedo aportar contenido al ecosistema. Trabajo con criptografía
> post-cuántica y tengo producto propio publicado; es una conversación que a la
> región le conviene tener ahora y no dentro de cinco años, cuando el estándar
> ya sea exigible.

Qué hace cada párrafo:

1. **Pide algo concreto.** «Dos o tres organizaciones» se puede atender;
   «clientes» no. Y describe el problema en los términos en que ellos lo viven.
2. **Desactiva la amenaza.** En un clúster hay firmas grandes, y el reflejo ante
   uno nuevo es «viene a competir». Decir que complementas abre esas puertas, y
   además es cierto: no puedes tomar un proyecto de veinte personas, y ellos no
   tienen a nadie que sepa de criptografía.
3. **Te vuelve útil para ellos.** Un clúster necesita miembros que traigan
   contenido a las charlas, no solo que asistan. Eso te mete en la programación,
   que es donde se ve un portafolio sin pagar por el espacio.

Está escrito con el marco que ellos usaron en el correo —«aunque compiten,
también cooperan»—, devuelto. Se nota, y para bien.

### Cliente objetivo
> Entidades públicas y empresas medianas con carga regulatoria: salud, servicios
> públicos, financiero, y cualquier organización con reportes recurrentes a
> superintendencias o ministerios.

### Sitio web
> https://xiliux.com

### ¿Alguna sugerencia o comentario adicional?

La mayoría lo deja en blanco. Es el único sitio donde se puede matar por
adelantado una conversación incómoda.

> Dos apuntes prácticos. El primero: opero como persona natural bajo la marca
> Xiliux, de modo que el NIT registrado es el de persona natural — lo aclaro de
> una vez por si el cruce con el registro mercantil genera dudas.
>
> El segundo: para el espacio de relacionamiento llevo el producto listo para
> demostrarlo funcionando, no diapositivas. Si es posible me sirve sala con
> proyección o pantalla compartida. Quedo atento a las fechas.

- **Desactiva el seguimiento incómodo.** Van a cruzar el NIT contra la matrícula
  mercantil. Si no coincide y no lo habías dicho, la llamada empieza con «oiga,
  una duda…». Dicho de antemano, no hay llamada — y lees como alguien que sabe
  cómo funciona el registro, que en una Cámara de Comercio no sobra.
- **Pide la pantalla y anuncia la demostración de una vez.** Sin pantalla no hay
  demostración; y quien organiza toma nota de que vas a demostrar en vivo
  mientras los demás llevan diapositivas.

---

## 2. Los 20 minutos

**Un solo producto con demostración, y el resto como prueba de profundidad.**
Un portafolio que enseña tres cosas no vende ninguna. Todos los asistentes
tienen el problema de **SIGER**; casi ninguno tiene el de Quipu — pero Quipu es
lo que explica por qué deberían creerte.

| Min | Qué | Objetivo |
|---|---|---|
| 0–2 | **Quién eres, en una frase.** «Construyo software donde el error es caro.» | Que no te confundan con una fábrica de apps |
| 2–5 | **El problema, con una pregunta a la sala.** «¿Cuántos informes periódicos debe entregar su organización al año, y quién lo sabe con certeza?» | Que el problema lo digan ellos |
| 5–12 | **Demostración en vivo de **SIGER**** (guion abajo) | Que vean funcionando lo que acabas de describir |
| 12–15 | **Por qué esto es difícil.** El día que vence y el día que se entrega no son lo mismo; un festivo cambia el plazo; «el día 30» no existe en febrero | Que entiendan que la hoja de cálculo no lo resuelve |
| 15–17 | **La prueba de profundidad.** Quipu en PyPI, el OPRF en producción, criptografía alineada con el estándar del NIST | Credibilidad técnica, sin venderlo |
| 17–20 | **Qué buscas y cómo seguir.** Una frase concreta, no «hablemos» | Que salgan sabiendo qué hacer contigo |

### La pregunta que abre la sala
No empieces con lo que haces. Empieza con:

> «Levante la mano quien sepa, ahora mismo y sin consultar, cuántos informes
> periódicos debe entregar su organización este mes.»

Nadie la levanta. Ese silencio es tu presentación.

---

## 3. Guion de la demostración (7 minutos)

Sobre la instancia local con datos ficticios: 276 informes, ~3 900 entregas.

**Arrancar antes de entrar a la sala**, no delante de ellos:

```bash
cd /mnt/data/informes
DATABASE_URL="sqlite:///./informes_local.db" DEPLOYMENT_PROFILE=standalone \
  .venv/bin/python main.py
```

Abrir `http://localhost:8003`, entrar, y **dejarlo abierto**. Si el equipo se
suspende a mitad de la demostración, se acabó la demostración.

1. **La lista** (30 s). 276 informes. «Esto es una entidad real, con los nombres
   cambiados. Nadie tenía esto en un solo sitio.»

2. **Mis Pendientes** (1 min). Lo que vence. Busca **«Registro de Contratos
   Vigentes»**, que dice —comprobado en los datos cargados—:

   > vence **jueves 1 de enero de 2026** · entregar antes de **miércoles 31 de
   > diciembre de 2025**

   Párate ahí, es el mejor momento de la demostración: «el informe de enero de
   2026 hay que entregarlo en diciembre de 2025. El vencimiento no se movió —lo
   fija la norma—; lo que se adelanta es la entrega, porque el 1 de enero no
   trabaja nadie. Son dos fechas distintas, y un sistema que las confunde hace
   que ese informe pertenezca al año anterior **y desaparezca del calendario de
   2026**.»

   Hay 45 entregas ajustadas en los datos por si esa no aparece; otra buena es
   «Monitoreo de Presupuesto Ejecutado», que vence el sábado 31 de enero y se
   entrega el viernes 30.

3. **Crear un informe** (3 min). Es el corazón. Abre el asistente del cronograma
   y marca **un solo día: el lunes 7 de septiembre de 2026**. La fecha no es
   casual — comprobado, produce estas ocho lecturas y ninguna otra:

   > todos los días desde esa fecha · todas las semanas, lunes · cada dos
   > semanas, lunes · el día 7 de cada mes · el 1º lunes de cada mes · **el 5º
   > día hábil de cada mes** · cada 7 de septiembre · solo esa fecha

   «Marqué un lunes. Eso puede ser ocho obligaciones distintas, y la marca es
   idéntica en las ocho. El sistema no adivina, porque adivinar sería inventarle
   la obligación al cliente.»

   Elige **«el 5º día hábil de cada mes»**: es la forma más frecuente en la
   norma colombiana —«dentro de los primeros cinco días hábiles del mes
   siguiente»— y **no se puede expresar con un calendario corriente**: si el mes
   empieza en festivo, el 5º hábil es el 8, no el 5. Ahí es donde se ve que esto
   no es un recordatorio.

   > Otras fechas dan el 3º o el 4º día hábil, que es menos reconocible. Si vas
   > a cambiar la fecha de la demostración, comprueba antes qué lecturas produce.

4. **La ficha** (1 min). «Los campos los define cada entidad. No traemos una
   plantilla de otro cliente.»

5. **Cerrar** (1 min). «Cada entrega queda firmada criptográficamente, y esa
   firma se puede verificar años después sin confiar en nosotros.»

### Si algo falla
Dilo y sigue. «Esto está en desarrollo activo y hoy no me acompañó» cuesta
mucho menos que fingir. La sala perdona un fallo; no perdona que la engañen.

---

## 4. Lo que NO se menciona

**La práctica jurídica.** Ni de pasada.

En una sala de negocios digitales, «abogado que también programa» te convierte
en freelance de software a ojos de quien podría darte un mandato — y el mandato
vale más. Si alguien pregunta por contratación tecnológica o protección de
datos, la respuesta es que lo tienes cubierto y lo hablan aparte. Fuera de esa
sala y por otro canal.

**No prometas fechas de entrega ni precios en la sala.** Ni de **SIGER**, que
todavía no tiene primer cliente privado. El precio se cotiza con el caso
delante, no de pie y con público.

---

## 5. Lo que conviene arreglar antes

- `xiliux.com/informes` responde 200 y ya encabeza «SIGER» — bien: si alguien te busca al salir,
  encuentra lo que presentaste. **Léelo antes** y confirma que dice lo mismo que
  vas a decir tú.
- `xiliux.com/oprf` da 404. El servicio vive bajo `/quipu`. No es grave, pero si
  vas a nombrar el OPRF, ten a mano la URL que sí existe.
- Lleva el enlace de `oprf.xiliux.com/v1/plans` abierto en una pestaña: es una
  demostración de treinta segundos de que hay algo corriendo de verdad.

---

## 6. Después de la reunión

El error de estos espacios es salir con veinte tarjetas y ningún compromiso.
Sal con **dos conversaciones agendadas**, no con veinte contactos.

El filtro para saber a quién perseguir: quien durante tu pregunta inicial hizo
un gesto de reconocimiento. Ese tiene el problema.
