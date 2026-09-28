"""Uso:
  python -m agente_ingresos iniciar            crea config.json a partir del ejemplo
  python -m agente_ingresos importar leads.csv añade leads (columnas: empresa,email,contacto,web,notas)
  python -m agente_ingresos ciclo              ejecuta un ciclo completo y sale (ideal para cron)
  python -m agente_ingresos ejecutar           bucle continuo, un ciclo cada `minutos_entre_ciclos`
  python -m agente_ingresos informe            muestra el informe actual
  python -m agente_ingresos pausar | reanudar  interruptor manual
"""

import json
import logging
import os
import shutil
import sys
import time

from .agente import Agente

BASE = os.environ.get("AGENTE_DIR", os.getcwd())
CONFIG = os.path.join(BASE, "config.json")
EJEMPLO = os.path.join(os.path.dirname(__file__), "config.ejemplo.json")


def main(argv):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    orden = argv[0] if argv else "ayuda"
    if orden == "iniciar":
        if os.path.exists(CONFIG):
            print(f"Ya existe {CONFIG}")
        else:
            shutil.copy(EJEMPLO, CONFIG)
            print(f"Creado {CONFIG}. Edítalo con los datos de tu negocio.")
        return 0
    if orden not in ("importar", "ciclo", "ejecutar", "informe", "pausar", "reanudar"):
        print(__doc__)
        return 1
    with open(CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)
    agente = Agente(cfg, BASE)
    if orden == "importar":
        print(f"{agente.importar_csv(argv[1])} leads nuevos importados")
    elif orden == "ciclo":
        agente.ciclo()
        print(agente.informe(agente.riesgo.motivo_pausa()))
    elif orden == "ejecutar":
        while True:
            agente.ciclo()
            time.sleep(cfg.get("minutos_entre_ciclos", 60) * 60)
    elif orden == "informe":
        print(agente.informe(agente.riesgo.motivo_pausa()))
    elif orden == "pausar":
        open(agente.riesgo.fichero_pausa, "w").close()
        print("Agente pausado")
    elif orden == "reanudar":
        agente.riesgo.reanudar()
        print("Agente reanudado")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
