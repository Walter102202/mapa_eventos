const test = require('node:test');
const assert = require('node:assert/strict');
const { escapeHtml, mdToHtml } = require('../js/escape.js');

test('escapeHtml escapa los cinco caracteres peligrosos', () => {
    assert.equal(escapeHtml(`<img src=x onerror="alert('1')">&`),
        '&lt;img src=x onerror=&quot;alert(&#39;1&#39;)&quot;&gt;&amp;');
});

test('escapeHtml convierte null/undefined en cadena vacía y números en texto', () => {
    assert.equal(escapeHtml(null), '');
    assert.equal(escapeHtml(undefined), '');
    assert.equal(escapeHtml(42), '42');
});

test('mdToHtml escapa antes de aplicar markdown', () => {
    const html = mdToHtml('## Título\n- **Alta**: <script>alert(1)</script>');
    assert.ok(!html.includes('<script>'));
    assert.ok(html.includes('&lt;script&gt;'));
    assert.ok(html.includes('<h3>Título</h3>'));
    assert.ok(html.includes('<li><strong>Alta</strong>: &lt;script&gt;alert(1)&lt;/script&gt;</li>'));
});

test('mdToHtml separa párrafos y saltos de línea', () => {
    assert.equal(mdToHtml('a\n\nb\nc'), '<p>a</p><p>b<br>c</p>');
});
