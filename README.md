# UnitEval 🔬
**Evaluador automático de pruebas unitarias Python con IA**

Trabajo de grado — Aplicación web local que detecta, ejecuta y analiza pruebas unitarias usando Claude o GPT-4o.

---

## Requisitos

- Python 3.10+
- pip

---

## Instalación

```bash
# 1. Clona o descarga el proyecto
cd uniteval

# 2. (Opcional pero recomendado) Crea un entorno virtual
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
.venv\Scripts\activate           # Windows

# 3. Instala dependencias
pip install -r requirements.txt
```

---

## Uso

```bash
python main.py
```

Abre el navegador en: **http://localhost:8080**

---

## Configuración

1. Ve a la pestaña **Configuración** en la interfaz
2. Ingresa la ruta a tu proyecto Python
3. Agrega tu API Key de Claude (Anthropic) o GPT-4o (OpenAI)
4. Guarda la configuración

---

## Flujo de uso

```
1. Escanear proyecto  →  Detecta archivos test_*.py con AST
2. Ejecutar pruebas   →  Corre pytest y captura resultados
3. Evaluar con IA     →  Envía cada prueba a Claude/GPT-4o
4. Ver análisis       →  Calidad, sugerencias, casos no cubiertos
```

---

## Estructura del proyecto

```
uniteval/
├── main.py              # Servidor FastAPI (punto de entrada)
├── scanner.py           # Detecta pruebas con AST (sin ejecutar código)
├── runner.py            # Ejecuta pytest y parsea resultados
├── ai_client.py         # Cliente para Claude y OpenAI
├── requirements.txt
├── config.json          # Generado automáticamente al guardar config
└── frontend/
    └── templates/
        └── index.html   # Interfaz web completa
```

---

## API REST (endpoints)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/config` | Obtiene configuración actual |
| POST | `/api/config` | Guarda configuración |
| POST | `/api/scan` | Escanea el proyecto en busca de pruebas |
| POST | `/api/run` | Ejecuta pytest en el proyecto |
| POST | `/api/analyze` | Analiza una prueba con IA |

---

## Modelos soportados

- **Claude Sonnet 4** (Anthropic) — recomendado
- **GPT-4o** (OpenAI)

---

## Próximas funcionalidades (roadmap)

- [ ] Exportar reporte PDF
- [ ] Historial de análisis por sesión
- [ ] Análisis de cobertura con `coverage.py`
- [ ] Sugerencias automáticas de pruebas faltantes
- [ ] Soporte para clases de prueba (`TestCase`)
