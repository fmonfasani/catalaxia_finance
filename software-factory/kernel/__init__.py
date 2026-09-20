"""Factory Kernel — nucleo de ejecucion de la Software Factory.

Independiente del ETL financiero de Catalaxia: ningun modulo de este paquete
importa `engine`, `scripts.engine`, `scripts.market` ni ningun otro componente
del pipeline financiero. Ver software-factory/FACTORY-KERNEL.md.
"""
from __future__ import annotations
