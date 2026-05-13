/**
 * =====================================================================
 * ANALYTICS CON PLOTLY - Dashboard de Control Logistico
 * Renderiza los gráficos detallados usando Plotly.js con DATOS REALES
 * =====================================================================
 */

// Inicializar gráficos detallados con datos REALES de la base de datos
async function inicializarGraficosDetallados() {
    console.log('📊 Cargando gráficos detallados con datos REALES...');

    if (typeof Plotly === 'undefined') {
        console.error('❌ Plotly.js no está cargado');
        return;
    }

    try {
        // Obtener filtros actuales
        const params = new URLSearchParams();
        if (filtroFechaInicio) params.append('fecha_inicio', filtroFechaInicio);
        if (filtroFechaFin) params.append('fecha_fin', filtroFechaFin);
        if (filtroDepartamento && filtroDepartamento !== 'todos') {
            params.append('departamento', filtroDepartamento);
        }

        // Consultar endpoint con datos REALES
        const response = await fetch(`${API_URL}/api/analytics/dashboard?${params.toString()}`, {
            method: 'GET',
            credentials: 'include'
        });

        if (!response.ok) {
            throw new Error('Error cargando datos del dashboard');
        }

        const data = await response.json();

        if (data.success && data.analytics_data) {
            const analyticsData = data.analytics_data;

            // Renderizar cada gráfico con datos REALES
            renderizarGraficoTimeline(analyticsData.timeline);
            renderizarGraficoCategorias(analyticsData.categorias);
            renderizarGraficoDepartamentos(analyticsData.departamentos);
            renderizarGraficoTiempo(analyticsData.tiempos_promedio);
            renderizarGraficoReportan(analyticsData.top_reportan);
            renderizarGraficoResuelven(analyticsData.top_resuelven);
            renderizarGraficoHoras(analyticsData.horas_pico);
            renderizarGraficoPuestos(analyticsData.puestos_problematicos);
            actualizarComparativaMensual(analyticsData.comparativa_mensual);
            actualizarTendenciaSemanal(analyticsData.tendencia_semanal);

            console.log(`✅ Gráficos detallados renderizados con ${data.total_incidencias} incidencias REALES`);
        } else {
            console.error('❌ Error en respuesta del servidor');
        }

    } catch (error) {
        console.error('❌ Error cargando gráficos:', error);
        mostrarNotificacion('❌ Error cargando gráficos detallados', 'error');
    }
}

// Configuración común de layout para todos los gráficos
const layoutComun = {
    margin: { t: 20, r: 20, b: 60, l: 60 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { family: 'Segoe UI, sans-serif', size: 12 },
    showlegend: false
};

const configComun = {
    responsive: true,
    displayModeBar: false
};

// Timeline - Gráfico de línea temporal con datos REALES
function renderizarGraficoTimeline(data) {
    if (!data || !data.labels) {
        console.warn('⚠️ No hay datos para timeline');
        return;
    }

    const trace = {
        x: data.labels,
        y: data.values,
        type: 'scatter',
        mode: 'lines+markers',
        line: { color: '#4299e1', width: 3, shape: 'spline' },
        marker: { size: 6, color: '#2c5282' },
        fill: 'tozeroy',
        fillcolor: 'rgba(66, 153, 225, 0.1)'
    };

    const layout = {
        ...layoutComun,
        xaxis: { tickangle: -45 },
        yaxis: { title: 'Incidencias' }
    };

    Plotly.newPlot('chart-timeline', [trace], layout, configComun);
}

// Categorías - Distribución por tipo con datos REALES
function renderizarGraficoCategorias(data) {
    if (!data || !data.labels) {
        console.warn('⚠️ No hay datos para categorías');
        return;
    }

    const trace = {
        x: data.labels,
        y: data.values,
        type: 'bar',
        marker: {
            color: ['#9f7aea', '#805ad5', '#6b46c1', '#553c9a', '#44337a', '#3c366b', '#2d2f5f']
        }
    };

    const layout = {
        ...layoutComun,
        yaxis: { title: 'Cantidad' }
    };

    Plotly.newPlot('chart-categorias', [trace], layout, configComun);
}

// Departamentos - Gráfico de pastel con datos REALES
function renderizarGraficoDepartamentos(data) {
    if (!data || !data.labels) {
        console.warn('⚠️ No hay datos para departamentos');
        return;
    }

    const trace = {
        labels: data.labels,
        values: data.values,
        type: 'pie',
        marker: {
            colors: ['#4299e1', '#48bb78', '#ed8936', '#9f7aea']
        },
        textinfo: 'label+percent',
        textposition: 'inside'
    };

    const layout = {
        ...layoutComun,
        margin: { t: 20, r: 20, b: 20, l: 20 }
    };

    Plotly.newPlot('chart-departamentos', [trace], layout, configComun);
}

// Tiempo promedio (barras horizontales) - Datos REALES
function renderizarGraficoTiempo(data) {
    if (!data || !data.labels || data.labels.length === 0) {
        console.warn('⚠️ No hay datos para tiempos');
        return;
    }

    const trace = {
        y: data.labels,
        x: data.values,
        type: 'bar',
        orientation: 'h',
        marker: { color: '#48bb78' }
    };

    const layout = {
        ...layoutComun,
        xaxis: { title: 'Minutos' },
        margin: { ...layoutComun.margin, l: 120 }
    };

    Plotly.newPlot('chart-tiempo', [trace], layout, configComun);
}

// Top reportan - Datos REALES
function renderizarGraficoReportan(data) {
    if (!data || !data.labels || data.labels.length === 0) {
        console.warn('⚠️ No hay datos para top reportan');
        return;
    }

    const trace = {
        y: data.labels,
        x: data.values,
        type: 'bar',
        orientation: 'h',
        marker: { color: '#fc8181' }
    };

    const layout = {
        ...layoutComun,
        xaxis: { title: 'Incidencias' },
        margin: { ...layoutComun.margin, l: 150 }
    };

    Plotly.newPlot('chart-reportan', [trace], layout, configComun);
}

// Top resuelven - Datos REALES
function renderizarGraficoResuelven(data) {
    if (!data || !data.labels || data.labels.length === 0) {
        console.warn('⚠️ No hay datos para top resuelven');
        return;
    }

    const trace = {
        y: data.labels,
        x: data.values,
        type: 'bar',
        orientation: 'h',
        marker: { color: '#68d391' }
    };

    const layout = {
        ...layoutComun,
        xaxis: { title: 'Resueltas' },
        margin: { ...layoutComun.margin, l: 150 }
    };

    Plotly.newPlot('chart-resuelven', [trace], layout, configComun);
}

// Horas pico - Datos REALES
function renderizarGraficoHoras(data) {
    if (!data || !data.labels) {
        console.warn('⚠️ No hay datos para horas pico');
        return;
    }

    const maxVal = Math.max(...data.values);
    const threshold = maxVal * 0.6;

    const trace = {
        x: data.labels,
        y: data.values,
        type: 'bar',
        marker: {
            color: data.values.map(v => v > threshold ? '#ed8936' : '#f6ad55')
        }
    };

    const layout = {
        ...layoutComun,
        xaxis: { tickangle: -45 },
        yaxis: { title: 'Incidencias' }
    };

    Plotly.newPlot('chart-horas', [trace], layout, configComun);
}

// Puestos problemáticos - Datos REALES
function renderizarGraficoPuestos(data) {
    if (!data || !data.labels || data.labels.length === 0) {
        console.warn('⚠️ No hay datos para puestos problemáticos');
        return;
    }

    const trace = {
        y: data.labels,
        x: data.values,
        type: 'bar',
        orientation: 'h',
        marker: { color: '#f56565' }
    };

    const layout = {
        ...layoutComun,
        xaxis: { title: 'Incidencias' },
        margin: { ...layoutComun.margin, l: 120 }
    };

    Plotly.newPlot('chart-puestos', [trace], layout, configComun);
}

// Comparativa mensual - Datos REALES
function actualizarComparativaMensual(data) {
    if (!data) {
        console.warn('⚠️ No hay datos para comparativa mensual');
        return;
    }

    document.getElementById('mes-actual-value').textContent = data.mes_actual || 0;
    document.getElementById('mes-anterior-value').textContent = data.mes_anterior || 0;
    document.getElementById('mes-actual-label').textContent = data.nombre_mes_actual || 'Mes Actual';
    document.getElementById('mes-anterior-label').textContent = data.nombre_mes_anterior || 'Mes Anterior';
}

// Tendencia semanal - Datos REALES
function actualizarTendenciaSemanal(data) {
    if (!data) {
        console.warn('⚠️ No hay datos para tendencia semanal');
        return;
    }

    const tendenciaElement = document.getElementById('trend-value');
    const labelElement = document.getElementById('trend-label');
    const porcentaje = data.porcentaje || 0;

    tendenciaElement.textContent = porcentaje >= 0 ? `+${porcentaje}%` : `${porcentaje}%`;
    labelElement.textContent = data.label || 'Estable →';

    // Color según tendencia
    tendenciaElement.className = 'trend-value';
    if (porcentaje > 10) {
        tendenciaElement.classList.add('negative');
    } else if (porcentaje < -10) {
        tendenciaElement.classList.add('positive');
    } else {
        tendenciaElement.classList.add('neutral');
    }

    document.getElementById('trend-semana-actual').textContent = data.semana_actual || 0;
    document.getElementById('trend-semana-anterior').textContent = data.semana_anterior || 0;
}

console.log('✅ Analytics Plotly cargado - Listo para usar DATOS REALES');
