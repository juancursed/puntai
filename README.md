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
python main.py          # o bien: python -m uniteval
```

Abre el navegador en: **http://localhost:6060** (puedes cambiar el puerto con la variable `UNITEVAL_PORT`).

Para correr las pruebas de UnitEval:

```bash
python -m pytest
```

---

## Configuración

1. Ve a la pestaña **Configuración** en la interfaz
2. Ingresa la ruta a tu proyecto Python
3. Agrega tu API Key desde Configuración, o defínela en `.env` (ver `.env.example`)
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
tg/
├── main.py                    # Punto de entrada (python main.py)
├── pyproject.toml             # Metadatos y configuración de pytest
├── requirements.txt
├── config.json                # Generado al guardar la configuración
├── uniteval/                  # Paquete de la aplicación
│   ├── __main__.py            # Arranque del servidor (python -m uniteval)
│   ├── app.py                 # Construye la app FastAPI
│   ├── routes.py              # Endpoints /api/...
│   ├── schemas.py             # Modelos de entrada (Pydantic)
│   ├── config.py              # Rutas, config.json y API keys (.env)
│   ├── reports.py             # Guarda y lee reportes en reports/
│   ├── core/
│   │   ├── scanner.py         # Detecta pruebas con AST (sin ejecutar código)
│   │   ├── runner.py          # Ejecuta pytest y parsea resultados
│   │   └── source_resolver.py # Localiza el código que ejercita cada prueba
│   └── ai/
│       ├── client.py          # analyze_test: elige el proveedor
│       ├── providers.py       # Llamadas HTTP a Claude, OpenAI y Laguna
│       ├── parser.py          # Convierte la respuesta en análisis estructurado
│       ├── prompts.py         # Carga y rellena los prompts
│       └── prompts/
│           ├── system.md      # Prompt de sistema (rol, 4 pasos, few-shot)
│           └── user.md        # Plantilla con el código fuente y la prueba
├── frontend/
│   ├── templates/index.html   # Estructura de la interfaz
│   └── static/
│       ├── css/styles.css     # Estilos (tema claro y oscuro)
│       └── js/app.js          # Lógica de la interfaz
├── tests/                     # Pruebas de UnitEval, una por módulo
└── Proyecto_test/             # Proyecto de ejemplo a evaluar
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
