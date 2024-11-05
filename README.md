# Tomi Metric Collector

## Iniciar la aplicación

 README en un solo bloque de código continuo para facilitar la copia
```sh
poetry run python tomi_metrics/app.py
poetry run gunicorn -w 4 -b 0.0.0.0:8000 tomi_metrics.app:app --reload
curl -X POST http://localhost:5000/metrics -H "Content-Type: application/json" -d '{
  "series": [
    {
      "metric": "tomi.metric.collector.test2.counter",
      "points": [[1730745173, 2]],
      "tags": ["host:localhost", "environment:develop"],
      "host": "localhost"
    }
  ]
}'

curl -X POST http://localhost:5000/log -H "Content-Type: application/json" -d '{
  "message": "An info occurred",
  "level": "info",
  "service": "test",
  "ddsource": "python",
  "hostname": "localhost",
  "tags": ["env:test"],
  "date": "2024-11-04T15:35:56"
}'

curl -X POST http://localhost:5000/log -H "Content-Type: application/json" -d '{
  "message": "An error occurred",
  "level": "error",
  "service": "test",
  "ddsource": "python",
  "hostname": "localhost",
  "tags": ["env:production"]
}'

curl -X POST https://tomi-metric-collector-production.up.railway.app/metrics -H "Content-Type: application/json" -d '{
  "series": [
    {
      "metric": "tomi.metric.collector.test4.counter",
      "points": [[1730746325, 1]],
      "tags": ["tag1:valor1asdas", "tag2:valor2wedaw"],
      "host": "production-server"
    }
  ]
}'

curl -X POST https://tomi-metric-collector-production.up.railway.app/log -H "Content-Type: application/json" -d '{
  "message": "An error occurred",
  "level": "error",
  "service": "test",
  "ddsource": "python",
  "hostname": "production-server",
  "tags": ["env:production"],
  "date": "2024-10-28T12:34:56"
}'

curl -o /dev/null -s -w "%{http_code}\n" -X POST https://tomi-metric-collector-production.up.railway.app/log -H "Content-Type: application/json" -d '{
  "message": "System initialized",
  "level": "info",
  "service": "test",
  "ddsource": "python",
  "hostname": "production-server",
  "tags": ["env:production"]
}'

curl -X POST https://tomi-metric-collector-production.up.railway.app/log -H "Content-Type: application/json" -d '{
  "message": "System started",
  "service": "test",
  "level": "info",
  "ddsource": "python",
  "hostname": "production-server",
  "tags": ["env:production"]
}'

# Nuevo endpoint para enviar un arreglo de logs https://tomi-metric-collector-production.up.railway.app
curl -X POST http://localhost:5000/logs -H "Content-Type: application/json" -d '{
  "logs": [
    {
      "message": "First log message11",
      "level": "info",
      "service": "test",
      "ddsource": "python",
      "hostname": "localhost",
      "tags": ["env:test"]

    },
    {
      "message": "Second log message22",
      "level": "error",
      "service": "test",
      "ddsource": "python",
      "hostname": "localhost",
      "tags": ["env:production"],
      "date": "2024-11-05T20:20:56"
    }
  ]
}'
