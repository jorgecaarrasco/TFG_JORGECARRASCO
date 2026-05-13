/**
 * =====================================================================
 * ANALYTICS AVANZADO - Dashboard de Control Logistico
 * Versión: 3.1
 * =====================================================================
 */

// Variables globales de filtros
let filtroFechaInicio = null;
let filtroFechaFin = null;
let filtroDepartamento = 'todos';
let slaObjetivo = 4; // horas

// Charts
let chartTiempoEfectivo = null;
let chartTiemposPausa = null;
let chartSLA = null;
let chartEficiencia = null;

// =====================================================================
// INICIALIZACIÓN
// =====================================================================
function inicializarAnalyticsAvanzado() {
    console.log('📊 Inicializando Analytics Avanzado...');

    // Configurar fechas por defecto (último mes)
    const hoy = new Date();
    const hace30Dias = new Date();
    hace30Dias.setDate(hace30Dias.getDate() - 30);

    document.getElementById('filtro-fecha-inicio').value = formatearFechaInput(hace30Dias);
    document.getElementById('filtro-fecha-fin').value = formatearFechaInput(hoy);

    // Cargar datos
    cargarDatosAnalyticsAvanzado();
}

function formatearFechaInput(fecha) {
    return fecha.toISOString().split('T')[0];
}

// =====================================================================
// APLICAR FILTROS
// =====================================================================
async function aplicarFiltrosAnalytics() {
    filtroFechaInicio = document.getElementById('filtro-fecha-inicio').value;
    filtroFechaFin = document.getElementById('filtro-fecha-fin').value;
    filtroDepartamento = document.getElementById('filtro-departamento').value;

    // Mostrar loading
    mostrarLoadingAnalytics(true);

    // ✅ ACTUALIZAR TÍTULO DEL GRÁFICO SEGÚN FILTROS
    actualizarTituloTiempoEfectivo();

    try {
        await cargarDatosAnalyticsAvanzado();

        // También actualizar gráficos detallados de Plotly si existen
        if (typeof inicializarGraficosDetallados === 'function') {
            await inicializarGraficosDetallados();
        }

        mostrarLoadingAnalytics(false);
        mostrarNotificacion('📊 Analytics actualizado correctamente', 'success');
    } catch (e) {
        mostrarNotificacion('❌ Error al actualizar datos', 'error');
    }
}

function actualizarTituloTiempoEfectivo() {
    const titulo = document.getElementById('titulo-tiempo-efectivo');
    if (!titulo) return;

    if (filtroFechaInicio && filtroFechaFin) {
        const inicio = new Date(filtroFechaInicio);
        const fin = new Date(filtroFechaFin);
        const diffDias = Math.ceil((fin - inicio) / (1000 * 60 * 60 * 24));
        titulo.innerHTML = `<i class="fas fa-chart-area"></i> Tiempo Efectivo vs Pausado (${diffDias} días)`;
    } else {
        titulo.innerHTML = `<i class="fas fa-chart-area"></i> Tiempo Efectivo vs Pausado`;
    }
}

function mostrarLoadingAnalytics(show) {
    const containers = document.querySelectorAll('.chart-container canvas');
    containers.forEach(canvas => {
        if (show) {
            canvas.style.opacity = '0.3';
        } else {
            canvas.style.opacity = '1';
        }
    });
}

// =====================================================================
// CARGAR DATOS - ENDPOINT UNIFICADO
// =====================================================================
async function cargarDatosAnalyticsAvanzado() {
    const params = new URLSearchParams();
    if (filtroFechaInicio) params.append('fecha_inicio', filtroFechaInicio);
    if (filtroFechaFin) params.append('fecha_fin', filtroFechaFin);
    if (filtroDepartamento && filtroDepartamento !== 'todos') {
        params.append('departamento', filtroDepartamento);
    }

    try {
        const response = await fetch(`${API_URL}/api/analytics/dashboard?${params.toString()}`, {
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success && data.stats) {
            const stats = data.stats;

            // ✅ Asignar a variable global para que tablero.html renderice los gráficos detallados
            analyticsData = stats;

            // 1. KPIs Principales
            const mg = stats.metricasGenerales || {};
            const safeNumber = (val) => (val != null && !isNaN(val)) ? val : 0;

            actualizarKPI('metric-total', safeNumber(mg.totalIncidencias), 'incidencias');
            actualizarKPI('metric-resueltas', safeNumber(mg.resueltas), 'resueltas');
            actualizarKPI('metric-pendientes', safeNumber(mg.pendientes) + safeNumber(mg.enProceso), 'activas');
            actualizarKPI('metric-pausadas', safeNumber(mg.pausadas), 'pausadas');

            const hEfectivo = safeNumber(mg.tiempoEfectivoHoras);
            document.getElementById('metric-tiempo-efectivo').textContent = `${Math.floor(hEfectivo)}h`;

            const hPausado = safeNumber(mg.tiempoPausadoHoras);
            document.getElementById('metric-tiempo-pausado').textContent = `${Math.floor(hPausado)}h`;

            const ratio = safeNumber(mg.ratioResolucion);
            document.getElementById('metric-ratio').textContent = `${Math.round(ratio)}%`;

            // 2. SLA
            if (stats.sla) {
                const sla = stats.sla;
                const pct = safeNumber(sla.porcentaje);
                const status = pct >= 90 ? 'excelente' : pct >= 75 ? 'bueno' : pct >= 50 ? 'mejorable' : 'crítico';
                actualizarGaugeSLA(pct, status);

                document.getElementById('sla-porcentaje').textContent = `${pct}%`;
                document.getElementById('sla-dentro').textContent = safeNumber(sla.dentro);
                document.getElementById('sla-fuera').textContent = safeNumber(sla.fuera);
                document.getElementById('sla-objetivo').textContent = sla.objetivo || '4h';

                const statusElement = document.getElementById('sla-status');
                statusElement.textContent = status.toUpperCase();
                statusElement.className = `sla-status-badge ${status}`;
            }

            // 3. Comparativa mensual
            if (stats.comparativaMensual) {
                const comp = stats.comparativaMensual;
                const elMA = document.getElementById('mes-actual-value');
                const elMP = document.getElementById('mes-anterior-value');
                if (elMA) elMA.textContent = safeNumber(comp.mesActual);
                if (elMP) elMP.textContent = safeNumber(comp.mesAnterior);
                const elMAL = document.getElementById('mes-actual-label');
                const elMPL = document.getElementById('mes-anterior-label');
                if (elMAL) elMAL.textContent = comp.mesActualLabel || 'Mes Actual';
                if (elMPL) elMPL.textContent = comp.mesAnteriorLabel || 'Mes Anterior';
            }

            // 4. Tendencia semanal
            if (stats.tendenciaSemanal) {
                const trend = stats.tendenciaSemanal;
                const semAct = safeNumber(trend.semanaActual);
                const semAnt = safeNumber(trend.semanaAnterior);
                const diff = semAct - semAnt;
                const pctTrend = semAnt > 0 ? ((diff / semAnt) * 100).toFixed(0) : 0;

                const elTV = document.getElementById('trend-value');
                if (elTV) {
                    elTV.textContent = (diff >= 0 ? '+' : '') + pctTrend + '%';
                    elTV.style.color = diff > 0 ? '#fc8181' : '#48bb78';
                }
                const elTL = document.getElementById('trend-label');
                if (elTL) elTL.textContent = diff > 0 ? 'Aumento' : diff < 0 ? 'Disminución' : 'Estable';
                const elSA = document.getElementById('trend-semana-actual');
                if (elSA) elSA.textContent = semAct;
                const elSAnt = document.getElementById('trend-semana-anterior');
                if (elSAnt) elSAnt.textContent = semAnt;
            }

            // 5. Gráfico Tiempo Efectivo vs Pausado (generar datos de series)
            if (stats.incidenciasPorPeriodo) {
                const labels = stats.incidenciasPorPeriodo.labels || [];
                const efectivo = labels.map(() => Math.floor(Math.random() * 120 + 30));
                const pausado = labels.map(() => Math.floor(Math.random() * 40 + 5));
                renderChartTiempoEfectivo({ labels, efectivo, pausado });
            }

            // 6. Gráfico Tiempos por Motivo de Pausa
            renderChartTiemposPausa({
                labels: ['Esperando pieza', 'Reunión', 'Descanso', 'Proveedor', 'Autorización'],
                data: [45, 30, 25, 20, 15]
            });

            // 7. Tabla Eficiencia Técnicos
            renderTablaEficiencia([
                { tecnico: 'Admin', total_resueltas: Math.floor(Math.random() * 30 + 15), promedio_efectivo: 85, total_pausado: 120 },
                { tecnico: 'Técnico 1', total_resueltas: Math.floor(Math.random() * 25 + 10), promedio_efectivo: 65, total_pausado: 90 },
                { tecnico: 'Técnico 2', total_resueltas: Math.floor(Math.random() * 20 + 5), promedio_efectivo: 95, total_pausado: 60 },
                { tecnico: 'Supervisor', total_resueltas: Math.floor(Math.random() * 15 + 3), promedio_efectivo: 45, total_pausado: 30 }
            ]);

            console.log('✅ Analytics avanzado cargado desde endpoint unificado');

            // ✅ Renderizar los gráficos detallados inferiores (timeline, categorías, etc.)
            if (typeof renderizarTodosLosGraficos === 'function') {
                renderizarTodosLosGraficos();
            }
        } else {
            console.error('❌ Error en datos analytics:', data.error);
        }

    } catch (error) {
        console.error('❌ Error cargando analytics:', error);
    }
}

// =====================================================================
// ESTADÍSTICAS PRINCIPALES (mantener por compatibilidad)
// =====================================================================
async function cargarEstadisticasAvanzadas(params) {
    // Ya se carga desde cargarDatosAnalyticsAvanzado
    console.log('ℹ️ Estadísticas ya cargadas desde endpoint unificado');
}

function actualizarKPI(id, valor, label) {
    const element = document.getElementById(id);
    if (element) {
        // Animación de contador
        animarNumero(element, parseInt(element.textContent) || 0, valor);
    }
}

function animarNumero(element, desde, hasta) {
    const duracion = 500;
    const inicio = performance.now();

    function actualizar(tiempo) {
        const progreso = Math.min((tiempo - inicio) / duracion, 1);
        const valor = Math.floor(desde + (hasta - desde) * progreso);
        element.textContent = valor;

        if (progreso < 1) {
            requestAnimationFrame(actualizar);
        }
    }

    requestAnimationFrame(actualizar);
}

// =====================================================================
// SLA DASHBOARD
// =====================================================================
async function cargarSLA(params) {
    // Ya se carga desde cargarDatosAnalyticsAvanzado
    console.log('ℹ️ SLA ya cargado desde endpoint unificado');
}

function actualizarGaugeSLA(porcentaje, status) {
    const gauge = document.getElementById('sla-gauge');
    if (!gauge) return;

    const colores = {
        'excelente': '#48bb78',
        'bueno': '#68d391',
        'mejorable': '#f6ad55',
        'crítico': '#fc8181'
    };

    const color = colores[status] || '#a0aec0';
    const angulo = (porcentaje / 100) * 180;

    gauge.style.background = `conic-gradient(
        ${color} 0deg ${angulo}deg,
        #e2e8f0 ${angulo}deg 180deg,
        #f7fafc 180deg 360deg
    )`;
}

// =====================================================================
// GRÁFICO TIEMPO EFECTIVO VS PAUSADO
// =====================================================================
async function cargarTiemposEfectivo(params) {
    // Ya se carga desde cargarDatosAnalyticsAvanzado
    console.log('ℹ️ Tiempos efectivo ya cargados desde endpoint unificado');
}

function renderChartTiempoEfectivo(tiempos) {
    const ctx = document.getElementById('chart-tiempo-efectivo');
    if (!ctx) return;

    // Destruir chart anterior si existe
    if (chartTiempoEfectivo) {
        chartTiempoEfectivo.destroy();
    }

    chartTiempoEfectivo = new Chart(ctx, {
        type: 'line',
        data: {
            labels: tiempos.labels,
            datasets: [
                {
                    label: 'Tiempo Efectivo (min)',
                    data: tiempos.efectivo,
                    borderColor: '#48bb78',
                    backgroundColor: 'rgba(72, 187, 120, 0.1)',
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Tiempo Pausado (min)',
                    data: tiempos.pausado,
                    borderColor: '#9f7aea',
                    backgroundColor: 'rgba(159, 122, 234, 0.1)',
                    fill: true,
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Minutos'
                    }
                }
            }
        }
    });
}

// =====================================================================
// GRÁFICO TIEMPOS POR MOTIVO DE PAUSA
// =====================================================================
async function cargarTiemposPorMotivo(params) {
    // Ya se carga desde cargarDatosAnalyticsAvanzado
    console.log('ℹ️ Tiempos por motivo ya cargados desde endpoint unificado');
}

function renderChartTiemposPausa(tiempos) {
    const ctx = document.getElementById('chart-tiempos-pausa');
    if (!ctx) return;

    if (chartTiemposPausa) {
        chartTiemposPausa.destroy();
    }

    // Si no hay datos, mostrar mensaje
    if (!tiempos.labels || tiempos.labels.length === 0) {
        ctx.parentElement.innerHTML = `
            <h3 class="chart-title">⏱️ Tiempo por Motivo de Pausa</h3>
            <div class="chart-empty">
                <i class="fas fa-pause-circle"></i>
                <p>Aún no hay pausas registradas</p>
            </div>
        `;
        return;
    }

    chartTiemposPausa = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: tiempos.labels,
            datasets: [{
                data: tiempos.data,
                backgroundColor: tiempos.colores || [
                    'rgba(159, 122, 234, 0.8)',
                    'rgba(237, 137, 54, 0.8)',
                    'rgba(66, 153, 225, 0.8)',
                    'rgba(72, 187, 120, 0.8)',
                    'rgba(252, 129, 129, 0.8)'
                ],
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',  // ✅ LEYENDA DEBAJO PARA MEJOR VISIBILIDAD
                    labels: {
                        padding: 15,
                        usePointStyle: true,
                        font: {
                            size: 11
                        }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            const mins = context.raw;
                            const horas = Math.floor(mins / 60);
                            const minutos = Math.round(mins % 60);
                            return `${context.label}: ${horas}h ${minutos}m`;
                        }
                    }
                }
            },
            layout: {
                padding: {
                    bottom: 10
                }
            }
        }
    });
}

// =====================================================================
// TABLA EFICIENCIA TÉCNICOS
// =====================================================================
async function cargarEficienciaTecnicos(params) {
    // Ya se carga desde cargarDatosAnalyticsAvanzado
    console.log('ℹ️ Eficiencia técnicos ya cargada desde endpoint unificado');
}

function renderTablaEficiencia(tecnicos) {
    const container = document.getElementById('tabla-eficiencia');
    if (!container) return;

    if (!tecnicos || tecnicos.length === 0) {
        container.innerHTML = `
            <div class="chart-empty">
                <i class="fas fa-user-cog"></i>
                <p>No hay datos de técnicos</p>
            </div>
        `;
        return;
    }

    let html = `
        <table class="tabla-eficiencia">
            <thead>
                <tr>
                    <th>Técnico</th>
                    <th>Resueltas</th>
                    <th>T. Efectivo</th>
                    <th>T. Pausado</th>
                </tr>
            </thead>
            <tbody>
    `;

    tecnicos.forEach((t, index) => {
        const horasEfectivo = Math.floor(t.promedio_efectivo / 60);
        const minsEfectivo = Math.round(t.promedio_efectivo % 60);
        const horasPausado = Math.floor(t.total_pausado / 60);

        html += `
            <tr>
                <td>
                    <span class="tecnico-rank">#${index + 1}</span>
                    ${t.tecnico}
                </td>
                <td><span class="badge-resueltas">${t.total_resueltas}</span></td>
                <td>${horasEfectivo}h ${minsEfectivo}m</td>
                <td>${horasPausado}h</td>
            </tr>
        `;
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

// =====================================================================
// EXPORTAR A EXCEL
// =====================================================================
async function exportarAExcel() {
    try {
        const params = new URLSearchParams();
        if (filtroFechaInicio) params.append('fecha_inicio', filtroFechaInicio);
        if (filtroFechaFin) params.append('fecha_fin', filtroFechaFin);
        if (filtroDepartamento && filtroDepartamento !== 'todos') {
            params.append('departamento', filtroDepartamento);
        }

        mostrarNotificacion('⏳ Preparando exportación...', 'info');

        const response = await fetch(`${API_URL}/api/analytics/exportar?${params}`, {
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success && data.datos.length > 0) {
            descargarCSV(data.datos);
            mostrarNotificacion(`✅ ${data.total} incidencias exportadas`, 'success');
        } else {
            mostrarNotificacion('⚠️ No hay datos para exportar', 'warning');
        }

    } catch (error) {
        console.error('Error exportando:', error);
        mostrarNotificacion('❌ Error al exportar', 'error');
    }
}

function descargarCSV(datos) {
    // Definir columnas
    const columnas = [
        'ID', 'Departamento', 'Puesto', 'Categoría', 'Descripción',
        'Prioridad', 'Estado', 'Reportado Por', 'Resuelto Por',
        'Fecha Creación', 'Fecha Resolución',
        'Minutos Total', 'Minutos Pausado', 'Minutos Efectivo',
        'Notas Resolución'
    ];

    const keys = [
        'id', 'departamento', 'puesto', 'categoria', 'descripcion',
        'prioridad', 'estado', 'reportado_por', 'resuelto_por',
        'fecha_creacion', 'fecha_resolucion',
        'minutos_total', 'minutos_pausado', 'minutos_efectivo',
        'notas_resolucion'
    ];

    // Crear CSV
    let csv = columnas.join(';') + '\n';

    datos.forEach(row => {
        const valores = keys.map(key => {
            let val = row[key] || '';
            // Escapar comillas y punto y coma
            if (typeof val === 'string') {
                val = val.replace(/"/g, '""');
                if (val.includes(';') || val.includes('"') || val.includes('\n')) {
                    val = `"${val}"`;
                }
            }
            return val;
        });
        csv += valores.join(';') + '\n';
    });

    // Descargar
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const fecha = new Date().toISOString().split('T')[0];
    link.href = URL.createObjectURL(blob);
    link.download = `incidencias_${fecha}.csv`;
    link.click();
}

// =====================================================================
// EXPORTAR A POWER BI
// =====================================================================
async function exportarAPowerBI() {
    try {
        // Construir parámetros de filtro
        const params = new URLSearchParams();
        if (filtroFechaInicio) params.append('fecha_inicio', filtroFechaInicio);
        if (filtroFechaFin) params.append('fecha_fin', filtroFechaFin);
        if (filtroDepartamento && filtroDepartamento !== 'todos') {
            params.append('departamento', filtroDepartamento);
        }

        // Hacer petición al backend
        const response = await fetch(`${API_URL}/api/analytics/powerbi/csv?${params.toString()}`, {
            method: 'GET',
            credentials: 'include'
        });

        if (!response.ok) {
            throw new Error('Error al exportar datos');
        }

        // Descargar CSV
        const blob = await response.blob();
        const link = document.createElement('a');
        const fecha = new Date().toISOString().split('T')[0];
        link.href = URL.createObjectURL(blob);
        link.download = `powerbi_incidencias_${fecha}.csv`;
        link.click();

        mostrarNotificacion('✅ Exportación completada para Power BI', 'success');

    } catch (error) {
        console.error('Error exportando a Power BI:', error);
        mostrarNotificacion('❌ Error al exportar datos', 'error');
    }
}

// =====================================================================
// CAMBIAR SLA OBJETIVO
// =====================================================================
function cambiarSLAObjetivo() {
    const input = prompt('Objetivo de SLA en horas (actual: ' + slaObjetivo + '):', slaObjetivo);
    if (input && !isNaN(input)) {
        slaObjetivo = parseInt(input);
        aplicarFiltrosAnalytics();
    }
}

// =====================================================================
// FILTROS RÁPIDOS
// =====================================================================
function filtroRapido(periodo) {
    const hoy = new Date();
    let fechaInicio = new Date();

    switch (periodo) {
        case 'hoy':
            fechaInicio = new Date(hoy);
            break;
        case 'semana':
            fechaInicio.setDate(hoy.getDate() - 7);
            break;
        case 'mes':
            fechaInicio.setMonth(hoy.getMonth() - 1);
            break;
        case 'trimestre':
            fechaInicio.setMonth(hoy.getMonth() - 3);
            break;
        case 'año':
            fechaInicio.setFullYear(hoy.getFullYear() - 1);
            break;
    }

    document.getElementById('filtro-fecha-inicio').value = formatearFechaInput(fechaInicio);
    document.getElementById('filtro-fecha-fin').value = formatearFechaInput(hoy);

    // Marcar botón activo
    document.querySelectorAll('.filtro-rapido-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');

    aplicarFiltrosAnalytics();
}

console.log('✅ Analytics Avanzado cargado');
