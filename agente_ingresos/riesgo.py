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
    """Bandido multibrazo (Thompson) sobre los ángulos de venta."""

    def __init__(self, db, angulos, rng=None):
        self.db = db
        self.rng = rng or random.Random()
        for a in angulos:
            db.ex("INSERT OR IGNORE INTO variantes (nombre) VALUES (?)", a)
        self.angulos = angulos

    def elegir(self) -> str:
        mejor, mejor_valor = None, -1.0
        for a in self.angulos:
            r = self.db.uno("SELECT envios, exitos FROM variantes WHERE nombre = ?", a)
            valor = self.rng.betavariate(1 + r["exitos"], 1 + r["envios"] - r["exitos"])
            if valor > mejor_valor:
                mejor, mejor_valor = a, valor
        return mejor

    def envio(self, angulo):
        self.db.ex("UPDATE variantes SET envios = envios + 1 WHERE nombre = ?", angulo)

    def exito(self, angulo):
        if angulo:
            self.db.ex("UPDATE variantes SET exitos = exitos + 1 WHERE nombre = ?", angulo)
