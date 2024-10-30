from flask import Flask, request, jsonify
import requests
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from datetime import datetime

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

app = Flask(__name__)

# Variables en memoria para almacenar los datos
metrics = []
logs = []

# Configuración de DataDog y MongoDB desde variables de entorno
DATADOG_API_URL = "https://api.datadoghq.com/api/v1/series"
DATADOG_API_KEY = os.getenv("DATADOG_API_KEY")  # Lee la API Key de DataDog desde variables de entorno
MONGO_URI = os.getenv("MONGO_URI")  # Lee la URI de MongoDB desde variables de entorno

# Conexión a MongoDB
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["tomi-db"]  # Reemplaza "database_name" con el nombre de tu base de datos
logs_collection = db["tomi-logs"]  # Colección para guardar los logs


def send_metric_to_datadog(metric_name, tags):
    """
    Función para enviar métricas a la API de DataDog.
    """
    headers = {
        "Content-Type": "application/json",
        "DD-API-KEY": DATADOG_API_KEY
    }
    payload = {
        "series": [
            {
                "metric": metric_name,
                "points": [[int(datetime.now().timestamp()), 1]],  # Utiliza datetime.now().timestamp() para el timestamp
                "tags": [f"{tag['key']}:{tag['value']}" for tag in tags]
            }
        ]
    }

    response = requests.post(DATADOG_API_URL, json=payload, headers=headers)
    return response.status_code, response.json()


def save_log_to_mongodb(message, level, log_date, service):
    """
    Función para almacenar logs en MongoDB.
    """
    log = {
        "message": message,
        "level": level,
        "date": log_date,
        "service": service
    }
    logs_collection.insert_one(log)


@app.route('/')
def hello_world():
    return "Hola Mundo", 200


@app.route('/metrics', methods=['POST'])
def save_metric():
    data = request.json
    metric_name = data.get('name')
    tags = data.get('tags')

    if not metric_name:
        return '', 400

    # Verificación de la estructura de cada tag
    if not isinstance(tags, list) or not all(isinstance(tag, dict) and "key" in tag and "value" in tag for tag in tags):
        return '', 400

    # Llamada a DataDog
    status_code, response = send_metric_to_datadog(metric_name, tags)
    if status_code != 202:
        return '', status_code

    metric = {
        "name": metric_name,
        "tags": tags
    }
    metrics.append(metric)
    return jsonify({"message": "Metric saved ok"}), 201  # Devuelve un mensaje de éxito en el cuerpo


@app.route('/log', methods=['POST'])
def save_log():
    data = request.json
    message = data.get('message')
    level = data.get('level')
    service = data.get('service')
    log_date = data.get('date', datetime.utcnow().isoformat())  # Usa la fecha actual si no se proporciona una

    # Validación de campos obligatorios
    if not message or not level or not service:
        return '', 400

    try:
        # Guardar log en MongoDB
        save_log_to_mongodb(message, level, log_date, service)
        return jsonify({"message": "Log saved ok"}), 201  # Devuelve un mensaje de éxito en el cuerpo
    except Exception as e:
        return '', 500  # Devuelve solo el código de error sin cuerpo en caso de fallo


if __name__ == '__main__':
    app.run(debug=True)
