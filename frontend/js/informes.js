/**
 * MVP Reportes de Baches - Informes por Comuna
 * Región Metropolitana de Santiago
 */

// Configuración
const API_BASE = '/api';
const CACHE_PREFIX = 'informe_';
const CACHE_COMUNAS_KEY = 'comunas_lista';
const CACHE_DURATION_MS = 60 * 60 * 1000; // 1 hora
const CACHE_COMUNAS_DURATION_MS = 24 * 60 * 60 * 1000; // 24 horas para lista de comunas

// ==================== INICIALIZACIÓN ====================

document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadComunasGrid();
});

function setupEventListeners() {
    // Botón volver en la vista de detalle de informe
    const btnVolver = document.getElementById('btnVolverLista');
    if (btnVolver) {
        btnVolver.addEventListener('click', volverAListaInformes);
    }

    // Buscador de comunas
    const searchComunas = document.getElementById('searchComunas');
    if (searchComunas) {
        searchComunas.addEventListener('input', onSearchComunasInput);
    }
}

// ==================== BUSCADOR DE COMUNAS ====================

function onSearchComunasInput(e) {
    const searchTerm = e.target.value.toLowerCase().trim();
    const cards = document.querySelectorAll('.comuna-card');

    // Normalizar texto para buscar (remover tildes)
    const normalizar = (str) => str.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    const searchNormalizado = normalizar(searchTerm);

    cards.forEach(card => {
        const nombreComuna = card.dataset.nombre;
        const nombreNormalizado = normalizar(nombreComuna);

        if (searchTerm === '' || nombreNormalizado.includes(searchNormalizado)) {
            card.style.display = '';
        } else {
            card.style.display = 'none';
        }
    });
}

// ==================== CARGA DE COMUNAS ====================

function getCachedComunas() {
    try {
        const cached = localStorage.getItem(CACHE_COMUNAS_KEY);
        if (!cached) return null;

        const { data, timestamp } = JSON.parse(cached);
        if (Date.now() - timestamp > CACHE_COMUNAS_DURATION_MS) {
            localStorage.removeItem(CACHE_COMUNAS_KEY);
            return null;
        }
        return data;
    } catch (e) {
        return null;
    }
}

function setCachedComunas(data) {
    try {
        localStorage.setItem(CACHE_COMUNAS_KEY, JSON.stringify({
            data: data,
            timestamp: Date.now()
        }));
    } catch (e) {
        console.warn('No se pudo guardar caché de comunas');
    }
}

async function loadComunasGrid() {
    const grid = document.getElementById('comunasGrid');

    // Intentar cargar desde caché primero
    const cachedComunas = getCachedComunas();
    if (cachedComunas) {
        console.log('Comunas cargadas desde caché');
        renderComunasGrid(cachedComunas, grid);
        return;
    }

    // Mostrar loading
    grid.innerHTML = '<div class="loading-grid"><div class="spinner"></div>Cargando comunas...</div>';

    try {
        // Fetch con timeout de 15 segundos
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000);

        const response = await fetch(`${API_BASE}/comunas/informes`, {
            signal: controller.signal
        });
        clearTimeout(timeoutId);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        if (!data.comunas || data.comunas.length === 0) {
            grid.innerHTML = '<div class="no-comunas">No hay comunas disponibles</div>';
            return;
        }

        // Guardar en caché
        setCachedComunas(data.comunas);

        // Renderizar
        renderComunasGrid(data.comunas, grid);

    } catch (error) {
        console.error('Error cargando comunas:', error);

        let errorMsg = 'Error al cargar comunas.';
        if (error.name === 'AbortError') {
            errorMsg = 'Conexión lenta. Intenta de nuevo.';
        }

        grid.innerHTML = `
            <div class="error-grid">
                ${errorMsg}
                <button class="btn-reintentar" onclick="loadComunasGrid()">Reintentar</button>
            </div>
        `;
    }
}

function renderComunasGrid(comunas, grid) {
    // Ya vienen ordenadas del backend
    grid.innerHTML = comunas.map(comuna => {
        // Usar campos abreviados del API optimizado
        const codigo = comuna.c || comuna.codigo_comuna;
        const nombre = comuna.n || comuna.nombre_comuna;
        const fecha = comuna.f || comuna.fecha_informe;
        const tieneInforme = !!fecha;

        const fechaFormateada = fecha
            ? new Date(fecha).toLocaleDateString('es-CL')
            : null;

        return `
            <div class="comuna-card ${tieneInforme ? 'tiene-informe' : 'sin-informe'}"
                 data-codigo="${codigo}"
                 data-nombre="${nombre}">
                <h3 class="comuna-card-nombre">${nombre}</h3>
                <div class="comuna-card-estado">
                    ${tieneInforme
                        ? `<span class="estado-con-informe">Informe: ${fechaFormateada}</span>`
                        : '<span class="estado-sin-informe">Sin informe</span>'
                    }
                </div>
            </div>
        `;
    }).join('');

    // Agregar eventos de clic
    grid.querySelectorAll('.comuna-card').forEach(card => {
        card.addEventListener('click', () => {
            showInformeDetalle(card.dataset.codigo, card.dataset.nombre);
        });
    });
}

// ==================== CACHÉ DE INFORMES ====================

function getCachedInforme(codigoComuna) {
    try {
        const cached = localStorage.getItem(CACHE_PREFIX + codigoComuna);
        if (!cached) return null;

        const { data, timestamp } = JSON.parse(cached);

        // Verificar si el caché ha expirado
        if (Date.now() - timestamp > CACHE_DURATION_MS) {
            localStorage.removeItem(CACHE_PREFIX + codigoComuna);
            return null;
        }

        return data;
    } catch (e) {
        return null;
    }
}

function setCachedInforme(codigoComuna, data) {
    try {
        const cacheEntry = {
            data: data,
            timestamp: Date.now()
        };
        localStorage.setItem(CACHE_PREFIX + codigoComuna, JSON.stringify(cacheEntry));
    } catch (e) {
        // Si localStorage está lleno, limpiar cachés antiguos
        clearOldCaches();
    }
}

function clearOldCaches() {
    try {
        const keys = Object.keys(localStorage).filter(k => k.startsWith(CACHE_PREFIX));
        keys.forEach(key => localStorage.removeItem(key));
    } catch (e) {
        console.warn('No se pudo limpiar caché:', e);
    }
}

// ==================== DETALLE DE INFORME ====================

async function showInformeDetalle(codigoComuna, nombreComuna, forceRefresh = false) {
    // Ocultar lista y mostrar detalle
    document.getElementById('informes-lista').classList.add('hidden');
    document.getElementById('informes-detalle').classList.remove('hidden');

    // Actualizar título
    document.getElementById('informeComuna').textContent = nombreComuna;

    const contenido = document.getElementById('informeContenido');
    const stats = document.getElementById('informeStats');

    // Intentar obtener del caché primero (si no es refresh forzado)
    if (!forceRefresh) {
        const cachedData = getCachedInforme(codigoComuna);
        if (cachedData) {
            console.log('Informe cargado desde caché');
            renderInforme(cachedData, nombreComuna, contenido, stats, true);
            return;
        }
    }

    // Mostrar loading
    contenido.innerHTML = '<div class="loading-informe"><div class="spinner"></div>Cargando informe...</div>';
    stats.innerHTML = '';

    try {
        // Fetch con timeout de 30 segundos para conexiones lentas
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);

        const response = await fetch(`${API_BASE}/comunas/${codigoComuna}/informe`, {
            signal: controller.signal
        });
        clearTimeout(timeoutId);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        // Guardar en caché si tiene informe
        if (data.tiene_informe) {
            setCachedInforme(codigoComuna, data);
        }

        // Renderizar el informe
        renderInforme(data, nombreComuna, contenido, stats, false, codigoComuna);

    } catch (error) {
        console.error('Error cargando informe:', error);

        let errorMsg = 'Error al cargar el informe.';
        if (error.name === 'AbortError') {
            errorMsg = 'La conexión tardó demasiado. Verifica tu conexión a internet.';
        } else if (error.message) {
            errorMsg = `Error: ${error.message}`;
        }

        contenido.innerHTML = `
            <div class="error-informe">
                <p>${errorMsg}</p>
                <button class="btn-reintentar" onclick="showInformeDetalle('${codigoComuna}', '${nombreComuna}', true)">
                    Reintentar
                </button>
            </div>
        `;
    }
}

function renderInforme(data, nombreComuna, contenido, stats, fromCache = false, codigoComuna = null) {
    // Mostrar estadísticas
    const cacheIndicator = fromCache ? '<span class="cache-badge">En caché</span>' : '';
    stats.innerHTML = `
        <span class="stat-item">
            <strong>${data.total_baches}</strong> baches reportados
        </span>
        ${cacheIndicator}
    `;

    if (!data.tiene_informe) {
        // No hay informe generado
        contenido.innerHTML = `
            <div class="sin-informe-mensaje">
                <div class="sin-informe-icono">📋</div>
                <h3>Comuna sin informe generado</h3>
                <p>Aún no se ha generado un informe de baches para ${nombreComuna}.</p>
                <p class="sin-informe-hint">Para generar un informe, ve a la página
                   <a href="/">Reportar Baches</a>, selecciona esta comuna y usa el Asistente IA.</p>
            </div>
        `;
        return;
    }

    // Mostrar el informe
    let informeHTML = `
        <div class="informe-fecha">
            Generado el ${new Date(data.generated_at).toLocaleString('es-CL')}
            ${fromCache && codigoComuna ? `<button class="btn-actualizar" onclick="showInformeDetalle('${codigoComuna}', '${nombreComuna}', true)">Actualizar</button>` : ''}
        </div>
        <div class="informe-resumen">
    `;

    // Convertir markdown a HTML
    let resumenHTML = data.resumen
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/^### (.*$)/gm, '<h4>$1</h4>')
        .replace(/^## (.*$)/gm, '<h3>$1</h3>')
        .replace(/^# (.*$)/gm, '<h2>$1</h2>')
        .replace(/^- (.*$)/gm, '<li>$1</li>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');

    resumenHTML = resumenHTML.replace(/(<li>.*<\/li>)+/g, '<ul>$&</ul>');

    informeHTML += `<p>${resumenHTML}</p></div>`;

    // Agregar top5 si existe
    if (data.top5 && data.top5.length > 0) {
        informeHTML += `
            <div class="informe-top5">
                <h4>Ubicaciones destacadas</h4>
                <ul class="top5-lista">
                    ${data.top5.map((item, idx) => `
                        <li class="top5-item">
                            <span class="top5-numero">${idx + 1}</span>
                            <div class="top5-info">
                                <strong>${item.num_reportes} reportes</strong>
                                <p>${item.descripcion || 'Sin descripción'}</p>
                            </div>
                        </li>
                    `).join('')}
                </ul>
            </div>
        `;
    }

    contenido.innerHTML = informeHTML;
}

function volverAListaInformes() {
    document.getElementById('informes-detalle').classList.add('hidden');
    document.getElementById('informes-lista').classList.remove('hidden');
}

// ==================== UTILIDADES ====================

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type}`;

    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3000);
}
