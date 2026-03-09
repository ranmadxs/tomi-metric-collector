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

// ============================================================
// HISTORIAL - Gráfico de consumo mensual
// ============================================================

let historialChart = null;

function actualizarMongoStatus(conectado) {
    const mongoBadge = document.getElementById('mongo-status');
    if (!mongoBadge) return;
    
    if (conectado) {
        mongoBadge.className = 'status-badge connected';
        mongoBadge.querySelector('.status-text').textContent = 'MongoDB Conectado';
    } else {
        mongoBadge.className = 'status-badge disconnected';
        mongoBadge.querySelector('.status-text').textContent = 'MongoDB Desconectado';
    }
}

function cargarHistorial() {
    fetch('/monitor/api/historial/status')
        .then(response => response.json())
        .then(status => {
            const card = document.getElementById('historial-card');
            const container = document.getElementById('historial-container');
            const disabled = document.getElementById('historial-disabled');
            const statusText = document.getElementById('historial-status');
            
            // Actualizar badge de MongoDB
            actualizarMongoStatus(status.conectado);
            
            if (!status.conectado) {
                // MongoDB no conectado - mostrar gris
                card.classList.add('disabled');
                container.style.display = 'none';
                disabled.style.display = 'flex';
                statusText.textContent = 'No disponible';
                return;
            }
            
            // MongoDB conectado - cargar datos
            card.classList.remove('disabled');
            container.style.display = 'block';
            disabled.style.display = 'none';
            
            fetch('/monitor/api/historial/diario')
                .then(response => response.json())
                .then(data => {
                    if (data.datos && data.datos.length > 0) {
                        statusText.textContent = `${data.total_dias} días`;
                        renderizarGrafico(data.datos);
                    } else {
                        statusText.textContent = 'Sin datos';
                    }
                })
                .catch(error => {
                    console.error('Error cargando historial:', error);
                    statusText.textContent = 'Error';
                });
        })
        .catch(error => {
            console.error('Error verificando historial:', error);
            const card = document.getElementById('historial-card');
            card.classList.add('disabled');
        });
}

function renderizarGrafico(datos) {
    const ctx = document.getElementById('historial-chart');
    if (!ctx) return;
    
    // Destruir gráfico anterior si existe
    if (historialChart) {
        historialChart.destroy();
    }
    
    // Preparar datos
    const labels = datos.map(d => {
        const fecha = new Date(d.fecha);
        return fecha.toLocaleDateString('es-CL', { day: '2-digit', month: 'short' });
    });
    const porcentajes = datos.map(d => d.porcentaje);
    
    // Crear gráfico
    historialChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Nivel Promedio %',
                data: porcentajes,
                borderColor: '#3B82F6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: 3,
                pointBackgroundColor: '#3B82F6'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const idx = context.dataIndex;
                            const d = datos[idx];
                            return [
                                `Nivel: ${d.porcentaje}%`,
                                `Litros: ${d.litros} L`,
                                `Muestras: ${d.muestras}`
                            ];
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        callback: function(value) {
                            return value + '%';
                        },
                        font: { size: 10 }
                    },
                    grid: {
                        color: 'rgba(0,0,0,0.05)'
                    }
                },
                x: {
                    ticks: {
                        font: { size: 9 },
                        maxRotation: 45
                    },
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

// Cargar historial al inicio y cada 5 minutos
cargarHistorial();
setInterval(cargarHistorial, 300000);
