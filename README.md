# Tomi Metric Collector

Colector centralizado de métricas y logs que actúa como intermediario entre tus aplicaciones y servicios de monitoreo (DataDog y MongoDB).

## Descripción

Tomi Metric Collector recibe métricas y logs desde múltiples aplicaciones y los distribuye a:
- **DataDog**: Para dashboards, alertas y monitoreo en tiempo real
- **MongoDB**: Para persistencia y consultas propias

### Características

- Procesamiento asíncrono con ThreadPoolExecutor (10 workers)
- Conexión lazy a MongoDB (no falla si no está disponible)
- Feature flags para habilitar/deshabilitar destinos independientemente
- Respuestas inmediatas (HTTP 202) sin bloquear
- Documentación Swagger/OpenAPI integrada

## Estructura del Proyecto

```
tomi-metric-collector/
├── tomi_metrics/
│   ├── app.py              # Lógica principal de la aplicación
│   ├── templates/
│   │   └── home.html       # Template HTML del home
│   └── static/
│       ├── css/
│       │   └── style.css   # Estilos CSS
│       └── js/
│           └── main.js     # JavaScript (función copiar)
├── pyproject.toml          # Configuración de Poetry
├── README.md
└── .env                    # Variables de entorno (no versionado)
```

## Instalación

```bash
# Clonar el repositorio
git clone https://github.com/tu-usuario/tomi-metric-collector.git
cd tomi-metric-collector

# Instalar dependencias
poetry install
```

## Configuración

Crear un archivo `.env` en la raíz del proyecto:

```env
MONGODB_URI=mongodb://usuario:password@host:puerto/
DATADOG_API_KEY=tu_api_key_de_datadog
ENABLE_MONGO_DB=true
ENABLE_SEND_LOG_TO_DATADOG=true
```

### Variables de entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `MONGODB_URI` | URI de conexión a MongoDB | - |
| `ENABLE_MONGO_DB` | Habilita almacenamiento en MongoDB | `false` |
| `DATADOG_API_KEY` | API Key de DataDog | - |
| `ENABLE_SEND_LOG_TO_DATADOG` | Habilita envío de logs a DataDog | `false` |

## Ejecución

### Desarrollo

```bash
poetry run python tomi_metrics/app.py
```

### Producción

```bash
poetry run gunicorn -w 4 -b 0.0.0.0:8000 tomi_metrics.app:app
```

## Documentación API

### Swagger UI
Accede a la documentación interactiva en: `http://localhost:5000/apidocs`

### Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/` | Home con documentación y estado |
| GET | `/apidocs` | Swagger UI |
| POST | `/metrics` | Enviar métricas |
| POST | `/log` | Enviar un log |
| POST | `/logs` | Enviar múltiples logs |

## Ejemplos de Uso

### Enviar métricas

```bash
curl -X POST http://localhost:5000/metrics \
  -H "Content-Type: application/json" \
  -d '{
    "series": [{
      "metric": "mi.metrica.contador",
      "points": [[1730745173, 2]],
      "tags": ["host:localhost", "environment:develop"],
      "host": "localhost"
    }]
  }'
```

### Enviar un log

```bash
curl -X POST http://localhost:5000/log \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Un evento ocurrió",
    "level": "info",
    "service": "mi-servicio",
    "ddsource": "python",
    "hostname": "localhost",
    "tags": ["env:production"],
    "date": "2024-11-04T15:35:56"
  }'
```

### Enviar múltiples logs

```bash
curl -X POST http://localhost:5000/logs \
  -H "Content-Type: application/json" \
  -d '{
    "logs": [
      {
        "message": "Primer log",
        "level": "info",
        "service": "mi-servicio"
      },
      {
        "message": "Segundo log",
        "level": "error",
        "service": "mi-servicio"
      }
    ]
  }'
```

## Arquitectura

```
┌─────────────┐     ┌──────────────────────┐     ┌──────────┐
│   App 1     │────▶│                      │────▶│ DataDog  │
├─────────────┤     │  Tomi Metric         │     └──────────┘
│   App 2     │────▶│  Collector           │
├─────────────┤     │                      │     ┌──────────┐
│   App N     │────▶│                      │────▶│ MongoDB  │
└─────────────┘     └──────────────────────┘     └──────────┘
```

## Base de datos

MongoDB almacena los datos en la base `tomi-db` con las siguientes colecciones:

- `tomi-logs`: Almacena todos los logs recibidos
- `tomi-metrics`: Almacena todas las métricas recibidas

## Despliegue

La aplicación está desplegada en Railway:
- **Producción**: https://tomi-metric-collector-production.up.railway.app
- **Swagger**: https://tomi-metric-collector-production.up.railway.app/apidocs

## Licencia

MIT
