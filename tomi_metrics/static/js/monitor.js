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
    
    // Preparar datos (agregar T12:00:00 para evitar problemas de zona horaria)
    const labels = datos.map(d => {
        const fecha = new Date(d.fecha + 'T12:00:00');
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
                backgroundColor: 'rgba(200, 210, 220, 0.4)',
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointBackgroundColor: '#3B82F6',
                borderWidth: 2
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
                        font: { size: 10 },
                        color: '#ffffff'
                    },
                    grid: {
                        color: 'rgba(148, 163, 184, 0.3)'
                    }
                },
                x: {
                    ticks: {
                        font: { size: 9 },
                        maxRotation: 45,
                        color: '#ffffff'
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

// ============================================================
// MODAL HISTORIAL DETALLADO
// ============================================================

let historialDetalladoChart = null;
let datosHistorialMes = null; // Guardar datos del mes para zoom

const MESES_ES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

function abrirHistorialDetallado() {
    const modal = document.getElementById('historial-modal');
    const loading = document.getElementById('modal-loading');
    const titulo = document.getElementById('modal-mes-titulo');
    
    modal.classList.remove('hidden');
    loading.classList.remove('hidden');
    
    fetch('/monitor/api/historial/mensual-horas')
        .then(response => {
            if (response.status === 401) {
                throw new Error('Debes iniciar sesión para ver el historial detallado');
            }
            return response.json();
        })
        .then(data => {
            loading.classList.add('hidden');
            
            if (data.error) {
                if (data.login_required) {
                    alert('Debes iniciar sesión para ver el historial detallado');
                    cerrarHistorialDetallado();
                    window.location.href = '/login?next=/monitor';
                } else {
                    alert('Error: ' + data.error);
                }
                return;
            }
            
            titulo.textContent = `${MESES_ES[data.mes]} ${data.anio}`;
            renderizarGraficoDetallado(data);
        })
        .catch(error => {
            loading.classList.add('hidden');
            console.error('Error cargando historial detallado:', error);
            alert(error.message || 'Error al cargar los datos');
            cerrarHistorialDetallado();
        });
}

function cerrarHistorialDetallado() {
    const modal = document.getElementById('historial-modal');
    modal.classList.add('hidden');
    
    if (historialDetalladoChart) {
        historialDetalladoChart.destroy();
        historialDetalladoChart = null;
    }
}

function renderizarGraficoDetallado(data) {
    // Guardar datos para zoom
    datosHistorialMes = data;
    renderizarVistaCompleta(data);
}

function renderizarVistaCompleta(data) {
    const ctx = document.getElementById('historial-detallado-chart');
    if (!ctx) return;
    
    if (historialDetalladoChart) {
        historialDetalladoChart.destroy();
    }
    
    // Ocultar botón volver
    const btnVolver = document.getElementById('btn-volver-mes');
    if (btnVolver) btnVolver.classList.add('hidden');
    
    // Crear labels para todos los días y horas del mes
    const labels = [];
    const valores = [];
    const datosMap = {};
    
    // Crear mapa de datos recibidos
    data.datos.forEach(d => {
        const key = `${d.fecha}-${d.hora}`;
        datosMap[key] = d;
    });
    
    // Nombre del mes para el título del eje
    const nombreMes = MESES_ES[data.mes];
    
    // Generar todos los días del mes con sus horas
    for (let dia = 1; dia <= data.dias_mes; dia++) {
        const fechaStr = `${data.anio}-${String(data.mes).padStart(2, '0')}-${String(dia).padStart(2, '0')}`;
        
        for (let hora = 0; hora < 24; hora++) {
            const key = `${fechaStr}-${hora}`;
            const dato = datosMap[key];
            
            // Label: mostrar solo el día a las 12h (centro del día)
            if (hora === 12) {
                labels.push(`${dia}`);
            } else {
                labels.push('');
            }
            
            valores.push(dato ? dato.litros : null);
        }
    }
    
    historialDetalladoChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Litros',
                data: valores,
                borderColor: '#3B82F6',
                backgroundColor: 'rgba(200, 210, 220, 0.3)',
                fill: true,
                tension: 0.2,
                pointRadius: 0,
                borderWidth: 1.5,
                spanGaps: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            onClick: function(evt, elements) {
                if (elements.length > 0) {
                    const idx = elements[0].index;
                    const dia = Math.floor(idx / 24) + 1;
                    zoomDia(dia);
                }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        title: function(context) {
                            const idx = context[0].dataIndex;
                            const dia = Math.floor(idx / 24) + 1;
                            const hora = idx % 24;
                            return `Día ${dia}, ${hora}:00 hrs (clic para zoom)`;
                        },
                        label: function(context) {
                            if (context.raw === null) return 'Sin datos';
                            return `${context.raw} L`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 5000,
                    ticks: {
                        callback: function(value) {
                            return value + ' L';
                        },
                        font: { size: 11 },
                        color: '#ffffff'
                    },
                    grid: {
                        color: 'rgba(148, 163, 184, 0.2)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: nombreMes,
                        color: '#ffffff',
                        font: { size: 12, weight: 'bold' },
                        align: 'end'
                    },
                    ticks: {
                        font: { size: 10 },
                        color: '#ffffff',
                        maxRotation: 0,
                        autoSkip: false
                    },
                    grid: {
                        color: 'rgba(148, 163, 184, 0.1)'
                    }
                }
            }
        }
    });
}

function zoomDia(dia) {
    if (!datosHistorialMes) return;
    
    const data = datosHistorialMes;
    const ctx = document.getElementById('historial-detallado-chart');
    if (!ctx) return;
    
    if (historialDetalladoChart) {
        historialDetalladoChart.destroy();
    }
    
    // Mostrar botón volver
    const btnVolver = document.getElementById('btn-volver-mes');
    if (btnVolver) btnVolver.classList.remove('hidden');
    
    // Crear mapa de datos
    const datosMap = {};
    data.datos.forEach(d => {
        const key = `${d.fecha}-${d.hora}`;
        datosMap[key] = d;
    });
    
    const nombreMes = MESES_ES[data.mes];
    const fechaStr = `${data.anio}-${String(data.mes).padStart(2, '0')}-${String(dia).padStart(2, '0')}`;
    
    // Generar las 24 horas del día
    const labels = [];
    const valores = [];
    
    for (let hora = 0; hora < 24; hora++) {
        const key = `${fechaStr}-${hora}`;
        const dato = datosMap[key];
        
        labels.push(`${hora}:00`);
        valores.push(dato ? dato.litros : null);
    }
    
    historialDetalladoChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Litros',
                data: valores,
                borderColor: '#3B82F6',
                backgroundColor: 'rgba(200, 210, 220, 0.3)',
                fill: true,
                tension: 0.3,
                pointRadius: 4,
                pointBackgroundColor: '#3B82F6',
                borderWidth: 2,
                spanGaps: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        title: function(context) {
                            const hora = context[0].dataIndex;
                            return `${hora}:00 hrs`;
                        },
                        label: function(context) {
                            if (context.raw === null) return 'Sin datos';
                            return `${context.raw} L`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 5000,
                    ticks: {
                        callback: function(value) {
                            return value + ' L';
                        },
                        font: { size: 11 },
                        color: '#ffffff'
                    },
                    grid: {
                        color: 'rgba(148, 163, 184, 0.2)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: `${dia} - ${nombreMes}`,
                        color: '#ffffff',
                        font: { size: 12, weight: 'bold' },
                        align: 'end'
                    },
                    ticks: {
                        font: { size: 10 },
                        color: '#ffffff',
                        maxRotation: 45
                    },
                    grid: {
                        color: 'rgba(148, 163, 184, 0.1)'
                    }
                }
            }
        }
    });
}

function volverVistaCompleta() {
    if (datosHistorialMes) {
        renderizarVistaCompleta(datosHistorialMes);
    }
}

// Cerrar modal con Escape
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        cerrarHistorialDetallado();
    }
});
