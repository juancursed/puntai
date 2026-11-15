# Carrito Demo — proyecto de ejemplo con pytest

Proyecto sencillo en Python (carrito de compras con descuentos) pensado para practicar pruebas unitarias con **pytest**.

## Estructura

```
proyecto_pytest/
├── src/carrito/
│   ├── __init__.py
│   ├── modelos.py      # Producto (dataclass inmutable con validaciones)
│   ├── carrito.py      # Clase Carrito
│   └── descuentos.py   # Descuentos porcentuales y cupones
├── tests/
│   ├── conftest.py     # Fixtures compartidas
│   ├── test_producto.py
│   ├── test_carrito.py
│   └── test_descuentos.py
├── pyproject.toml      # Configuración de pytest
└── requirements.txt
```

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate      # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecutar las pruebas

```bash
pytest                          # todas las pruebas
pytest tests/test_carrito.py    # un archivo
pytest -k cupon                 # filtrar por nombre
pytest -x                       # detenerse en el primer fallo
pytest --cov=carrito --cov-report=term-missing   # cobertura
```

## Conceptos de pytest que se muestran

- **Fixtures** (`conftest.py`): datos reutilizables entre archivos.
- **`@pytest.mark.parametrize`**: un mismo test con múltiples casos.
- **`pytest.raises`**: verificar excepciones (con `match` para el mensaje).
- **Pruebas de integración ligera**: carrito + descuentos.
