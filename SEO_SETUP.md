# Guía de Configuración SEO - Xiliux Portfolio

Este documento contiene instrucciones completas para configurar y verificar el SEO del portafolio en Google Search Console.

## 📋 Resumen de Mejoras Implementadas

### ✅ Meta Tags Avanzados
- **Title tags** descriptivos y optimizados (< 60 caracteres)
- **Meta descriptions** únicas por página (< 155 caracteres)
- **Keywords** específicas por página
- **Canonical URLs** para evitar contenido duplicado
- **Meta robots** optimizados para indexación

### ✅ Open Graph y Twitter Cards
- Open Graph completo para compartir en redes sociales
- Twitter Cards para mejor preview en Twitter
- Imágenes optimizadas para social media

### ✅ Structured Data (Schema.org)
- **ProfessionalService** schema para la página principal
- **Person** schema para perfil profesional
- **CreativeWork** schema para proyectos individuales
- **Offers** schema con precios de servicios

### ✅ Sitemap.xml Mejorado
- URLs completas con prioridad
- Fecha de última modificación (lastmod)
- Frecuencia de cambio (changefreq)
- Prioridad por tipo de página

### ✅ Optimización de Rendimiento
- **Lazy loading** en imágenes de proyectos
- **Preconnect** y **dns-prefetch** para recursos externos
- Alt text descriptivo en todas las imágenes
- Atributo `lang="es"` en HTML

### ✅ Integraciones Configurables
- Google Analytics 4 (GA4)
- Google Search Console verification

---

## 🚀 Configuración de Google Analytics

### 1. Crear Cuenta de Google Analytics

1. Accede a [Google Analytics](https://analytics.google.com/)
2. Crea una nueva cuenta o usa una existente
3. Crea una nueva propiedad:
   - Nombre: **Xiliux Portfolio**
   - Zona horaria: **Europa/Madrid** (o tu zona)
   - Moneda: **EUR** o **USD**
4. Configura un stream de datos web:
   - URL del sitio: `https://xiliux.com`
   - Nombre del stream: **Xiliux Website**

### 2. Obtener ID de Medición

Una vez creado el stream, verás un **ID de medición** con formato: `G-XXXXXXXXXX`

### 3. Configurar en tu Aplicación

Edita el archivo `.env` y actualiza la línea:

```bash
GOOGLE_ANALYTICS_ID=G-XXXXXXXXXX  # Reemplaza con tu ID real
```

### 4. Verificar Instalación

1. Ejecuta la aplicación: `python main.py`
2. Abre el sitio en tu navegador
3. En Google Analytics → Tiempo real → Visión general
4. Deberías ver tu visita registrada en 1-2 minutos

---

## 🔍 Configuración de Google Search Console

### 1. Añadir Propiedad

1. Accede a [Google Search Console](https://search.google.com/search-console/)
2. Click en **Añadir propiedad**
3. Selecciona **Prefijo de URL**: `https://xiliux.com`

### 2. Verificar Propiedad (Método: Etiqueta HTML)

Google te dará varias opciones de verificación. Usa la **etiqueta HTML meta**:

1. Selecciona **Etiqueta HTML**
2. Copia el código de verificación (solo la parte del `content`):
   ```html
   <meta name="google-site-verification" content="tu-codigo-aqui" />
   ```
3. El valor que necesitas es solo: `tu-codigo-aqui`

### 3. Configurar en tu Aplicación

Edita el archivo `.env` y actualiza la línea:

```bash
GOOGLE_SEARCH_CONSOLE_VERIFICATION=tu-codigo-aqui  # Sin "content=" ni comillas
```

### 4. Desplegar y Verificar

1. Reinicia la aplicación: `python main.py`
2. Verifica que el meta tag aparezca en el HTML (View Page Source)
3. En Google Search Console, click **Verificar**
4. ¡Listo! La verificación debería ser instantánea

---

## 📊 Enviar Sitemap a Google Search Console

### 1. Verificar Sitemap

Tu sitemap está disponible en: `https://xiliux.com/sitemap.xml`

Verifica que funciona accediendo directamente a esa URL.

### 2. Enviar Sitemap en Search Console

1. En Google Search Console, selecciona tu propiedad
2. Ve a **Sitemaps** (menú lateral izquierdo)
3. En "Añadir un nuevo sitemap", escribe: `sitemap.xml`
4. Click en **Enviar**

### 3. Verificar Estado

El sitemap puede tardar unas horas o días en procesarse. Estados posibles:

- ✅ **Correcto**: Google indexó exitosamente
- ⚠️ **Con advertencias**: Funciona pero hay sugerencias
- ❌ **Error**: Hay que revisar el formato XML

---

## 🎯 Métricas Clave a Monitorear

### En Google Search Console

1. **Rendimiento**
   - Impresiones totales
   - Clics totales
   - CTR promedio
   - Posición promedia

2. **Cobertura**
   - Páginas indexadas
   - Páginas excluidas
   - Errores de rastreo

3. **Experiencia**
   - Core Web Vitals
   - Usabilidad móvil

4. **Enlaces**
   - Enlaces externos (backlinks)
   - Enlaces internos más frecuentes

### En Google Analytics

1. **Tiempo real**
   - Usuarios activos
   - Páginas más vistas

2. **Adquisición**
   - Fuentes de tráfico (Organic, Direct, Referral, Social)
   - Términos de búsqueda

3. **Comportamiento**
   - Páginas más visitadas
   - Tiempo promedio en página
   - Tasa de rebote

4. **Conversiones** (configurar eventos personalizados)
   - Descargas de guía PDF
   - Envíos de formulario de contacto
   - Clics en botones de proyectos

---

## 🔧 Mantenimiento SEO Continuo

### Semanalmente
- [ ] Revisar nuevas palabras clave en Search Console
- [ ] Verificar que no haya errores de rastreo
- [ ] Monitorear posiciones de páginas clave

### Mensualmente
- [ ] Actualizar sitemap si hay nuevos proyectos
- [ ] Analizar rendimiento de páginas en Analytics
- [ ] Revisar y optimizar meta descriptions basadas en CTR
- [ ] Verificar velocidad del sitio (PageSpeed Insights)

### Trimestralmente
- [ ] Auditoría completa de SEO técnico
- [ ] Actualizar structured data si hay cambios en servicios
- [ ] Revisar y actualizar keywords según tendencias
- [ ] Análisis de competencia

---

## 📱 Herramientas Adicionales Recomendadas

### Análisis SEO
- **PageSpeed Insights**: https://pagespeed.web.dev/
- **Mobile-Friendly Test**: https://search.google.com/test/mobile-friendly
- **Rich Results Test**: https://search.google.com/test/rich-results
- **Schema Markup Validator**: https://validator.schema.org/

### Monitoreo
- **Google Trends**: Tendencias de búsqueda
- **Answer The Public**: Ideas de contenido
- **Ubersuggest**: Análisis de keywords
- **Ahrefs** o **SEMrush**: Análisis profesional (de pago)

### Performance
- **GTmetrix**: https://gtmetrix.com/
- **WebPageTest**: https://www.webpagetest.org/
- **Lighthouse** (integrado en Chrome DevTools)

---

## 🎨 Próximos Pasos Sugeridos (Opcionales)

### Contenido
1. **Blog**: Agregar sección de blog con artículos técnicos
   - Mejora el SEO con contenido fresco
   - Posiciona en long-tail keywords
   - Demuestra expertise

2. **Case Studies**: Casos de éxito detallados
   - Aumenta credibilidad
   - Genera backlinks
   - Mejora conversión

3. **Testimonios**: Agregar testimonios de clientes
   - Schema de Review/Rating
   - Aumenta confianza

### Técnico
1. **AMP** (Accelerated Mobile Pages): Opcional pero mejora velocidad en móviles
2. **PWA** (Progressive Web App): Instalable, funciona offline
3. **CDN**: Cloudflare o similar para mejor velocidad global
4. **Compresión de imágenes**: WebP en lugar de PNG/JPG

### Marketing
1. **Email marketing**: Capturar leads con newsletter
2. **Retargeting**: Pixel de Facebook/LinkedIn
3. **Social proof**: Integrar feed de redes sociales
4. **Call-to-action** mejorados: A/B testing de CTAs

---

## 📞 Soporte

Si encuentras problemas con la configuración de SEO:

1. Verifica que las variables de entorno estén correctamente configuradas
2. Revisa los logs de la aplicación
3. Usa las herramientas de validación mencionadas
4. Consulta la documentación oficial de Google Search Console

---

**Última actualización**: 2026-01-06
**Versión**: 1.0
