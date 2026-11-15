from .modelos import Producto


class Carrito:
    """Carrito de compras sencillo."""

    def __init__(self):
        self._items: dict[str, tuple[Producto, int]] = {}

    def agregar(self, producto: Producto, cantidad: int = 1) -> None:
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor que cero")
        actual = self._items.get(producto.nombre)
        if actual:
            self._items[producto.nombre] = (producto, actual[1] + cantidad)
        else:
            self._items[producto.nombre] = (producto, cantidad)

    def eliminar(self, nombre: str) -> None:
        if nombre not in self._items:
            raise KeyError(f"El producto '{nombre}' no está en el carrito")
        del self._items[nombre]

    def cantidad_de(self, nombre: str) -> int:
        return self._items[nombre][1] if nombre in self._items else 0

    def total_items(self) -> int:
        return sum(cantidad for _, cantidad in self._items.values())

    def subtotal(self) -> float:
        return round(
            sum(p.precio * cantidad for p, cantidad in self._items.values()), 2
        )

    def esta_vacio(self) -> bool:
        return not self._items

    def vaciar(self) -> None:
        self._items.clear()
