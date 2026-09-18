/**
 * Utilidades compartidas para renderizar texto de usuarios o del LLM sin XSS.
 * Cargar ANTES de app.js / informes.js. Todo lo que venga de la API o de
 * Nominatim y termine en innerHTML / bindPopup pasa por acá.
 */

function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/**
 * Markdown mínimo (negrita, cursiva, títulos, listas, párrafos) sobre texto
 * YA escapado. Los tags que genera son los únicos que pueden llegar al DOM.
 */
function mdToHtml(text) {
    let html = escapeHtml(text)
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/^### (.*$)/gm, '<h4>$1</h4>')
        .replace(/^## (.*$)/gm, '<h3>$1</h3>')
        .replace(/^# (.*$)/gm, '<h2>$1</h2>')
        .replace(/^- (.*$)/gm, '<li>$1</li>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');

    html = html.replace(/(<li>.*<\/li>)+/g, '<ul>$&</ul>');
    return `<p>${html}</p>`;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { escapeHtml, mdToHtml };
}
