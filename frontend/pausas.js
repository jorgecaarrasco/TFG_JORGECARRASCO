/**
 * =====================================================================
 * SISTEMA DE PAUSAS PARA INCIDENCIAS - Dashboard de Control Logistico
 * Versión: 3.2
 * =====================================================================
 * Este archivo contiene toda la lógica del sistema de pausas y timeline
 * =====================================================================
 */

// =====================================================================
// VARIABLES GLOBALES
// =====================================================================
let motivosPausa = [];
let incidenciaSeleccionadaId = null;

// =====================================================================
// CARGAR MOTIVOS DE PAUSA
// =====================================================================
async function cargarMotivosPausa() {
    try {
        const response = await fetch(`${API_URL}/api/motivos-pausa`, {
            credentials: 'include'
        });
        const data = await response.json();
        if (data.success) {
            motivosPausa = data.motivos || [];
            console.log(`✅ Motivos de pausa cargados: ${motivosPausa.length}`);
        }
    } catch (error) {
        console.error('❌ Error cargando motivos de pausa:', error);
    }
}

// =====================================================================
// MODAL DE PAUSAR INCIDENCIA
// =====================================================================
function abrirModalPausar(incidenciaId) {
    incidenciaSeleccionadaId = incidenciaId;
    
    const modal = document.getElementById('modalPausarIncidencia');
    const select = document.getElementById('selectMotivoPausa');
    
    // Limpiar y popular select
    select.innerHTML = '<option value="">Selecciona un motivo...</option>';
    motivosPausa.forEach(motivo => {
        select.innerHTML += `<option value="${motivo.codigo}" data-requiere="${motivo.requiere_descripcion}">
            ${motivo.descripcion}
        </option>`;
    });
    
    // Reset campos
    document.getElementById('descripcionPausaAdicional').value = '';
    document.getElementById('grupoDescripcionAdicional').style.display = 'none';
    
    modal.style.display = 'block';
}

function cerrarModalPausar() {
    document.getElementById('modalPausarIncidencia').style.display = 'none';
    incidenciaSeleccionadaId = null;
}

// Mostrar/ocultar campo de descripción adicional según el motivo
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        const select = document.getElementById('selectMotivoPausa');
        if (select) {
            select.addEventListener('change', function() {
                const option = this.options[this.selectedIndex];
                const requiere = option.getAttribute('data-requiere') === 'True';
                document.getElementById('grupoDescripcionAdicional').style.display = 
                    (requiere || this.value === 'OTRO') ? 'block' : 'none';
            });
        }
    }, 1000);
});

async function confirmarPausarIncidencia() {
    const motivo = document.getElementById('selectMotivoPausa').value;
    const descripcion = document.getElementById('descripcionPausaAdicional').value.trim();
    
    if (!motivo) {
        alert('⚠️ Selecciona un motivo de pausa');
        return;
    }
    
    if (motivo === 'OTRO' && !descripcion) {
        alert('⚠️ Describe el motivo de la pausa');
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/api/incidencias/${incidenciaSeleccionadaId}/pausar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                motivo: motivo,
                descripcion: descripcion || null
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            cerrarModalPausar();
            await loadIncidencias();
            await mostrarDetalleIncidencia(incidenciaSeleccionadaId);
            mostrarNotificacion('⏸️ Incidencia pausada correctamente', 'success');
        } else {
            alert(`❌ Error: ${data.error}`);
        }
    } catch (error) {
        console.error('Error pausando incidencia:', error);
        alert(`❌ Error: ${error.message}`);
    }
}

// =====================================================================
// REANUDAR INCIDENCIA
// =====================================================================
// Alias para el botón de la lista
function reanudarIncidencia(incidenciaId) {
    abrirModalReanudar(incidenciaId);
}

function abrirModalReanudar(incidenciaId) {
    incidenciaSeleccionadaId = incidenciaId;
    
    const modal = document.getElementById('modalReanudarIncidencia');
    
    // Reset campos
    document.getElementById('motivoReanudar').value = '';
    
    modal.style.display = 'block';
}

function cerrarModalReanudar() {
    document.getElementById('modalReanudarIncidencia').style.display = 'none';
    incidenciaSeleccionadaId = null;
}

async function confirmarReanudarIncidencia() {
    const notas = document.getElementById('motivoReanudar').value.trim();
    
    if (!notas) {
        mostrarNotificacion('⚠️ El motivo de reanudación es obligatorio', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/api/incidencias/${incidenciaSeleccionadaId}/reanudar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ notas: notas })
        });
        
        const data = await response.json();
        
        if (data.success) {
            cerrarModalReanudar();
            await loadIncidencias();
            await mostrarDetalleIncidencia(incidenciaSeleccionadaId);
            mostrarNotificacion('▶️ Incidencia reanudada correctamente', 'success');
        } else {
            mostrarNotificacion(`❌ Error: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('Error reanudando incidencia:', error);
        mostrarNotificacion(`❌ Error: ${error.message}`, 'error');
    }
}

// =====================================================================
// TIMELINE DE INCIDENCIA
// =====================================================================
async function cargarTimeline(incidenciaId) {
    try {
        const response = await fetch(`${API_URL}/api/incidencias/${incidenciaId}/timeline`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        if (data.success) {
            renderTimeline(data.timeline, data.pausas);
        }
    } catch (error) {
        console.error('Error cargando timeline:', error);
    }
}

function renderTimeline(timeline, pausas) {
    const container = document.getElementById('timeline-container');
    if (!container) return;
    
    if (!timeline || timeline.length === 0) {
        container.innerHTML = '<p class="timeline-empty">No hay eventos registrados</p>';
        return;
    }
    
    const iconos = {
        'CREADA': 'fa-plus-circle',
        'EN_PROCESO': 'fa-tools',
        'PAUSADA': 'fa-pause-circle',
        'REANUDADA': 'fa-play-circle',
        'RESUELTA': 'fa-check-circle',
        'COMENTARIO': 'fa-comment',
        'EDITADA': 'fa-edit'
    };
    
    const colores = {
        'CREADA': '#4299e1',
        'EN_PROCESO': '#f6ad55',
        'PAUSADA': '#9f7aea',
        'REANUDADA': '#48bb78',
        'RESUELTA': '#68d391',
        'COMENTARIO': '#a0aec0',
        'EDITADA': '#ed8936'
    };
    
    let html = '<div class="timeline">';
    
    timeline.forEach(evento => {
        const fecha = new Date(evento.fecha_evento);
        const fechaStr = fecha.toLocaleDateString('es-ES', {
            day: '2-digit',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        const icono = iconos[evento.tipo_evento] || 'fa-circle';
        const color = colores[evento.tipo_evento] || '#a0aec0';
        
        html += `
            <div class="timeline-item" data-tipo="${evento.tipo_evento}">
                <div class="timeline-icon" style="background: ${color}">
                    <i class="fas ${icono}"></i>
                </div>
                <div class="timeline-content">
                    <div class="timeline-header">
                        <span class="timeline-tipo">${evento.tipo_evento.replace('_', ' ')}</span>
                        <span class="timeline-fecha">${fechaStr}</span>
                    </div>
                    <p class="timeline-descripcion">${evento.descripcion}</p>
                    <span class="timeline-usuario">👤 ${evento.usuario}</span>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    
    // Añadir resumen de pausas si hay
    if (pausas && pausas.length > 0) {
        const totalMinutosPausado = pausas
            .filter(p => p.duracion_minutos)
            .reduce((acc, p) => acc + p.duracion_minutos, 0);
        
        html += `
            <div class="timeline-resumen-pausas">
                <i class="fas fa-clock"></i>
                <span>Total pausado: <strong>${formatearTiempo(totalMinutosPausado)}</strong></span>
                <span class="badge-pausas">${pausas.length} pausa${pausas.length > 1 ? 's' : ''}</span>
            </div>
        `;
    }
    
    container.innerHTML = html;
}

function formatearTiempo(minutos) {
    if (minutos < 60) {
        return `${minutos} min`;
    } else {
        const horas = Math.floor(minutos / 60);
        const mins = minutos % 60;
        return `${horas}h ${mins}min`;
    }
}

// =====================================================================
// NOTIFICACIONES
// =====================================================================
function mostrarNotificacion(mensaje, tipo = 'info') {
    // Crear elemento de notificación
    const notif = document.createElement('div');
    notif.className = `notificacion notif-${tipo}`;
    notif.innerHTML = mensaje;
    
    // Añadir al body
    document.body.appendChild(notif);
    
    // Animar entrada
    setTimeout(() => notif.classList.add('visible'), 10);
    
    // Remover después de 3 segundos
    setTimeout(() => {
        notif.classList.remove('visible');
        setTimeout(() => notif.remove(), 300);
    }, 3000);
}

// =====================================================================
// GESTIÓN DE MOTIVOS DE PAUSA (ADMIN)
// =====================================================================
async function abrirGestionMotivosPausa() {
    await cargarMotivosPausa();
    
    const modal = document.getElementById('modalGestionMotivosPausa');
    const container = document.getElementById('listaMotivosPausa');
    
    if (!container) return;
    
    let html = '';
    motivosPausa.forEach(motivo => {
        html += `
            <div class="motivo-item ${motivo.activo ? '' : 'inactivo'}">
                <div class="motivo-info">
                    <span class="motivo-codigo">${motivo.codigo}</span>
                    <span class="motivo-descripcion">${motivo.descripcion}</span>
                </div>
                <div class="motivo-acciones">
                    <button onclick="toggleMotivoActivo('${motivo.codigo}', ${!motivo.activo})" 
                            class="btn-toggle ${motivo.activo ? 'activo' : ''}">
                        <i class="fas ${motivo.activo ? 'fa-eye' : 'fa-eye-slash'}"></i>
                    </button>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html || '<p>No hay motivos configurados</p>';
    modal.style.display = 'block';
}

function cerrarGestionMotivosPausa() {
    document.getElementById('modalGestionMotivosPausa').style.display = 'none';
}

async function toggleMotivoActivo(codigo, activo) {
    try {
        const response = await fetch(`${API_URL}/api/motivos-pausa/${codigo}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ activo: activo })
        });
        
        const data = await response.json();
        if (data.success) {
            await cargarMotivosPausa();
            abrirGestionMotivosPausa(); // Refrescar lista
        }
    } catch (error) {
        console.error('Error actualizando motivo:', error);
    }
}

async function crearNuevoMotivoPausa() {
    const codigo = prompt('Código del motivo (ej: ESPERANDO_CLIENTE):');
    if (!codigo) return;
    
    const descripcion = prompt('Descripción del motivo:');
    if (!descripcion) return;
    
    try {
        const response = await fetch(`${API_URL}/api/motivos-pausa`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                codigo: codigo.toUpperCase().replace(/\s+/g, '_'),
                descripcion: descripcion
            })
        });
        
        const data = await response.json();
        if (data.success) {
            await cargarMotivosPausa();
            abrirGestionMotivosPausa();
            mostrarNotificacion('✅ Motivo creado correctamente', 'success');
        } else {
            alert(`❌ Error: ${data.error}`);
        }
    } catch (error) {
        console.error('Error creando motivo:', error);
    }
}

// =====================================================================
// CALCULAR MÉTRICAS DE TIEMPO
// =====================================================================
function calcularTiempoEfectivo(incidencia) {
    if (!incidencia.fecha_creacion) return { total: 0, pausado: 0, efectivo: 0 };
    
    const inicio = new Date(incidencia.fecha_creacion);
    const fin = incidencia.fecha_resolucion 
        ? new Date(incidencia.fecha_resolucion) 
        : new Date();
    
    const totalMinutos = Math.floor((fin - inicio) / 60000);
    const pausadoMinutos = incidencia.tiempo_pausado_minutos || 0;
    const efectivoMinutos = totalMinutos - pausadoMinutos;
    
    return {
        total: totalMinutos,
        pausado: pausadoMinutos,
        efectivo: efectivoMinutos,
        totalFormateado: formatearTiempo(totalMinutos),
        pausadoFormateado: formatearTiempo(pausadoMinutos),
        efectivoFormateado: formatearTiempo(efectivoMinutos)
    };
}

// =====================================================================
// INICIALIZACIÓN
// =====================================================================
document.addEventListener('DOMContentLoaded', () => {
    // Cargar motivos de pausa al iniciar
    setTimeout(() => {
        cargarMotivosPausa();
    }, 1000);
});

console.log('✅ Sistema de pausas cargado correctamente');
