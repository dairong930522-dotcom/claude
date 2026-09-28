import re

from ..db import ahora
from .base import REGLAS, Subagente
from .comercial import registrar_envio

ESQUEMA = {"type": "object", "additionalProperties": False, "required": ["intencion", "respuesta"],
           "properties": {
               "intencion": {"type": "string", "enum": [
                   "interesado", "pregunta", "no_interesado", "baja", "requiere_humano"]},
               "respuesta": {"type": "string"}}}


class Recepcionista(Subagente):
    nombre = "recepcionista"
    descripcion = "Lee las respuestas, contesta dudas, envía el enlace de pago y gestiona bajas"
    presupuesto_pct = 0.25
    rol = ("Eres el comercial que atiende las respuestas de clientes potenciales.\n" + REGLAS
           + "\n- Si la pregunta requiere información que no tienes (contratos, descuentos, "
             "casos a medida), clasifícala como 'requiere_humano' y no respondas nada concreto.")

    def ejecutar(self):
        n = bajas = 0
        for remitente, asunto, cuerpo, msg_id in self.ctx.correo.leer_no_leidos():
            lead = self.db.lead_por_email(remitente)
            if not lead:
                continue
            self.db.ex("INSERT INTO mensajes (lead_id, direccion, asunto, cuerpo, fecha) VALUES (?,?,?,?,?)",
                       lead["id"], "entrada", asunto, cuerpo, ahora())
            if re.search(r"\bbaja\b|unsubscribe", f"{asunto} {cuerpo[:300]}", re.I):
                self.db.excluir(remitente, "baja solicitada")
                bajas += 1
                continue
            self.procesar(lead, asunto, cuerpo, msg_id)
            n += 1
        return {"atendidas": n, "bajas": bajas}

    def procesar(self, lead, asunto, cuerpo, msg_id=None):
        enlace = self.ctx.pagos.enlace(lead["id"])
        r = self.pensar(
            "respuesta",
            f"{self.ctx.negocio()}\nEnlace de pago: {enlace}\n\nEl cliente {lead['empresa']} respondió:\n"
            f"Asunto: {asunto}\n{cuerpo[:4000]}\n\n"
            "Clasifica la intención y redacta la respuesta. Si está interesado, incluye el enlace de pago.",
            ESQUEMA,
        )
        intencion = r["intencion"]
        if intencion in ("baja", "no_interesado"):
            self.db.excluir(lead["email"], intencion)
            return intencion
        if intencion == "requiere_humano":
            self.db.estado_lead(lead["id"], "requiere_humano")
            self.db.escalar(lead["id"], f"{asunto}: {cuerpo[:300]}")
            return intencion
        if lead["estado"] == "contactado":
            self.ctx.selector.exito(lead["variante"])
        asunto_re = "Re: " + asunto.removeprefix("Re: ")
        self.ctx.correo.enviar(lead["email"], asunto_re, r["respuesta"], msg_id)
        registrar_envio(self.db, lead, asunto_re, r["respuesta"], "negociando")
        return intencion
