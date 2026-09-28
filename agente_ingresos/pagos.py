"""Cobros con Stripe: un enlace de pago por oferta y detección de pagos completados.
Sin STRIPE_API_KEY funciona en modo simulado (enlace ficticio, sin ingresos)."""

import os
import time


class Pagos:
    def __init__(self, db, cfg):
        self.db = db
        self.cfg = cfg
        self.activo = bool(os.environ.get("STRIPE_API_KEY"))
        if self.activo:
            import stripe
            stripe.api_key = os.environ["STRIPE_API_KEY"]
            self.stripe = stripe

    def enlace(self, lead_id) -> str:
        base = self.db.get("stripe_enlace_url")
        if not base:
            base = self._crear_enlace() if self.activo else "https://pago.ejemplo.com/SIMULADO"
            self.db.set("stripe_enlace_url", base)
        # client_reference_id permite atribuir el pago al lead
        return f"{base}?client_reference_id=lead_{lead_id}"

    def _crear_enlace(self) -> str:
        n = self.cfg["negocio"]
        producto = self.stripe.Product.create(name=n["oferta"][:250])
        precio = self.stripe.Price.create(
            product=producto.id,
            unit_amount=int(round(n["precio"] * 100)),
            currency=n.get("moneda", "eur"),
        )
        enlace = self.stripe.PaymentLink.create(line_items=[{"price": precio.id, "quantity": 1}])
        self.db.set("stripe_enlace_id", enlace.id)
        return enlace.url

    def sincronizar(self) -> float:
        """Registra pagos nuevos; devuelve el importe nuevo cobrado."""
        enlace_id = self.db.get("stripe_enlace_id")
        if not (self.activo and enlace_id):
            return 0.0
        desde = int(self.db.get("stripe_ultima_sync", int(time.time()) - 7 * 86400))
        nuevo = 0.0
        sesiones = self.stripe.checkout.Session.list(
            payment_link=enlace_id, status="complete", created={"gte": desde}, limit=100
        )
        for s in sesiones.auto_paging_iter():
            if s.payment_status != "paid":
                continue
            lead_id = None
            ref = s.client_reference_id or ""
            if ref.startswith("lead_") and ref[5:].isdigit():
                lead_id = int(ref[5:])
            importe = (s.amount_total or 0) / 100
            if self.db.registrar_ingreso(s.id, importe, s.currency, lead_id):
                nuevo += importe
                if lead_id:
                    self.db.estado_lead(lead_id, "cliente")
        self.db.set("stripe_ultima_sync", int(time.time()) - 3600)
        return nuevo
