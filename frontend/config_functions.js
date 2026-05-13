// =============================================================================
// CONFIG_FUNCTIONS.JS - Funciones de Configuración del Sistema
// =============================================================================

// Toggle secciones
function toggleSeccion(id) {
    const s = document.getElementById(id);
    const c = document.getElementById(id.replace('-section', '-chevron'));
    if (s.style.display === 'none') {
        s.style.display = 'block';
        if (c) c.style.transform = 'rotate(180deg)';
    } else {
        s.style.display = 'none';
        if (c) c.style.transform = 'rotate(0deg)';
    }
}

// =============================================================================
// FUNCIONES DE CONFIGURACIÓN MASIVA (RFID y ZEBRA)
// =============================================================================

// Función para actualizar rango de zebra según selección
function actualizarRangoZebra() {
    const dept = document.getElementById('config-zebra-dept').value;
    const desdeInput = document.getElementById('config-zebra-desde');
    const hastaInput = document.getElementById('config-zebra-hasta');
    const hintElement = document.getElementById('zebra-range-hint');
    if (!desdeInput || !hastaInput) return;

    if (dept === 'custom') {
        desdeInput.value = '';
        hastaInput.value = '';
        hastaInput.disabled = true;
        hastaInput.style.opacity = '0.5';
        if (hintElement) hintElement.textContent = '💡 Introduce un solo número de puesto';
    } else {
        hastaInput.disabled = false;
        hastaInput.style.opacity = '1';

        const rangos = {
            'todos': { d: '1', h: '60', t: '✨ Todas las impresoras', c: '#9f7aea' },
            'packing': { d: '4', h: '60', t: '📦 Packing: 4 al 60', c: '#4299e1' },
            'return': { d: '1', h: '20', t: '↩️ Return: 1 al 20', c: '#48bb78' },
            'vas': { d: '1', h: '10', t: '🏷️ VAS: 1 al 10', c: '#ed8936' }
        };

        const r = rangos[dept] || rangos['todos'];
        desdeInput.value = r.d;
        hastaInput.value = r.h;
        if (hintElement) {
            hintElement.textContent = r.t;
            hintElement.style.color = r.c;
        }
    }
}

// Reiniciar RFIDs masivamente con filtro
async function ejecutarReinicioMasivoRFID() {
    const dept = document.getElementById('config-rfid-dept').value;
    const desde = document.getElementById('config-rfid-desde').value;
    const hasta = document.getElementById('config-rfid-hasta').value;
    const filter = document.getElementById('config-rfid-filter').value;

    if (!desde || !hasta) {
        alert('⚠️ Especifica el rango de puestos');
        return;
    }

    const filterText = filter === 'odd' ? ' (solo impares)' : filter === 'even' ? ' (solo pares)' : '';
    if (!confirm(`¿Reiniciar RFIDs de ${dept.toUpperCase()} (Puestos ${desde}-${hasta}${filterText})?`)) return;

    try {
        const r = await fetch(`${API_URL}/api/config/rfid/reboot-masivo`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                department: dept,
                desde: parseInt(desde),
                hasta: parseInt(hasta),
                filter: filter
            })
        });
        const d = await r.json();
        if (d.success) {
            alert(`✅ Reinicio completado: ${d.exitosos}/${d.total} exitosos`);
        } else {
            alert(`❌ Error: ${d.error}`);
        }
    } catch (e) {
        alert('❌ Error de conexión');
    }
}

// Aplicar configuración Zebra masiva
async function aplicarConfiguracionZebra() {
    const dept = document.getElementById('config-zebra-dept').value;
    const desde = document.getElementById('config-zebra-desde').value;
    const hasta = document.getElementById('config-zebra-hasta').value;
    const darkness = document.getElementById('config-zebra-darkness').value;
    const left = document.getElementById('config-zebra-left').value;
    const top = document.getElementById('config-zebra-top').value;
    const locked = document.getElementById('config-zebra-lock').checked;
    const filtro = document.getElementById('config-zebra-filtro')?.value || 'todos';
    const ipDirecta = document.getElementById('config-zebra-ip-directa')?.value?.trim();

    // Si hay IP directa, configurar esa IP específica
    if (ipDirecta) {
        if (!confirm(`¿Aplicar configuración a la IP: ${ipDirecta}?`)) return;

        try {
            const r = await fetch(`${API_URL}/api/zebra/config-ip`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    ip: ipDirecta,
                    darkness: darkness ? parseInt(darkness) : null,
                    left_position: left ? parseInt(left) : null,
                    top_position: top ? parseInt(top) : null
                })
            });
            const d = await r.json();
            if (d.success) {
                alert(`✅ Configuración aplicada a ${ipDirecta}`);
            } else {
                alert(`❌ Error: ${d.error}`);
            }
        } catch (e) {
            alert('❌ Error de conexión');
        }
        return;
    }

    if (dept === 'custom' && !desde) {
        alert('⚠️ Especifica un puesto');
        return;
    }
    if (dept !== 'custom' && (!desde || !hasta)) {
        alert('⚠️ Especifica el rango');
        return;
    }

    const finalHasta = dept === 'custom' ? desde : hasta;
    const filtroText = filtro === 'pares' ? ' (solo pares)' : filtro === 'impares' ? ' (solo impares)' : '';
    if (!confirm(`¿Aplicar configuración a Zebras ${dept.toUpperCase()} (${desde}-${finalHasta}${filtroText})?`)) return;

    try {
        const r = await fetch(`${API_URL}/api/config/zebra/aplicar-masivo`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                departamento: dept === 'custom' ? 'packing' : dept,
                desde: parseInt(desde),
                hasta: parseInt(finalHasta),
                darkness: darkness ? parseInt(darkness) : null,
                left_position: left ? parseInt(left) : null,
                top_position: top ? parseInt(top) : null,
                locked: locked,
                filtro: filtro
            })
        });
        const d = await r.json();
        if (d.success) {
            alert(`✅ Aplicado: ${d.exitosos}/${d.total} exitosos`);
        } else {
            alert(`❌ Error: ${d.error}`);
        }
    } catch (e) {
        alert('❌ Error de conexión');
    }
}

// Restaurar configuración predeterminada
async function restaurarConfiguracionImplicita() {
    const dept = document.getElementById('config-zebra-dept').value;
    const desde = document.getElementById('config-zebra-desde').value;
    const hasta = document.getElementById('config-zebra-hasta').value;

    if (!desde || (dept !== 'custom' && !hasta)) {
        alert('⚠️ Especifica el rango');
        return;
    }

    const finalHasta = dept === 'custom' ? desde : hasta;
    if (!confirm(`¿Restaurar valores predeterminados de Zebras ${dept.toUpperCase()} (${desde}-${finalHasta})?`)) return;

    try {
        const r = await fetch(`${API_URL}/api/config/zebra/restaurar-defaults`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                departamento: dept === 'custom' ? 'packing' : dept,
                desde: parseInt(desde),
                hasta: parseInt(finalHasta)
            })
        });
        const d = await r.json();
        if (d.success) {
            alert(`✅ Restaurado: ${d.exitosos}/${d.total} exitosos`);
        } else {
            alert(`❌ Error: ${d.error}`);
        }
    } catch (e) {
        alert('❌ Error de conexión');
    }
}

// Función para establecer presets de RFID
function setRfidPreset(preset) {
    const deptSelect = document.getElementById('config-rfid-dept');
    const desdeInput = document.getElementById('config-rfid-desde');
    const hastaInput = document.getElementById('config-rfid-hasta');
    const filterSelect = document.getElementById('config-rfid-filter');
    if (!deptSelect || !desdeInput || !hastaInput) return;

    switch (preset) {
        case 'packing-all':
            deptSelect.value = 'packing';
            desdeInput.value = '4';
            hastaInput.value = '60';
            break;
        case 'linea1':
            deptSelect.value = 'packing';
            desdeInput.value = '4';
            hastaInput.value = '20';
            break;
        case 'linea2':
            deptSelect.value = 'packing';
            desdeInput.value = '21';
            hastaInput.value = '40';
            break;
        case 'linea3':
            deptSelect.value = 'packing';
            desdeInput.value = '41';
            hastaInput.value = '60';
            break;
    }
}

// Guardar configuración de una impresora individual desde el modal de mesa
async function guardarConfiguracionZebra(e) {
    if (e && e.preventDefault) e.preventDefault();

    const ip = document.getElementById('zebra-ip-display').textContent.trim();
    const darkness = document.getElementById('zebra-darkness').value;
    const left = document.getElementById('zebra-left').value;
    const top = document.getElementById('zebra-top').value;
    const speed = document.getElementById('zebra-speed').value;

    const config = {
        ip: ip,
        darkness: parseInt(darkness),
        left: parseInt(left),
        top: parseInt(top),
        speed: parseInt(speed)
    };

    try {
        const response = await fetch(`${API_URL}/api/zebra/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(config)
        });

        const data = await response.json();

        if (data.success) {
            alert('✅ Configuración enviada a la impresora con éxito');
            cerrarModalZebra();
        } else {
            alert(`❌ Error: ${data.error}`);
        }
    } catch (error) {
        console.error('Error configurando zebra:', error);
        alert('❌ Error de conexión al configurar impresora');
    }
}

function toggleInput(id, enabled) {
    document.getElementById(id).disabled = !enabled;
}

// =============================================================================
// AUTO-RELLENAR RANGOS SEGÚN DEPARTAMENTO
// =============================================================================
const RANGOS_DEPARTAMENTO = {
    'packing': { desde: 4, hasta: 60 },
    'return': { desde: 1, hasta: 20 },
    'vas': { desde: 1, hasta: 10 },
    'todos': { desde: 1, hasta: 60 }
};

function autoRellenarRango(seccion) {
    const deptSelect = document.getElementById(`${seccion}-dept`);
    const desdeInput = document.getElementById(`${seccion}-desde`);
    const hastaInput = document.getElementById(`${seccion}-hasta`);

    if (!deptSelect || !desdeInput || !hastaInput) return;

    const dept = deptSelect.value;
    const rango = RANGOS_DEPARTAMENTO[dept] || RANGOS_DEPARTAMENTO['packing'];

    desdeInput.value = rango.desde;
    hastaInput.value = rango.hasta;
}

// Auto-rellenar al cargar la página
document.addEventListener('DOMContentLoaded', function () {
    setTimeout(() => {
        autoRellenarRango('test');
        autoRellenarRango('chequeo');
        autoRellenarRango('sleep');
    }, 100);
});

// =============================================================================
// IMPRESORAS BLOQUEADAS
// =============================================================================
async function cargarImpresorasBloqueadas() {
    try {
        const r = await fetch(`${API_URL}/api/zebra/bloqueadas`, { credentials: 'include' });
        const d = await r.json();
        if (d.success) {
            const list = document.getElementById('bloqueadas-list');
            const count = document.getElementById('bloqueadas-count');

            if (count) count.textContent = d.impresoras.length;

            if (d.impresoras.length === 0) {
                list.innerHTML = '<p style="color:#48bb78; text-align:center; padding:20px;"><i class="fas fa-check-circle"></i> No hay impresoras bloqueadas</p>';
                return;
            }

            let h = '<table style="width:100%;border-collapse:collapse;font-size:13px">';
            h += '<thead><tr style="background:#f7fafc"><th style="padding:8px;text-align:left">Puesto</th><th style="padding:8px">IP</th><th style="padding:8px">Contraste</th><th style="padding:8px">Acción</th></tr></thead><tbody>';

            d.impresoras.forEach(i => {
                h += `<tr style="border-bottom:1px solid #e2e8f0">
                    <td style="padding:8px;font-weight:600">${i.departamento.toUpperCase()}-${i.puesto}</td>
                    <td style="padding:8px;font-family:monospace;font-size:11px">${i.ip}</td>
                    <td style="padding:8px;text-align:center">${i.darkness_custom || 'Default'}</td>
                    <td style="padding:8px;text-align:center">
                        <button class="modal-button secondary" onclick="desbloquearImpresora('${i.departamento}',${i.puesto})" style="padding:4px 10px;font-size:11px">
                            <i class="fas fa-unlock"></i> Desbloquear
                        </button>
                    </td>
                </tr>`;
            });
            h += '</tbody></table>';
            list.innerHTML = h;
        } else {
            alert(`❌ ${d.error}`);
        }
    } catch (e) {
        console.error('Error cargando bloqueadas:', e);
        document.getElementById('bloqueadas-list').innerHTML = '<p style="color:#e53e3e;text-align:center">Error cargando datos</p>';
    }
}

async function desbloquearImpresora(dept, puesto) {
    if (!confirm(`¿Desbloquear impresora ${dept.toUpperCase()}-${puesto}?\n\nEsto permitirá que el sistema modifique su configuración automáticamente.`)) return;

    try {
        const r = await fetch(`${API_URL}/api/zebra/desbloquear`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ impresoras: [{ departamento: dept, puesto }] })
        });
        const d = await r.json();
        if (d.success) {
            alert('✅ Impresora desbloqueada correctamente');
            cargarImpresorasBloqueadas();
        } else {
            alert(`❌ ${d.error}`);
        }
    } catch (e) {
        alert('❌ Error de conexión');
    }
}

// =============================================================================
// ESTADO IMPRESORAS BD
// =============================================================================
async function cargarTodasConfiguraciones() {
    const dept = document.getElementById('filter-dept-configs')?.value || '';
    try {
        let url = `${API_URL}/api/zebra/config/lista`;
        if (dept) url += `?departamento=${dept}`;

        const r = await fetch(url, { credentials: 'include' });
        const d = await r.json();

        if (d.success) {
            const list = document.getElementById('configs-list');
            if (d.impresoras.length === 0) {
                list.innerHTML = '<p style="color:#718096;text-align:center">No hay configuraciones</p>';
                return;
            }

            let h = '<table style="width:100%;border-collapse:collapse;font-size:11px">';
            h += '<thead><tr style="background:#edf2f7;position:sticky;top:0;z-index:1"><th style="padding:6px;background:#edf2f7">Puesto</th><th style="padding:6px;background:#edf2f7">Contraste</th><th style="padding:6px;background:#edf2f7">Pos.Izq</th><th style="padding:6px;background:#edf2f7">🔒</th></tr></thead><tbody>';

            d.impresoras.forEach(i => {
                const bloq = i.custom_locked ? '🔒' : '';
                const darkness = i.darkness_custom !== null ? i.darkness_custom : (i.darkness_default || 5);
                const leftPos = i.left_position !== null ? i.left_position : 0;
                const rowBg = i.custom_locked ? '#fffbeb' : '';
                h += `<tr style="border-bottom:1px solid #edf2f7;background:${rowBg}">
                    <td style="padding:6px;font-weight:600">${i.departamento.toUpperCase()}-${i.puesto}</td>
                    <td style="padding:6px;text-align:center">${darkness}</td>
                    <td style="padding:6px;text-align:center">${leftPos}</td>
                    <td style="padding:6px;text-align:center">${bloq}</td>
                </tr>`;
            });
            h += '</tbody></table>';
            list.innerHTML = h;
        } else {
            alert(`❌ ${d.error}`);
        }
    } catch (e) {
        console.error('Error cargando configuraciones:', e);
    }
}
// =============================================================================
// TEST DE IMPRESORAS
// =============================================================================
async function iniciarTestImpresoras() {
    // Verificar si hay puesto específico o IP directa
    const puestoEspecifico = document.getElementById('test-puesto-especifico')?.value?.trim();
    const ipDirecta = document.getElementById('test-ip-directa')?.value?.trim();

    // Si hay IP directa, enviar test a esa IP
    if (ipDirecta) {
        if (!confirm(`Se enviará test a la IP: ${ipDirecta}. ¿Continuar?`)) return;
        await enviarTestIPDirecta(ipDirecta);
        return;
    }

    // Si hay puesto específico (ej: PACK-15)
    if (puestoEspecifico) {
        const match = puestoEspecifico.toUpperCase().match(/^(PACK|PACKING|RET|RETURN|VAS)-?(\d+)$/);
        if (!match) {
            alert('⚠️ Formato inválido. Usa: PACK-15, RET-3, VAS-1');
            return;
        }
        let dept = match[1].toLowerCase();
        if (dept === 'pack') dept = 'packing';
        if (dept === 'ret') dept = 'return';
        const puesto = parseInt(match[2]);

        if (!confirm(`Se enviará test a ${dept.toUpperCase()}-${puesto}. ¿Continuar?`)) return;
        await enviarTestsImpresoras([{ departamento: dept, puesto: puesto }]);
        return;
    }

    // Modo rango normal
    const dept = document.getElementById('test-dept').value;
    const desde = parseInt(document.getElementById('test-desde').value);
    const hasta = parseInt(document.getElementById('test-hasta').value);
    const filtro = document.getElementById('test-filtro').value;

    if (!desde || !hasta) {
        alert('⚠️ Especifica rango de puestos');
        return;
    }

    const depts = dept === 'todos' ? ['packing', 'return', 'vas'] : [dept];
    let imps = [];

    for (const d of depts) {
        for (let p = desde; p <= hasta; p++) {
            if (filtro === 'pares' && p % 2 !== 0) continue;
            if (filtro === 'impares' && p % 2 === 0) continue;
            imps.push({ departamento: d, puesto: p });
        }
    }

    if (imps.length === 0) {
        alert('⚠️ No hay impresoras en el rango seleccionado');
        return;
    }

    if (!confirm(`Se enviará test a ${imps.length} impresoras. ¿Continuar?`)) return;

    await enviarTestsImpresoras(imps);
}

// Test a IP directa (sin estar en BD)
async function enviarTestIPDirecta(ip) {
    try {
        const r = await fetch(`${API_URL}/api/zebra/test-ip`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ ip: ip })
        });
        const d = await r.json();
        if (d.success) {
            alert(`✅ Test enviado a ${ip}`);
        } else {
            alert(`❌ Error: ${d.error}`);
        }
    } catch (e) {
        alert('❌ Error enviando test');
    }
}

// El backend determina automáticamente el tipo de etiqueta basándose en left_position:
// left_position = 0 o 20 -> etiqueta grande (4x6")
// left_position = -215 -> etiqueta pequeña (2x1")

async function enviarTestsImpresoras(imps, tipoEtiqueta = 'auto') {
    try {
        const r = await fetch(`${API_URL}/api/zebra/test`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ impresoras: imps, tipo_etiqueta: tipoEtiqueta })
        });
        const d = await r.json();
        if (d.success) {
            window.testResults = d.resultados;
            mostrarChecklistTest(d.resultados);
        } else {
            alert(`❌ ${d.error}`);
        }
    } catch (e) {
        alert('❌ Error enviando tests');
    }
}

function mostrarChecklistTest(results) {
    let h = '<div style="margin-bottom:15px"><p><strong>Tests enviados.</strong> Verifica cada etiqueta e indica si salió correcta:</p></div>';
    h += '<div style="max-height:400px;overflow-y:auto"><table style="width:100%;border-collapse:collapse">';
    h += '<thead><tr style="background:#f7fafc;position:sticky;top:0"><th style="padding:10px">Puesto</th><th style="padding:10px">✅ OK</th><th style="padding:10px">❌ MAL</th><th style="padding:10px">Observaciones</th></tr></thead><tbody>';

    results.forEach((r, i) => {
        const p = r.puesto || `${r.departamento?.toUpperCase()}-${r.puesto_num}`;
        h += `<tr style="border-bottom:1px solid #e2e8f0">
            <td style="padding:10px;font-weight:600">${p}</td>
            <td style="padding:10px;text-align:center"><input type="radio" name="test_${i}" value="ok" checked style="width:20px;height:20px"></td>
            <td style="padding:10px;text-align:center"><input type="radio" name="test_${i}" value="mal" style="width:20px;height:20px"></td>
            <td style="padding:10px"><input type="text" id="obs_${i}" placeholder="Solo si hay problema" style="width:100%;padding:5px;border:1px solid #cbd5e0;border-radius:4px"></td>
        </tr>`;
    });
    h += '</tbody></table></div>';
    h += '<div style="margin-top:20px;display:flex;gap:10px"><button class="modal-button primary" onclick="procesarResultadosTest(' + results.length + ')"><i class="fas fa-check"></i> Finalizar Revisión</button><button class="modal-button secondary" onclick="cerrarModalGenerico()">Cancelar</button></div>';

    mostrarModalGenerico('Checklist de Tests de Impresión', h);
}

async function procesarResultadosTest(total) {
    const resultados = [];
    for (let i = 0; i < total; i++) {
        const estado = document.querySelector(`input[name="test_${i}"]:checked`).value;
        const obs = document.getElementById(`obs_${i}`).value;
        resultados.push({
            departamento: window.testResults[i].departamento,
            puesto: window.testResults[i].puesto_num || window.testResults[i].puesto,
            estado: estado,
            observaciones: obs
        });
    }

    try {
        const r = await fetch(`${API_URL}/api/zebra/test-ui`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ resultados })
        });
        const d = await r.json();
        if (d.success) {
            const malos = resultados.filter(r => r.estado === 'mal').length;
            alert(`✅ Revisión completada\n\n✅ OK: ${total - malos}\n❌ Con problemas: ${malos}\n📋 Incidencias creadas: ${d.incidencias_creadas}`);
            cerrarModalGenerico();
        } else {
            alert(`❌ ${d.error}`);
        }
    } catch (e) {
        alert('❌ Error procesando resultados');
    }
}

// =============================================================================
// CHEQUEO GENERAL COMPLETO
// =============================================================================
const COMPONENTES_CHEQUEO = [
    { id: 'pantalla', nombre: 'Pantalla', icono: 'fa-desktop' },
    { id: 'teclado', nombre: 'Teclado', icono: 'fa-keyboard' },
    { id: 'raton', nombre: 'Ratón', icono: 'fa-mouse-pointer' },
    { id: 'soporte_pistola', nombre: 'Soporte Pistola', icono: 'fa-hand-holding' },
    { id: 'pistola', nombre: 'Pistola', icono: 'fa-barcode' },
    { id: 'impresora', nombre: 'Impresora', icono: 'fa-print' },
    { id: 'soporte_impresora', nombre: 'Soporte Impresora', icono: 'fa-cube' },
    { id: 'cognex', nombre: 'Cognex', icono: 'fa-camera' },
    { id: 'rfid', nombre: 'RFID', icono: 'fa-wifi' }
];

function iniciarChequeoGeneralCompleto() {
    const dept = document.getElementById('chequeo-dept').value;
    const desde = parseInt(document.getElementById('chequeo-desde').value);
    const hasta = parseInt(document.getElementById('chequeo-hasta').value);
    const filtro = document.getElementById('chequeo-filtro').value;

    let puestos = [];
    for (let p = desde; p <= hasta; p++) {
        if (filtro === 'pares' && p % 2 !== 0) continue;
        if (filtro === 'impares' && p % 2 === 0) continue;
        puestos.push({ departamento: dept, puesto: p });
    }

    if (puestos.length === 0) {
        alert('⚠️ No hay puestos en el rango seleccionado');
        return;
    }

    // Inicializar datos de chequeo
    window.chequeoData = {
        puestos: puestos,
        resultados: [],
        indiceActual: 0,
        dept: dept
    };

    mostrarPuestoChequeo();
}

function mostrarPuestoChequeo() {
    const data = window.chequeoData;

    if (data.indiceActual >= data.puestos.length) {
        finalizarChequeoGeneral();
        return;
    }

    const puesto = data.puestos[data.indiceActual];
    const puestoId = `${puesto.departamento.toUpperCase()}-${puesto.puesto}`;
    const progreso = `${data.indiceActual + 1} / ${data.puestos.length}`;

    let h = `
        <div style="margin-bottom:20px;display:flex;justify-content:space-between;align-items:center">
            <h3 style="font-size:24px;font-weight:700;color:#2d3748">${puestoId}</h3>
            <span style="background:#4299e1;color:white;padding:5px 15px;border-radius:20px;font-size:14px">${progreso}</span>
        </div>
        <p style="color:#718096;margin-bottom:20px">Marca el estado de cada componente (por defecto aparecen como BIEN):</p>
        
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:15px;margin-bottom:20px">
    `;

    COMPONENTES_CHEQUEO.forEach(comp => {
        h += `
            <div style="background:#f7fafc;border-radius:12px;padding:15px;text-align:center" id="comp-card-${comp.id}">
                <i class="fas ${comp.icono}" style="font-size:24px;color:#4299e1;margin-bottom:10px;display:block"></i>
                <p style="font-weight:600;margin-bottom:10px">${comp.nombre}</p>
                <div style="display:flex;gap:5px;justify-content:center">
                    <button type="button" class="btn-comp-estado bien activo" id="btn-${comp.id}-bien" onclick="toggleEstadoComponente('${comp.id}','bien')" style="padding:8px 15px;border-radius:6px;border:none;cursor:pointer;background:#48bb78;color:white;font-weight:600">
                        ✅ BIEN
                    </button>
                    <button type="button" class="btn-comp-estado mal" id="btn-${comp.id}-mal" onclick="toggleEstadoComponente('${comp.id}','mal')" style="padding:8px 15px;border-radius:6px;border:2px solid #e53e3e;cursor:pointer;background:white;color:#e53e3e;font-weight:600">
                        ❌ MAL
                    </button>
                </div>
            </div>
        `;
    });

    h += `
        </div>
        
        <div style="margin-bottom:20px">
            <label style="font-weight:600;display:block;margin-bottom:8px">Observaciones (opcional):</label>
            <textarea id="chequeo-observaciones" style="width:100%;padding:10px;border:1px solid #cbd5e0;border-radius:8px;min-height:60px" placeholder="Añade notas sobre el estado del puesto..."></textarea>
        </div>
        
        <div style="display:flex;gap:10px;justify-content:space-between;flex-wrap:wrap">
            <button class="modal-button secondary" onclick="saltarPuesto()" ${data.indiceActual === 0 ? 'disabled' : ''}>
                <i class="fas fa-arrow-left"></i> Anterior
            </button>
            <button class="modal-button primary" onclick="guardarPuestoChequeo()" style="flex:2;background:linear-gradient(135deg,#48bb78,#38a169)">
                <i class="fas fa-check"></i> Guardar y Siguiente
            </button>
            <button class="modal-button" onclick="pausarChequeo()" style="background:linear-gradient(135deg,#f6ad55,#ed8936);color:white">
                <i class="fas fa-pause"></i> Pausar
            </button>
            <button class="modal-button secondary" onclick="cancelarChequeo()">
                <i class="fas fa-times"></i> Cancelar
            </button>
        </div>
    `;

    mostrarModalGenerico('Chequeo General de Puestos', h, '700px');

    // Inicializar estados como 'bien' para todos los componentes
    window.estadosComponentes = {};
    COMPONENTES_CHEQUEO.forEach(comp => {
        window.estadosComponentes[comp.id] = 'bien';
    });
}

function toggleEstadoComponente(componenteId, estado) {
    window.estadosComponentes[componenteId] = estado;

    const btnBien = document.getElementById(`btn-${componenteId}-bien`);
    const btnMal = document.getElementById(`btn-${componenteId}-mal`);
    const card = document.getElementById(`comp-card-${componenteId}`);

    if (estado === 'bien') {
        btnBien.style.background = '#48bb78';
        btnBien.style.color = 'white';
        btnBien.style.border = 'none';
        btnMal.style.background = 'white';
        btnMal.style.color = '#e53e3e';
        btnMal.style.border = '2px solid #e53e3e';
        card.style.background = '#f7fafc';
    } else {
        btnMal.style.background = '#e53e3e';
        btnMal.style.color = 'white';
        btnMal.style.border = 'none';
        btnBien.style.background = 'white';
        btnBien.style.color = '#48bb78';
        btnBien.style.border = '2px solid #48bb78';
        card.style.background = '#fff5f5';
    }
}

function saltarPuesto() {
    if (window.chequeoData.indiceActual > 0) {
        window.chequeoData.indiceActual--;
        window.chequeoData.resultados.pop();
        mostrarPuestoChequeo();
    }
}

function pausarChequeo() {
    const data = window.chequeoData;

    if (!data) {
        alert('⚠️ No hay chequeo activo para pausar');
        return;
    }

    // Guardar estado en localStorage
    const estadoPausado = {
        puestos: data.puestos,
        resultados: data.resultados,
        indiceActual: data.indiceActual,
        dept: data.dept,
        fechaPausa: new Date().toISOString()
    };

    localStorage.setItem('chequeoPausado', JSON.stringify(estadoPausado));

    // Mostrar botón de reanudar
    const btnReanudar = document.getElementById('btn-reanudar-chequeo');
    if (btnReanudar) {
        btnReanudar.style.display = 'block';
    }

    cerrarModalGenerico();

    const pendientes = data.puestos.length - data.indiceActual;
    alert(`⏸️ Chequeo pausado\n\n✅ Revisados: ${data.resultados.length}\n📋 Pendientes: ${pendientes}\n\nPuedes reanudar en cualquier momento desde el botón "Reanudar".`);
}

function reanudarChequeo() {
    const estadoGuardado = localStorage.getItem('chequeoPausado');

    if (!estadoGuardado) {
        alert('⚠️ No hay ningún chequeo pausado');
        document.getElementById('btn-reanudar-chequeo').style.display = 'none';
        return;
    }

    const estado = JSON.parse(estadoGuardado);
    const fechaPausa = new Date(estado.fechaPausa);
    const ahora = new Date();
    const horasPasadas = (ahora - fechaPausa) / (1000 * 60 * 60);

    // Mostrar info del chequeo pausado
    const pendientes = estado.puestos.length - estado.indiceActual;
    const mensaje = `📋 Chequeo pausado encontrado\n\n` +
        `Departamento: ${estado.dept.toUpperCase()}\n` +
        `Revisados: ${estado.resultados.length}\n` +
        `Pendientes: ${pendientes}\n` +
        `Pausado hace: ${horasPasadas.toFixed(1)} horas\n\n` +
        `¿Deseas continuar desde donde lo dejaste?`;

    if (!confirm(mensaje)) {
        if (confirm('¿Deseas descartar el chequeo pausado y empezar uno nuevo?')) {
            localStorage.removeItem('chequeoPausado');
            document.getElementById('btn-reanudar-chequeo').style.display = 'none';
        }
        return;
    }

    // Restaurar estado
    window.chequeoData = {
        puestos: estado.puestos,
        resultados: estado.resultados,
        indiceActual: estado.indiceActual,
        dept: estado.dept
    };

    mostrarPuestoChequeo();
}

function cancelarChequeo() {
    if (!confirm('¿Estás seguro de cancelar el chequeo?\n\nSe perderá todo el progreso actual.')) {
        return;
    }

    // Limpiar datos
    window.chequeoData = null;
    window.estadosComponentes = null;
    localStorage.removeItem('chequeoPausado');

    // Ocultar botón reanudar
    const btnReanudar = document.getElementById('btn-reanudar-chequeo');
    if (btnReanudar) {
        btnReanudar.style.display = 'none';
    }

    cerrarModalGenerico();
    alert('❌ Chequeo cancelado');
}

// Verificar si hay chequeo pausado al cargar la página
document.addEventListener('DOMContentLoaded', function () {
    setTimeout(() => {
        const estadoGuardado = localStorage.getItem('chequeoPausado');
        if (estadoGuardado) {
            const btnReanudar = document.getElementById('btn-reanudar-chequeo');
            if (btnReanudar) {
                btnReanudar.style.display = 'block';
            }
        }
    }, 500);
});

async function guardarPuestoChequeo() {
    const data = window.chequeoData;
    const puesto = data.puestos[data.indiceActual];
    const observaciones = document.getElementById('chequeo-observaciones').value;

    // Guardar resultado
    const resultado = {
        departamento: puesto.departamento,
        puesto: puesto.puesto,
        componentes: { ...window.estadosComponentes },
        observaciones: observaciones
    };

    data.resultados.push(resultado);
    data.indiceActual++;

    mostrarPuestoChequeo();
}

async function finalizarChequeoGeneral() {
    const data = window.chequeoData;

    // Contar problemas
    let totalProblemas = 0;
    let puestosConProblemas = 0;

    data.resultados.forEach(r => {
        const problemas = Object.values(r.componentes).filter(v => v === 'mal').length;
        if (problemas > 0) {
            puestosConProblemas++;
            totalProblemas += problemas;
        }
    });

    // Mostrar resumen
    let h = `
        <div style="text-align:center;margin-bottom:20px">
            <i class="fas fa-clipboard-check" style="font-size:48px;color:#38b2ac"></i>
            <h3 style="margin-top:15px;font-size:24px">Chequeo Completado</h3>
        </div>
        
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:15px;margin-bottom:20px;text-align:center">
            <div style="background:#f0fff4;padding:20px;border-radius:12px">
                <p style="font-size:32px;font-weight:700;color:#48bb78">${data.resultados.length}</p>
                <p style="color:#718096">Puestos revisados</p>
            </div>
            <div style="background:#fff5f5;padding:20px;border-radius:12px">
                <p style="font-size:32px;font-weight:700;color:#e53e3e">${puestosConProblemas}</p>
                <p style="color:#718096">Puestos con problemas</p>
            </div>
            <div style="background:#faf5ff;padding:20px;border-radius:12px">
                <p style="font-size:32px;font-weight:700;color:#805ad5">${totalProblemas}</p>
                <p style="color:#718096">Total componentes mal</p>
            </div>
        </div>
    `;

    if (puestosConProblemas > 0) {
        h += '<h4 style="margin-bottom:10px">Problemas detectados:</h4>';
        h += '<div style="max-height:200px;overflow-y:auto;background:#f7fafc;border-radius:8px;padding:10px">';

        data.resultados.forEach(r => {
            const componentesMal = Object.entries(r.componentes)
                .filter(([k, v]) => v === 'mal')
                .map(([k, v]) => COMPONENTES_CHEQUEO.find(c => c.id === k)?.nombre || k);

            if (componentesMal.length > 0) {
                h += `<p style="margin-bottom:8px"><strong>${r.departamento.toUpperCase()}-${r.puesto}:</strong> ${componentesMal.join(', ')}</p>`;
            }
        });
        h += '</div>';
    }

    h += `
        <div style="margin-top:20px;display:flex;gap:10px">
            <button class="modal-button primary" onclick="enviarChequeoAlServidor()" style="flex:1;background:#38b2ac">
                <i class="fas fa-save"></i> Guardar en Base de Datos
            </button>
            <button class="modal-button secondary" onclick="cerrarModalGenerico()">
                Cerrar sin guardar
            </button>
        </div>
    `;

    mostrarModalGenerico('Resumen del Chequeo', h, '600px');

    // Limpiar chequeo pausado ya que se ha completado
    localStorage.removeItem('chequeoPausado');
    const btnReanudar = document.getElementById('btn-reanudar-chequeo');
    if (btnReanudar) btnReanudar.style.display = 'none';
}

async function enviarChequeoAlServidor() {
    const data = window.chequeoData;

    try {
        const r = await fetch(`${API_URL}/api/chequeo/guardar-lote`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ resultados: data.resultados })
        });
        const d = await r.json();

        if (d.success) {
            // Limpiar chequeo pausado del localStorage
            localStorage.removeItem('chequeoPausado');
            const btnReanudar = document.getElementById('btn-reanudar-chequeo');
            if (btnReanudar) btnReanudar.style.display = 'none';

            alert(`✅ Chequeo guardado correctamente\n\nPuestos procesados: ${d.procesados}\nIncidencias creadas: ${d.incidencias_creadas}`);
            cerrarModalGenerico();
        } else {
            alert(`❌ ${d.error}`);
        }
    } catch (e) {
        alert('❌ Error guardando chequeo');
    }
}

// =============================================================================
// CONFIGURACIÓN DE SUSPENSIÓN CON TIMEOUT
// =============================================================================
async function aplicarTimeoutSuspension() {
    const dept = document.getElementById('sleep-dept').value;
    const timeoutHoras = parseInt(document.getElementById('sleep-timeout').value);
    const desde = parseInt(document.getElementById('sleep-desde').value) || null;
    const hasta = parseInt(document.getElementById('sleep-hasta').value) || null;

    // Calcular minutos (las impresoras Zebra usan minutos para el timeout)
    const timeoutMinutos = timeoutHoras * 60;

    const textoTimeout = timeoutHoras === 0 ? 'DESACTIVADA (siempre activa)' : `${timeoutHoras} hora(s)`;
    const textoRango = desde && hasta ? ` para puestos ${desde}-${hasta}` : '';

    if (!confirm(`¿Aplicar timeout de suspensión: ${textoTimeout}\nDepartamento: ${dept.toUpperCase()}${textoRango}?`)) return;

    try {
        const r = await fetch(`${API_URL}/api/zebra/config/sleep-timeout`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                departamento: dept,
                timeout_minutos: timeoutMinutos,
                desde: desde,
                hasta: hasta
            })
        });
        const d = await r.json();

        if (d.success) {
            alert(`✅ Configuración aplicada\n\nImpresoras actualizadas: ${d.actualizadas}\nFallidas: ${d.fallidas}`);
        } else {
            alert(`❌ ${d.error}`);
        }
    } catch (e) {
        alert('❌ Error aplicando configuración');
    }
}

// =============================================================================
// VERIFICAR CONFIGURACIONES ZEBRA (CON MODAL Y CORRECCIÓN AUTOMÁTICA)
// =============================================================================
async function verificarConfiguracionesZebra() {
    // Obtener departamento seleccionado
    const deptFilter = document.getElementById('filter-dept-configs')?.value || '';

    // Mostrar modal de carga
    mostrarModalGenerico('Verificando Impresoras...', `
        <div style="text-align:center;padding:40px">
            <i class="fas fa-spinner fa-spin" style="font-size:48px;color:#4299e1"></i>
            <p style="margin-top:20px;color:#718096">Conectando con las impresoras...</p>
            <p style="font-size:12px;color:#a0aec0">Esto puede tardar unos segundos</p>
        </div>
    `, '500px');

    try {
        // Llamar al endpoint de verificación con corrección automática
        let url = `${API_URL}/api/zebra/verificar-y-corregir`;
        if (deptFilter) url += `?departamento=${deptFilter}`;

        const r = await fetch(url, { credentials: 'include' });
        const d = await r.json();

        if (d.success) {
            // Construir contenido del modal
            let h = `
                <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:15px;margin-bottom:20px;text-align:center">
                    <div style="background:#f0fff4;padding:15px;border-radius:12px">
                        <p style="font-size:28px;font-weight:700;color:#48bb78">${d.total}</p>
                        <p style="color:#718096;font-size:12px">Total revisadas</p>
                    </div>
                    <div style="background:#f0fff4;padding:15px;border-radius:12px">
                        <p style="font-size:28px;font-weight:700;color:#38a169">${d.correctas}</p>
                        <p style="color:#718096;font-size:12px">Correctas</p>
                    </div>
                    <div style="background:#fefcbf;padding:15px;border-radius:12px">
                        <p style="font-size:28px;font-weight:700;color:#d69e2e">${d.corregidas || 0}</p>
                        <p style="color:#718096;font-size:12px">Corregidas</p>
                    </div>
                    <div style="background:#e9d8fd;padding:15px;border-radius:12px">
                        <p style="font-size:28px;font-weight:700;color:#805ad5">${d.bloqueadas}</p>
                        <p style="color:#718096;font-size:12px">Bloqueadas</p>
                    </div>
                </div>
            `;

            if (d.corregidas && d.corregidas > 0) {
                h += `
                    <div style="background:#fffff0;border:1px solid #d69e2e;border-radius:8px;padding:15px;margin-bottom:20px">
                        <p style="color:#744210;font-weight:600"><i class="fas fa-wrench"></i> Se corrigieron ${d.corregidas} impresoras automáticamente</p>
                        <p style="color:#744210;font-size:13px">El contraste se ha ajustado a 5 en todas las impresoras no bloqueadas.</p>
                    </div>
                `;
            }

            if (d.issues && d.issues.length > 0) {
                h += `
                    <h4 style="margin-bottom:10px;color:#2d3748"><i class="fas fa-exclamation-triangle" style="color:#ed8936"></i> Problemas detectados (${d.issues.length})</h4>
                    <div style="max-height:250px;overflow-y:auto;background:#f7fafc;border-radius:8px">
                        <table style="width:100%;border-collapse:collapse;font-size:13px">
                            <thead>
                                <tr style="background:#edf2f7;position:sticky;top:0">
                                    <th style="padding:10px;text-align:left;background:#edf2f7">Puesto</th>
                                    <th style="padding:10px;text-align:left;background:#edf2f7">Estado</th>
                                    <th style="padding:10px;text-align:left;background:#edf2f7">Problema</th>
                                </tr>
                            </thead>
                            <tbody>
                `;

                d.issues.forEach(issue => {
                    const estadoIcon = issue.corregido ? '✅' : (issue.bloqueada ? '🔒' : '⚠️');
                    const estadoText = issue.corregido ? 'Corregido' : (issue.bloqueada ? 'Bloqueada' : 'Pendiente');
                    const rowBg = issue.corregido ? '#f0fff4' : (issue.bloqueada ? '#fffbeb' : '#fff5f5');

                    h += `
                        <tr style="border-bottom:1px solid #e2e8f0;background:${rowBg}">
                            <td style="padding:10px;font-weight:600">${issue.puesto}</td>
                            <td style="padding:10px">${estadoIcon} ${estadoText}</td>
                            <td style="padding:10px">${issue.problemas}</td>
                        </tr>
                    `;
                });

                h += '</tbody></table></div>';
            } else if (d.con_issues === 0) {
                h += `
                    <div style="text-align:center;padding:20px;background:#f0fff4;border-radius:8px">
                        <i class="fas fa-check-circle" style="font-size:36px;color:#48bb78"></i>
                        <p style="margin-top:10px;color:#2f855a;font-weight:600">¡Todas las impresoras están correctamente configuradas!</p>
                    </div>
                `;
            }

            h += `
                <div style="margin-top:20px;text-align:right">
                    <button class="modal-button primary" onclick="cerrarModalGenerico();cargarTodasConfiguraciones()" style="background:#4299e1">
                        <i class="fas fa-check"></i> Aceptar
                    </button>
                </div>
            `;

            mostrarModalGenerico('Resultado de Verificación', h, '700px');
        } else {
            mostrarModalGenerico('Error', `
                <div style="text-align:center;padding:30px">
                    <i class="fas fa-times-circle" style="font-size:48px;color:#e53e3e"></i>
                    <p style="margin-top:15px;color:#c53030">${d.error}</p>
                    <button class="modal-button secondary" onclick="cerrarModalGenerico()" style="margin-top:20px">Cerrar</button>
                </div>
            `, '400px');
        }
    } catch (e) {
        console.error('Error verificando:', e);
        mostrarModalGenerico('Error de Conexión', `
            <div style="text-align:center;padding:30px">
                <i class="fas fa-wifi" style="font-size:48px;color:#e53e3e"></i>
                <p style="margin-top:15px;color:#c53030">No se pudo conectar con el servidor</p>
                <button class="modal-button secondary" onclick="cerrarModalGenerico()" style="margin-top:20px">Cerrar</button>
            </div>
        `, '400px');
    }
}

// =============================================================================
// MODAL GENÉRICO
// =============================================================================
function mostrarModalGenerico(titulo, contenido, maxWidth = '800px') {
    // Crear modal si no existe
    let modal = document.getElementById('modalGenerico');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'modalGenerico';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content" style="max-width:${maxWidth}">
                <div class="modal-header">
                    <h2 class="modal-title" id="modalGenericoTitulo"></h2>
                    <span class="close-modal" onclick="cerrarModalGenerico()">&times;</span>
                </div>
                <div id="modalGenericoContenido"></div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    modal.querySelector('.modal-content').style.maxWidth = maxWidth;
    document.getElementById('modalGenericoTitulo').textContent = titulo;
    document.getElementById('modalGenericoContenido').innerHTML = contenido;
    modal.style.display = 'block';
}

function cerrarModalGenerico() {
    const modal = document.getElementById('modalGenerico');
    if (modal) modal.style.display = 'none';
}

// =============================================================================
// CARGAR DATOS AL ENTRAR EN CONFIGURACIONES
// =============================================================================
document.addEventListener('DOMContentLoaded', function () {
    // Auto-cargar bloqueadas cuando se muestre la pestaña de configuraciones
    const tabConfig = document.getElementById('tab-configuraciones');
    if (tabConfig) {
        tabConfig.addEventListener('click', function () {
            setTimeout(() => {
                cargarImpresorasBloqueadas();
                cargarTodasConfiguraciones();
            }, 100);
        });
    }
});

// =============================================================================
// MODAL AJUSTAR IMPRESORAS (PARA SUPERVISOR/JEFE_EQUIPO)
// =============================================================================

function abrirModalAjustarImpresoras() {
    const modal = document.getElementById('modalAjustarImpresoras');
    if (modal) {
        modal.style.display = 'block';

        // Resetear a modo rango por defecto
        const radioRango = document.querySelector('input[name="ajustar-modo"][value="rango"]');
        if (radioRango) radioRango.checked = true;
        toggleModoAjustar();

        autoRellenarRangoAjustar();
        actualizarPreviewAjustar();

        // Seleccionar tipo por defecto según departamento
        const dept = document.getElementById('ajustar-dept').value;
        seleccionarTipoEtiqueta(dept === 'packing' ? 'grande' : 'pequena');
    }
}

function cerrarModalAjustarImpresoras() {
    const modal = document.getElementById('modalAjustarImpresoras');
    if (modal) modal.style.display = 'none';
}

function autoRellenarRangoAjustar() {
    const dept = document.getElementById('ajustar-dept').value;
    const desdeInput = document.getElementById('ajustar-desde');
    const hastaInput = document.getElementById('ajustar-hasta');

    const rangos = {
        'packing': { desde: 4, hasta: 60 },
        'return': { desde: 1, hasta: 20 },
        'vas': { desde: 1, hasta: 10 }
    };

    const rango = rangos[dept] || rangos['packing'];
    desdeInput.value = rango.desde;
    hastaInput.value = rango.hasta;

    // Auto-seleccionar tipo de etiqueta según departamento
    seleccionarTipoEtiqueta(dept === 'packing' ? 'grande' : 'pequena');

    actualizarPreviewAjustar();
}

function toggleModoAjustar() {
    const modo = document.querySelector('input[name="ajustar-modo"]:checked').value;
    const divRango = document.getElementById('ajustar-modo-rango');
    const divUnico = document.getElementById('ajustar-modo-especifico');

    if (modo === 'rango') {
        divRango.style.display = 'block';
        divUnico.style.display = 'none';
    } else {
        divRango.style.display = 'none';
        divUnico.style.display = 'block';
    }
    actualizarPreviewAjustar();
}

function actualizarPreviewAjustar() {
    const modo = document.querySelector('input[name="ajustar-modo"]:checked').value;
    const preview = document.getElementById('ajustar-preview');
    let cantidad = 0;

    if (modo === 'rango') {
        const desde = parseInt(document.getElementById('ajustar-desde').value) || 1;
        const hasta = parseInt(document.getElementById('ajustar-hasta').value) || 1;
        const filtro = document.getElementById('ajustar-filtro').value;
        for (let i = desde; i <= hasta; i++) {
            if (filtro === 'todos') cantidad++;
            else if (filtro === 'pares' && i % 2 === 0) cantidad++;
            else if (filtro === 'impares' && i % 2 !== 0) cantidad++;
        }
    } else {
        const puestoU = document.getElementById('ajustar-puesto-unico').value;
        cantidad = puestoU ? 1 : 0;
    }
    preview.innerHTML = `<i class="fas fa-print"></i> ${cantidad} impresora${cantidad !== 1 ? 's' : ''} seleccionada${cantidad !== 1 ? 's' : ''}`;
}

// Añadir listeners para actualizar preview
document.addEventListener('DOMContentLoaded', function () {
    setTimeout(() => {
        const desdeInput = document.getElementById('ajustar-desde');
        const hastaInput = document.getElementById('ajustar-hasta');
        const filtroInput = document.getElementById('ajustar-filtro');
        const unicoInput = document.getElementById('ajustar-puesto-unico');
        if (desdeInput) desdeInput.addEventListener('input', actualizarPreviewAjustar);
        if (hastaInput) hastaInput.addEventListener('input', actualizarPreviewAjustar);
        if (filtroInput) filtroInput.addEventListener('change', actualizarPreviewAjustar);
        if (unicoInput) unicoInput.addEventListener('input', actualizarPreviewAjustar);
    }, 500);
});

function seleccionarTipoEtiqueta(tipo) {
    const btnGrande = document.getElementById('btn-etiqueta-grande');
    const btnPequena = document.getElementById('btn-etiqueta-pequena');
    const inputTipo = document.getElementById('ajustar-tipo-etiqueta');

    if (tipo === 'grande') {
        btnGrande.style.background = '#f0fff4';
        btnGrande.style.borderColor = '#48bb78';
        btnGrande.style.color = '#2f855a';
        btnPequena.style.background = '#f7fafc';
        btnPequena.style.borderColor = '#cbd5e0';
        btnPequena.style.color = '#4a5568';
    } else {
        btnPequena.style.background = '#fff3f0';
        btnPequena.style.borderColor = '#ff6b47';
        btnPequena.style.color = '#ff6b47';
        btnGrande.style.background = '#f7fafc';
        btnGrande.style.borderColor = '#cbd5e0';
        btnGrande.style.color = '#4a5568';
    }

    inputTipo.value = tipo;
}

async function aplicarAjusteImpresoras() {
    const dept = document.getElementById('ajustar-dept').value;
    const desde = parseInt(document.getElementById('ajustar-desde').value);
    const hasta = parseInt(document.getElementById('ajustar-hasta').value);
    const filtro = document.getElementById('ajustar-filtro').value;
    const tipo = document.getElementById('ajustar-tipo-etiqueta').value;

    const modo = document.querySelector('input[name="ajustar-modo"]:checked').value;
    const leftPosition = tipo === 'grande' ? 0 : -215;
    const tipoTexto = tipo === 'grande' ? 'PACKING' : 'RETURN o VAS';

    let cantidad = 0;
    let confirmMsg = "";

    if (modo === 'rango') {
        for (let i = desde; i <= hasta; i++) {
            if (filtro === 'todos') cantidad++;
            else if (filtro === 'pares' && i % 2 === 0) cantidad++;
            else if (filtro === 'impares' && i % 2 !== 0) cantidad++;
        }
        confirmMsg = `¿Aplicar configuración para etiquetas ${tipoTexto} a ${cantidad} impresoras?\n\nDepartamento: ${dept.toUpperCase()}\nPuestos: ${desde} - ${hasta} (${filtro})\nPosición izquierda: ${leftPosition}`;
    } else {
        const puestoU = document.getElementById('ajustar-puesto-unico').value;
        if (!puestoU) {
            alert('⚠️ Indica el número de puesto');
            return;
        }
        cantidad = 1;
        confirmMsg = `¿Aplicar configuración para etiquetas ${tipoTexto} al puesto ${puestoU}?\n\nDepartamento: ${dept.toUpperCase()}\nPosición izquierda: ${leftPosition}`;
    }

    if (!confirm(confirmMsg)) {
        return;
    }

    // Cerrar modal y mostrar cargando
    cerrarModalAjustarImpresoras();

    // Mostrar modal de carga
    mostrarModalGenerico('Aplicando cambios...', `
        <div style="text-align:center;padding:40px">
            <i class="fas fa-spinner fa-spin" style="font-size:48px;color:#ff6b47"></i>
            <p style="margin-top:20px;color:#718096">Configurando impresoras...</p>
            <p style="font-size:12px;color:#a0aec0">Esto puede tardar unos segundos</p>
        </div>
    `, '400px');

    try {
        const impresoras = [];

        if (modo === 'rango') {
            for (let p = desde; p <= hasta; p++) {
                if (filtro === 'todos' || (filtro === 'pares' && p % 2 === 0) || (filtro === 'impares' && p % 2 !== 0)) {
                    impresoras.push({ departamento: dept, puesto: p });
                }
            }
        } else {
            const puestoU = parseInt(document.getElementById('ajustar-puesto-unico').value);
            impresoras.push({ departamento: dept, puesto: puestoU });
        }

        const r = await fetch(`${API_URL}/api/zebra/config/left-position`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                impresoras: impresoras,
                left_position: leftPosition
            })
        });
        const d = await r.json();

        if (d.success) {
            // Mostrar resultado
            let h = `
                <div style="text-align:center;padding:20px">
                    <i class="fas fa-check-circle" style="font-size:64px;color:#48bb78"></i>
                    <h3 style="margin-top:15px;color:#2d3748">¡Cambios aplicados!</h3>
                </div>
                
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin:20px 0;text-align:center">
                    <div style="background:#f0fff4;padding:15px;border-radius:12px">
                        <p style="font-size:32px;font-weight:700;color:#48bb78">${d.actualizadas || cantidad}</p>
                        <p style="color:#718096">Impresoras actualizadas</p>
                    </div>
                    <div style="background:${d.fallidas > 0 ? '#fff5f5' : '#f7fafc'};padding:15px;border-radius:12px">
                        <p style="font-size:32px;font-weight:700;color:${d.fallidas > 0 ? '#e53e3e' : '#718096'}">${d.fallidas || 0}</p>
                        <p style="color:#718096">Fallidas</p>
                    </div>
                </div>
                
                <div style="background:#f7fafc;padding:15px;border-radius:8px;margin-bottom:20px">
                    <p style="color:#4a5568"><strong>Configuración aplicada:</strong></p>
                    <p style="color:#718096">Tipo: ${tipoTexto}</p>
                    <p style="color:#718096">Posición izquierda: ${leftPosition}</p>
                </div>
                
                <button class="modal-button primary" onclick="cerrarModalGenerico()" style="width:100%;background:linear-gradient(135deg,#ff6b47,#ff4f2a)">
                    <i class="fas fa-check"></i> Aceptar
                </button>
            `;

            mostrarModalGenerico('Resultado', h, '450px');
        } else {
            mostrarModalGenerico('Error', `
                <div style="text-align:center;padding:30px">
                    <i class="fas fa-times-circle" style="font-size:48px;color:#e53e3e"></i>
                    <p style="margin-top:15px;color:#c53030">${d.error}</p>
                    <button class="modal-button secondary" onclick="cerrarModalGenerico()" style="margin-top:20px">Cerrar</button>
                </div>
            `, '400px');
        }
    } catch (e) {
        console.error('Error aplicando ajuste:', e);
        mostrarModalGenerico('Error de Conexión', `
            <div style="text-align:center;padding:30px">
                <i class="fas fa-wifi" style="font-size:48px;color:#e53e3e"></i>
                <p style="margin-top:15px;color:#c53030">No se pudo conectar con el servidor</p>
                <button class="modal-button secondary" onclick="cerrarModalGenerico()" style="margin-top:20px">Cerrar</button>
            </div>
        `, '400px');
    }
}
// =============================================================================
// CONFIGURACIÓN DE TIMEOUT DE SUSPENSIÓN (SLEEP TIMEOUT)
// =============================================================================
async function aplicarTimeoutSuspension() {
    const dept = document.getElementById('sleep-dept').value;
    const timeout = document.getElementById('sleep-timeout').value;
    const desde = document.getElementById('sleep-desde').value;
    const hasta = document.getElementById('sleep-hasta').value;

    const timeoutText = timeout === '0' ? 'DESACTIVADA' : `${timeout} horas`;

    if (!confirm(`¿Aplicar timeout de suspensión de ${timeoutText} a las impresoras de ${dept.toUpperCase()}?`)) {
        return;
    }

    try {
        const response = await fetch(`${API_URL}/api/zebra/config/sleep-timeout`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                departamento: dept,
                timeout_minutos: parseInt(timeout) * 60, // El backend espera minutos
                desde: desde ? parseInt(desde) : null,
                hasta: hasta ? parseInt(hasta) : null
            })
        });

        const data = await response.json();

        if (data.success) {
            alert(`✅ Configuración de suspensión aplicada:\n\n` +
                `Actualizadas: ${data.actualizadas}\n` +
                `Fallidas: ${data.fallidas}\n` +
                `Timeout: ${timeoutText}`);
        } else {
            alert(`❌ Error: ${data.error}`);
        }
    } catch (error) {
        console.error('Error aplicando timeout:', error);
        alert('❌ Error de conexión al servidor');
    }
}
async function refrescarBaseDeDatos() {
    try {
        const btn = event?.target?.closest('button');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Sincronizando impresoras...';
        }

        const response = await fetch(`${API_URL}/api/admin/reload-config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ sync_printers: true })
        });
        const data = await response.json();

        if (data.success) {
            console.log('✅ Configuración recargada en el backend', data);
            // Ahora recargar la lista en el frontend
            await cargarTodasConfiguraciones();

            // Mostrar resultado de sincronización de impresoras
            const sync = data.sync_printers || {};
            if (sync.total > 0) {
                alert(`✅ Sincronización completada\n\n` +
                    `📊 Impresoras sincronizadas: ${sync.ok}/${sync.total}\n` +
                    `❌ Fallidas: ${sync.failed}\n\n` +
                    `Se han leído los parámetros reales de cada impresora.`);
            } else {
                alert('✅ Base de Datos y configuraciones refrescadas con éxito');
            }
        } else {
            alert(`❌ Error recargando: ${data.error}`);
        }
    } catch (e) {
        console.error('Error refrescando BD:', e);
        alert('❌ Error de conexión');
    } finally {
        const btn = document.querySelector('button[onclick="refrescarBaseDeDatos()"]');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-sync"></i> Refrescar BD';
        }
    }
}

// =============================================================================
// PROGRAMACIÓN DE REINICIO AUTOMÁTICO DE RFID
// =============================================================================

// Cargar configuración actual de programación RFID
async function cargarProgramacionRfid() {
    try {
        const r = await fetch(`${API_URL}/api/rfid/schedule`, {
            credentials: 'include'
        });
        const data = await r.json();

        if (data.success && data.schedule) {
            const schedule = data.schedule;

            // Marcar el checkbox de activado
            document.getElementById('rfid-schedule-enabled').checked = schedule.enabled;

            // Marcar días
            for (let i = 0; i <= 6; i++) {
                const checkbox = document.getElementById(`rfid-day-${i}`);
                if (checkbox) {
                    checkbox.checked = schedule.days.includes(i);
                }
            }

            // Establecer hora
            if (schedule.time) {
                document.getElementById('rfid-schedule-time').value = schedule.time;
            }

            actualizarTextoSchedule(schedule);
        } else {
            document.getElementById('rfid-schedule-text').innerHTML = '<i class="fas fa-times-circle" style="color:#e53e3e;"></i> No hay programación configurada';
        }
    } catch (e) {
        console.error('Error cargando programación RFID:', e);
        document.getElementById('rfid-schedule-text').innerHTML = '<i class="fas fa-exclamation-triangle" style="color:#ed8936;"></i> Error cargando';
    }
}

// Actualizar texto de estado de la programación
function actualizarTextoSchedule(schedule) {
    const textEl = document.getElementById('rfid-schedule-text');
    const diasNombres = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];

    if (!schedule.enabled) {
        textEl.innerHTML = '<i class="fas fa-pause-circle" style="color:#718096;"></i> Reinicio automático <b>desactivado</b>';
        return;
    }

    if (!schedule.days || schedule.days.length === 0) {
        textEl.innerHTML = '<i class="fas fa-exclamation-circle" style="color:#ed8936;"></i> Sin días configurados';
        return;
    }

    const diasTexto = schedule.days.map(d => diasNombres[d]).join(', ');
    textEl.innerHTML = `<i class="fas fa-check-circle" style="color:#38a169;"></i> Reinicio automático <b>activado</b> los <b>${diasTexto}</b> a las <b>${schedule.time}</b>`;
}

// Guardar programación
async function guardarProgramacionRfid() {
    const enabled = document.getElementById('rfid-schedule-enabled').checked;
    const time = document.getElementById('rfid-schedule-time').value;

    // Obtener días seleccionados
    const days = [];
    for (let i = 0; i <= 6; i++) {
        const checkbox = document.getElementById(`rfid-day-${i}`);
        if (checkbox && checkbox.checked) {
            days.push(i);
        }
    }

    if (enabled && days.length === 0) {
        alert('⚠️ Selecciona al menos un día de la semana');
        return;
    }

    try {
        const r = await fetch(`${API_URL}/api/rfid/schedule`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ enabled, days, time })
        });
        const data = await r.json();

        if (data.success) {
            alert('✅ Programación guardada correctamente');
            actualizarTextoSchedule({ enabled, days, time });
        } else {
            alert(`❌ Error: ${data.error}`);
        }
    } catch (e) {
        alert('❌ Error de conexión');
    }
}

// Toggle activar/desactivar
function toggleRfidSchedule() {
    const enabled = document.getElementById('rfid-schedule-enabled').checked;
    const time = document.getElementById('rfid-schedule-time').value;
    const days = [];
    for (let i = 0; i <= 6; i++) {
        const checkbox = document.getElementById(`rfid-day-${i}`);
        if (checkbox && checkbox.checked) {
            days.push(i);
        }
    }
    actualizarTextoSchedule({ enabled, days, time });
}

// Cargar programación al iniciar
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(cargarProgramacionRfid, 1000);
});
