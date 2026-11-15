import pytest

from carrito import aplicar_cupon, aplicar_descuento_porcentaje


@pytest.mark.parametrize(
    "monto, porcentaje, esperado",
    [
        (100, 0, 100),
        (100, 10, 90),
        (200, 25, 150),
        (50, 100, 0),
        (19.99, 15, 16.99),
    ],
)
def test_descuento_porcentaje(monto, porcentaje, esperado):
    assert aplicar_descuento_porcentaje(monto, porcentaje) == esperado


@pytest.mark.parametrize("porcentaje", [-1, 101, 500])
def test_porcentaje_fuera_de_rango(porcentaje):
    with pytest.raises(ValueError, match="porcentaje"):
        aplicar_descuento_porcentaje(100, porcentaje)


def test_monto_negativo():
    with pytest.raises(ValueError, match="monto"):
        aplicar_descuento_porcentaje(-5, 10)


def test_cupon_valido():
    assert aplicar_cupon(100, "BIENVENIDO10") == 90


def test_cupon_ignora_mayusculas_y_espacios():
    assert aplicar_cupon(100, "  verano20 ") == 80


def test_cupon_invalido():
    with pytest.raises(ValueError, match="Cupón inválido"):
        aplicar_cupon(100, "NOEXISTE")


def test_descuento_sobre_subtotal_del_carrito(carrito_con_items):
    """Prueba de integración ligera entre Carrito y descuentos."""
    total = aplicar_cupon(carrito_con_items.subtotal(), "VERANO20")
    assert total == 8.0
