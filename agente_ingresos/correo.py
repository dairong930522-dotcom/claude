"""Envío (SMTP) y lectura (IMAP) de correo. En modo prueba no se envía nada:
los mensajes se guardan como .eml en salida/borradores para revisarlos."""

import email
import imaplib
import os
import smtplib
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr

from .db import ahora


class Correo:
    def __init__(self, cfg, carpeta_salida, modo_prueba=True):
        self.cfg = cfg
        self.modo_prueba = modo_prueba
        self.borradores = os.path.join(carpeta_salida, "borradores")
        os.makedirs(self.borradores, exist_ok=True)

    def _pie(self):
        n = self.cfg["negocio"]
        return (
            f"\n\n--\n{n['remitente_nombre']} · {n['nombre']}\n{n['direccion_postal']}\n"
            "Si no quieres recibir más correos, responde con la palabra BAJA y no volveremos a escribirte."
        )

    def enviar(self, para, asunto, cuerpo, en_respuesta_a=None) -> str:
        n = self.cfg["negocio"]
        remitente = os.environ.get("SMTP_USER", "agente@ejemplo.com")
        m = EmailMessage()
        m["From"] = f"{n['remitente_nombre']} <{remitente}>"
        m["To"] = para
        m["Subject"] = asunto
        m["Date"] = formatdate(localtime=True)
        m["Message-ID"] = make_msgid()
        m["List-Unsubscribe"] = f"<mailto:{remitente}?subject=BAJA>"
        if en_respuesta_a:
            m["In-Reply-To"] = en_respuesta_a
            m["References"] = en_respuesta_a
        m.set_content(cuerpo + self._pie())

        if self.modo_prueba:
            nombre = f"{ahora().replace(':', '')}_{para.replace('@', '_at_')}.eml"
            with open(os.path.join(self.borradores, nombre), "wb") as f:
                f.write(bytes(m))
            return "borrador"

        with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587"))) as s:
            s.starttls()
            s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
            s.send_message(m)
        return "enviado"

    def leer_no_leidos(self):
        """Devuelve [(email_remitente, asunto, cuerpo, message_id)] de la bandeja de entrada."""
        if not os.environ.get("IMAP_HOST"):
            return []
        resultado = []
        with imaplib.IMAP4_SSL(os.environ["IMAP_HOST"]) as im:
            im.login(os.environ.get("IMAP_USER", os.environ.get("SMTP_USER")),
                     os.environ.get("IMAP_PASS", os.environ.get("SMTP_PASS")))
            im.select("INBOX")
            _, ids = im.search(None, "UNSEEN")
            for i in ids[0].split():
                _, datos = im.fetch(i, "(RFC822)")
                msg = email.message_from_bytes(datos[0][1])
                remitente = parseaddr(msg.get("From", ""))[1].lower()
                asunto = str(make_header(decode_header(msg.get("Subject", ""))))
                resultado.append((remitente, asunto, _cuerpo_texto(msg), msg.get("Message-ID")))
        return resultado


def _cuerpo_texto(msg) -> str:
    if msg.is_multipart():
        for parte in msg.walk():
            if parte.get_content_type() == "text/plain":
                return parte.get_payload(decode=True).decode(parte.get_content_charset() or "utf-8", "replace")
        return ""
    return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", "replace")
