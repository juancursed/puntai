"""Arranca el servidor: python -m uniteval"""

import os

import uvicorn

from uniteval.config import DEFAULT_PORT


def main() -> None:
    port = int(os.environ.get("UNITEVAL_PORT", DEFAULT_PORT))
    print(f"\n🔬 UnitEval arrancando en http://localhost:{port}\n")
    uvicorn.run("uniteval.app:app", host="127.0.0.1", port=port, reload=True)


if __name__ == "__main__":
    main()
