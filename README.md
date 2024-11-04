```sh {"id":"01HJQ7F9RXZBJJ4YEQA7Q49GYF"}
poetry run python tomi_metrics/app.py


poetry run gunicorn -w 4 -b 0.0.0.0:8000 tomi_metrics.app:app --reload
```

```sh
curl -X POST http://localhost:5000/metrics \
     -H "Content-Type: application/json" \
     -d '{
           "metric": "cpu_usage",
           "points": [[1700749200, 0.5]],
           "tags": ["host:server1", "environment:production"]
         }'
```

```sh
curl -X POST http://localhost:5000/log \
     -H "Content-Type: application/json" \
     -d '{
           "message": "An error occurred",
           "level": "error",
           "service": "test",
           "date": "2024-10-28T12:34:56"
         }'
```

### tomi-metric-collector-production.up.railway.app

```sh
curl -X POST https://tomi-metric-collector-production.up.railway.app/metrics \
     -H "Content-Type: application/json" \
     -d '{
           "metric": "tomi.metric.collector.test.counter",
           "points": [[1700749200, 1]],
           "tags": ["tag1:valor1asdas", "tag2:valor2wedaw"]
         }'
```

```sh
curl -X POST https://tomi-metric-collector-production.up.railway.app/log \
     -H "Content-Type: application/json" \
     -d '{
           "message": "An error occurred",
           "level": "error",
           "service": "test",
           "date": "2024-10-28T12:34:56"
         }'
```

```sh
curl -o /dev/null -s -w "%{http_code}\n" -X POST http://tomi-metric-collector-production.up.railway.app/log \
     -H "Content-Type: application/json" \
     -d '{
           "message": "System initialized",
           "level": "info",
           "service": "test"
         }'
```

```sh
curl -X POST https://tomi-metric-collector-production.up.railway.app/log \
     -H "Content-Type: application/json" \
     -d '{
           "message": "System started",
           "service": "test",
           "level": "info"
         }'
```
