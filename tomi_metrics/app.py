from flask import Flask, request, jsonify
import requests
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from datetime import datetime, timezone

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

app = Flask(__name__)

# Variables en memoria para almacenar los datos
metrics = []
logs = []

# Configuración de DataDog y MongoDB desde variables de entorno
DATADOG_API_URL = "https://api.datadoghq.com/api/v1/series?api_key="
DATADOG_API_KEY = os.getenv("DATADOG_API_KEY")  # API Key de DataDog desde variables de entorno
MONGO_URI = os.getenv("MONGODB_URI")  # URI de MongoDB desde variables de entorno
ENABLE_SEND_LOG_TO_DATADOG = os.getenv("ENABLE_SEND_LOG_TO_DATADOG", "False").lower() == "true"
ENABLE_MONGO_DB = os.getenv("ENABLE_MONGO_DB", "False").lower() == "true"  # Default False para métricas y logs

# Conexión a MongoDB
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["tomi-db"]
logs_collection = db["tomi-logs"]
dmMetrics = db["tomi-metrics"]

def send_metric_to_datadog(series):
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "series": series
    }
    response = requests.post(DATADOG_API_URL + DATADOG_API_KEY, json=payload, headers=headers)
    print(f"{response.status_code} {response.json()}")
    return response.status_code, response.json()

def send_metric_to_mongodb(series):
    if not ENABLE_MONGO_DB:
        return  # Salir si el almacenamiento en MongoDB está deshabilitado

    for metric in series:
        metric["created_at"] = datetime.now(timezone.utc)  # Fecha de creación en UTC
        try:
            dmMetrics.insert_one(metric)
            print("Métrica insertada en MongoDB correctamente.")
        except Exception as e:
            print(f"Error al insertar la métrica en MongoDB: {e}")
            raise

@app.route('/')
def hello_world():
    return "Hola Mundo", 200

@app.route('/metrics', methods=['POST'])
def save_metric():
    data = request.json
    series = data.get("series", [])
    
    if not series or not isinstance(series, list):
        return jsonify({"error": "Formato de datos incorrecto"}), 400

    # Enviar las métricas a DataDog y MongoDB
    status_code, response = send_metric_to_datadog(series)
    if status_code != 202:
        return '', status_code

    send_metric_to_mongodb(series)

    metrics.extend(series)
    return jsonify({"message": "Metric saved ok"}), 201

@app.route('/log', methods=['POST'])
def save_log():
    data = request.json
    message = data.get('message')
    level = data.get('level', 'info')
    service = data.get('service', 'my-service')
    ddsource = data.get('ddsource', 'python')
    hostname = data.get('hostname', os.getenv("HOSTNAME", "localhost"))
    tags = data.get('tags', [])
    log_date = data.get('date', datetime.utcnow().isoformat())

    if not message or not service:
        return '', 400

    log_entry = {
        "message": message,
        "ddsource": ddsource,
        "service": service,
        "hostname": hostname,
        "status": level,
        "tags": tags,
        "date": log_date
    }

    try:
        save_log_to_mongodb(message, level, log_date, service, ddsource, hostname, tags)
    except Exception as e:
        print(f"Error al insertar el log en MongoDB: {e}")
        return '', 500

    send_log_to_datadog(log_entry)

    return jsonify({"message": "Log saved ok"}), 201

def save_log_to_mongodb(message, level, log_date, service, ddsource, hostname, tags):
    if not ENABLE_MONGO_DB:
        return  # Salir si el almacenamiento de logs en MongoDB está deshabilitado

    created_at = datetime.now(timezone.utc)
    
    if isinstance(log_date, str):
        try:
            log_date = datetime.strptime(log_date, '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            print("Error: log_date no tiene el formato correcto. Usando fecha actual.")
            log_date = created_at
    elif log_date is None:
        log_date = created_at

    if isinstance(tags, str):
        tags = tags.split(',')

    log = {
        "message": message,
        "level": level,
        "date": log_date,
        "service": service,
        "ddsource": ddsource,
        "hostname": hostname,
        "tags": tags,
        "created_at": created_at
    }
    try:
        logs_collection.insert_one(log)
        print("Log insertado en MongoDB correctamente.")
    except Exception as e:
        print(f"Error al insertar el log en MongoDB: {e}")
        raise

def send_log_to_datadog(log_entry):
    if not ENABLE_SEND_LOG_TO_DATADOG:
        return  # Salir si el envío está deshabilitado

    try:
        headers = {
            "Content-Type": "application/json",
            "DD-API-KEY": DATADOG_API_KEY
        }
        datadog_response = requests.post(
            "https://http-intake.logs.datadoghq.com/v1/input",
            json=log_entry,
            headers=headers
        )
        if datadog_response.status_code != 200:
            print(f"Error al enviar el log a DataDog: Status {datadog_response.status_code}")
    except Exception as e:
        print(f"Error al enviar el log a DataDog: {e}")

if __name__ == '__main__':
    app.run(debug=True)
