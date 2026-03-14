"""
Monitor de Estanque - Posada en el Bosque
Paraíso Los Quinquelles

Módulo para monitorear el nivel de agua del estanque via MQTT.
"""

from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for
from functools import wraps
from datetime import datetime, timezone
from collections import deque
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient
import re
import json
import threading
import time
import tomllib
import random
import os
import paho.mqtt.client as mqtt

# Cargar variables de entorno
load_dotenv()

# MongoDB configuración
MONGO_URI = os.getenv("MONGODB_URI", "")
mongo_client_estanque = None
_historial_collections = {}  # cache por db_name

# Limpiar archivo de simulación viejo al iniciar (evita quedarse en modo simulación)
_SIM_FILE = os.path.join('/tmp', 'monitor_simulacion.flag')
if os.path.exists(_SIM_FILE):
    try:
        os.remove(_SIM_FILE)
        print("🧹 Archivo de simulación limpiado al iniciar")
    except:
        pass

# Blueprint para las rutas del monitor
monitor_bp = Blueprint('monitor', __name__, url_prefix='/monitor')


def login_required(f):
    """Decorador para proteger rutas que requieren autenticación."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def login_required_api(f):
    """Decorador para APIs que requieren autenticación (retorna JSON)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({"error": "No autorizado", "login_required": True}), 401
        return f(*args, **kwargs)
    return decorated_function

# ============================================================
# CONFIGURACIÓN
# ============================================================

# Obtener versión del pyproject.toml
BASE_DIR = Path(__file__).resolve().parent.parent
APP_VERSION = "1.0.0"

try:
    with open(BASE_DIR / "pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
        APP_VERSION = pyproject.get("tool", {}).get("poetry", {}).get("version", APP_VERSION)
except Exception:
    pass

# Configuración del estanque
PARCELA_NOMBRE = "Posada en el Bosque"
PARCELA_UBICACION = "Paraíso Los Quinquelles"
ALTURA_SENSOR = 145  # cm desde el fondo del estanque
CAPACIDAD_LITROS = 5000  # litros cuando está lleno

# Configuración MQTT (desde variables de entorno)
MQTT_HOST = os.getenv('MQTT_HOST', 'broker.mqttdashboard.com')
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
MQTT_USERNAME = os.getenv('MQTT_USERNAME', 'test')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', 'test')
MQTT_TOPIC_OUT = os.getenv('MQTT_TOPIC_OUT', 'yai-mqtt/01C40A24/out')

def _device_from_mqtt_topic(topic: str) -> str:
    """Extrae el deviceId del topic MQTT. Ej: yai-mqtt/YUS-0.2.8-COSTA/out -> YUS-0.2.8-COSTA"""
    parts = topic.strip().split("/")
    return parts[-2] if len(parts) >= 2 else topic

# ============================================================
# MONGODB - HISTORIAL
# ============================================================

def _sanitize_db_name(name: str) -> str:
    """Sanitiza el nombre de base de datos para MongoDB.
    Solo permite [a-zA-Z0-9_-]. Reemplaza el resto por _.
    Ej: YUS-0.2.8-COSTA -> YUS-0_2_8-COSTA
    """
    if not name or not isinstance(name, str):
        return "tomi-db"
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", name.strip())
    return safe[:64] or "tomi-db"

def get_db_name_from_request() -> str:
    """
    Obtiene el nombre de la base de datos desde el header X-Aia-Origin.
    Si no viene el header, retorna 'tomi-db' (base por defecto).
    """
    try:
        # X-Aia-Origin (preferido, proxies no lo filtran) o aia_origin (fallback)
        value = (
            request.headers.get("X-Aia-Origin", "").strip()
            or request.headers.get("aia_origin", "").strip()
        )
        return _sanitize_db_name(value) if value else "tomi-db"
    except Exception:
        return "tomi-db"

def get_historial_collection(db_name: str = "tomi-db"):
    """Obtiene la colección de historial de MongoDB para la base de datos indicada."""
    global mongo_client_estanque, _historial_collections

    if not MONGO_URI:
        return None

    db_name = _sanitize_db_name(db_name) or "tomi-db"

    if mongo_client_estanque is None:
        try:
            mongo_client_estanque = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            mongo_client_estanque.admin.command('ping')
            print("✅ MongoDB conectado para historial del estanque")
        except Exception as e:
            print(f"❌ Error conectando MongoDB para historial: {e}")
            return None

    if db_name not in _historial_collections:
        db = mongo_client_estanque[db_name]
        _historial_collections[db_name] = db["estanque-historial"]

    return _historial_collections[db_name]

def get_audit_info(source: str = "system"):
    """Obtiene información de auditoría del request actual o del sistema."""
    try:
        from flask import request as flask_request
        user_origin = flask_request.remote_addr or flask_request.headers.get('X-Forwarded-For', 'unknown')
        user_agent = flask_request.headers.get('User-Agent', 'unknown')
        return {
            "user_origin": user_origin,
            "user_agent": user_agent
        }
    except:
        return {
            "user_origin": source,
            "user_agent": source
        }

def guardar_en_mongodb(datos: dict, origin: str = "mqtt-10", audit: dict = None, db_name: str = None, channel_id: str = None, device_id: str = None):
    """Guarda un registro en MongoDB (hora_local como clave única).
    db_name: base de datos destino. Si None, usa 'tomi-db' (compatibilidad MQTT/interno).
    channel_id, device_id: opcionales, desde body JSON (channelId, deviceId).
    """
    db = db_name if db_name is not None else "tomi-db"
    collection = get_historial_collection(db)
    if collection is None:
        return False
    
    # Obtener audit info si no se proporciona
    if audit is None:
        audit = get_audit_info(origin)
    
    # Truncar a minuto para la clave (evita duplicados en el mismo minuto)
    hora_local = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    sensor = device_id or datos.get("device_id") or _device_from_mqtt_topic(MQTT_TOPIC_OUT) or "YUS-0.2.8-COSTA"
    registro = {
        "timestamp": datetime.now(timezone.utc),
        "hora_local": hora_local,
        "distancia": round(datos.get("distancia", 0), 2),
        "altura_agua": round(datos.get("altura_agua", 0), 2),
        "litros": round(datos.get("litros", 0), 2),
        "porcentaje": round(datos.get("porcentaje", 0), 2),
        "estado": datos.get("estado", ""),
        "muestras": datos.get("lecturas_en_buffer", 1),
        "sensor": sensor,
        "ubicacion": PARCELA_NOMBRE,
        "origin": origin,
        "user_origin": audit.get("user_origin"),
        "user_agent": audit.get("user_agent")
    }
    if channel_id:
        registro["channelId"] = channel_id
    if device_id:
        registro["deviceId"] = device_id
    
    try:
        # Upsert: actualiza si existe hora_local, inserta si no existe
        result = collection.update_one(
            {"hora_local": hora_local},
            {"$set": registro},
            upsert=True
        )
        
        if result.upserted_id:
            print(f"📊 MongoDB [{origin}] nuevo: {hora_local} - {registro['porcentaje']}%")
        else:
            print(f"📊 MongoDB [{origin}] actualizado: {hora_local} - {registro['porcentaje']}%")
        return True
    except Exception as e:
        print(f"❌ Error guardando en MongoDB: {e}")
        return False

# ============================================================
# ESTADO Y DATOS
# ============================================================

# Historial de mediciones (últimas 100)
historial = deque(maxlen=100)

# Buffer para promedio móvil de 10 lecturas (suaviza errores del sensor)
lecturas_buffer = deque(maxlen=10)

# Estado de conexión MQTT
mqtt_connected = False
mqtt_thread_started = False
# Timestamp de la última lectura recibida (UTC)
last_mqtt_message_ts = None

# Estado actual del monitor
estado = {
    "distancia": None,
    "litros": None,
    "porcentaje": None,
    "altura_agua": None,
    "estado": "sin_datos",
    "ultima_lectura": None
}

# ============================================================
# FUNCIONES DE CÁLCULO
# ============================================================

def calcular_nivel(distancia_sensor: float, altura_sensor: float = ALTURA_SENSOR) -> dict:
    """Calcula los litros y porcentaje basándose en la distancia del sensor.
    Nota: La corrección (< 21 → restar 15) se aplica en el listener MQTT.

    altura_sensor: altura total (cm) desde el sensor hasta el fondo del estanque.
    """
    altura_agua = altura_sensor - distancia_sensor
    if altura_agua < 0:
        altura_agua = 0
    if altura_agua > altura_sensor:
        altura_agua = altura_sensor
    
    porcentaje = (altura_agua / altura_sensor) * 100 if altura_sensor else 0
    litros = (altura_agua / altura_sensor) * CAPACIDAD_LITROS if altura_sensor else 0
    
    if distancia_sensor > 140:
        estado_nivel = "peligro"
    elif distancia_sensor > 80:
        estado_nivel = "alerta"
    else:
        estado_nivel = "normal"
    
    return {
        "distancia": distancia_sensor,
        "altura_agua": altura_agua,
        "litros": litros,
        "porcentaje": porcentaje,
        "estado": estado_nivel
    }

# ============================================================
# MQTT
# ============================================================

def on_mqtt_connect(client, userdata, flags, reason_code, properties):
    """Callback cuando se conecta al broker MQTT."""
    global mqtt_connected
    if reason_code == 0:
        mqtt_connected = True
        print(f"✅ MQTT Conectado a {MQTT_HOST}")
        client.subscribe(MQTT_TOPIC_OUT)
        print(f"📡 Suscrito a: {MQTT_TOPIC_OUT}")
    else:
        mqtt_connected = False
        print(f"❌ Error MQTT: {reason_code}")

def on_mqtt_disconnect(client, userdata, flags, reason_code, properties):
    """Callback cuando se desconecta del broker MQTT."""
    global mqtt_connected
    mqtt_connected = False
    print(f"⚠️ MQTT Desconectado: {reason_code}")

def on_mqtt_message(client, userdata, msg):
    """Callback cuando llega un mensaje MQTT."""
    global estado, lecturas_buffer
    
    try:
        payload = msg.payload.decode('utf-8').strip()

        # Intentar leer JSON (nuevo formato)
        device_id_mqtt = None
        channel_id = None
        distancia_raw = None
        altura_sensor = ALTURA_SENSOR
        fill_level = None
        status = None

        try:
            payload_json = json.loads(payload)
            device_id_mqtt = payload_json.get("deviceId") or payload_json.get("device_id")
            channel_id = payload_json.get("channelId") or payload_json.get("channel_id")
            status = payload_json.get("status")
            distancia_raw = float(payload_json.get("distanceCm") or payload_json.get("distancia") or 0)
            altura_sensor = float(payload_json.get("tankDepthCm") or altura_sensor)
            fill_level = payload_json.get("fillLevelPercent")
            if fill_level is not None:
                fill_level = float(fill_level)
        except Exception:
            payload_json = None

        # Manejar ambos formatos: JSON (nuevo) y CSV (viejo)
        if payload_json and status == "OKO":
            # Corrección: si lectura < 21, restar 15 a la distancia
            if distancia_raw is not None and distancia_raw < 21:
                distancia_raw = max(0, distancia_raw - 15)

            # Agregar al buffer de lecturas
            lecturas_buffer.append(distancia_raw)

            # Calcular promedio de las últimas 10 lecturas (o las que haya)
            distancia_promedio = sum(lecturas_buffer) / len(lecturas_buffer)
            
            # Usar el promedio para calcular el nivel (puede venir con altura de tanque)
            datos = calcular_nivel(distancia_promedio, altura_sensor=altura_sensor)

            # Si el payload nos provee fillLevelPercent, usarlo como referencia
            if fill_level is not None:
                datos["porcentaje"] = fill_level
                datos["litros"] = round((fill_level / 100.0) * CAPACIDAD_LITROS, 2)
                datos["altura_agua"] = round((fill_level / 100.0) * altura_sensor, 2)

            datos["ultima_lectura"] = datetime.now(timezone.utc).isoformat()
            datos["raw"] = payload
            datos["distancia_raw"] = distancia_raw
            datos["lecturas_en_buffer"] = len(lecturas_buffer)
            datos["device_id"] = device_id_mqtt
            if channel_id:
                datos["channel_id"] = channel_id

            estado = datos
            # Registrar timestamp de última lectura MQTT
            global last_mqtt_message_ts
            last_mqtt_message_ts = datetime.now(timezone.utc)

            historial.append({
                "timestamp": datos["ultima_lectura"],
                "distancia": distancia_promedio,
                "distancia_raw": distancia_raw,
                "litros": datos["litros"],
                "porcentaje": datos["porcentaje"],
                "estado": datos["estado"]
            })

            # Guardar en MongoDB cuando el buffer tiene 10 lecturas
            if len(lecturas_buffer) == 10:
                guardar_en_mongodb(datos, "mqtt-10", channel_id=channel_id, device_id=device_id_mqtt)

            print(f"💧 Nivel: {datos['litros']:.0f}L ({datos['porcentaje']:.1f}%) - Promedio de {len(lecturas_buffer)} lecturas")
        else:
            # Formato antiguo: YUS-0.2.8-COSTA,OKO,88.75,...
            partes = payload.split(',')
            if len(partes) >= 3 and "OKO" in partes[1]:
                device_id_mqtt = partes[0].strip()  # Ej: YUS-0.2.8-COSTA
                distancia_raw = float(partes[2])
                # Corrección: si lectura < 21, restar 15 a la distancia
                if distancia_raw < 21:
                    distancia_raw = max(0, distancia_raw - 15)

                # Agregar al buffer de lecturas
                lecturas_buffer.append(distancia_raw)
                
                # Calcular promedio de las últimas 10 lecturas (o las que haya)
                distancia_promedio = sum(lecturas_buffer) / len(lecturas_buffer)
                
                # Usar el promedio para calcular el nivel
                datos = calcular_nivel(distancia_promedio)
                datos["ultima_lectura"] = datetime.now(timezone.utc).isoformat()
                datos["raw"] = payload
                datos["distancia_raw"] = distancia_raw
                datos["lecturas_en_buffer"] = len(lecturas_buffer)
                datos["device_id"] = device_id_mqtt

                estado = datos
                
                historial.append({
                    "timestamp": datos["ultima_lectura"],
                    "distancia": distancia_promedio,
                    "distancia_raw": distancia_raw,
                    "litros": datos["litros"],
                    "porcentaje": datos["porcentaje"],
                    "estado": datos["estado"]
                })
                
                # Guardar en MongoDB cada vez que llega una lectura (upsert por minuto)
                # Se fuerza la base de datos a tomi-db para evitar que se escriba en otra.
                guardar_en_mongodb(datos, "mqtt", db_name="tomi-db")
                
                print(f"💧 Nivel: {datos['litros']:.0f}L ({datos['porcentaje']:.1f}%) - Promedio de {len(lecturas_buffer)} lecturas")

    except Exception as e:
        print(f"❌ Error procesando mensaje MQTT: {e}")

def iniciar_mqtt():
    """Inicia la conexión MQTT en un thread separado."""
    global mqtt_connected
    
    while True:
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
            client.on_connect = on_mqtt_connect
            client.on_disconnect = on_mqtt_disconnect
            client.on_message = on_mqtt_message
            
            print(f"🔌 Conectando a MQTT {MQTT_HOST}:{MQTT_PORT}...")
            client.connect(MQTT_HOST, MQTT_PORT, 60)
            client.loop_forever()
        except Exception as e:
            mqtt_connected = False
            print(f"❌ Error MQTT: {e} - Reintentando en 5s...")
            time.sleep(5)

def start_mqtt_thread():
    """Inicia el thread MQTT (solo una vez)."""
    global mqtt_thread_started
    
    if mqtt_thread_started:
        return
    
    mqtt_thread_started = True
    mqtt_thread = threading.Thread(target=iniciar_mqtt, daemon=True)
    mqtt_thread.start()
    print("🚀 Thread MQTT iniciado")

def get_mqtt_status():
    """Retorna el estado de conexión MQTT para mostrar en el home.

    Si no llega ninguna lectura en 60s, marca como desconectado.
    """
    global mqtt_connected, last_mqtt_message_ts

    connected = mqtt_connected
    status = "Conectado" if mqtt_connected else "Desconectado"

    if mqtt_connected and last_mqtt_message_ts is not None:
        elapsed = (datetime.now(timezone.utc) - last_mqtt_message_ts).total_seconds()
        if elapsed > 60:
            connected = False
            status = "Desconectado (sin mensajes)"

    return {
        "connected": connected,
        "info": MQTT_HOST,
        "status": status
    }

# ============================================================
# RUTAS
# ============================================================

@monitor_bp.route('/')
def home():
    """
    Monitor de Estanque - Dashboard
    ---
    tags:
      - Monitor Estanque
    responses:
      200:
        description: Dashboard del monitor de estanque
    """
    is_logged_in = session.get('logged_in', False)
    
    return render_template('monitor.html',
                         parcela_nombre=PARCELA_NOMBRE,
                         parcela_ubicacion=PARCELA_UBICACION,
                         altura_sensor=ALTURA_SENSOR,
                         capacidad_litros=CAPACIDAD_LITROS,
                         version=APP_VERSION,
                         is_logged_in=is_logged_in)

@monitor_bp.route('/api/estado')
def api_estado():
    """
    Estado actual del estanque
    ---
    tags:
      - Monitor Estanque
    responses:
      200:
        description: Estado actual del nivel de agua
        schema:
          type: object
          properties:
            distancia:
              type: number
            litros:
              type: number
            porcentaje:
              type: number
            estado:
              type: string
              enum: [normal, alerta, peligro, sin_datos]
    """
    response = dict(estado)
    response["mqtt_connected"] = mqtt_connected
    return jsonify(response)

@monitor_bp.route('/api/historial')
def api_historial():
    """
    Historial de mediciones del estanque
    ---
    tags:
      - Monitor Estanque
    responses:
      200:
        description: Últimas 100 mediciones
    """
    return jsonify(list(historial))

@monitor_bp.route('/api/config')
def api_config():
    """
    Configuración del estanque
    ---
    tags:
      - Monitor Estanque
    responses:
      200:
        description: Configuración del estanque
    """
    return jsonify({
        "parcela_nombre": PARCELA_NOMBRE,
        "parcela_ubicacion": PARCELA_UBICACION,
        "altura_sensor": ALTURA_SENSOR,
        "capacidad_litros": CAPACIDAD_LITROS,
        "mqtt_host": MQTT_HOST,
        "mqtt_topic": MQTT_TOPIC_OUT
    })

@monitor_bp.route('/api/lecturas', methods=['POST'])
def api_lecturas():
    """
    Recibir batch de lecturas del sensor (lista JSON).
    El ESP32 acumula lecturas y envía cada ~1 minuto.
    ---
    tags:
      - Monitor Estanque
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [lecturas]
          properties:
            lecturas:
              type: array
              items:
                type: object
                properties:
                  deviceId: { type: string }
                  channelId: { type: string }
                  status: { type: string }
                  distanceCm: { type: number }
                  litros: { type: number }
                  fillLevelPercent: { type: number }
                  timestamp: { type: string }
    responses:
      202:
        description: Batch recibido
      400:
        description: Formato incorrecto
    """
    data = request.json
    if not data or not isinstance(data, dict):
        return jsonify({"error": "JSON inválido"}), 400

    lecturas = data.get("lecturas", [])
    if not isinstance(lecturas, list):
        return jsonify({"error": "lecturas debe ser un array"}), 400

    db_name = get_db_name_from_request()
    guardadas = 0
    for item in lecturas:
        if not isinstance(item, dict):
            continue
        if item.get("status") != "OKO":
            continue
        try:
            distancia = float(item.get("distanceCm", 0))
            litros = float(item.get("litros", 0))
            porcentaje = float(item.get("fillLevelPercent", 0))
            device_id = item.get("deviceId", "unknown")
            channel_id = item.get("channelId", "")
            datos = {
                "distancia": distancia,
                "litros": litros,
                "porcentaje": porcentaje,
                "altura_agua": ALTURA_SENSOR - distancia if distancia <= ALTURA_SENSOR else 0,
                "estado": "peligro" if distancia > 140 else ("alerta" if distancia > 80 else "normal"),
                "lecturas_en_buffer": 1,
                "device_id": device_id,
                "channel_id": channel_id
            }
            if guardar_en_mongodb(datos, f"http-batch-{channel_id or device_id}", db_name=db_name, device_id=device_id, channel_id=channel_id or None):
                guardadas += 1
        except Exception:
            pass

    return jsonify({"message": "Batch recibido", "guardadas": guardadas, "total": len(lecturas)}), 202


@monitor_bp.route('/api/simular/<int:distancia>')
def api_simular(distancia):
    """
    Simular una lectura del sensor (solo preview, no afecta datos reales)
    ---
    tags:
      - Monitor Estanque
    parameters:
      - name: distancia
        in: path
        type: integer
        required: true
        description: Distancia simulada del sensor (0-160 cm)
    responses:
      200:
        description: Preview de datos calculados para la distancia
    """
    datos = calcular_nivel(distancia)
    datos["simulado"] = True
    return jsonify(datos)


@monitor_bp.route('/api/historial/hora')
def api_historial_hora():
    """
    Obtiene el historial de mediciones promediadas por hora desde MongoDB.
    ---
    tags:
      - Monitor Estanque
    parameters:
      - name: dias
        in: query
        type: integer
        required: false
        default: 7
        description: Cantidad de días hacia atrás a consultar
    responses:
      200:
        description: Lista de mediciones promediadas por hora
    """
    from datetime import timedelta
    
    dias = int(request.args.get('dias', 7))
    collection = get_historial_collection()
    
    if collection is None:
        return jsonify({
            "error": "MongoDB no disponible",
            "historial": []
        })
    
    fecha_inicio = datetime.now(timezone.utc) - timedelta(days=dias)
    
    try:
        cursor = collection.find(
            {"timestamp": {"$gte": fecha_inicio}},
            {"_id": 0}
        ).sort("timestamp", -1).limit(500)
        
        historial_db = list(cursor)
        
        # Convertir timestamps a string para JSON
        for item in historial_db:
            if "timestamp" in item:
                item["timestamp"] = item["timestamp"].isoformat()
        
        return jsonify({
            "dias": dias,
            "total": len(historial_db),
            "historial": historial_db
        })
    except Exception as e:
        return jsonify({
            "error": str(e),
            "historial": []
        })


@monitor_bp.route('/api/historial/forzar-guardado', methods=['POST'])
def forzar_guardado_historial():
    """
    Fuerza el guardado del buffer actual de historial en MongoDB.
    Lee el header X-Aia-Origin para determinar la base de datos destino.
    Si no viene, usa la base de datos 'tomi-db' (por defecto).
    ---
    tags:
      - Monitor Estanque
    responses:
      200:
        description: Resultado del guardado
    """
    db_name = get_db_name_from_request()
    body = request.get_json(silent=True) or {}
    channel_id = body.get("channelId")
    device_id = body.get("deviceId")
    if isinstance(channel_id, str):
        channel_id = channel_id.strip() or None
    else:
        channel_id = None
    if isinstance(device_id, str):
        device_id = device_id.strip() or None
    else:
        device_id = None
    if estado:
        resultado = guardar_en_mongodb(estado, "manual", db_name=db_name, channel_id=channel_id, device_id=device_id)
        return jsonify({
            "mensaje": "Registro guardado" if resultado else "Error al guardar",
            "guardado": resultado,
            "db": db_name
        })
    return jsonify({
        "mensaje": "No hay datos para guardar",
        "guardado": False,
        "db": db_name
    })


@monitor_bp.route('/api/historial/diario')
def api_historial_diario():
    """
    Obtiene el historial agregado por día (promedio diario) del último mes.
    ---
    tags:
      - Monitor Estanque
    responses:
      200:
        description: Lista de promedios diarios
    """
    from datetime import timedelta
    
    collection = get_historial_collection()
    
    if collection is None:
        return jsonify({
            "habilitado": False,
            "error": "MongoDB no disponible",
            "datos": []
        })
    
    fecha_inicio = datetime.now(timezone.utc) - timedelta(days=30)
    
    try:
        # Agregación por día
        pipeline = [
            {"$match": {"timestamp": {"$gte": fecha_inicio}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                "porcentaje_promedio": {"$avg": "$porcentaje"},
                "litros_promedio": {"$avg": "$litros"},
                "distancia_promedio": {"$avg": "$distancia"},
                "muestras": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}},
            {"$project": {
                "_id": 0,
                "fecha": "$_id",
                "porcentaje": {"$round": ["$porcentaje_promedio", 1]},
                "litros": {"$round": ["$litros_promedio", 0]},
                "distancia": {"$round": ["$distancia_promedio", 1]},
                "muestras": 1
            }}
        ]
        
        datos = list(collection.aggregate(pipeline))
        
        return jsonify({
            "habilitado": True,
            "total_dias": len(datos),
            "datos": datos
        })
    except Exception as e:
        return jsonify({
            "habilitado": True,
            "error": str(e),
            "datos": []
        })


@monitor_bp.route('/api/historial/status')
def api_historial_status():
    """
    Verifica si el historial de MongoDB está habilitado y conectado.
    ---
    tags:
      - Monitor Estanque
    responses:
      200:
        description: Estado de la conexión a MongoDB
    """
    collection = get_historial_collection()
    
    return jsonify({
        "configurado": bool(MONGO_URI),
        "conectado": collection is not None
    })


@monitor_bp.route('/api/historial/mensual-horas')
@login_required_api
def api_historial_mensual_horas():
    """
    Obtiene el historial del mes actual agrupado por día y hora.
    ---
    tags:
      - Monitor Estanque
    responses:
      200:
        description: Lista de promedios por hora del mes actual
    """
    from datetime import timedelta
    import calendar
    
    collection = get_historial_collection()
    
    if collection is None:
        return jsonify({
            "habilitado": False,
            "error": "MongoDB no disponible",
            "datos": []
        })
    
    # Obtener primer y último día del mes actual
    ahora = datetime.now(timezone.utc)
    primer_dia = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ultimo_dia_num = calendar.monthrange(ahora.year, ahora.month)[1]
    
    try:
        # Zona horaria de Chile
        tz_chile = "America/Santiago"
        
        # Agregación por día y hora (en hora local de Chile)
        pipeline = [
            {"$match": {"timestamp": {"$gte": primer_dia}}},
            {"$group": {
                "_id": {
                    "fecha": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp", "timezone": tz_chile}},
                    "hora": {"$hour": {"date": "$timestamp", "timezone": tz_chile}}
                },
                "porcentaje_promedio": {"$avg": "$porcentaje"},
                "litros_promedio": {"$avg": "$litros"},
                "muestras": {"$sum": 1}
            }},
            {"$sort": {"_id.fecha": 1, "_id.hora": 1}},
            {"$project": {
                "_id": 0,
                "fecha": "$_id.fecha",
                "hora": "$_id.hora",
                "porcentaje": {"$round": ["$porcentaje_promedio", 1]},
                "litros": {"$round": ["$litros_promedio", 0]},
                "muestras": 1
            }}
        ]
        
        datos = list(collection.aggregate(pipeline))
        
        return jsonify({
            "habilitado": True,
            "mes": ahora.month,
            "anio": ahora.year,
            "dias_mes": ultimo_dia_num,
            "total_registros": len(datos),
            "datos": datos
        })
    except Exception as e:
        return jsonify({
            "habilitado": True,
            "error": str(e),
            "datos": []
        })

