"""Configuración común de pytest: permite importar el paquete uniteval desde la raíz."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
