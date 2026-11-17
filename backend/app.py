import os, io, base64, uuid, random
from pathlib import Path
from datetime import date, datetime, timedelta
import mysql.connector, qrcode
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent
CERT_PATH = BASE_DIR / "certs" / "server.crt"
KEY_PATH = BASE_DIR / "certs" / "server.key"
app = Flask(__name__, static_folder=str(BASE_DIR / "frontend"), static_url_path="")
CORS(app)

HTML_PAGES = {"index": "html/index.html", "registrar": "html/registrar.html",
              "personas": "html/personas.html", "escanear": "html/escanear.html"}

def db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"), user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""), database=os.getenv("DB_NAME", "asistencia"))

def qr_b64(texto):
    buf = io.BytesIO()
    qrcode.make(texto).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

def hhmm(v):
    return str(v)[:5] if v is not None else None

@app.get("/")
def inicio():
    return app.send_static_file(HTML_PAGES["index"])

@app.get("/<nombre_pagina>.html")
def paginas(nombre_pagina):
    archivo = HTML_PAGES.get(nombre_pagina)
    if not archivo:
        return "Página no encontrada", 404
    return app.send_static_file(archivo)

# ---------- Registrar ----------
@app.post("/api/personas")
def crear_persona():
    d = request.json or {}
    nombre, email = (d.get("nombre") or "").strip(), (d.get("email") or "").strip()
    if not nombre or not email:
        return jsonify({"error": "Nombre y correo son obligatorios"}), 400
    token = str(uuid.uuid4())
    con = db(); cur = con.cursor()
    try:
        cur.execute("""INSERT INTO personas (nombre,email,tipo,cargo,departamento,qr_token)
                       VALUES (%s,%s,%s,%s,%s,%s)""",
                    (nombre, email, d.get("tipo", "interno"), d.get("cargo", ""),
                     d.get("departamento", ""), token))
        pid = cur.lastrowid
        codigo = f"PR-{pid:04d}"
        cur.execute("UPDATE personas SET codigo=%s WHERE id=%s", (codigo, pid))
        con.commit()
    except mysql.connector.IntegrityError:
        return jsonify({"error": "Ya existe una persona con ese correo"}), 409
    finally:
        con.close()
    return jsonify({"id": pid, "codigo": codigo, "qr": qr_b64(token)}), 201

# ---------- Personas ----------
@app.get("/api/personas")
def listar():
    q = f"%{request.args.get('q', '')}%"
    con = db(); cur = con.cursor(dictionary=True)
    cur.execute("""SELECT p.id, p.codigo, p.nombre, p.cargo, p.departamento, a.hora_entrada,
                          IF(a.id IS NULL,'pendiente','presente') AS estado
                   FROM personas p
                   LEFT JOIN asistencias a ON a.persona_id=p.id AND a.fecha=CURDATE()
                   WHERE p.activo=1 AND (p.nombre LIKE %s OR p.departamento LIKE %s)
                   ORDER BY p.nombre""", (q, q))
    filas = cur.fetchall(); con.close()
    for f in filas:
        f["hora_entrada"] = hhmm(f["hora_entrada"])
    return jsonify(filas)

@app.get("/api/personas/<int:pid>/qr")
def ver_qr(pid):
    con = db(); cur = con.cursor(dictionary=True)
    cur.execute("SELECT nombre, codigo, qr_token FROM personas WHERE id=%s", (pid,))
    p = cur.fetchone(); con.close()
    if not p:
        return jsonify({"error": "No encontrada"}), 404
    return jsonify({"nombre": p["nombre"], "codigo": p["codigo"], "qr": qr_b64(p["qr_token"])})

# ---------- Escanear ----------
@app.post("/api/asistencia")
def ruta_asistencia():
    return registrar((request.json or {}).get("token", ""))

def registrar(token):
    con = db(); cur = con.cursor(dictionary=True)
    cur.execute("SELECT id, nombre FROM personas WHERE qr_token=%s AND activo=1", (token,))
    p = cur.fetchone()
    if not p:
        con.close(); return jsonify({"error": "QR no válido"}), 404
    cur.execute("SELECT hora_entrada FROM asistencias WHERE persona_id=%s AND fecha=CURDATE()", (p["id"],))
    previa = cur.fetchone()
    if previa:
        con.close()
        return jsonify({"aviso": "Ya registró su entrada hoy", "nombre": p["nombre"],
                        "hora": hhmm(previa["hora_entrada"])})
    hora = datetime.now().strftime("%H:%M:%S")
    cur.execute("INSERT INTO asistencias (persona_id,fecha,hora_entrada) VALUES (%s,CURDATE(),%s)",
                (p["id"], hora))
    con.commit(); con.close()
    return jsonify({"ok": True, "nombre": p["nombre"], "hora": hora[:5]}), 201

@app.post("/api/simular")
def simular():
    """Elige al azar a alguien pendiente y registra su entrada (solo pruebas)."""
    con = db(); cur = con.cursor(dictionary=True)
    cur.execute("""SELECT p.qr_token FROM personas p
                   LEFT JOIN asistencias a ON a.persona_id=p.id AND a.fecha=CURDATE()
                   WHERE p.activo=1 AND a.id IS NULL""")
    filas = cur.fetchall(); con.close()
    if not filas:
        return jsonify({"aviso": "No hay personas pendientes para simular"})
    return registrar(random.choice(filas)["qr_token"])

# ---------- Resumen ----------
@app.get("/api/resumen")
def resumen():
    con = db(); cur = con.cursor(dictionary=True)
    cur.execute("SELECT COUNT(*) n FROM personas WHERE activo=1")
    total = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) n FROM asistencias WHERE fecha=CURDATE()")
    presentes = cur.fetchone()["n"]
    cur.execute("""SELECT fecha, COUNT(*) n FROM asistencias
                   WHERE fecha >= CURDATE() - INTERVAL 6 DAY GROUP BY fecha""")
    por_dia = {r["fecha"]: r["n"] for r in cur.fetchall()}
    semana = []
    for i in range(6, -1, -1):
        dia = date.today() - timedelta(days=i)
        pct = round(por_dia.get(dia, 0) * 100 / total) if total else 0
        semana.append({"dia": dia.weekday(), "pct": pct, "hoy": i == 0})
    cur.execute("""SELECT p.nombre, p.departamento, a.hora_entrada
                   FROM asistencias a JOIN personas p ON p.id=a.persona_id
                   WHERE a.fecha=CURDATE() ORDER BY a.hora_entrada DESC LIMIT 5""")
    recientes = [{"nombre": r["nombre"], "area": r["departamento"], "hora": hhmm(r["hora_entrada"])}
                 for r in cur.fetchall()]
    con.close()
    return jsonify({"total": total, "presentes": presentes, "pendientes": total - presentes,
                    "semana": semana, "recientes": recientes})

# ---------- Historial anual ----------
@app.get("/api/historial")
def historial():
    anio = int(request.args.get("anio", date.today().year))
    con = db(); cur = con.cursor(dictionary=True)
    cur.execute("SELECT COUNT(*) n FROM personas WHERE activo=1")
    total = cur.fetchone()["n"]
    cur.execute("""SELECT MONTH(fecha) mes, COUNT(*) n, COUNT(DISTINCT fecha) dias
                   FROM asistencias WHERE YEAR(fecha)=%s GROUP BY MONTH(fecha)""", (anio,))
    datos = {r["mes"]: r for r in cur.fetchall()}
    con.close()
    meses = []
    for m in range(1, 13):
        r = datos.get(m)
        pct = round(r["n"] * 100 / (r["dias"] * total)) if r and total else 0
        meses.append({"mes": m, "pct": pct, "entradas": r["n"] if r else 0})
    return jsonify({"anio": anio, "meses": meses})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True, ssl_context=(str(CERT_PATH), str(KEY_PATH)))
