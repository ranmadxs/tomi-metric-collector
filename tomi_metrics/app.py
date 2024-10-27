from flask import Flask, request, jsonify

app = Flask(__name__)

# Variables en memoria para almacenar los datos
metricas = []
logs = []

@app.route('/')
def hola_mundo():
    return "Hola Mundo", 200

@app.route('/metrics', methods=['POST'])
def guardar_metrica():
    data = request.json
    nombre_metrica = data.get('name')
    tags = data.get('tags')

    if not nombre_metrica:
        return jsonify({"error": "metric name required"}), 400

    # Verificación de la estructura de cada tag
    if not isinstance(tags, list) or not all(isinstance(tag, dict) and "key" in tag and "value" in tag for tag in tags):
        return jsonify({"error": "Cada tag debe ser un diccionario con 'key' y 'value'"}), 400

    metrica = {
        "name": nombre_metrica,
        "tags": tags
    }
    metricas.append(metrica)
    return jsonify({"message": "Metric Saved", "data": metrica}), 201

@app.route('/log', methods=['POST'])
def guardar_log():
    data = request.json
    mensaje = data.get('message')
    severidad = data.get('level')

    if not mensaje or not severidad:
        return jsonify({"error": "Mensaje y severidad son requeridos"}), 400

    log = {
        "message": mensaje,
        "level": severidad
    }
    logs.append(log)
    return jsonify({"message": "Log saved", "data": log}), 201

if __name__ == '__main__':
    app.run(debug=True)
