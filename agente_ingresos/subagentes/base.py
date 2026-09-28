"""Piezas comunes de los subagentes.

Cada subagente tiene un rol (su propio prompt de sistema), un modelo opcional,
y una parte del presupuesto diario de IA. Si gasta su parte, se detiene él
solo sin frenar a los demás."""

import os
import re

from ..llm import PresupuestoAgotado

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)

REGLAS = """Reglas obligatorias:
- Escribe en el idioma del cliente (por defecto, español), tono cercano y profesional.
- No inventes datos, clientes, testimonios, cifras ni garantías. Si no sabes algo, no lo afirmes.
- No prometas resultados garantizados ni uses urgencia falsa.
- Mensajes cortos (máx. 120 palabras), una sola llamada a la acción.
- No incluyas firma ni pie: se añaden automáticamente."""


class PresupuestoSubagenteAgotado(PresupuestoAgotado):
    """Solo afecta a un subagente; el director sigue con los demás."""


class Contexto:
    """Recursos compartidos que el director entrega a cada subagente."""

    def __init__(self, cfg, db, llm, correo, pagos, selector, riesgo, salida):
        self.cfg, self.db, self.llm = cfg, db, llm
        self.correo, self.pagos, self.selector, self.riesgo = correo, pagos, selector, riesgo
        self.salida = salida

    def negocio(self) -> str:
        n = self.cfg["negocio"]
        return (
            f"Negocio: {n['nombre']}\nOferta: {n['oferta']}\n"
            f"Precio: {n['precio']} {n.get('moneda', 'eur').upper()}\n"
            f"Cliente ideal: {n['cliente_ideal']}\nPropuesta de valor: {n['propuesta_valor']}\n"
            f"Web: {n.get('web', '')}"
        )


class Subagente:
    nombre = ""
    descripcion = ""
    rol = ""
    presupuesto_pct = 0.0  # parte del presupuesto diario de IA

    def __init__(self, ctx: Contexto):
        self.ctx = ctx
        conf = ctx.cfg.get("subagentes", {}).get(self.nombre, {})
        self.activo = conf.get("activo", True)
        self.modelo = conf.get("modelo")
        self.pct = conf.get("presupuesto_pct", self.presupuesto_pct)
        self.conf = conf

    @property
    def db(self):
        return self.ctx.db

    def presupuesto(self) -> float:
        return self.pct * self.ctx.cfg["limites"]["presupuesto_ia_diario_usd"]

    def gasto_hoy(self) -> float:
        return self.db.coste_dia_prefijo(f"ia:{self.nombre}:")

    def _comprobar(self):
        if self.gasto_hoy() >= self.presupuesto():
            raise PresupuestoSubagenteAgotado(
                f"{self.nombre}: agotada su parte del presupuesto ({self.presupuesto():.2f} USD)")

    def _kw(self):
        return {"modelo": self.modelo} if self.modelo else {}

    def pensar(self, tarea, prompt, esquema, extra_rol=""):
        self._comprobar()
        return self.ctx.llm.json(f"{self.nombre}:{tarea}", self.rol + extra_rol, prompt, esquema, **self._kw())

    def investigar(self, tarea, prompt, **kw):
        self._comprobar()
        return self.ctx.llm.investigar(f"{self.nombre}:{tarea}", self.rol, prompt, **kw, **self._kw())

    def ejecutar(self):
        raise NotImplementedError

    def guardar(self, subcarpeta, nombre_fichero, texto):
        carpeta = os.path.join(self.ctx.salida, subcarpeta)
        os.makedirs(carpeta, exist_ok=True)
        with open(os.path.join(carpeta, nombre_fichero), "w", encoding="utf-8") as f:
            f.write(texto)
