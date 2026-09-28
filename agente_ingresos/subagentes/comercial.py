import logging
from datetime import datetime, timedelta

from ..db import ahora, hoy
from .base import REGLAS, Subagente

log = logging.getLogger("agente.comercial")
ESQUEMA = {"type": "object", "additionalProperties": False, "required": ["asunto", "cuerpo"],
           "properties": {"asunto": {"type": "string"}, "cuerpo": {"type": "string"}}}


def enviados_hoy(db) -> int:
    return db.uno("SELECT COUNT(*) c FROM mensajes WHERE direccion = 'salida' AND fecha LIKE ?",
                  hoy() + "%")["c"]


def registrar_envio(db, lead, asunto, cuerpo, estado, angulo=None):
    db.ex("INSERT INTO mensajes (lead_id, direccion, asunto, cuerpo, fecha) VALUES (?,?,?,?,?)",
          lead["id"], "salida", asunto, cuerpo, ahora())
    if angulo:
        db.ex("UPDATE leads SET estado = ?, contactos = contactos + 1, ultimo_contacto = ?, variante = ?"
              " WHERE id = ?", estado, ahora(), angulo, lead["id"])
    else:
        db.ex("UPDATE leads SET estado = ?, contactos = contactos + 1, ultimo_contacto = ? WHERE id = ?",
              estado, ahora(), lead["id"])


class Comercial(Subagente):
    nombre = "comercial"
    descripcion = "Escribe el primer email y los seguimientos a cada lead"
    presupuesto_pct = 0.3
    rol = "Eres un comercial experto en venta consultiva por email.\n" + REGLAS

    def _escribir(self, lead, angulo, historial=""):
        return self.pensar(
            "redaccion",
            f"{self.ctx.negocio()}\n\nDestinatario: {lead['empresa']} ({lead['web'] or 's/web'})\n"
            f"Por qué encaja: {lead['notas'] or 'desconocido'}\nÁngulo a usar: {angulo}\n"
            + (f"\nMensajes previos sin respuesta:\n{historial}\nEscribe un seguimiento breve y distinto."
               if historial else "\nEscribe el primer email. No incluyas enlace de pago todavía."),
            ESQUEMA,
        )

    def _cupo(self):
        return max(self.ctx.cfg["limites"]["emails_por_dia"] - enviados_hoy(self.db), 0)

    def contactar(self) -> int:
        n = 0
        for lead in self.db.q("SELECT * FROM leads WHERE estado = 'nuevo' ORDER BY id LIMIT ?", self._cupo()):
            if self.db.excluido(lead["email"]):
                continue
            angulo = self.ctx.selector.elegir()
            m = self._escribir(lead, angulo)
            estado = self.ctx.correo.enviar(lead["email"], m["asunto"], m["cuerpo"])
            registrar_envio(self.db, lead, m["asunto"], m["cuerpo"], "contactado", angulo)
            self.ctx.selector.envio(angulo)
            log.info("Contacto %s a %s (%s)", estado, lead["email"], angulo)
            n += 1
        return n

    def seguir(self) -> int:
        lim = self.ctx.cfg["limites"]
        limite = (datetime.now() - timedelta(days=lim["dias_entre_seguimientos"])).isoformat()
        n = 0
        for lead in self.db.q(
                "SELECT * FROM leads WHERE estado = 'contactado' AND contactos <= ? AND ultimo_contacto < ?"
                " ORDER BY ultimo_contacto LIMIT ?", lim["seguimientos_max"], limite, self._cupo()):
            previos = self.db.q("SELECT asunto, cuerpo FROM mensajes WHERE lead_id = ? ORDER BY id", lead["id"])
            historial = "\n---\n".join(f"{p['asunto']}\n{p['cuerpo']}" for p in previos)
            m = self._escribir(lead, lead["variante"] or self.ctx.selector.elegir(), historial)
            self.ctx.correo.enviar(lead["email"], m["asunto"], m["cuerpo"])
            registrar_envio(self.db, lead, m["asunto"], m["cuerpo"], "contactado")
            n += 1
        # quien no responde tras el último seguimiento se cierra
        self.db.ex("UPDATE leads SET estado = 'sin_respuesta' WHERE estado = 'contactado' AND contactos > ?"
                   " AND ultimo_contacto < ?", lim["seguimientos_max"], limite)
        return n

    def ejecutar(self):
        return {"contactados": self.contactar(), "seguimientos": self.seguir()}
