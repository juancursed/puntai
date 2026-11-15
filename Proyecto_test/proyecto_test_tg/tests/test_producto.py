import dataclasses

import pytest

from carrito import Producto


def test_crear_producto_valido():
    p = Producto("Leche", 3.2)
    assert p.nombre == "Leche"
    assert p.precio == 3.2


@pytest.mark.parametrize("nombre", ["", "   "])
def test_nombre_vacio_lanza_error(nombre):
    with pytest.raises(ValueError, match="nombre"):
        Producto(nombre, 1.0)


def test_precio_negativo_lanza_error():
    with pytest.raises(ValueError, match="negativo"):
        Producto("Leche", -1)


def test_producto_es_inmutable():
    p = Producto("Leche", 3.2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.precio = 5
