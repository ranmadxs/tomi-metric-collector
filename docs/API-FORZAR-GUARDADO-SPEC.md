# Especificación: Endpoint Forzar Guardado - Tomi Metric Collector

## Resumen

Este documento describe el endpoint **Forzar Guardado** del Monitor de Estanque de Tomi Metric Collector. Permite a un sensor o sistema externo solicitar que el colector guarde en MongoDB el estado actual del estanque (nivel de agua, litros, porcentaje, etc.) que tiene en memoria.

**URL base pública:** `https://tomicolector.cl`

---

## Endpoint: Forzar Guardado

### Información general

| Campo | Valor |
|-------|-------|
| **URL completa** | `https://tomicolector.cl/monitor/api/historial/forzar-guardado` |
| **Método HTTP** | `POST` |
| **Autenticación** | No requiere |
| **Header** | `aia_origin` — valor = nombre de la base de datos MongoDB destino. Si no viene, se usa `dump` |
| **Content-Type** | No aplica (sin body) |

### Descripción

El colector mantiene en memoria el estado actual del estanque, alimentado principalmente por lecturas MQTT. Este endpoint **fuerza el guardado inmediato** de ese estado en MongoDB (colección `estanque-historial`), sin esperar al guardado automático (que ocurre cada 10 lecturas MQTT).

**Caso de uso típico:** Un sensor o cron programado llama a este endpoint en horarios específicos (ej: cada hora, cada 6 horas) para asegurar que haya un registro en la base de datos en ese momento, aunque no se hayan acumulado 10 lecturas MQTT.

**Base de datos destino:** El valor del header `aia_origin` define el **nombre de la base de datos MongoDB** donde se guardan los datos. Si no se envía el header, se usa la base de datos `dump`. Los datos siempre se guardan en la colección `estanque-historial` dentro de esa base.

### Request

```
POST https://tomicolector.cl/monitor/api/historial/forzar-guardado
```

- **Body:** No se envía body. El request puede estar vacío.
- **Headers:**
  - `aia_origin` — **Nombre de la base de datos MongoDB** donde guardar. Ej: `YUS-001`, `YUS-ESTANQUE1`, `parcela-costa`. Si no se envía, se usa `dump`.
  - Opcionalmente `Content-Type: application/json` si el cliente lo envía por defecto.

### Response

**Content-Type:** `application/json`

#### Caso éxito (hay datos para guardar)

```json
{
  "mensaje": "Registro guardado",
  "guardado": true
}
```

**HTTP Status:** `200 OK`

#### Caso sin datos

Si el colector no tiene ningún dato en memoria (ej: MQTT desconectado y nunca recibió lecturas):

```json
{
  "mensaje": "No hay datos para guardar",
  "guardado": false
}
```

**HTTP Status:** `200 OK`

#### Caso error de guardado

Si hay datos pero falla la escritura en MongoDB:

```json
{
  "mensaje": "Error al guardar",
  "guardado": false
}
```

**HTTP Status:** `200 OK`

---

## Ejemplos de implementación

### cURL

```bash
curl -X POST https://tomicolector.cl/monitor/api/historial/forzar-guardado \
  -H "aia_origin: YUS-XXXXX"
```

### Python (requests)

```python
import requests

response = requests.post(
    "https://tomicolector.cl/monitor/api/historial/forzar-guardado",
    headers={"aia_origin": "YUS-XXXXX"}
)
data = response.json()
if data.get("guardado"):
    print("Guardado OK:", data["mensaje"])
else:
    print("No guardado:", data["mensaje"])
```

### Python (urllib)

```python
import urllib.request

req = urllib.request.Request(
    "https://tomicolector.cl/monitor/api/historial/forzar-guardado",
    method="POST",
    headers={"aia_origin": "YUS-XXXXX"}
)
with urllib.request.urlopen(req) as resp:
    import json
    data = json.loads(resp.read().decode())
    print(data)
```

### ESP32 / Arduino (HTTPClient)

```cpp
#include <HTTPClient.h>
#include <WiFi.h>

void forzarGuardado() {
  HTTPClient http;
  http.begin("https://tomicolector.cl/monitor/api/historial/forzar-guardado");
  http.addHeader("aia_origin", "YUS-XXXXX");
  http.addHeader("Content-Type", "application/json");
  int httpCode = http.POST("");  // body vacío
  
  if (httpCode > 0) {
    String payload = http.getString();
    // payload: {"mensaje":"Registro guardado","guardado":true}
  }
  http.end();
}
```

### Node.js (fetch)

```javascript
const response = await fetch(
  "https://tomicolector.cl/monitor/api/historial/forzar-guardado",
  {
    method: "POST",
    headers: { "aia_origin": "YUS-XXXXX" }
  }
);
const data = await response.json();
console.log(data.guardado ? "Guardado" : "No guardado");
```

---

## Programación recomendada

| Frecuencia | Uso |
|------------|-----|
| Cada 1 hora | Registro horario consistente |
| Cada 6 horas | Menor tráfico, suficiente para tendencias |
| Cada 15–30 min | Mayor granularidad temporal |

**Nota:** El guardado automático ya ocurre cada 10 lecturas MQTT. Este endpoint es complementario para forzar un registro en momentos concretos (ej: cron diario a las 00:00).

---

## Datos que se guardan

El registro en MongoDB incluye (calculados a partir del estado en memoria):

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `hora_local` | string | Clave única: `YYYY-MM-DD HH:MM` (truncado a minuto) |
| `timestamp` | datetime | UTC |
| `distancia` | float | cm (sensor al agua) |
| `altura_agua` | float | cm |
| `litros` | float | Volumen estimado |
| `porcentaje` | float | 0–100 |
| `estado` | string | `normal`, `alerta`, `peligro` |
| `origin` | string | `"manual"` cuando se usa este endpoint |

**Ubicación en MongoDB:** Los datos se guardan en `{aia_origin}/estanque-historial` (o `dump/estanque-historial` si no viene el header).

---

## Alternativa: enviar lecturas desde el sensor

Si el sensor **envía sus propios datos** (distancia, litros, porcentaje) en lugar de depender de MQTT, debe usar otro endpoint:

**POST** `https://tomicolector.cl/monitor/api/lecturas`

**Body (JSON):**
```json
{
  "lecturas": [
    {
      "deviceId": "sensor-01",
      "channelId": "estanque",
      "status": "OKO",
      "distanceCm": 45.2,
      "litros": 1200,
      "fillLevelPercent": 68.5,
      "timestamp": "2025-03-10T12:00:00Z"
    }
  ]
}
```

Cada lectura con `status: "OKO"` se guarda directamente en MongoDB. También usa el header `aia_origin` para determinar la base de datos destino (o `dump` si no viene).

---

## Resumen para IA

1. **URL:** `https://tomicolector.cl/monitor/api/historial/forzar-guardado`
2. **Método:** `POST`
3. **Header:** `aia_origin` = nombre de la base de datos MongoDB (si no viene → `dump`)
4. **Body:** vacío
5. **Auth:** ninguna
6. **Respuesta:** JSON con `guardado` (boolean) y `mensaje` (string)
7. **Propósito:** Forzar que el colector guarde en MongoDB el estado actual del estanque que tiene en memoria.
8. **Base de datos:** Los datos se guardan en `{aia_origin}/estanque-historial` o `dump/estanque-historial` si no hay header.
