"""
UnitEval - Evaluador de pruebas unitarias con IA
Ejecutar con: python main.py  (equivale a: python -m uniteval)

Expone `app` para que Vercel detecte la aplicación FastAPI en este archivo.
"""

from uniteval.__main__ import main
from uniteval.app import app

__all__ = ["app"]

if __name__ == "__main__":
    main()
