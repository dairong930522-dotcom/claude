import csv

from .base import EMAIL_RE, Subagente


class Prospector(Subagente):
    nombre = "prospector"
    descripcion = "Busca empresas que encajan con el cliente ideal"
    presupuesto_pct = 0.25
    rol = ("Eres un investigador de mercado B2B. Solo recopilas datos de contacto "
           "profesionales publicados por las propias empresas (su web o ficha oficial).")

    def importar_csv(self, ruta) -> int:
        n = 0
        with open(ruta, newline="", encoding="utf-8") as f:
            for fila in csv.DictReader(f):
                email = (fila.get("email") or "").strip()
                if EMAIL_RE.match(email) and self.db.anadir_lead(
                        fila.get("empresa", ""), email, fila.get("contacto", ""),
                        fila.get("web", ""), fila.get("notas", ""), "csv"):
                    n += 1
        return n

    def ejecutar(self):
        p = self.ctx.cfg["prospeccion"]
        pendientes = self.db.uno("SELECT COUNT(*) c FROM leads WHERE estado = 'nuevo'")["c"]
        if not p.get("busqueda_web") or pendientes >= self.ctx.cfg["limites"]["emails_por_dia"]:
            return {"nuevos": 0, "pendientes": pendientes}
        ya = [r["email"] for r in self.db.q("SELECT email FROM leads ORDER BY id DESC LIMIT 50")]
        encontrados = self.investigar(
            "busqueda",
            f"{self.ctx.negocio()}\nZona: {p.get('zona', '')}\n\n"
            f"Busca {p['leads_por_ciclo']} empresas reales que encajen con el cliente ideal y que "
            "publiquen un email de contacto corporativo (no personal). Evita estos emails: "
            f"{', '.join(ya) or 'ninguno'}.\n"
            "Devuelve SOLO un array JSON de objetos con las claves: empresa, email, web, "
            "fuente (URL donde aparece el email), motivo (por qué encaja, una frase).",
            max_busquedas=p.get("max_busquedas", 5),
        )
        n = 0
        for e in encontrados:
            email = str(e.get("email", "")).strip()
            if EMAIL_RE.match(email) and e.get("fuente") and self.db.anadir_lead(
                    e.get("empresa", ""), email, "", e.get("web", ""), e.get("motivo", ""), e["fuente"]):
                n += 1
        return {"nuevos": n, "pendientes": pendientes + n}
