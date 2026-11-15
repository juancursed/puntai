from dataclasses import dataclass


@dataclass(frozen=True)
class Producto:
    """Representa un producto con nombre y precio unitario."""

    nombre: str
    precio: float

    def __post_init__(self):
        if not self.nombre or not self.nombre.strip():
            raise ValueError("El nombre del producto no puede estar vacío")
        if self.precio < 0:
            raise ValueError("El precio no puede ser negativo")
