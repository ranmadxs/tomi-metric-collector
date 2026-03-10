from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flasgger import Swagger, swag_from
import requests
from pymongo import MongoClient
import os
import secrets
from functools import wraps
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import tomllib

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Obtener información del proyecto desde pyproject.toml
BASE_DIR = Path(__file__).resolve().parent.parent
APP_NAME = "Tomi Metric Collector"
APP_VERSION = "0.1.12"

try:
    with open(BASE_DIR / "pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
        APP_NAME = pyproject.get("tool", {}).get("poetry", {}).get("name", APP_NAME)
        APP_VERSION = pyproject.get("tool", {}).get("poetry", {}).get("version", APP_VERSION)
except Exception:
    pass

def get_readme_content():
    """Lee el contenido del README.md"""
    try:
        with open(BASE_DIR / "README.md", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "README no disponible"

def check_mongodb_connection():
    """Verifica si MongoDB está conectado y retorna info de conexión"""
    mongo_uri = os.getenv("MONGODB_URI", "")
    
    if not mongo_uri:
        return {
            "connected": False,
            "status": "No configurado",
            "uri": "No configurado"
        }
    
    try:
        test_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
        test_client.admin.command('ping')
        test_client.close()
        return {
            "connected": True,
            "status": "Conectado",
            "uri": mask_uri(mongo_uri)
        }
    except Exception as e:
        return {
            "connected": False,
            "status": "Error de conexión",
            "uri": mask_uri(mongo_uri)
        }

def check_datadog_connection():
    """Verifica si DataDog está configurado y retorna info"""
    api_key = os.getenv("DATADOG_API_KEY", "")
    enabled = os.getenv("ENABLE_SEND_LOG_TO_DATADOG", "False").lower() == "true"
    
    if not enabled:
        return {
            "connected": False,
            "enabled": False,
            "status": "Deshabilitado",
            "api_key": mask_api_key(api_key) if api_key else "No configurado"
        }
    
    if not api_key:
        return {
            "connected": False,
            "enabled": True,
            "status": "API Key no configurada",
            "api_key": "No configurado"
        }
    
    try:
        response = requests.get(
            "https://api.datadoghq.com/api/v1/validate",
            headers={"DD-API-KEY": api_key},
            timeout=5
        )
        if response.status_code == 200:
            return {
                "connected": True,
                "enabled": True,
                "status": "Conectado",
                "api_key": mask_api_key(api_key)
            }
        else:
            return {
                "connected": False,
                "enabled": True,
                "status": "Error de conexión",
                "api_key": mask_api_key(api_key)
            }
    except Exception as e:
        return {
            "connected": False,
            "enabled": True,
            "status": "Error de conexión",
            "api_key": mask_api_key(api_key)
        }

def mask_uri(uri, max_length=25):
    """Oculta credenciales en la URI de MongoDB y limita longitud"""
    if not uri:
        return "No configurado"
    try:
        if "@" in uri:
            parts = uri.split("@")
            host_part = parts[-1]
            if len(host_part) > max_length:
                host_part = host_part[:max_length] + "..."
            return f"***@{host_part}"
        if len(uri) > max_length:
            return uri[:max_length] + "..."
        return uri
    except Exception:
        return "***"

def mask_api_key(key):
    """Oculta la API key mostrando solo los primeros y últimos caracteres"""
    if not key:
        return "No configurado"
    if len(key) < 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')

# Secret key para sesiones
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))

# Autenticación
AUTH_USERNAME = os.getenv('AUTH_USERNAME', 'admin')
AUTH_PASSWORD = os.getenv('AUTH_PASSWORD', 'admin')


def login_required(f):
    """Decorador para proteger rutas que requieren autenticación."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# Configuración de Swagger
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/"
}

swagger_template = {
    "info": {
        "title": APP_NAME,
        "description": "Colector centralizado de métricas y logs para DataDog y MongoDB",
        "version": APP_VERSION,
        "contact": {
            "name": "Edgar",
        }
    },
    "basePath": "/",
    "schemes": ["http", "https"],
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)

# Variables en memoria para almacenar los datos
metrics = []
logs = []

# Configuración de DataDog y MongoDB desde variables de entorno
DATADOG_API_URL = "https://api.datadoghq.com/api/v1/series?api_key="
DATADOG_API_KEY = os.getenv("DATADOG_API_KEY")  # API Key de DataDog desde variables de entorno
MONGO_URI = os.getenv("MONGODB_URI", "")  # URI de MongoDB desde variables de entorno
ENABLE_SEND_LOG_TO_DATADOG = os.getenv("ENABLE_SEND_LOG_TO_DATADOG", "False").lower() == "true"

# Conexión lazy a MongoDB
mongo_client = None
db = None
logs_collection = None
dmMetrics = None

def get_mongo_collections():
    """Inicializa la conexión a MongoDB de forma lazy (solo cuando se necesita)"""
    global mongo_client, db, logs_collection, dmMetrics
    
    if not MONGO_URI:
        return None, None
    
    if mongo_client is None:
        try:
            mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            mongo_client.admin.command('ping')
            db = mongo_client["tomi-db"]
            logs_collection = db["tomi-logs"]
            dmMetrics = db["tomi-metrics"]
            print("Conexión a MongoDB establecida correctamente.")
        except Exception as e:
            print(f"Error al conectar a MongoDB: {e}")
            return None, None
    
    return logs_collection, dmMetrics

# Crear un ejecutor de hilos con un número específico de trabajadores
executor = ThreadPoolExecutor(max_workers=10)

def send_metric_to_datadog(series):
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "series": series
    }
    try:
        response = requests.post(DATADOG_API_URL + DATADOG_API_KEY, json=payload, headers=headers)
        print(f"{response.status_code} {response.json()}")
        return response.status_code, response.json()
    except Exception as e:
        print(f"Error al enviar métricas a DataDog: {e}")
        print(payload)
        return 500, {"error": str(e)}

def send_metric_to_mongodb(series):
    if not MONGO_URI:
        return  # Salir si MongoDB no está configurado

    _, metrics_collection = get_mongo_collections()
    if metrics_collection is None:
        print("MongoDB no disponible, métrica no guardada.")
        return

    for metric in series:
        metric["created_at"] = datetime.now(timezone.utc)  # Fecha de creación en UTC
        try:
            metrics_collection.insert_one(metric)
            print("Métrica insertada en MongoDB correctamente.")
        except Exception as e:
            print(f"Error al insertar la métrica en MongoDB: {e}")

def process_log_entry(data):
    message = data.get('message')
    level = data.get('level', 'info')
    service = data.get('service', 'my-service')
    ddsource = data.get('ddsource', 'python')
    hostname = data.get('hostname', os.getenv("HOSTNAME", "localhost"))
    tags = data.get('tags', [])
    log_date = data.get('date', datetime.now(timezone.utc).isoformat())

    if not message or not service:
        raise ValueError("Cada log debe tener un mensaje y servicio")

    log_entry = {
        "message": message,
        "ddsource": ddsource,
        "service": service,
        "hostname": hostname,
        "status": level,
        "tags": tags,
        "date": log_date
    }

    save_log_to_mongodb(message, level, log_date, service, ddsource, hostname, tags)
    send_log_to_datadog(log_entry)

def process_log_entry_safe(data):
    try:
        process_log_entry(data)
    except ValueError as e:
        print(f"Error de valor en el log: {e}")
    except Exception as e:
        print(f"Error inesperado al procesar el log: {e}")

# ============================================================
# AUTENTICACIÓN
# ============================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login."""
    error = None
    next_url = request.args.get('next', '')
    
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        next_url = request.form.get('next', '')
        
        if username == AUTH_USERNAME and password == AUTH_PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            if next_url:
                return redirect(next_url)
            return redirect(url_for('home'))
        else:
            error = 'Usuario o contraseña incorrectos'
    
    return render_template('login.html', error=error, version=APP_VERSION, next_url=next_url)


@app.route('/logout')
def logout():
    """Cerrar sesión."""
    session.clear()
    next_url = request.args.get('next', '')
    if next_url and next_url != '/':
        return redirect(next_url)
    return redirect(url_for('login'))


# ============================================================
# ENDPOINTS
# ============================================================

@app.route('/')
@login_required
def home():
    """
    Home - Documentación y estado de la API
    ---
    tags:
      - General
    responses:
      200:
        description: Página principal con documentación y estado de conexiones
    """
    mongo_status = check_mongodb_connection()
    datadog_status = check_datadog_connection()
    mqtt_status = get_mqtt_status()
    
    is_logged_in = session.get('logged_in', False)
    
    return render_template(
        'home.html',
        app_name=APP_NAME,
        app_version=APP_VERSION,
        mongo_status=mongo_status,
        datadog_status=datadog_status,
        mqtt_status=mqtt_status,
        is_logged_in=is_logged_in
    ), 200

@app.route('/metrics', methods=['POST'])
def save_metric():
    """
    Enviar métricas
    ---
    tags:
      - Metrics
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - series
          properties:
            series:
              type: array
              description: Lista de métricas a enviar
              items:
                type: object
                properties:
                  metric:
                    type: string
                    description: Nombre de la métrica
                    example: "mi.metrica.contador"
                  points:
                    type: array
                    description: Puntos de datos [[timestamp, valor]]
                    items:
                      type: array
                      items:
                        type: number
                    example: [[1730745173, 2]]
                  tags:
                    type: array
                    description: Tags asociados a la métrica
                    items:
                      type: string
                    example: ["host:localhost", "environment:develop"]
                  host:
                    type: string
                    description: Hostname del origen
                    example: "localhost"
    responses:
      202:
        description: Métrica recibida y en proceso
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Metric recibido y en proceso"
      400:
        description: Formato de datos incorrecto
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Formato de datos incorrecto"
    """
    data = request.json
    series = data.get("series", [])
    
    if not series or not isinstance(series, list):
        return jsonify({"error": "Formato de datos incorrecto"}), 400

    # Enviar las métricas a DataDog y MongoDB en segundo plano
    executor.submit(send_metric_to_datadog, series)
    executor.submit(send_metric_to_mongodb, series)

    metrics.extend(series)
    return jsonify({"message": "Metric recibido y en proceso"}), 202

@app.route('/log', methods=['POST'])
def save_log():
    """
    Enviar un log individual
    ---
    tags:
      - Logs
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - message
            - service
          properties:
            message:
              type: string
              description: Mensaje del log
              example: "Un evento ocurrió"
            level:
              type: string
              description: Nivel del log
              enum: [debug, info, warning, error, critical]
              default: info
              example: "info"
            service:
              type: string
              description: Nombre del servicio
              example: "mi-servicio"
            ddsource:
              type: string
              description: Fuente del log para DataDog
              default: python
              example: "python"
            hostname:
              type: string
              description: Hostname del origen
              example: "localhost"
            tags:
              type: array
              description: Tags asociados al log
              items:
                type: string
              example: ["env:production"]
            date:
              type: string
              format: date-time
              description: Fecha del evento (ISO 8601)
              example: "2024-11-04T15:35:56"
    responses:
      202:
        description: Log recibido y en proceso
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Log recibido y en proceso"
      400:
        description: No se proporcionaron datos
        schema:
          type: object
          properties:
            error:
              type: string
              example: "No se proporcionaron datos"
    """
    data = request.json
    if not data:
        return jsonify({"error": "No se proporcionaron datos"}), 400

    # Enviar la tarea al ejecutor de hilos
    executor.submit(process_log_entry_safe, data)

    return jsonify({"message": "Log recibido y en proceso"}), 202

@app.route('/logs', methods=['POST'])
def save_logs():
    """
    Enviar múltiples logs
    ---
    tags:
      - Logs
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - logs
          properties:
            logs:
              type: array
              description: Lista de logs a enviar
              items:
                type: object
                required:
                  - message
                  - service
                properties:
                  message:
                    type: string
                    description: Mensaje del log
                    example: "Primer log"
                  level:
                    type: string
                    description: Nivel del log
                    enum: [debug, info, warning, error, critical]
                    default: info
                    example: "info"
                  service:
                    type: string
                    description: Nombre del servicio
                    example: "mi-servicio"
                  ddsource:
                    type: string
                    description: Fuente del log
                    default: python
                    example: "python"
                  hostname:
                    type: string
                    description: Hostname del origen
                    example: "localhost"
                  tags:
                    type: array
                    items:
                      type: string
                    example: ["env:test"]
                  date:
                    type: string
                    format: date-time
                    example: "2024-11-04T15:35:56"
    responses:
      202:
        description: Todos los logs recibidos y en proceso
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Todos los logs han sido recibidos y estan en proceso"
      400:
        description: Formato de datos incorrecto
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Formato de datos incorrecto"
    """
    data = request.json
    logs_array = data.get("logs", [])

    if not logs_array or not isinstance(logs_array, list):
        return jsonify({"error": "Formato de datos incorrecto"}), 400

    for log in logs_array:
        executor.submit(process_log_entry_safe, log)

    return jsonify({"message": "Todos los logs han sido recibidos y estan en proceso"}), 202

def save_log_to_mongodb(message, level, log_date, service, ddsource, hostname, tags):
    if not MONGO_URI:
        return  # Salir si MongoDB no está configurado

    logs_col, _ = get_mongo_collections()
    if logs_col is None:
        print("MongoDB no disponible, log no guardado.")
        return

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
    print(log_date)
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
        logs_col.insert_one(log)
        print("Log insertado en MongoDB correctamente.")
    except Exception as e:
        print(f"Error al insertar el log en MongoDB: {e}")

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
        else:
            print("Log enviado a DataDog correctamente")
    except Exception as e:
        print(f"Error al enviar el log a DataDog: {e}")

# ============================================================
# MONITOR DE ESTANQUE (Blueprint)
# ============================================================
from tomi_metrics.monitor_estanque import monitor_bp, start_mqtt_thread, get_mqtt_status

app.register_blueprint(monitor_bp)

# Iniciar MQTT thread al cargar el módulo
start_mqtt_thread()

if __name__ == '__main__':
    app.run(debug=True)
