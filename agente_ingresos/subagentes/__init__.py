"""Subagentes especializados. El director (agente.Agente) los ejecuta en este orden."""

from .analista import Analista
from .cobrador import Cobrador
from .comercial import Comercial
from .marketing import Marketing
from .prospector import Prospector
from .recepcionista import Recepcionista

ORDEN = [Cobrador, Recepcionista, Prospector, Comercial, Marketing, Analista]
