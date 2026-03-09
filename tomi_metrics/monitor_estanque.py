"""
Monitor de Estanque - Posada en el Bosque
Paraíso Los Quinquelles

Módulo para monitorear el nivel de agua del estanque via MQTT.
"""

from flask import Blueprint, render_template, jsonify, request
from datetime import datetime, timezone
from collections import deque
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient
import threading
import time
import tomllib
import random
import os
import paho.mqtt.client as mqtt

# Cargar variables de entorno
load_dotenv()

# MongoDB configuración
MONGO_URI = os.getenv("MONGODB_URI")
ENABLE_MONGO_DB = os.getenv("ENABLE_MONGO_DB", "False").lower() == "true"
mongo_client_estanque = None
historial_collection = None

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
ALTURA_SENSOR = 160  # cm desde el fondo del estanque
CAPACIDAD_LITROS = 5000  # litros cuando está lleno

# Configuración MQTT (desde variables de entorno)
MQTT_HOST = os.getenv('MQTT_HOST', 'broker.mqttdashboard.com')
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
MQTT_USERNAME = os.getenv('MQTT_USERNAME', 'test')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', 'test')
MQTT_TOPIC_OUT = os.getenv('MQTT_TOPIC_OUT', 'yai-mqtt/YUS-0.2.8-COSTA/out')

# ============================================================
# MONGODB - HISTORIAL
# ============================================================

def get_historial_collection():
    """Obtiene la colección de historial de MongoDB."""
    global mongo_client_estanque, historial_collection
    
    if not ENABLE_MONGO_DB or not MONGO_URI:
        return None
    
    if mongo_client_estanque is None:
        try:
            mongo_client_estanque = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            mongo_client_estanque.admin.command('ping')
            db = mongo_client_estanque["tomi-db"]
            historial_collection = db["estanque-historial"]
            print("✅ MongoDB conectado para historial del estanque")
        except Exception as e:
            print(f"❌ Error conectando MongoDB para historial: {e}")
            return None
    
    return historial_collection

# Buffer para promediar datos por hora
datos_hora_actual = []
ultima_hora_guardada = None

def guardar_historial_hora():
    """Guarda el promedio de la hora actual en MongoDB."""
    global datos_hora_actual, ultima_hora_guardada
    
    if not datos_hora_actual:
        return
    
    collection = get_historial_collection()
    if collection is None:
        return
    
    # Calcular promedios
    n = len(datos_hora_actual)
    promedio = {
        "timestamp": datetime.now(timezone.utc),
        "hora_local": datetime.now().strftime("%Y-%m-%d %H:00"),
        "distancia": round(sum(d["distancia"] for d in datos_hora_actual) / n, 2),
        "altura_agua": round(sum(d["altura_agua"] for d in datos_hora_actual) / n, 2),
        "litros": round(sum(d["litros"] for d in datos_hora_actual) / n, 2),
        "porcentaje": round(sum(d["porcentaje"] for d in datos_hora_actual) / n, 2),
        "estado": datos_hora_actual[-1]["estado"],
        "muestras": n,
        "sensor": MQTT_TOPIC_OUT,
        "ubicacion": PARCELA_NOMBRE
    }
    
    try:
        collection.insert_one(promedio)
        print(f"📊 Historial guardado: {promedio['hora_local']} - {promedio['porcentaje']}% ({n} muestras)")
        datos_hora_actual.clear()
    except Exception as e:
        print(f"❌ Error guardando historial: {e}")

def agregar_dato_historial(datos: dict):
    """Agrega un dato al buffer de la hora actual y guarda si cambió la hora."""
    global datos_hora_actual, ultima_hora_guardada
    
    hora_actual = datetime.now().strftime("%Y-%m-%d %H")
    
    # Si cambió la hora, guardar el promedio anterior
    if ultima_hora_guardada and hora_actual != ultima_hora_guardada:
        guardar_historial_hora()
    
    ultima_hora_guardada = hora_actual
    
    # Agregar dato al buffer
    datos_hora_actual.append({
        "distancia": datos.get("distancia", 0),
        "altura_agua": datos.get("altura_agua", 0),
        "litros": datos.get("litros", 0),
        "porcentaje": datos.get("porcentaje", 0),
        "estado": datos.get("estado", "sin_datos")
    })

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

def calcular_nivel(distancia_sensor: float) -> dict:
    """Calcula los litros y porcentaje basándose en la distancia del sensor."""
    altura_agua = ALTURA_SENSOR - distancia_sensor
    if altura_agua < 0:
        altura_agua = 0
    if altura_agua > ALTURA_SENSOR:
        altura_agua = ALTURA_SENSOR
    
    porcentaje = (altura_agua / ALTURA_SENSOR) * 100
    litros = (altura_agua / ALTURA_SENSOR) * CAPACIDAD_LITROS
    
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
        
        # Formato: YUS-0.2.8-COSTA,OKO,88.75,2026-03-07...
        partes = payload.split(',')
        
        if len(partes) >= 3 and "OKO" in partes[1]:
            distancia_raw = float(partes[2])
            
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
            
            estado = datos
            
            historial.append({
                "timestamp": datos["ultima_lectura"],
                "distancia": distancia_promedio,
                "distancia_raw": distancia_raw,
                "litros": datos["litros"],
                "porcentaje": datos["porcentaje"],
                "estado": datos["estado"]
            })
            
            # Agregar al historial de MongoDB (promediado por hora)
            agregar_dato_historial(datos)
            
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
    """Retorna el estado de conexión MQTT para mostrar en el home."""
    global mqtt_connected
    return {
        "connected": mqtt_connected,
        "info": MQTT_HOST,
        "status": "Conectado" if mqtt_connected else "Desconectado"
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
    return render_template('monitor.html',
                         parcela_nombre=PARCELA_NOMBRE,
                         parcela_ubicacion=PARCELA_UBICACION,
                         altura_sensor=ALTURA_SENSOR,
                         capacidad_litros=CAPACIDAD_LITROS,
                         version=APP_VERSION)

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


@monitor_bp.route('/api/historial')
def api_historial():
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
    ---
    tags:
      - Monitor Estanque
    responses:
      200:
        description: Resultado del guardado
    """
    muestras_pendientes = len(datos_hora_actual)
    guardar_historial_hora()
    return jsonify({
        "mensaje": "Historial guardado",
        "muestras_guardadas": muestras_pendientes
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
        "habilitado": ENABLE_MONGO_DB,
        "conectado": collection is not None
    })

