# LEX — esqueleto (modelo de datos + motor de mapeo)

Núcleo de un SaaS vertical para despachos de extranjería. Esto **no** es la app
entera: es la pieza que de verdad importa y que casi nadie puede construir, el
motor que rellena cualquier EX a partir de datos guardados una sola vez.

## Qué hay aquí
- `db/modelo.sql` — modelo Postgres: multi-tenant con **RLS** (aislamiento entre
  despachos), cliente canónico (datos reutilizables), expedientes, esquemas de
  formulario **versionados** y auditoría de PDFs generados.
- `src/motor.js` — el motor data-driven. Rellena por **coordenadas** (PDFs planos
  del Ministerio) o por **nombre de campo** (PDFs rellenables). Sin nada cableado
  por formulario.
- `esquemas/EX-modelo.v1.json` — ejemplo de esquema: mapea claves del cliente a
  posiciones del PDF.
- `src/datos-canonicos.js` — diccionario de campos del cliente + cliente de prueba.
- `demo.js` — prueba de extremo a extremo (crea una plantilla, la rellena, guarda).

## Correrlo
```bash
npm install pdf-lib
node demo.js
# -> salida/EX-modelo-relleno.pdf
```

## Lo importante: añadir un EX real (sin tocar código)
Esto es la clave del producto. Por cada formulario oficial, **una vez**:

1. Mira si el PDF oficial tiene campos rellenables o es plano.
2. **Si es plano:** mides las coordenadas de cada hueco una sola vez y creas un
   esquema con `"modo": "overlay"` (x, y, página). Robusto frente a los PDFs
   traicioneros del gobierno (AcroForm/XFA poco fiables).
3. **Si es rellenable:** usas `"modo": "acroform"` con el nombre del campo del PDF
   (`"campo_pdf": "..."`).
4. Insertas ese JSON en la tabla `esquemas_formulario` como una versión nueva.

Resultado: cuando el Ministerio cambia un EX, insertas `v2` y conviven las dos.
**Actualizar un formulario = una fila en la BD, no un redespliegue.** Esa es la
diferencia entre tu prototipo con mapeos cableados y un producto a escala.

## Detalle de coordenadas
pdf-lib usa origen **abajo-izquierda** (y crece hacia arriba). Tenlo presente al
medir; en el esquema las coords ya están en ese sistema.

## Lo que viene después (no está aquí todavía)
- API + autenticación + multi-tenant real (fijar `app.despacho_id` por petición).
- La captura de datos del cliente una sola vez = **LexIntake** como front.
- Alojamiento en la UE, cifrado y contrato de encargado del tratamiento.
- Los PDFs oficiales EX reales y sus esquemas medidos.
- Validación por campo + flujo "rellena → el abogado revisa y firma".
