# Primer prompt para Claude Code

Abre el proyecto en Claude Code y pega esto:

---

Lee `CLAUDE.md` entero antes de empezar. Respeta los principios no negociables,
sobre todo el mapeo data-driven y el aislamiento por RLS.

Haz estas tareas **en orden**, enseñándome el resultado de cada una antes de pasar
a la siguiente, y trabajando en ramas:

1. **Entorno local.** Levanta Postgres (docker-compose), aplica `db/modelo.sql`, y
   crea `.env` a partir de `.env.example`. Crea además el rol `lex_app` NO
   propietario de las tablas y dale los permisos justos para que la RLS se aplique.

2. **Seed.** Un script que inserte: un despacho de prueba, un usuario admin con la
   clave hasheada (bcrypt), y que cargue `esquemas/EX-modelo.v1.json` en la tabla
   `esquemas_formulario`. Copia `plantillas/EX-MODELO.pdf` como plantilla de ese
   formulario.

3. **Flujo de punta a punta.** Arranca la API (`npm run dev`) y verifica con curl:
   login -> crear un cliente -> crear un expediente del formulario EX-MODELO ->
   `POST /api/expedientes/:id/generar` -> que devuelva el PDF relleno. Comprueba que
   un token de otro despacho NO puede ver ese cliente (que la RLS funciona).

4. **Tests.** Añade tests del servicio `generar` y del aislamiento por tenant.

No metas datos reales de clientes todavía. Si algo del esqueleto está incompleto o
mal, corrígelo y dime qué cambiaste y por qué.

---

Cuando esto funcione, el siguiente paso es el **primer EX real**: elige el
formulario de más volumen del despacho, mide sus coordenadas y crea su esquema.
