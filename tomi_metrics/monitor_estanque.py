"""
Monitor de Estanque - Posada en el Bosque
Paraíso Los Quinquelles

Módulo para monitorear el nivel de agua del estanque via MQTT.
"""

from flask import Blueprint, render_template, jsonify
from datetime import datetime, timezone
from collections import deque
from pathlib import Path
import threading
import time
import tomllib
import paho.mqtt.client as mqtt

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

# Configuración MQTT
MQTT_HOST = "broker.mqttdashboard.com"
MQTT_PORT = 1883
MQTT_USERNAME = "test"
MQTT_PASSWORD = "test"
MQTT_TOPIC = "yai-mqtt/YUS-0.2.8-COSTA/out"

# ============================================================
# ESTADO Y DATOS
# ============================================================

# Historial de mediciones (últimas 100)
historial = deque(maxlen=100)

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
        client.subscribe(MQTT_TOPIC)
        print(f"📡 Suscrito a: {MQTT_TOPIC}")
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
    global estado
    
    try:
        payload = msg.payload.decode('utf-8').strip()
        print(f"📨 MQTT: {payload}")
        
        # Formato: YUS-0.2.8-COSTA,OKO,88.75,2026-03-07...
        partes = payload.split(',')
        
        if len(partes) >= 3 and "OKO" in partes[1]:
            distancia = float(partes[2])
            datos = calcular_nivel(distancia)
            datos["ultima_lectura"] = datetime.now(timezone.utc).isoformat()
            datos["raw"] = payload
            
            estado = datos
            
            historial.append({
                "timestamp": datos["ultima_lectura"],
                "distancia": distancia,
                "litros": datos["litros"],
                "porcentaje": datos["porcentaje"],
                "estado": datos["estado"]
            })
            
            print(f"💧 Nivel: {datos['litros']:.0f}L ({datos['porcentaje']:.1f}%) - {datos['estado'].upper()}")
            
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
        "mqtt_topic": MQTT_TOPIC
    })

@monitor_bp.route('/api/simular/<float:distancia>')
def api_simular(distancia):
    """
    Simular una lectura del sensor (para pruebas)
    ---
    tags:
      - Monitor Estanque
    parameters:
      - name: distancia
        in: path
        type: number
        required: true
        description: Distancia simulada del sensor (0-160 cm)
    responses:
      200:
        description: Datos calculados para la distancia simulada
    """
    global estado
    
    datos = calcular_nivel(distancia)
    datos["ultima_lectura"] = datetime.now(timezone.utc).isoformat()
    datos["simulado"] = True
    
    estado = datos
    
    historial.append({
        "timestamp": datos["ultima_lectura"],
        "distancia": distancia,
        "litros": datos["litros"],
        "porcentaje": datos["porcentaje"],
        "estado": datos["estado"]
    })
    
    return jsonify(datos)
