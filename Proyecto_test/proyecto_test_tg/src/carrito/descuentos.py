CUPONES = {
    "BIENVENIDO10": 10,
    "VERANO20": 20,
}


def aplicar_descuento_porcentaje(monto: float, porcentaje: float) -> float:
    """Aplica un descuento porcentual (0-100) a un monto."""
    if monto < 0:
        raise ValueError("El monto no puede ser negativo")
    if not 0 <= porcentaje <= 100:
        raise ValueError("El porcentaje debe estar entre 0 y 100")
    return round(monto * (1 - porcentaje / 100), 2)


def aplicar_cupon(monto: float, codigo: str) -> float:
    """Aplica un cupón válido al monto. Lanza ValueError si no existe."""
    porcentaje = CUPONES.get(codigo.strip().upper())
    if porcentaje is None:
        raise ValueError(f"Cupón inválido: {codigo}")
    return aplicar_descuento_porcentaje(monto, porcentaje)
