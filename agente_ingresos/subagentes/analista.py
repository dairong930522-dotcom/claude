from ..db import hoy
from .base import Subagente

ESQUEMA = {"type": "object", "additionalProperties": False, "required": ["angulos_nuevos", "recomendaciones"],
           "properties": {"angulos_nuevos": {"type": "array", "items": {"type": "string"}},
                          "recomendaciones": {"type": "array", "items": {"type": "string"}}}}


class Analista(Subagente):
    """Revisa los resultados una vez al día: retira los ángulos de venta que
    rinden claramente peor, pide ángulos nuevos para sustituirlos y deja
    recomendaciones para el dueño."""

    nombre = "analista"
    descripcion = "Mide resultados, retira lo que no funciona y propone mejoras"
    presupuesto_pct = 0.1
    rol = ("Eres un analista de ventas. Te basas solo en los datos que recibes; "
           "si los datos son pocos, lo dices y no sacas conclusiones fuertes.")

    def ejecutar(self):
        if self.db.get("analista_dia") == hoy():
            return {"revisado": False}
        min_envios = self.conf.get("min_envios_para_juzgar", 20)
        max_activos = self.conf.get("max_angulos_activos", 5)
        sel = self.ctx.selector

        activos = sel.activos()
        juzgables = [a for a in activos if a["envios"] >= min_envios]
        retirados = []
        if len(juzgables) >= 2:
            tasa = {a["nombre"]: a["exitos"] / a["envios"] for a in juzgables}
            mejor = max(tasa.values())
            for nombre, t in sorted(tasa.items(), key=lambda x: x[1]):
                if len(activos) - len(retirados) <= 2:
                    break
                if t < mejor * 0.5:
                    sel.retirar(nombre)
                    retirados.append(nombre)

        total_envios = sum(a["envios"] for a in activos)
        huecos = min(len(retirados), max_activos - (len(activos) - len(retirados)))
        nuevos, recomendaciones = [], []
        if huecos > 0 or total_envios >= min_envios:
            est = {r["estado"]: r["c"] for r in self.db.q("SELECT estado, COUNT(*) c FROM leads GROUP BY estado")}
            todos = self.db.q("SELECT * FROM variantes")
            r = self.pensar(
                "revision",
                f"{self.ctx.negocio()}\n\nResultados por ángulo (respuestas positivas/envíos, activo):\n"
                + "\n".join(f"- {v['nombre']}: {v['exitos']}/{v['envios']} {'activo' if v['activo'] else 'retirado'}"
                            for v in todos)
                + f"\nLeads por estado: {est}\nIngresos totales: {self.db.ingreso_total():.2f}\n"
                  f"Gasto total: {self.db.coste_total():.2f} USD\n\n"
                  f"Propón exactamente {max(huecos, 0)} ángulos de venta nuevos (frases cortas, distintos "
                  "de los existentes, inspirados en lo que mejor funciona) y hasta 3 recomendaciones "
                  "concretas para el dueño del negocio.",
                ESQUEMA,
            )
            for a in r["angulos_nuevos"][:max(huecos, 0)]:
                if sel.anadir(a):
                    nuevos.append(a)
            recomendaciones = r["recomendaciones"][:3]
            self.guardar("analisis", f"{hoy()}.md", "# Recomendaciones del analista\n\n"
                         + "\n".join(f"- {x}" for x in recomendaciones))
        self.db.set("analista_dia", hoy())
        return {"retirados": retirados, "nuevos": nuevos, "recomendaciones": len(recomendaciones)}
