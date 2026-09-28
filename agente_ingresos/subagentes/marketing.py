from ..db import hoy
from .base import REGLAS, Subagente

ESQUEMA = {"type": "object", "additionalProperties": False, "required": ["piezas"],
           "properties": {"piezas": {"type": "array", "items": {
               "type": "object", "additionalProperties": False, "required": ["canal", "titulo", "texto"],
               "properties": {"canal": {"type": "string"}, "titulo": {"type": "string"},
                              "texto": {"type": "string"}}}}}}


class Marketing(Subagente):
    nombre = "marketing"
    descripcion = "Crea cada día contenido para redes y blog"
    presupuesto_pct = 0.1
    rol = "Eres un especialista en marketing de contenidos.\n" + REGLAS.replace(
        "Mensajes cortos (máx. 120 palabras), una sola llamada a la acción.",
        "Cada pieza adaptada a su canal, útil por sí misma y con una llamada a la acción.")

    def ejecutar(self):
        if self.db.get("marketing_dia") == hoy():
            return {"piezas": 0}
        mk = self.ctx.cfg["marketing"]
        anteriores = self.db.get("marketing_titulos", "")
        r = self.pensar(
            "contenido",
            f"{self.ctx.negocio()}\n\nCrea {mk['piezas_por_dia']} piezas de contenido para hoy en los canales "
            f"{', '.join(mk['canales'])}. Temas distintos, que eduquen al cliente ideal.\n"
            f"No repitas estos temas recientes: {anteriores or 'ninguno'}",
            ESQUEMA,
        )
        self.guardar("contenido", f"{hoy()}.md", "".join(
            f"## [{p['canal']}] {p['titulo']}\n\n{p['texto']}\n\n" for p in r["piezas"]))
        titulos = [p["titulo"] for p in r["piezas"]] + anteriores.split(" | ")
        self.db.set("marketing_titulos", " | ".join(t for t in titulos if t)[:1500])
        self.db.set("marketing_dia", hoy())
        return {"piezas": len(r["piezas"])}
