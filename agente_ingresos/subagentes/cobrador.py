from .base import Subagente


class Cobrador(Subagente):
    nombre = "cobrador"
    descripcion = "Detecta pagos en Stripe y marca como cliente a quien paga"

    def ejecutar(self):
        return {"cobrado": self.ctx.pagos.sincronizar()}
