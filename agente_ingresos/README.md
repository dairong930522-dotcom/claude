# Agente de ingresos

Agente autónomo que, en cada ciclo (por defecto cada hora):

1. **Cobra**: detecta pagos en Stripe y los atribuye al cliente que los hizo.
2. **Atiende respuestas**: lee tu bandeja, clasifica cada respuesta con Claude y contesta
   (con el enlace de pago si hay interés). Si no sabe responder, **te lo escala**.
3. **Busca clientes**: investiga en la web empresas que encajan con tu cliente ideal y que
   publican un email corporativo (guarda la URL de origen de cada contacto).
4. **Vende**: escribe emails personalizados y hace hasta 2 seguimientos.
5. **Aprende**: prueba varios "ángulos de venta" y cada vez usa más el que mejor responde
   (muestreo de Thompson).
6. **Hace marketing**: genera cada día piezas de contenido para tus redes/blog en `salida/contenido/`.
7. **Informa**: escribe `salida/informe.md` y te lo envía por email una vez al día.

## Lo que ningún sistema puede hacer: garantizar que nunca pierdes

Nadie puede prometer "ganar siempre". Lo que sí hace este agente es **acotar la pérdida máxima
de antemano**:

| Protección | Qué hace |
|---|---|
| `presupuesto_ia_diario_usd` | Deja de llamar a la IA en cuanto el gasto del día llega al límite. |
| `perdida_maxima_usd` | Si gastos − ingresos alcanza este valor, **se pausa solo** y no se reactiva hasta que tú lo decidas. |
| `emails_por_dia` | Evita que tu dominio acabe marcado como spam. |
| `modo_prueba: true` | Por defecto **no envía nada**: guarda los emails en `salida/borradores/` para que los revises. |
| Fichero `PAUSA` | `python -m agente_ingresos pausar` lo detiene al instante. |

Con la configuración de ejemplo, lo peor que puede pasar es perder 60 USD antes de que el agente
se pare. Si da beneficios, sigue solo.

**Lo que decide si gana dinero es la oferta**, no el agente: un servicio concreto, a un precio
razonable, para un cliente que lo necesite. El agente automatiza el trabajo repetitivo, pero no
sustituye a un producto que la gente quiera comprar.

## Legalidad (léelo antes de activar el modo real)

- El agente solo contacta a **emails corporativos publicados por las empresas**, se identifica, incluye
  dirección postal y opción de baja, y **nunca vuelve a escribir a quien dice no o pide la baja**.
- Aun así, el email comercial no solicitado está regulado (en España, LSSI art. 21 y RGPD; en la UE,
  cada país tiene sus normas). Consulta si tu caso está permitido; en algunos países necesitas
  consentimiento previo incluso entre empresas. Si tienes dudas, usa solo leads que te hayan dado
  permiso importándolos por CSV y pon `"busqueda_web": false`.
- Usa un dominio/buzón dedicado a ventas, no tu correo personal.

## Puesta en marcha

```bash
pip install -r agente_ingresos/requirements.txt
cp agente_ingresos/.env.ejemplo .env      # rellena las claves
set -a; source .env; set +a

python -m agente_ingresos iniciar         # crea config.json -> edítalo con TU negocio
python -m agente_ingresos ciclo           # un ciclo en modo prueba: revisa salida/
```

Cuando los borradores te convenzan, cambia `"modo_prueba": false` en `config.json` y déjalo
funcionando solo:

```bash
python -m agente_ingresos ejecutar        # bucle continuo
# o con cron, un ciclo cada hora:
# 0 * * * * cd /ruta && set -a && . ./.env && python -m agente_ingresos ciclo
```

Otros comandos: `importar leads.csv` (columnas `empresa,email,contacto,web,notas`), `informe`,
`pausar`, `reanudar`.

## Qué necesitas

- Clave de API de Anthropic (`ANTHROPIC_API_KEY`).
- Un buzón con SMTP/IMAP (Google Workspace, Zoho, etc.).
- Cuenta de Stripe (`STRIPE_API_KEY`). El agente crea el producto y el enlace de pago solo.
- `EMAIL_DUENO`: donde recibirás el informe diario y los casos que requieren una persona.

El modelo por defecto es `claude-opus-5`, con reintento automático en otro modelo si una petición
se rechaza. Para abaratar, puedes poner `"modelo": "claude-sonnet-5"` en `config.json`.

## Tests

```bash
python -m unittest discover -s agente_ingresos/tests -t .
```
