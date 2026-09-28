"""Autogestión del riesgo y optimización.

- Freno de pérdidas: si (gastos - ingresos) supera `perdida_maxima_usd`, el agente
  se pausa solo y avisa. Así la pérdida máxima posible queda acotada de antemano.
- Presupuesto diario de IA (ver llm.py).
- Interruptor manual: si existe el fichero PAUSA, el agente no hace nada.
- Muestreo de Thompson: elige el ángulo de venta que mejor está funcionando,
  sin dejar de probar los demás.
"""

import os
import random


class Riesgo:
    def __init__(self, db, cfg, carpeta_base):
        self.db = db
        self.lim = cfg["limites"]
        self.fichero_pausa = os.path.join(carpeta_base, "PAUSA")

    def balance(self) -> float:
        """Ingresos - gastos. Los ingresos se tratan como USD (aprox. si cobras en EUR)."""
        return self.db.ingreso_total() - self.db.coste_total()

    def motivo_pausa(self):
        if os.path.exists(self.fichero_pausa):
            return "Pausa manual (existe el fichero PAUSA)"
        if self.db.get("pausa_automatica") == "1":
            return self.db.get("pausa_motivo", "Pausa automática")
        if -self.balance() >= self.lim["perdida_maxima_usd"]:
            motivo = (
                f"Freno de pérdidas: gastos - ingresos = {-self.balance():.2f} USD "
                f"(límite {self.lim['perdida_maxima_usd']} USD)"
            )
            self.db.set("pausa_automatica", "1")
            self.db.set("pausa_motivo", motivo)
            return motivo
        return None

    def reanudar(self):
        self.db.set("pausa_automatica", "0")
        if os.path.exists(self.fichero_pausa):
            os.remove(self.fichero_pausa)


class Selector:
    """Bandido multibrazo (Thompson) sobre los ángulos de venta activos.
    Los ángulos del config son la semilla; el subagente Analista puede retirar
    los que no funcionan y proponer otros nuevos."""

    def __init__(self, db, angulos, rng=None):
        self.db = db
        self.rng = rng or random.Random()
        for a in angulos:
            db.ex("INSERT OR IGNORE INTO variantes (nombre) VALUES (?)", a)

    def activos(self):
        return self.db.q("SELECT * FROM variantes WHERE activo = 1 ORDER BY nombre")

    def elegir(self) -> str:
        mejor, mejor_valor = None, -1.0
        for r in self.activos():
            valor = self.rng.betavariate(1 + r["exitos"], 1 + r["envios"] - r["exitos"])
            if valor > mejor_valor:
                mejor, mejor_valor = r["nombre"], valor
        return mejor

    def envio(self, angulo):
        self.db.ex("UPDATE variantes SET envios = envios + 1 WHERE nombre = ?", angulo)

    def exito(self, angulo):
        if angulo:
            self.db.ex("UPDATE variantes SET exitos = exitos + 1 WHERE nombre = ?", angulo)

    def retirar(self, angulo):
        self.db.ex("UPDATE variantes SET activo = 0 WHERE nombre = ?", angulo)

    def anadir(self, angulo) -> bool:
        angulo = angulo.strip()
        if not angulo or self.db.uno("SELECT 1 FROM variantes WHERE nombre = ?", angulo):
            return False
        from .db import ahora
        self.db.ex("INSERT INTO variantes (nombre, creado) VALUES (?, ?)", angulo, ahora())
        return True
