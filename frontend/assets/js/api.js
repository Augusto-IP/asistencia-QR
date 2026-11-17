// Backend: ruta relativa si abres desde Flask (puerto 5000); absoluta si usas Live Server
const API = location.port === "5000" ? "" : "http://localhost:5000";

async function api(ruta, opciones = {}) {
  try {
    const res = await fetch(API + ruta, {
      headers: { "Content-Type": "application/json" }, ...opciones,
      body: opciones.body ? JSON.stringify(opciones.body) : undefined,
    });
    const datos = await res.json().catch(() => ({}));
    if (!res.ok && !datos.error) datos.error = "Error del servidor";
    return datos;
  } catch (e) {
    return { error: "No hay conexión con el servidor. ¿Está corriendo app.py?" };
  }
}

// Evita inyectar HTML desde los datos
const esc = s => String(s ?? "").replace(/[&<>"']/g,
  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const iniciales = n => n.trim().split(/\s+/).slice(0, 2).map(p => p[0]).join("").toUpperCase();
const color = n => "c" + ([...n].reduce((a, c) => a + c.charCodeAt(0), 0) % 5);

const ICONOS = {
  home: '<path d="M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10"/>',
  cam: '<path d="M4 8h3l2-3h6l2 3h3v12H4z"/><circle cx="12" cy="13" r="4"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-4 3-6 6.5-6s6.5 2 6.5 6M16 4.8a3.5 3.5 0 010 6.4M18 14.4c2.2.7 3.5 2.6 3.5 5.6"/>',
  plus: '<path d="M12 4v16M4 12h16"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  cal: '<rect x="3.5" y="5" width="17" height="15" rx="3"/><path d="M8 3v4M16 3v4M3.5 10h17"/>',
  qr: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><path d="M14 14h3v3h-3zM19 19h2M14 20h1"/>',
};
const svg = n => `<svg viewBox="0 0 24 24">${ICONOS[n]}</svg>`;

(function () {
  const pagina = location.pathname.split("/").pop() || "index.html";
  const items = [["index.html", "Resumen", "home"], ["escanear.html", "Escanear", "cam"],
                 ["personas.html", "Personas", "users"], ["registrar.html", "Registrar", "plus"]];
  document.getElementById("menu").innerHTML = "<h6>MENÚ PRINCIPAL</h6>" +
    items.map(([href, txt, ic]) =>
      `<a href="${href}" class="${pagina === href ? "on" : ""}">${svg(ic)}${txt}</a>`).join("");
})();
