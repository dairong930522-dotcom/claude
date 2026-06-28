# LEX — contexto del proyecto (léeme primero)

## Qué es
SaaS vertical para **despachos de extranjería en España**. Rellena los
formularios oficiales **EX** y gestiona expedientes. El cliente que paga es el
despacho; los usuarios son abogados y tramitadores.

## La ventaja (por qué este producto y no otro)
Lo construye alguien que es **tramitador de extranjería y programador a la vez** —
combinación rarísima. No competimos por tener una idea original, sino por **nicho
(España), ejecución y distribución**. Asúmelo en cada decisión: preferimos simple,
correcto y vendible a vistoso.

## Stack
- Backend: **Node + Express**, **PostgreSQL**, **pdf-lib** (MIT, se puede vender).
- Front de captura (aparte, futuro): React/Vite = "LexIntake".

## Principios de arquitectura — NO NEGOCIABLES
1. **Mapeo data-driven.** Nada cableado por formulario en el código. Cada EX es un
   esquema JSON guardado en la tabla `esquemas_formulario` y **versionado**.
   Añadir o actualizar un EX = una fila en la BD, **nunca** un redespliegue.
   El motor (`src/motor.js`) no se toca al añadir formularios.
2. **Cliente canónico.** Los datos del cliente se escriben **una sola vez**
   (tabla `clientes`) y se reutilizan en todos los EX. Lo raro va en `datos_extra`.
3. **Multi-tenant con RLS.** Toda consulta tras el login pasa por `conTenant()`
   (`src/db.js`), que fija `app.despacho_id` y deja que la Row-Level Security de
   Postgres aísle por despacho. La app conecta con un rol **NO propietario** de las
   tablas (si fuera el dueño, la RLS no se aplica). El login es la excepción y usa
   la función `autenticar_usuario` (SECURITY DEFINER). Nunca filtrar datos entre
   despachos.
4. **RGPD y responsabilidad.** Se manejan datos sensibles (NIE, pasaporte, familia).
   Cifrado, hosting en la UE, contrato de encargado del tratamiento por despacho, y
   auditoría de cada PDF en la tabla `generaciones`. El producto **rellena**; el
   abogado **revisa y firma** — jamás presentación automática. Validación por campo.
5. **PDFs oficiales traicioneros.** Los EX mezclan PDFs planos y rellenables. El
   motor soporta dos modos por campo: `overlay` (coordenadas, robusto para planos/
   XFA) y `acroform` (por nombre de campo). Para EX planos, usar `overlay`.

## Estado actual
- **Hecho (el núcleo):** `db/modelo.sql` (modelo + RLS + función de login),
  `src/motor.js` (motor data-driven, probado), `esquemas/EX-modelo.v1.json` (ejemplo),
  `demo.js` (genera un PDF relleno de extremo a extremo).
- **Esqueleto de API (punto de partida, con TODOs):** `src/server.js`, login
  (`src/rutas/auth.js`), middleware (`src/middleware/auth.js`), tenant (`src/db.js`),
  servicio de generación (`src/servicios/generar.js`) y rutas de clientes y
  expedientes. Falta cablearlo a una BD real y sembrar datos.

## Estructura
```
db/modelo.sql          modelo de datos + RLS + login
esquemas/*.json        un esquema por formulario (data-driven)
plantillas/*.pdf       el PDF oficial por formulario (EX-MODELO.pdf incluido de demo)
src/motor.js           motor de mapeo (no tocar al añadir formularios)
src/db.js              pool + conTenant (RLS)
src/middleware/auth.js JWT -> req.despachoId / req.usuarioId
src/rutas/             auth, clientes, expedientes
src/servicios/         generar.js (orquesta datos + esquema + motor + auditoría)
src/server.js          arranque Express
demo.js                prueba del motor sin BD
```

## Convenciones
- Dominio y comentarios en español. Errores como `{ error }`; el código HTTP va en
  `err.status`. Validación con `zod`.

## Roadmap (lo que hay que construir, en orden)
1. **Entorno + seed:** Postgres local, aplicar `db/modelo.sql`, sembrar un despacho,
   un usuario admin (bcrypt) y cargar `esquemas/EX-modelo.v1.json` en la BD.
2. **Flujo de punta a punta:** login -> crear cliente -> crear expediente -> generar
   PDF. Que funcione contra la BD real.
3. **Primer EX real:** medir las coordenadas del PDF oficial de mayor volumen en el
   despacho y crear su esquema. Usarlo en el trabajo real (validar por uso).
4. **LexIntake:** front React/Vite para capturar al cliente una sola vez.
5. **Producción:** hosting UE, cifrado, DPA, tests.

## Antes de meter datos reales
Cerrar por escrito la **propiedad de LexForm** y el **permiso de Despacho Breña**
para usar clientes de prueba. Es protección legal, no burocracia.
