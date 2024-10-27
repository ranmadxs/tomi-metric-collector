README.md

```sh {"id":"01HJQ7F9RXZBJJ4YEQA7Q49GYF"}
poetry run python tomi_metrics/app.py


poetry run gunicorn -w 4 -b 0.0.0.0:8000 tomi_metrics.app:app --reload

```