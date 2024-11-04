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
DATADOG_API_URL = "https://api.datadoghq.com/api/v1/series?api_key="
DATADOG_API_KEY = os.getenv("DATADOG_API_KEY")  # Lee la API Key de DataDog desde variables de entorno
MONGO_URI = os.getenv("MONGODB_URI")  # Lee la URI de MongoDB desde variables de entorno
# Flag para habilitar/deshabilitar el envío de logs a DataDog desde variables de entorno
ENABLE_SEND_LOG_TO_DATADOG = os.getenv("ENABLE_SEND_LOG_TO_DATADOG", "False").lower() == "true"

# Conexión a MongoDB
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["tomi-db"]
logs_collection = db["tomi-logs"]

def send_metric_to_datadog(metric_name, tags, points):
    """
    Función para enviar métricas a la API de DataDog con soporte para puntos específicos.
    """
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "series": [
            {
                "metric": metric_name,
                "points": points,
                "tags": tags
            }
        ]
    }

    response = requests.post(DATADOG_API_URL + DATADOG_API_KEY, json=payload, headers=headers)
    print(f"{response.status_code} {response.json()}")
    return response.status_code, response.json()

from datetime import datetime, timezone

def save_log_to_mongodb(message, level, log_date, service, ddsource, hostname, tags):
    """
    Función para almacenar logs en MongoDB con la estructura completa y con fecha de creación automática.
    """
    # Obtener la fecha y hora actual en formato datetime para MongoDB
    created_at = datetime.now(timezone.utc)
    
    # Convertir log_date a datetime si es una cadena en el formato especificado
    if isinstance(log_date, str):
        try:
            log_date = datetime.strptime(log_date, '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            print("Error: log_date no tiene el formato correcto. Usando fecha actual.")
            log_date = created_at  # Usa la fecha actual si el formato no coincide
    elif log_date is None:
        log_date = created_at  # Usa la fecha actual si no se proporciona log_date

    # Procesar tags: si es una cadena, dividirla en una lista
    if isinstance(tags, str):
        tags = tags.split(',')  # Divide los tags en una lista si están en una cadena separada por comas

    log = {
        "message": message,
        "level": level,
        "date": log_date,
        "service": service,
        "ddsource": ddsource,
        "hostname": hostname,
        "tags": tags,           # Almacenar los tags como una lista de strings
        "created_at": created_at
    }
    try:
        logs_collection.insert_one(log)
        print("Log insertado en MongoDB correctamente.")
    except Exception as e:
        print(f"Error al insertar el log en MongoDB: {e}")
        raise



def send_log_to_datadog(log_entry):
    """
    Función para enviar logs a DataDog solo si el flag ENABLE_SEND_LOG_TO_DATADOG está habilitado.
    """
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

@app.route('/')
def hello_world():
    return "Hola Mundo", 200

@app.route('/metrics', methods=['POST'])
def save_metric():
    data = request.json
    metric_name = data.get('metric')
    points = data.get('points')
    tags = data.get('tags', [])

    # Validación de la estructura
    if not metric_name or not isinstance(points, list) or not all(isinstance(tag, str) for tag in tags):
        return '', 400

    # Enviar a DataDog con los datos en el formato esperado
    status_code, response = send_metric_to_datadog(metric_name, tags, points)
    if status_code != 202:
        return '', status_code

    metric = {
        "metric": metric_name,
        "points": points,
        "tags": tags
    }
    metrics.append(metric)
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

    # Validación de campos obligatorios
    if not message or not service:
        return '', 400

    # Crear el log en el formato esperado por DataDog
    log_entry = {
        "message": message,
        "ddsource": ddsource,
        "service": service,
        "hostname": hostname,
        "status": level,
        "tags": tags,
        "date": log_date
    }

    # Guardar en MongoDB con el nuevo formato
    try:
        save_log_to_mongodb(message, level, log_date, service, ddsource, hostname, tags)
    except Exception as e:
        print(f"Error al insertar el log en MongoDB: {e}")
        return '', 500

    # Enviar log a DataDog
    send_log_to_datadog(log_entry)

    return jsonify({"message": "Log saved ok"}), 201

if __name__ == '__main__':
    app.run(debug=True)
