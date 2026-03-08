// Elementos del DOM
const elements = {
    connectionStatus: document.getElementById('connection-status'),
    tankWater: document.getElementById('tank-water'),
    litrosDisplay: document.getElementById('litros-display'),
    estadoCard: document.getElementById('estado-card'),
    estadoIcon: document.getElementById('estado-icon'),
    estadoText: document.getElementById('estado-text'),
    porcentajeValue: document.getElementById('porcentaje-value'),
    porcentajeBar: document.getElementById('porcentaje-bar'),
    litrosValue: document.getElementById('litros-value'),
    alturaValue: document.getElementById('altura-value'),
    distanciaValue: document.getElementById('distancia-value'),
    timestampValue: document.getElementById('timestamp-value'),
    sensorWaves: document.getElementById('sensor-waves'),
    // Mini widgets móviles
    mobilePorcentaje: document.getElementById('mobile-porcentaje'),
    mobileDistancia: document.getElementById('mobile-distancia')
};

// Estados y sus configuraciones
const estadoConfig = {
    normal: {
        icon: '✅',
        text: 'Nivel Normal',
        class: 'normal'
    },
    alerta: {
        icon: '⚠️',
        text: 'Nivel Bajo - Alerta',
        class: 'alerta'
    },
    peligro: {
        icon: '🚨',
        text: '¡NIVEL CRÍTICO!',
        class: 'peligro'
    },
    sin_datos: {
        icon: '⏳',
        text: 'Esperando datos...',
        class: ''
    }
};

// Actualizar la interfaz con nuevos datos
function actualizarUI(datos) {
    if (!datos || datos.porcentaje === null) return;

    const config = estadoConfig[datos.estado] || estadoConfig.sin_datos;

    // Actualizar tanque visual (siempre azul)
    elements.tankWater.style.height = `${datos.porcentaje}%`;

    // Actualizar ondas del sensor (llegan hasta 10% dentro del agua)
    const tankHeight = 300; // altura del tanque en px
    const nivelAgua = datos.porcentaje; // porcentaje de agua
    // Las ondas van desde arriba hasta 10% dentro del agua
    const penetracion = Math.min(10, nivelAgua * 0.1); // máximo 10% de penetración
    const wavesHeight = tankHeight * (100 - nivelAgua + penetracion) / 100;
    if (elements.sensorWaves) {
        elements.sensorWaves.style.height = `${wavesHeight}px`;
    }

    // Actualizar litros en el tanque (solo el número, "[Litros]" está en small)
    elements.litrosDisplay.textContent = Math.round(datos.litros);

    // Actualizar card de estado
    elements.estadoCard.className = 'metric-card main-metric ' + config.class;
    elements.estadoIcon.textContent = config.icon;
    elements.estadoText.textContent = config.text;

    // Actualizar métricas
    elements.porcentajeValue.textContent = `${datos.porcentaje.toFixed(1)}%`;
    elements.porcentajeBar.style.width = `${datos.porcentaje}%`;
    elements.litrosValue.textContent = `${Math.round(datos.litros)} [Litros]`;
    elements.alturaValue.textContent = `${datos.altura_agua.toFixed(1)} cm`;
    elements.distanciaValue.textContent = `${datos.distancia.toFixed(1)} cm`;

    // Actualizar mini widgets móviles
    if (elements.mobilePorcentaje) {
        elements.mobilePorcentaje.textContent = `${datos.porcentaje.toFixed(1)}%`;
    }
    if (elements.mobileDistancia) {
        elements.mobileDistancia.textContent = `${datos.distancia.toFixed(1)} cm`;
    }

    // Actualizar timestamp
    if (datos.ultima_lectura) {
        const fecha = new Date(datos.ultima_lectura);
        elements.timestampValue.textContent = fecha.toLocaleString('es-CL');
    }

    // Efecto visual de actualización
    document.querySelectorAll('.metric-card').forEach(card => {
        card.style.animation = 'none';
        card.offsetHeight; // Trigger reflow
        card.style.animation = null;
    });
}

// Marcar como conectado/desconectado
function setConnected(connected) {
    const dashboard = document.querySelector('.dashboard');
    
    if (connected) {
        elements.connectionStatus.className = 'status-badge connected';
        elements.connectionStatus.querySelector('.status-text').textContent = 'MQTT Conectado';
        dashboard.classList.remove('disconnected-state');
    } else {
        elements.connectionStatus.className = 'status-badge disconnected';
        elements.connectionStatus.querySelector('.status-text').textContent = 'MQTT Desconectado';
        dashboard.classList.add('disconnected-state');
        
        // Mostrar estado desconectado
        mostrarDesconectado();
    }
}

// Mostrar UI en estado desconectado
function mostrarDesconectado() {
    elements.tankWater.style.height = '0%';
    elements.litrosDisplay.textContent = '🔌';
    elements.porcentajeValue.textContent = '--%';
    elements.litrosValue.textContent = '-- [Litros]';
    elements.alturaValue.textContent = '-- cm';
    elements.distanciaValue.textContent = '-- cm';
    elements.porcentajeBar.style.width = '0%';
    elements.estadoIcon.textContent = '🔌';
    elements.estadoText.textContent = 'Sin conexión';
    elements.estadoCard.className = 'metric-card main-metric disconnected';
    elements.timestampValue.textContent = '--';
    
    // Ocultar ondas del sensor
    if (elements.sensorWaves) {
        elements.sensorWaves.style.height = '0px';
    }
}

// Estado de preview
let previewActivo = false;

// Función para preview de simulación
function simularPreview(distancia) {
    previewActivo = true;
    mostrarOverlay(true);
    
    fetch(`/monitor/api/simular/${distancia}`)
        .then(response => response.json())
        .then(datos => {
            console.log('🧪 Preview:', datos);
            actualizarUI(datos);
        })
        .catch(error => {
            console.error('Error en simulación:', error);
        });
}

// Volver a datos reales
function volverDatosReales() {
    previewActivo = false;
    mostrarOverlay(false);
    cargarEstado();
}

// Mostrar/ocultar overlay
function mostrarOverlay(activo) {
    const overlay = document.getElementById('simulation-overlay');
    if (overlay) {
        if (activo) {
            overlay.classList.remove('hidden');
        } else {
            overlay.classList.add('hidden');
        }
    }
}

// Función para cargar estado
function cargarEstado() {
    fetch('/monitor/api/estado')
        .then(response => {
            if (!response.ok) throw new Error('Error de red');
            return response.json();
        })
        .then(datos => {
            // Mostrar estado de conexión MQTT
            setConnected(datos.mqtt_connected);
            
            // No actualizar UI si está en modo preview
            if (previewActivo) return;
            
            if (datos.porcentaje !== null) {
                actualizarUI(datos);
            }
        })
        .catch(error => {
            console.error('Error cargando estado:', error);
            setConnected(false);
        });
}

// Cargar estado inicial
cargarEstado();

// Actualizar cada 3 segundos para datos en tiempo real
setInterval(cargarEstado, 3000);
