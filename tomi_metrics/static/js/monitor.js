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
    timestampValue: document.getElementById('timestamp-value')
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

    // Actualizar litros en el tanque
    elements.litrosDisplay.textContent = `${Math.round(datos.litros)} [Litros]`;

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

// Marcar como conectado
function setConnected(connected) {
    if (connected) {
        elements.connectionStatus.className = 'status-badge connected';
        elements.connectionStatus.querySelector('.status-text').textContent = 'MQTT Conectado';
    } else {
        elements.connectionStatus.className = 'status-badge disconnected';
        elements.connectionStatus.querySelector('.status-text').textContent = 'MQTT Desconectado';
    }
}

// Función para simular lecturas
function simular(distancia) {
    fetch(`/monitor/api/simular/${distancia}`)
        .then(response => response.json())
        .then(datos => {
            console.log('🧪 Simulación:', datos);
        })
        .catch(error => {
            console.error('Error en simulación:', error);
        });
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
