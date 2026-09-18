/**
 * MVP Reportes de Baches - Frontend
 * Región Metropolitana de Santiago
 */

// Configuración
const API_BASE = '/api';
const SANTIAGO_CENTER = [-33.4489, -70.6693];
const DEFAULT_ZOOM = 11;

// Estado de la aplicación
let map = null;
let markersLayer = null;
let comunasLayer = null;
let comunasGeoJSON = null;  // Referencia al layer GeoJSON de comunas
let selectedMarker = null;
let selectedComuna = null;
let modoIndicarBache = false; // Modo para indicar bache en el mapa

// Búsqueda de direcciones
let searchTimeout = null;
const SEARCH_DEBOUNCE_MS = 300;
const NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search';

// Geolocalización
let lastLocationTime = null;
let watchId = null; // ID del watcher de geolocalización
let locationAttempts = 0; // Contador de intentos
const LOCATION_EXPIRY_MS = 5 * 60 * 1000; // 5 minutos en milisegundos
const MAX_ACCURACY_METERS = 50; // Precisión máxima aceptada en metros
const MAX_LOCATION_ATTEMPTS = 3; // Máximo de intentos
const LOCATION_TIMEOUT_MS = 3000; // Timeout por intento (3 segundos)

// Colores por severidad
const SEVERIDAD_COLORS = {
    alta: { border: '#d32f2f', fill: '#ffcdd2' },
    media: { border: '#f57c00', fill: '#ffe0b2' },
    baja: { border: '#388e3c', fill: '#c8e6c9' }
};

// ==================== INICIALIZACIÓN ====================

document.addEventListener('DOMContentLoaded', () => {
    initMap();
    loadComunas();
    setupEventListeners();
});

function initMap() {
    // Crear mapa centrado en Santiago
    map = L.map('map').setView(SANTIAGO_CENTER, DEFAULT_ZOOM);

    // Agregar capa base de OpenStreetMap
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 19
    }).addTo(map);

    // Crear capas para marcadores y comunas
    markersLayer = L.layerGroup().addTo(map);
    comunasLayer = L.layerGroup().addTo(map);

    // Agregar leyenda
    addLegend();

    // Evento de clic en el mapa para seleccionar ubicación
    map.on('click', onMapClick);
}

function addLegend() {
    const legend = L.control({ position: 'bottomright' });

    legend.onAdd = function() {
        const div = L.DomUtil.create('div', 'map-legend');
        div.innerHTML = `
            <h4>Severidad</h4>
            <div class="legend-item">
                <span class="legend-color" style="border-color: ${SEVERIDAD_COLORS.alta.border}; background: ${SEVERIDAD_COLORS.alta.fill}"></span>
                <span>Alta</span>
            </div>
            <div class="legend-item">
                <span class="legend-color" style="border-color: ${SEVERIDAD_COLORS.media.border}; background: ${SEVERIDAD_COLORS.media.fill}"></span>
                <span>Media</span>
            </div>
            <div class="legend-item">
                <span class="legend-color" style="border-color: ${SEVERIDAD_COLORS.baja.border}; background: ${SEVERIDAD_COLORS.baja.fill}"></span>
                <span>Baja</span>
            </div>
        `;
        return div;
    };

    legend.addTo(map);
}

function setupEventListeners() {
    // Selector de comuna personalizado
    setupCustomComunaSelect();

    // Buscador de direcciones
    const searchInput = document.getElementById('searchDireccion');
    if (searchInput) {
        searchInput.addEventListener('input', onSearchInput);
        searchInput.addEventListener('focus', onSearchFocus);
        searchInput.addEventListener('blur', onSearchBlur);
    }

    // Botón de ubicación GPS
    document.getElementById('btnUbicacion').addEventListener('click', onGetUbicacion);

    // Botón de indicar bache en mapa
    document.getElementById('btnIndicarBache').addEventListener('click', toggleModoIndicarBache);

    // Formulario de reporte
    document.getElementById('reporteForm').addEventListener('submit', onReporteSubmit);

    // Botón de resumen IA / Agente
    document.getElementById('btnResumen').addEventListener('click', onGenerarResumen);

    // Campo de prompt del agente IA - habilitar botón cuando hay texto
    const promptIA = document.getElementById('promptIA');
    if (promptIA) {
        promptIA.addEventListener('input', onPromptIAInput);
    }

    // Upload de foto
    setupFotoUpload();
}

// ==================== UPLOAD DE FOTO ====================

function setupFotoUpload() {
    const fotoInput = document.getElementById('foto');
    const btnRemove = document.getElementById('btnRemoveFoto');

    if (fotoInput) {
        fotoInput.addEventListener('change', onFotoSelected);
    }

    if (btnRemove) {
        btnRemove.addEventListener('click', removeFoto);
    }
}

function onFotoSelected(e) {
    const file = e.target.files[0];
    if (!file) return;

    // Validar tamaño (5MB)
    if (file.size > 5 * 1024 * 1024) {
        showToast('La imagen es muy grande. Máximo 5MB', 'error');
        e.target.value = '';
        return;
    }

    // Validar tipo
    const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (!validTypes.includes(file.type)) {
        showToast('Tipo de archivo no válido. Use JPG, PNG o WebP', 'error');
        e.target.value = '';
        return;
    }

    // Mostrar preview
    const reader = new FileReader();
    reader.onload = function(event) {
        const preview = document.getElementById('fotoPreview');
        const previewImg = document.getElementById('fotoPreviewImg');
        const uploadLabel = document.querySelector('.foto-upload-label');

        previewImg.src = event.target.result;
        preview.classList.remove('hidden');
        uploadLabel.classList.add('has-foto');

        // Cambiar texto
        uploadLabel.querySelector('.foto-text').textContent = 'Cambiar imagen';
    };
    reader.readAsDataURL(file);
}

function removeFoto() {
    const fotoInput = document.getElementById('foto');
    const preview = document.getElementById('fotoPreview');
    const uploadLabel = document.querySelector('.foto-upload-label');

    fotoInput.value = '';
    preview.classList.add('hidden');
    uploadLabel.classList.remove('has-foto');
    uploadLabel.querySelector('.foto-text').textContent = 'Seleccionar imagen';
}

function onPromptIAInput(e) {
    const prompt = e.target.value.trim();
    const btn = document.getElementById('btnResumen');

    // Habilitar si hay prompt O si hay comuna seleccionada
    if (prompt.length >= 3 || selectedComuna) {
        btn.disabled = false;
    } else {
        btn.disabled = true;
    }
}

// ==================== BÚSQUEDA DE DIRECCIONES ====================

function onSearchInput(e) {
    const query = e.target.value.trim();

    // Limpiar timeout anterior
    if (searchTimeout) {
        clearTimeout(searchTimeout);
    }

    // Si la consulta es muy corta, ocultar resultados
    if (query.length < 3) {
        hideSearchResults();
        return;
    }

    // Mostrar loading
    showSearchLoading();

    // Debounce: esperar antes de buscar
    searchTimeout = setTimeout(() => {
        searchDireccion(query);
    }, SEARCH_DEBOUNCE_MS);
}

function onSearchFocus() {
    const query = document.getElementById('searchDireccion').value.trim();
    if (query.length >= 3) {
        document.getElementById('searchResults').classList.remove('hidden');
    }
}

function onSearchBlur() {
    // Delay para permitir clic en resultados
    setTimeout(() => {
        hideSearchResults();
    }, 200);
}

async function searchDireccion(query) {
    try {
        // Buscar en Santiago, Chile
        const params = new URLSearchParams({
            q: query + ', Santiago, Chile',
            format: 'json',
            addressdetails: 1,
            limit: 5,
            countrycodes: 'cl'
        });

        const url = `${NOMINATIM_URL}?${params.toString()}`;
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`HTTP error: ${response.status}`);
        }

        const results = await response.json();
        displaySearchResults(results);
    } catch (error) {
        console.error('Error buscando dirección:', error);
        showSearchError();
    }
}

function displaySearchResults(results) {
    const container = document.getElementById('searchResults');

    if (results.length === 0) {
        container.innerHTML = '<div class="search-no-results">No se encontraron resultados</div>';
        container.classList.remove('hidden');
        return;
    }

    container.innerHTML = results.map(result => {
        // Construir dirección más completa
        const parts = result.display_name.split(',').map(p => p.trim());
        let calle, numero, comuna;

        // Si el primer elemento es un número, el segundo es la calle
        if (/^\d+$/.test(parts[0]) && parts.length > 1) {
            numero = parts[0];
            calle = parts[1];
        } else {
            calle = parts[0];
            numero = '';
        }

        // Buscar la comuna en los datos de dirección de Nominatim
        if (result.address) {
            comuna = result.address.suburb ||
                     result.address.borough ||
                     result.address.city_district ||
                     result.address.town ||
                     result.address.city || '';
        } else {
            // Fallback: buscar en las partes del display_name
            comuna = parts.find(p =>
                !p.includes('Región') &&
                !p.includes('Chile') &&
                !p.includes('Provincia') &&
                !p.match(/^\d/)
            ) || parts[2] || '';
        }

        // Construir texto principal: "Calle Número, Comuna"
        const mainText = numero ? `${calle} ${numero}, ${comuna}` : `${calle}, ${comuna}`;
        const secondaryText = parts.slice(3, 5).join(', ');

        return `
            <div class="search-result-item"
                 data-lat="${escapeHtml(result.lat)}"
                 data-lon="${escapeHtml(result.lon)}"
                 data-name="${escapeHtml(mainText)}">
                <div class="result-main">${escapeHtml(mainText)}</div>
                <div class="result-secondary">${escapeHtml(secondaryText)}</div>
            </div>
        `;
    }).join('');

    // Agregar eventos de clic
    container.querySelectorAll('.search-result-item').forEach(item => {
        item.addEventListener('mousedown', onSearchResultClick);
    });

    container.classList.remove('hidden');
}

function onSearchResultClick(e) {
    const item = e.currentTarget;
    const lat = parseFloat(item.dataset.lat);
    const lon = parseFloat(item.dataset.lon);
    const name = item.dataset.name;

    // Actualizar input de búsqueda
    document.getElementById('searchDireccion').value = name;

    // Ocultar resultados
    hideSearchResults();

    // Mover mapa a la ubicación
    const latlng = L.latLng(lat, lon);
    map.setView(latlng, 17);

    // Colocar marcador
    if (selectedMarker) {
        map.removeLayer(selectedMarker);
    }

    selectedMarker = L.marker(latlng, {
        icon: L.divIcon({
            className: 'selected-location-marker',
            html: '<div style="background: #1a237e; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>',
            iconSize: [20, 20],
            iconAnchor: [10, 10]
        })
    }).addTo(map);

    selectedMarker.bindPopup(`Dirección: ${escapeHtml(name)}`).openPopup();

    // Actualizar formulario
    document.getElementById('lat').value = lat.toFixed(6);
    document.getElementById('lon').value = lon.toFixed(6);
    document.getElementById('direccion').value = name; // Guardar dirección
    document.getElementById('btnReportar').disabled = false;

    // Limpiar timestamp de ubicación GPS
    lastLocationTime = null;

    // Detectar comuna
    const comunaDetectada = detectarComunaEnPunto(latlng);
    if (comunaDetectada) {
        setComunaSelectValue(comunaDetectada.codigo);
        showUbicacionStatus(`Dirección en ${comunaDetectada.nombre}`, 'success');
    } else {
        showUbicacionStatus('Dirección seleccionada', 'success');
    }
}

function showSearchLoading() {
    const container = document.getElementById('searchResults');
    container.innerHTML = '<div class="search-loading">Buscando...</div>';
    container.classList.remove('hidden');
}

function showSearchError() {
    const container = document.getElementById('searchResults');
    container.innerHTML = '<div class="search-no-results">Error al buscar. Intenta de nuevo.</div>';
    container.classList.remove('hidden');
}

function hideSearchResults() {
    document.getElementById('searchResults').classList.add('hidden');
}

// ==================== GEOCODIFICACIÓN INVERSA ====================

const NOMINATIM_REVERSE_URL = 'https://nominatim.openstreetmap.org/reverse';

async function obtenerDireccionDeCoordenadas(latlng, comunaDetectada) {
    try {
        const params = new URLSearchParams({
            lat: latlng.lat,
            lon: latlng.lng,
            format: 'json',
            addressdetails: 1
        });

        const response = await fetch(`${NOMINATIM_REVERSE_URL}?${params.toString()}`);

        if (!response.ok) {
            throw new Error('Error en geocodificación inversa');
        }

        const data = await response.json();

        // Construir dirección legible
        let direccion = construirDireccionDesdeReversa(data, comunaDetectada);

        // Actualizar campo oculto y campo de búsqueda
        document.getElementById('direccion').value = direccion;
        document.getElementById('searchDireccion').value = direccion;

        // Actualizar popup del marcador
        if (selectedMarker) {
            selectedMarker.setPopupContent(`Dirección: ${escapeHtml(direccion)}`);
        }

        showUbicacionStatus(`Bache marcado: ${direccion}`, 'success');

    } catch (error) {
        console.error('Error obteniendo dirección:', error);

        // Si falla, usar comuna como fallback
        const fallbackDireccion = comunaDetectada ?
            `Ubicación en ${escapeHtml(comunaDetectada.nombre)}` :
            'Ubicación seleccionada';

        if (selectedMarker) {
            selectedMarker.setPopupContent(fallbackDireccion);
        }

        showUbicacionStatus(comunaDetectada ?
            `Bache marcado en ${comunaDetectada.nombre}` :
            'Bache marcado. Selecciona la comuna.', 'success');
    }
}

function construirDireccionDesdeReversa(data, comunaDetectada) {
    const address = data.address || {};

    // Obtener calle
    const calle = address.road || address.pedestrian || address.footway ||
                  address.street || address.path || '';

    // Obtener número
    const numero = address.house_number || '';

    // Obtener comuna (de Nominatim o de nuestra detección)
    let comuna = address.suburb || address.borough || address.city_district ||
                 address.town || address.city || '';

    // Si tenemos comunaDetectada de nuestro sistema, preferirla
    if (comunaDetectada && comunaDetectada.nombre) {
        comuna = comunaDetectada.nombre;
    }

    // Construir dirección
    let partes = [];

    if (calle) {
        if (numero) {
            partes.push(`${calle} ${numero}`);
        } else {
            partes.push(calle);
        }
    }

    if (comuna) {
        partes.push(comuna);
    }

    // Si no tenemos nada, usar las coordenadas
    if (partes.length === 0) {
        return `Lat: ${data.lat}, Lon: ${data.lon}`;
    }

    return partes.join(', ');
}

async function obtenerDireccionDeGPS(latlng, accuracy, comunaDetectada) {
    try {
        const params = new URLSearchParams({
            lat: latlng.lat,
            lon: latlng.lng,
            format: 'json',
            addressdetails: 1
        });

        const response = await fetch(`${NOMINATIM_REVERSE_URL}?${params.toString()}`);

        if (!response.ok) {
            throw new Error('Error en geocodificación inversa');
        }

        const data = await response.json();

        // Construir dirección legible
        let direccion = construirDireccionDesdeReversa(data, comunaDetectada);

        // Actualizar campo oculto y campo de búsqueda
        document.getElementById('direccion').value = direccion;
        document.getElementById('searchDireccion').value = direccion;

        // Actualizar popup del marcador
        if (selectedMarker) {
            selectedMarker.setPopupContent(`Dirección: ${escapeHtml(direccion)}`);
        }

        showUbicacionStatus(
            `${direccion} (precisión: ~${Math.round(accuracy)}m). Expira en 5 min.`,
            'success'
        );

    } catch (error) {
        console.error('Error obteniendo dirección:', error);

        // Fallback: mostrar solo la comuna y precisión
        showUbicacionStatus(
            comunaDetectada ?
                `Ubicación en ${comunaDetectada.nombre} (precisión: ~${Math.round(accuracy)}m). Expira en 5 min.` :
                `Ubicación obtenida (precisión: ~${Math.round(accuracy)}m). Expira en 5 min.`,
            'success'
        );

        if (selectedMarker) {
            selectedMarker.setPopupContent(
                comunaDetectada ? `Tu ubicación en ${escapeHtml(comunaDetectada.nombre)}` : 'Tu ubicación actual'
            );
        }
    }
}

function toggleModoIndicarBache() {
    const btn = document.getElementById('btnIndicarBache');

    modoIndicarBache = !modoIndicarBache;

    if (modoIndicarBache) {
        btn.classList.add('active');
        btn.innerHTML = '<span class="ubicacion-icon">👆</span> Haz clic en el mapa...';
        showUbicacionStatus('Haz clic en el mapa donde está el bache', 'loading');

        // Cambiar cursor del mapa
        document.getElementById('map').style.cursor = 'crosshair';
    } else {
        btn.classList.remove('active');
        btn.innerHTML = '<span class="ubicacion-icon">🖱️</span> Indicar Bache en mapa';

        // Restaurar cursor
        document.getElementById('map').style.cursor = '';

        // Ocultar mensaje
        document.getElementById('ubicacionStatus').classList.add('hidden');
    }
}

// ==================== GEOLOCALIZACIÓN ====================

function isLocationExpired() {
    if (!lastLocationTime) return true;
    return (Date.now() - lastLocationTime) > LOCATION_EXPIRY_MS;
}

function onGetUbicacion() {
    const btn = document.getElementById('btnUbicacion');

    if (!btn) {
        console.error('Botón de ubicación no encontrado');
        return;
    }

    // Verificar soporte de geolocalización
    if (!navigator.geolocation) {
        showUbicacionStatus('Tu navegador no soporta geolocalización', 'error');
        return;
    }

    // Cancelar cualquier watch anterior
    stopWatchingLocation();

    // Reiniciar contador de intentos
    locationAttempts = 0;

    // Iniciar búsqueda de ubicación
    startWatchingLocation();
}

function startWatchingLocation() {
    const btn = document.getElementById('btnUbicacion');
    locationAttempts++;

    // Mostrar estado de carga
    btn.disabled = true;
    btn.classList.add('loading');

    if (locationAttempts === 1) {
        btn.innerHTML = '<span class="ubicacion-icon">⏳</span> Obteniendo ubicación...';
        showUbicacionStatus('Buscando señal GPS... Esto puede tomar unos segundos.', 'loading');
    } else {
        btn.innerHTML = `<span class="ubicacion-icon">⏳</span> Reintentando (${locationAttempts}/${MAX_LOCATION_ATTEMPTS})...`;
        showUbicacionStatus(`Reintentando obtener ubicación precisa... (intento ${locationAttempts}/${MAX_LOCATION_ATTEMPTS})`, 'loading');
    }

    // Opciones de geolocalización - alta precisión
    const options = {
        enableHighAccuracy: true,
        timeout: LOCATION_TIMEOUT_MS,
        maximumAge: 0
    };

    // Usar watchPosition para obtener actualizaciones continuas
    watchId = navigator.geolocation.watchPosition(
        (position) => onWatchPositionSuccess(position),
        (error) => onWatchPositionError(error),
        options
    );

    // Timeout de seguridad: si no obtenemos buena precisión en el tiempo límite
    setTimeout(() => {
        if (watchId !== null) {
            // Aún estamos buscando, verificar si debemos reintentar
            stopWatchingLocation();

            if (locationAttempts < MAX_LOCATION_ATTEMPTS) {
                // Reintentar
                startWatchingLocation();
            } else {
                // Máximo de intentos alcanzado
                onLocationFinalFailure();
            }
        }
    }, LOCATION_TIMEOUT_MS);
}

function stopWatchingLocation() {
    if (watchId !== null) {
        navigator.geolocation.clearWatch(watchId);
        watchId = null;
    }
}

function onWatchPositionSuccess(position) {
    const { accuracy } = position.coords;

    // Si la precisión es aceptable, usar esta ubicación
    if (accuracy <= MAX_ACCURACY_METERS) {
        stopWatchingLocation();
        onUbicacionSuccess(position);
    } else {
        // Precisión aún no es suficiente, mostrar progreso
        showUbicacionStatus(
            `Mejorando precisión... actual: ~${Math.round(accuracy)}m (necesario: ≤${MAX_ACCURACY_METERS}m)`,
            'loading'
        );
        // El watchPosition seguirá llamando esta función con nuevas posiciones
    }
}

function onWatchPositionError(error) {
    stopWatchingLocation();

    if (locationAttempts < MAX_LOCATION_ATTEMPTS) {
        // Reintentar
        setTimeout(() => startWatchingLocation(), 1000);
    } else {
        onUbicacionError(error);
    }
}

function onLocationFinalFailure() {
    const btn = document.getElementById('btnUbicacion');

    btn.disabled = false;
    btn.classList.remove('loading');
    btn.innerHTML = '<span class="ubicacion-icon">📍</span> Usar mi ubicación';

    // Mostrar mensaje con botón de reintentar
    showUbicacionStatusWithRetry(
        `No se pudo obtener ubicación precisa después de ${MAX_LOCATION_ATTEMPTS} intentos. ` +
        'Tu dispositivo no tiene GPS o está desactivado.'
    );
}

function showUbicacionStatusWithRetry(mensaje) {
    const status = document.getElementById('ubicacionStatus');
    if (!status) return;

    status.innerHTML = `
        <div>${mensaje}</div>
        <button type="button" id="btnReintentarUbicacion" class="btn-reintentar">
            🔄 Solicitar permiso nuevamente
        </button>
        <div class="help-text-small">O selecciona manualmente en el mapa</div>
    `;
    status.className = 'ubicacion-status error';
    status.classList.remove('hidden');

    // Agregar evento al botón de reintentar
    document.getElementById('btnReintentarUbicacion').addEventListener('click', solicitarPermisoNuevamente);
}

function solicitarPermisoNuevamente() {
    // Ocultar mensaje actual
    const status = document.getElementById('ubicacionStatus');
    status.classList.add('hidden');

    // Reiniciar contador y solicitar ubicación nuevamente
    locationAttempts = 0;
    startWatchingLocation();
}

function onUbicacionSuccess(position) {
    const { latitude, longitude, accuracy } = position.coords;
    const btn = document.getElementById('btnUbicacion');

    // Restaurar botón
    btn.disabled = false;
    btn.classList.remove('loading');
    btn.innerHTML = '<span class="ubicacion-icon">📍</span> Usar mi ubicación';

    // Registrar timestamp de ubicación
    lastLocationTime = Date.now();

    // Actualizar campos del formulario
    document.getElementById('lat').value = latitude.toFixed(6);
    document.getElementById('lon').value = longitude.toFixed(6);

    // Limpiar dirección anterior temporalmente
    document.getElementById('direccion').value = '';
    document.getElementById('searchDireccion').value = '';

    // Habilitar botón de reportar
    document.getElementById('btnReportar').disabled = false;

    // Actualizar marcador en el mapa
    const latlng = L.latLng(latitude, longitude);

    if (selectedMarker) {
        map.removeLayer(selectedMarker);
    }

    selectedMarker = L.marker(latlng, {
        icon: L.divIcon({
            className: 'selected-location-marker',
            html: '<div style="background: #1a237e; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>',
            iconSize: [20, 20],
            iconAnchor: [10, 10]
        })
    }).addTo(map);

    selectedMarker.bindPopup('Obteniendo dirección...').openPopup();

    // Centrar mapa en la ubicación
    map.setView(latlng, 17);

    // Detectar y seleccionar la comuna automáticamente
    const comunaDetectada = detectarComunaEnPunto(latlng);
    if (comunaDetectada) {
        // Actualizar el selector de comuna
        setComunaSelectValue(comunaDetectada.codigo);
    }

    // Obtener dirección mediante geocodificación inversa
    obtenerDireccionDeGPS(latlng, accuracy, comunaDetectada);
}

function detectarComunaEnPunto(latlng) {
    if (!comunasGeoJSON) return null;

    let comunaEncontrada = null;

    comunasGeoJSON.eachLayer(layer => {
        // Verificar si el punto está dentro del polígono de la comuna
        if (layer.getBounds && layer.getBounds().contains(latlng)) {
            // Verificar más precisamente si está dentro del polígono
            if (isPointInLayer(latlng, layer)) {
                comunaEncontrada = {
                    codigo: layer.codigoComuna,
                    nombre: layer.feature?.properties?.nombre_comuna || 'Comuna'
                };
            }
        }
    });

    return comunaEncontrada;
}

function isPointInLayer(latlng, layer) {
    // Para polígonos simples
    if (layer.getLatLngs) {
        const latLngs = layer.getLatLngs();
        // GeoJSON puede tener múltiples anillos (MultiPolygon)
        if (Array.isArray(latLngs[0]) && Array.isArray(latLngs[0][0])) {
            // MultiPolygon - verificar cada polígono
            for (const polygon of latLngs) {
                if (isPointInPolygon(latlng, polygon[0])) {
                    return true;
                }
            }
        } else if (Array.isArray(latLngs[0])) {
            // Polygon con anillos
            return isPointInPolygon(latlng, latLngs[0]);
        } else {
            // Polygon simple
            return isPointInPolygon(latlng, latLngs);
        }
    }
    return false;
}

function isPointInPolygon(point, polygon) {
    // Algoritmo ray-casting para detectar punto en polígono
    const x = point.lat;
    const y = point.lng;
    let inside = false;

    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
        const xi = polygon[i].lat;
        const yi = polygon[i].lng;
        const xj = polygon[j].lat;
        const yj = polygon[j].lng;

        if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) {
            inside = !inside;
        }
    }

    return inside;
}

function onUbicacionError(error) {
    const btn = document.getElementById('btnUbicacion');

    // Restaurar botón
    btn.disabled = false;
    btn.classList.remove('loading');
    btn.innerHTML = '<span class="ubicacion-icon">📍</span> Usar mi ubicación';

    // Mensajes de error según el código
    let mensaje;
    switch (error.code) {
        case error.PERMISSION_DENIED:
            mensaje = 'Permiso de ubicación denegado. Puedes seleccionar manualmente en el mapa.';
            break;
        case error.POSITION_UNAVAILABLE:
            mensaje = 'Ubicación no disponible. Intenta de nuevo o selecciona en el mapa.';
            break;
        case error.TIMEOUT:
            mensaje = 'Tiempo de espera agotado. Intenta de nuevo o selecciona en el mapa.';
            break;
        default:
            mensaje = 'Error al obtener ubicación. Selecciona manualmente en el mapa.';
    }

    showUbicacionStatus(mensaje, 'error');
}

function showUbicacionStatus(mensaje, tipo) {
    const status = document.getElementById('ubicacionStatus');
    if (!status) return;

    status.textContent = mensaje;
    status.className = `ubicacion-status ${tipo}`;
    status.classList.remove('hidden');

    // Auto-ocultar después de 8 segundos si es éxito
    if (tipo === 'success') {
        setTimeout(() => {
            status.classList.add('hidden');
        }, 8000);
    }
}

// ==================== CARGA DE DATOS ====================

// ==================== SELECTOR DE COMUNA PERSONALIZADO ====================

let comunasData = []; // Almacenar datos de comunas para búsqueda

function setupCustomComunaSelect() {
    const trigger = document.getElementById('comunaSelectTrigger');
    const dropdown = document.getElementById('comunaDropdown');
    const searchInput = document.getElementById('comunaSearchInput');

    if (!trigger || !dropdown) return;

    // Abrir/cerrar dropdown al hacer clic en el trigger
    trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleComunaDropdown();
    });

    // Filtrar opciones al escribir en el buscador
    if (searchInput) {
        searchInput.addEventListener('input', onComunaSearchInput);
        searchInput.addEventListener('click', (e) => e.stopPropagation());
    }

    // Cerrar dropdown al hacer clic fuera
    document.addEventListener('click', (e) => {
        if (!e.target.closest('#comunaSelectContainer')) {
            closeComunaDropdown();
        }
    });
}

function toggleComunaDropdown() {
    const trigger = document.getElementById('comunaSelectTrigger');
    const dropdown = document.getElementById('comunaDropdown');
    const searchInput = document.getElementById('comunaSearchInput');

    if (dropdown.classList.contains('hidden')) {
        dropdown.classList.remove('hidden');
        trigger.classList.add('open');
        if (searchInput) {
            searchInput.value = '';
            searchInput.focus();
            filterComunaOptions('');
        }
    } else {
        closeComunaDropdown();
    }
}

function closeComunaDropdown() {
    const trigger = document.getElementById('comunaSelectTrigger');
    const dropdown = document.getElementById('comunaDropdown');

    dropdown.classList.add('hidden');
    trigger.classList.remove('open');
}

function onComunaSearchInput(e) {
    const searchTerm = e.target.value.toLowerCase().trim();
    filterComunaOptions(searchTerm);
}

let comunaOptionTouched = false; // Evitar doble disparo touch + click

function onComunaOptionClick(e) {
    // Si ya se procesó con touch, ignorar click
    if (comunaOptionTouched) {
        comunaOptionTouched = false;
        return;
    }

    const option = e.target.closest('.custom-select-option');
    if (option && !option.classList.contains('hidden')) {
        e.preventDefault();
        e.stopPropagation();
        handleComunaSelection(option);
    }
}

function onComunaOptionTouch(e) {
    const option = e.target.closest('.custom-select-option');
    if (option && !option.classList.contains('hidden')) {
        e.preventDefault();
        e.stopPropagation();
        comunaOptionTouched = true;
        handleComunaSelection(option);
    }
}

function handleComunaSelection(option) {
    const codigo = option.dataset.value;
    const nombre = option.dataset.nombre;
    const baches = option.dataset.baches;

    console.log('Seleccionando comuna:', codigo, nombre, baches);
    selectComuna(codigo, nombre, baches);
}

function filterComunaOptions(searchTerm) {
    const optionsContainer = document.getElementById('comunaOptions');
    const options = optionsContainer.querySelectorAll('.custom-select-option');

    // Normalizar texto (quitar tildes)
    const normalizar = (str) => str.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    const searchNormalizado = normalizar(searchTerm);

    let visibleCount = 0;

    options.forEach(option => {
        const text = option.textContent;
        const textNormalizado = normalizar(text);

        if (searchTerm === '' || textNormalizado.includes(searchNormalizado)) {
            option.classList.remove('hidden');
            visibleCount++;
        } else {
            option.classList.add('hidden');
        }
    });

    // Mostrar mensaje si no hay resultados
    let noResults = optionsContainer.querySelector('.custom-select-no-results');
    if (visibleCount === 0) {
        if (!noResults) {
            noResults = document.createElement('div');
            noResults.className = 'custom-select-no-results';
            noResults.textContent = 'No se encontraron comunas';
            optionsContainer.appendChild(noResults);
        }
        noResults.style.display = 'block';
    } else if (noResults) {
        noResults.style.display = 'none';
    }
}

function selectComuna(codigoComuna, nombreComuna, totalBaches) {
    const hiddenInput = document.getElementById('comunaSelect');
    const valueSpan = document.querySelector('.custom-select-value');

    // Actualizar valor oculto
    hiddenInput.value = codigoComuna;

    // Actualizar texto visible
    valueSpan.textContent = `${nombreComuna} (${totalBaches} baches)`;
    valueSpan.classList.remove('placeholder');

    // Marcar opción como seleccionada
    const options = document.querySelectorAll('.custom-select-option');
    options.forEach(opt => {
        opt.classList.toggle('selected', opt.dataset.value === codigoComuna);
    });

    // Cerrar dropdown
    closeComunaDropdown();

    // Disparar la lógica de cambio de comuna
    onComunaChange({ target: { value: codigoComuna } });
}

function setComunaSelectValue(codigoComuna) {
    // Buscar la comuna en los datos
    const comuna = comunasData.find(c => c.codigo_comuna === codigoComuna);
    if (comuna) {
        selectComuna(comuna.codigo_comuna, comuna.nombre_comuna, comuna.total_baches);
    }
}

function setComunaSelectValueNoZoom(codigoComuna) {
    // Buscar la comuna en los datos
    const comuna = comunasData.find(c => c.codigo_comuna === codigoComuna);
    if (comuna) {
        const hiddenInput = document.getElementById('comunaSelect');
        const valueSpan = document.querySelector('.custom-select-value');

        // Actualizar valor oculto
        hiddenInput.value = codigoComuna;

        // Actualizar texto visible
        valueSpan.textContent = `${comuna.nombre_comuna} (${comuna.total_baches} baches)`;
        valueSpan.classList.remove('placeholder');

        // Marcar opción como seleccionada
        const options = document.querySelectorAll('.custom-select-option');
        options.forEach(opt => {
            opt.classList.toggle('selected', opt.dataset.value === codigoComuna);
        });

        // Cargar baches sin zoom
        onComunaSelect(codigoComuna, false);
    }
}

async function loadComunas() {
    try {
        const response = await fetch(`${API_BASE}/comunas`);
        const data = await response.json();

        // Guardar datos para búsqueda
        comunasData = data.comunas.sort((a, b) => a.nombre_comuna.localeCompare(b.nombre_comuna));

        // Llenar el selector personalizado
        const optionsContainer = document.getElementById('comunaOptions');

        comunasData.forEach(comuna => {
            const option = document.createElement('div');
            option.className = 'custom-select-option';
            option.dataset.value = comuna.codigo_comuna;
            option.dataset.nombre = comuna.nombre_comuna;
            option.dataset.baches = comuna.total_baches;
            option.textContent = `${comuna.nombre_comuna} (${comuna.total_baches} baches)`;
            optionsContainer.appendChild(option);
        });

        // Usar event delegation para mejor soporte en móvil
        optionsContainer.addEventListener('click', onComunaOptionClick);
        optionsContainer.addEventListener('touchend', onComunaOptionTouch);

        // Intentar cargar GeoJSON de comunas para el mapa
        loadComunasGeoJSON();

    } catch (error) {
        console.error('Error cargando comunas:', error);
        showToast('Error al cargar comunas', 'error');
    }
}

async function loadComunasGeoJSON() {
    try {
        const response = await fetch(`${API_BASE}/comunas/geojson`);
        const geojson = await response.json();

        comunasGeoJSON = L.geoJSON(geojson, {
            style: {
                color: '#3949ab',
                weight: 1,
                fillColor: '#e8eaf6',
                fillOpacity: 0.1
            },
            onEachFeature: (feature, layer) => {
                const props = feature.properties;
                // Guardar referencia al código de comuna en el layer
                layer.codigoComuna = props.codigo_comuna;

                layer.bindTooltip(escapeHtml(props.nombre_comuna), {
                    permanent: false,
                    direction: 'center'
                });

                layer.on('click', (e) => {
                    // Si estamos en modo indicar bache, procesar el clic para marcar
                    if (modoIndicarBache) {
                        procesarClicMapa(e.latlng);
                        return;
                    }

                    // Solo actualizar selector y cargar baches, SIN hacer zoom
                    setComunaSelectValueNoZoom(props.codigo_comuna);
                });
            }
        }).addTo(comunasLayer);

    } catch (error) {
        console.error('Error cargando GeoJSON de comunas:', error);
    }
}

function zoomToComuna(codigoComuna) {
    if (!comunasGeoJSON) return false;

    let found = false;
    comunasGeoJSON.eachLayer(layer => {
        if (layer.codigoComuna === codigoComuna) {
            map.fitBounds(layer.getBounds(), { padding: [20, 20] });
            found = true;
        }
    });

    // Forzar redibujado del mapa (necesario en móvil)
    setTimeout(() => {
        map.invalidateSize();
    }, 100);

    return found;
}

async function loadBachesComuna(codigoComuna) {
    try {
        const response = await fetch(`${API_BASE}/comunas/${codigoComuna}/baches?page_size=200`);
        const data = await response.json();

        // Limpiar marcadores anteriores
        markersLayer.clearLayers();

        // Actualizar estadísticas
        document.getElementById('totalBaches').textContent = data.total;
        document.getElementById('comunaStats').classList.remove('hidden');

        // Agregar marcadores de baches
        data.baches.forEach(bache => {
            addBacheMarker(bache);
        });

    } catch (error) {
        console.error('Error cargando baches:', error);
        showToast('Error al cargar baches', 'error');
    }
}

// ==================== MARCADORES ====================

function addBacheMarker(bache) {
    const colors = SEVERIDAD_COLORS[bache.severidad] || SEVERIDAD_COLORS.media;

    const marker = L.circleMarker([bache.lat, bache.lon], {
        radius: 8,
        fillColor: colors.fill,
        color: colors.border,
        weight: 2,
        opacity: 1,
        fillOpacity: 0.8
    });

    const fecha = new Date(bache.created_at).toLocaleDateString('es-CL');

    marker.bindPopup(`
        <div class="popup-title">Bache #${escapeHtml(bache.id)}</div>
        <div class="popup-info">
            ${bache.direccion ? `<p><strong>Dirección:</strong> ${escapeHtml(bache.direccion)}</p>` : ''}
            <p><strong>Severidad:</strong> ${escapeHtml(bache.severidad)}</p>
            <p><strong>Fecha:</strong> ${escapeHtml(fecha)}</p>
            ${bache.comentario ? `<p><strong>Comentario:</strong> ${escapeHtml(bache.comentario)}</p>` : ''}
        </div>
    `);

    marker.addTo(markersLayer);
}

// ==================== EVENTOS ====================

function onMapClick(e) {
    // Solo permitir marcar si el modo está activo
    if (!modoIndicarBache) return;

    procesarClicMapa(e.latlng);
}

function procesarClicMapa(latlng) {
    // Actualizar campos del formulario
    document.getElementById('lat').value = latlng.lat.toFixed(6);
    document.getElementById('lon').value = latlng.lng.toFixed(6);

    // Limpiar dirección anterior temporalmente
    document.getElementById('direccion').value = '';
    document.getElementById('searchDireccion').value = '';

    // Habilitar botón de reportar
    document.getElementById('btnReportar').disabled = false;

    // Limpiar timestamp de ubicación GPS (ya que es ubicación manual)
    lastLocationTime = null;

    // Actualizar o crear marcador de selección
    if (selectedMarker) {
        map.removeLayer(selectedMarker);
    }

    selectedMarker = L.marker(latlng, {
        icon: L.divIcon({
            className: 'selected-location-marker',
            html: '<div style="background: #1a237e; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>',
            iconSize: [20, 20],
            iconAnchor: [10, 10]
        })
    }).addTo(map);

    selectedMarker.bindPopup('Obteniendo dirección...').openPopup();

    // Detectar comuna automáticamente
    const comunaDetectada = detectarComunaEnPunto(latlng);
    if (comunaDetectada) {
        setComunaSelectValueNoZoom(comunaDetectada.codigo);
    }

    // Obtener dirección mediante geocodificación inversa
    obtenerDireccionDeCoordenadas(latlng, comunaDetectada);

    // Desactivar modo de indicar bache
    modoIndicarBache = false;
    const btn = document.getElementById('btnIndicarBache');
    btn.classList.remove('active');
    btn.innerHTML = '<span class="ubicacion-icon">🖱️</span> Indicar en mapa';
    document.getElementById('map').style.cursor = '';
}

async function onComunaChange(e) {
    const codigoComuna = e.target.value;

    if (!codigoComuna) {
        markersLayer.clearLayers();
        document.getElementById('comunaStats').classList.add('hidden');
        document.getElementById('btnResumen').disabled = true;
        document.getElementById('resumenContent').classList.add('hidden');
        selectedComuna = null;
        return;
    }

    // Desde el dropdown SÍ hacer zoom
    await onComunaSelect(codigoComuna, true);
}

async function onComunaSelect(codigoComuna, conZoom = true) {
    selectedComuna = codigoComuna;
    document.getElementById('btnResumen').disabled = false;
    document.getElementById('resumenContent').classList.add('hidden');

    // Solo hacer zoom si se solicita (desde dropdown sí, desde clic en mapa no)
    if (conZoom) {
        zoomToComuna(codigoComuna);
    }

    // Cargar los baches
    await loadBachesComuna(codigoComuna);
}

async function onReporteSubmit(e) {
    e.preventDefault();

    const lat = parseFloat(document.getElementById('lat').value);
    const lon = parseFloat(document.getElementById('lon').value);
    const severidad = document.getElementById('severidad').value;
    const comentario = document.getElementById('comentario').value;
    const direccion = document.getElementById('direccion').value || '';
    const fotoInput = document.getElementById('foto');
    const foto = fotoInput && fotoInput.files[0] ? fotoInput.files[0] : null;

    if (!lat || !lon) {
        showToast('Selecciona una ubicación en el mapa o usa el botón de ubicación', 'error');
        return;
    }

    // Verificar si la ubicación obtenida por GPS ha expirado (5 minutos)
    if (lastLocationTime && isLocationExpired()) {
        showUbicacionStatus('Tu ubicación ha expirado. Por favor, actualízala antes de reportar.', 'error');
        showToast('Ubicación expirada. Presiona "Usar mi ubicación" nuevamente.', 'error');
        return;
    }

    const btn = document.getElementById('btnReportar');
    btn.disabled = true;
    btn.textContent = foto ? 'Verificando imagen...' : 'Enviando...';

    try {
        let response;

        if (foto) {
            // Usar FormData para enviar con foto
            const formData = new FormData();
            formData.append('lat', lat);
            formData.append('lon', lon);
            formData.append('severidad', severidad);
            formData.append('comentario', comentario);
            formData.append('direccion', direccion);
            formData.append('foto', foto);

            btn.textContent = 'Subiendo...';

            response = await fetch(`${API_BASE}/reportes/con-foto`, {
                method: 'POST',
                body: formData
            });
        } else {
            // Sin foto, usar JSON normal
            response = await fetch(`${API_BASE}/reportes`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ lat, lon, severidad, comentario, direccion })
            });
        }

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error al crear reporte');
        }

        const data = await response.json();

        showToast(`Reporte creado en ${data.nombre_comuna}`, 'success');

        // Limpiar formulario
        document.getElementById('comentario').value = '';
        document.getElementById('direccion').value = '';
        document.getElementById('searchDireccion').value = '';
        if (selectedMarker) {
            map.removeLayer(selectedMarker);
            selectedMarker = null;
        }
        document.getElementById('lat').value = '';
        document.getElementById('lon').value = '';

        // Limpiar foto
        removeFoto();

        // Recargar baches si estamos viendo esa comuna
        if (selectedComuna === data.codigo_comuna) {
            await loadBachesComuna(selectedComuna);
        }

        // Seleccionar la comuna del reporte
        if (selectedComuna !== data.codigo_comuna) {
            setComunaSelectValueNoZoom(data.codigo_comuna);
        }

    } catch (error) {
        console.error('Error:', error);
        showToast(error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Reportar Bache';
    }
}

async function onGenerarResumen() {
    const promptInput = document.getElementById('promptIA');
    const prompt = promptInput ? promptInput.value.trim() : '';

    // Si no hay prompt, generar uno por defecto basado en la comuna seleccionada
    let finalPrompt = prompt;
    if (!finalPrompt) {
        if (selectedComuna) {
            // Obtener nombre de la comuna del selector
            const select = document.getElementById('comunaSelect');
            const comunaNombre = select.options[select.selectedIndex]?.text.split(' (')[0] || 'la comuna seleccionada';
            finalPrompt = `Hazme un resumen completo de los baches de ${comunaNombre}. Incluye las calles más afectadas, la severidad de los baches y las direcciones exactas cuando estén disponibles.`;
        } else {
            showToast('Escribe una consulta o selecciona una comuna', 'error');
            return;
        }
    }

    const btn = document.getElementById('btnResumen');
    btn.disabled = true;
    btn.innerHTML = '<span class="loading-dots">Consultando agente</span>';

    // Mostrar loading en el área de contenido
    const resumenContent = document.getElementById('resumenContent');
    resumenContent.classList.remove('hidden');
    document.getElementById('resumenTexto').innerHTML = '<div class="ia-loading">Analizando datos...</div>';
    document.getElementById('top5Container').classList.add('hidden');

    try {
        const response = await fetch(`${API_BASE}/comunas/agente`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt: finalPrompt,
                codigo_comuna: selectedComuna
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error al consultar el agente');
        }

        const data = await response.json();

        // Mostrar respuesta del agente (escapada + markdown mínimo, ver escape.js)
        document.getElementById('resumenTexto').innerHTML = mdToHtml(data.respuesta);

        // Ocultar sección de top5 ya que el agente da info más flexible
        document.getElementById('top5Container').classList.add('hidden');

        // Fecha de generación
        const fecha = new Date(data.generated_at).toLocaleString('es-CL');
        document.getElementById('resumenFecha').textContent = fecha;

    } catch (error) {
        console.error('Error:', error);
        document.getElementById('resumenTexto').innerHTML =
            `<p class="error-message">Error: ${escapeHtml(error.message)}</p>`;
        showToast('Error al consultar el agente', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Consultar Agente IA';
    }
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

