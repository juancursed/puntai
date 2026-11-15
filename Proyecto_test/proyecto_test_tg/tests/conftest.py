import pytest

from carrito import Carrito, Producto


@pytest.fixture
def manzana():
    return Producto("Manzana", 1.5)


@pytest.fixture
def pan():
    return Producto("Pan", 2.0)


@pytest.fixture
def carrito_vacio():
    return Carrito()


@pytest.fixture
def carrito_con_items(manzana, pan):
    carrito = Carrito()
    carrito.agregar(manzana, 4)  # 6.0
    carrito.agregar(pan, 2)      # 4.0
    return carrito
