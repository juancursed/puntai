import pytest


def test_carrito_nuevo_esta_vacio(carrito_vacio):
    assert carrito_vacio.esta_vacio()
    assert carrito_vacio.total_items() == 0
    assert carrito_vacio.subtotal() == 0


def test_agregar_producto(carrito_vacio, manzana):
    carrito_vacio.agregar(manzana, 3)
    assert carrito_vacio.cantidad_de("Manzana") == 3
    assert not carrito_vacio.esta_vacio()


def test_agregar_mismo_producto_acumula_cantidad(carrito_vacio, manzana):
    carrito_vacio.agregar(manzana, 2)
    carrito_vacio.agregar(manzana, 3)
    assert carrito_vacio.cantidad_de("Manzana") == 5


@pytest.mark.parametrize("cantidad", [0, -1, -10])
def test_agregar_cantidad_invalida(carrito_vacio, manzana, cantidad):
    with pytest.raises(ValueError):
        carrito_vacio.agregar(manzana, cantidad)


def test_subtotal_y_total_items(carrito_con_items):
    assert carrito_con_items.subtotal() == 10.0
    assert carrito_con_items.total_items() == 6


def test_eliminar_producto(carrito_con_items):
    carrito_con_items.eliminar("Pan")
    assert carrito_con_items.cantidad_de("Pan") == 0
    assert carrito_con_items.subtotal() == 6.0


def test_eliminar_producto_inexistente(carrito_vacio):
    with pytest.raises(KeyError):
        carrito_vacio.eliminar("Fantasma")


def test_vaciar_carrito(carrito_con_items):
    carrito_con_items.vaciar()
    assert carrito_con_items.esta_vacio()
