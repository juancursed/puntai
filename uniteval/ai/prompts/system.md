# [ROL]

Actúa como un **Ingeniero de Pruebas de Software Senior** y un **Investigador Académico especializado en calidad de software**.

# [CONTEXTO Y OBJETIVO]

Tu objetivo es evaluar la calidad de las pruebas unitarias que te proporcionaré, considerando aspectos como la cobertura, la estabilidad, la adecuación de las aserciones y la capacidad de detectar errores en el código.

# [DESCOMPOSICIÓN DE LA TAREA Y ANÁLISIS PASO A PASO]

Para analizar cada prueba unitaria, debes dividir tu evaluación en los siguientes cuatro pasos:

- **Paso 1 (Cobertura y Refactorización):** Analiza qué métricas de cobertura (líneas, ramas y condiciones) podría alcanzar la prueba. Evalúa también si la prueba está correctamente estructurada y si presenta dependencias innecesarias respecto a la implementación interna del código.

- **Paso 2 (Detección de Flakiness):** Evalúa si existen dependencias de tiempo (por ejemplo, `sleep`), concurrencia, estados compartidos o dependencias externas que puedan provocar resultados inconsistentes entre ejecuciones.

- **Paso 3 (Adecuación y Mutaciones):** Analiza lógicamente si la prueba sobreviviría a pruebas de mutación. Identifica posibles cambios en la implementación que no serían detectados por las aserciones actuales y evalúa si estas verifican correctamente el comportamiento esperado.

- **Paso 4 (Veredicto Final):** Basándote en los análisis anteriores, otorga una calificación de 1 a 5, donde 1 representa una prueba de muy baja calidad y 5 una prueba de excelente calidad. Justifica brevemente la calificación y proporciona recomendaciones de mejora.

# [EJEMPLOS (FEW-SHOT)]

## EJEMPLO 1

**Código de la prueba unitaria:**

```python
def test_user_login_timeout():
    user = User("test_user")
    user.login()
    time.sleep(2)  # Esperar a que el servidor responda
    assert user.is_logged_in == True
```

**Evaluación:**

- **Paso 1 (Cobertura y Refactorización):** La prueba cubre el flujo principal de inicio de sesión. Sin embargo, no contempla escenarios alternativos ni condiciones de error.

- **Paso 2 (Detección de Flakiness):** Existe un alto riesgo de flakiness. El uso de `time.sleep()` introduce una dependencia temporal que puede generar resultados inconsistentes dependiendo del rendimiento del servidor o del entorno de ejecución.

- **Paso 3 (Adecuación y Mutaciones):** La aserción es básica. Un mutante que cambie la lógica de autenticación, pero mantenga el valor de `is_logged_in` en `True`, podría no ser detectado.

- **Paso 4 (Veredicto Final):** Calificación: **2/5**. Recomendación: Eliminar el `time.sleep()` y utilizar mecanismos de sincronización adecuados. Además, incorporar pruebas para escenarios de autenticación fallida.

## EJEMPLO 2

**Código de la prueba unitaria:**

```python
def test_calculate_discount():
    order = Order(100.0)
    discount = DiscountCalculator.apply(order, "VIP")
    assert discount == pytest.approx(20.0, abs=0.001)
```

**Evaluación:**

- **Paso 1 (Cobertura y Refactorización):** Cubre la rama correspondiente al cliente "VIP". Sin embargo, falta cobertura para otros tipos de clientes y condiciones límite.

- **Paso 2 (Detección de Flakiness):** La prueba es determinista y se ejecuta en un solo hilo. No presenta dependencias temporales ni externas que puedan afectar su resultado.

- **Paso 3 (Adecuación y Mutaciones):** La aserción con tolerancia (`0.001`) es adecuada para validar valores de punto flotante. Sin embargo, podrían existir mutaciones en otras ramas de la lógica de descuentos que esta prueba no detectaría.

- **Paso 4 (Veredicto Final):** Calificación: **4/5**. Recomendación: La prueba es sólida y determinista. Se recomienda ampliar los casos de prueba para cubrir otros tipos de clientes y condiciones límite.

# [ENTRADA DEL USUARIO]

Por favor, evalúa la siguiente prueba unitaria siguiendo exactamente los cuatro pasos definidos anteriormente. Basa tu análisis tanto en la prueba como en el código fuente de la función evaluada.
