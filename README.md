# Tomi Metric Collector

## Iniciar la aplicación

```sh
poetry run python tomi_metrics/app.py
```

o utilizando Gunicorn:

```sh
poetry run gunicorn -w 4 -b 0.0.0.0:8000 tomi_metrics.app:app --reload
```

## Ejemplos de solicitudes

### Enviar métrica localmente

```sh
curl -X POST http://localhost:5000/metrics \
     -H "Content-Type: application/json" \
     -d '{
           "metric": "tomi.metric.collector.test2.counter",
           "points": [[1730745173, 2]],
           "tags": ["host:localhost", "environment:develop"]
         }'
```

### Enviar log localmente

```sh
curl -X POST http://localhost:5000/log \
     -H "Content-Type: application/json" \
     -d '{
           "message": "An info occurred",
           "level": "info",
           "service": "test",
           "ddsource": "python",
           "hostname": "localhost",
           "tags": ["env:test"],
           "date": "2024-11-04T15:35:56"
         }'


curl -X POST http://localhost:5000/log \
     -H "Content-Type: application/json" \
     -d '{
           "message": "An error occurred",
           "level": "error",
           "service": "test",
           "ddsource": "python",
           "hostname": "localhost",
           "tags": ["env:production"],
           "date": "2024-11-04T14:34:56"
         }'
```

### Enviar métrica a producción

```sh
curl -X POST https://tomi-metric-collector-production.up.railway.app/metrics \
     -H "Content-Type: application/json" \
     -d '{
           "metric": "tomi.metric.collector.test3.counter",
           "points": [[1730746325, 1]],
           "tags": ["tag1:valor1asdas", "tag2:valor2wedaw"]
         }'
```

### Enviar log a producción

```sh
curl -X POST https://tomi-metric-collector-production.up.railway.app/log \
     -H "Content-Type: application/json" \
     -d '{
           "message": "An error occurred",
           "level": "error",
           "service": "test",
           "ddsource": "python",
           "hostname": "production-server",
           "tags": ["env:production"],
           "date": "2024-10-28T12:34:56"
         }'
```

### Verificar respuesta HTTP sin mostrar salida

```sh
curl -o /dev/null -s -w "%{http_code}\n" -X POST https://tomi-metric-collector-production.up.railway.app/log \
     -H "Content-Type: application/json" \
     -d '{
           "message": "System initialized",
           "level": "info",
           "service": "test",
           "ddsource": "python",
           "hostname": "production-server",
           "tags": ["env:production"]
         }'
```

### Ejemplo de log adicional a producción

```sh
curl -X POST https://tomi-metric-collector-production.up.railway.app/log \
     -H "Content-Type: application/json" \
     -d '{
           "message": "System started",
           "service": "test",
           "level": "info",
           "ddsource": "python",
           "hostname": "production-server",
           "tags": ["env:production"]
         }'
```
