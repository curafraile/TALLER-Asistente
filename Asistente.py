from flask import Flask, render_template, request, redirect, session, Response
import sqlite3, os

app = Flask(__name__)
app.secret_key = "clave_secreta"

# 🔧 Crear base de datos y tablas si no existen
def inicializar_db():
    con = sqlite3.connect("database.db")
    cur = con.cursor()

    # Tabla de usuarios con email y rol
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            clave TEXT NOT NULL,
            email TEXT,
            rol TEXT CHECK(rol IN ('docente', 'admin')) DEFAULT 'docente'
        )
    """)

    # Tabla de docentes vinculada a usuarios
    cur.execute("""
        CREATE TABLE IF NOT EXISTS docentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            apellido TEXT NOT NULL,
            area TEXT,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )
    """)

    # Tabla de asistencia
    cur.execute("""
        CREATE TABLE IF NOT EXISTS asistencia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            presente TEXT NOT NULL,
            usuario_id INTEGER
        )
    """)

    # Tabla de notas
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumno TEXT NOT NULL,
            nota TEXT NOT NULL,
            usuario_id INTEGER
        )
    """)

    con.commit()

    # Insertar usuarios y docentes si no hay datos
    cur.execute("SELECT COUNT(*) FROM usuarios")
    if cur.fetchone()[0] == 0:
        usuarios = [
            ('juan', 'clave123', 'juan@escuela.edu', 'docente'),
            ('maria', 'clave456', 'maria@escuela.edu', 'docente'),
            ('admin', 'adminpass', 'admin@escuela.edu', 'admin')
        ]
        cur.executemany("""
            INSERT INTO usuarios (usuario, clave, email, rol)
            VALUES (?, ?, ?, ?)
        """, usuarios)

        # Obtener IDs
        cur.execute("SELECT id FROM usuarios WHERE usuario = 'juan'")
        juan_id = cur.fetchone()[0]
        cur.execute("SELECT id FROM usuarios WHERE usuario = 'maria'")
        maria_id = cur.fetchone()[0]

        docentes = [
            (juan_id, 'Juan', 'Pérez', 'Taller'),
            (maria_id, 'María', 'Gómez', 'Taller')
        ]
        cur.executemany("""
            INSERT INTO docentes (usuario_id, nombre, apellido, area)
            VALUES (?, ?, ?, ?)
        """, docentes)

    con.commit()
    con.close()

inicializar_db()

def conectar():
    return sqlite3.connect("database.db")

@app.before_request
def verificar_login():
    rutas_libres = ["/login", "/logout"]
    if not session.get("usuario_id") and request.path not in rutas_libres:
        return redirect("/login")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        clave = request.form["clave"]
        con = conectar()
        cur = con.cursor()
        cur.execute("SELECT id, rol FROM usuarios WHERE usuario=? AND clave=?", (usuario, clave))
        resultado = cur.fetchone()
        con.close()
        if resultado:
            session["usuario_id"] = resultado[0]
            session["usuario"] = usuario
            session["rol"] = resultado[1]
            return redirect("/")
        else:
            return render_template("login.html", error="Credenciales incorrectas")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/")
@app.route("/")
def index():
    con = conectar()
    cur = con.cursor()
    cur.execute("SELECT nombre, apellido FROM docentes WHERE usuario_id = ?", (session["usuario_id"],))
    datos = cur.fetchone()
    con.close()

    if datos:
        nombre, apellido = datos
    else:
        nombre, apellido = "", ""

    return render_template("index.html", nombre=nombre, apellido=apellido)


@app.route("/asistencia", methods=["GET", "POST"])
def asistencia():
    con = conectar()
    cur = con.cursor()
    if request.method == "POST":
        nombre = request.form["nombre"]
        presente = request.form.get("presente", "no")
        cur.execute("INSERT INTO asistencia (nombre, presente, usuario_id) VALUES (?, ?, ?)",
                    (nombre, presente, session["usuario_id"]))
        con.commit()
    cur.execute("SELECT * FROM asistencia WHERE usuario_id=?", (session["usuario_id"],))
    datos = cur.fetchall()
    con.close()
    return render_template("asistencia.html", datos=datos)

@app.route("/notas", methods=["GET", "POST"])
def notas():
    con = conectar()
    cur = con.cursor()
    if request.method == "POST":
        alumno = request.form["alumno"]
        nota = request.form["nota"]
        cur.execute("INSERT INTO notas (alumno, nota, usuario_id) VALUES (?, ?, ?)",
                    (alumno, nota, session["usuario_id"]))
        con.commit()
    cur.execute("SELECT * FROM notas WHERE usuario_id=?", (session["usuario_id"],))
    datos = cur.fetchall()
    con.close()
    return render_template("notas.html", datos=datos)

@app.route("/exportar_asistencia")
def exportar_asistencia():
    con = conectar()
    cur = con.cursor()
    cur.execute("SELECT * FROM asistencia WHERE usuario_id=?", (session["usuario_id"],))
    datos = cur.fetchall()
    con.close()
    def generar():
        yield "id,nombre,presente\n"
        for fila in datos:
            yield f"{fila[0]},{fila[1]},{fila[2]}\n"
    return Response(generar(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=asistencia.csv"})

@app.route("/exportar_notas")
def exportar_notas():
    con = conectar()
    cur = con.cursor()
    cur.execute("SELECT * FROM notas WHERE usuario_id=?", (session["usuario_id"],))
    datos = cur.fetchall()
    con.close()
    def generar():
        yield "id,alumno,nota\n"
        for fila in datos:
            yield f"{fila[0]},{fila[1]},{fila[2]}\n"
    return Response(generar(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=notas.csv"})
@app.route('/perfil')
def perfil():
    if 'usuario_id' not in session:
        return redirect("/login")

    usuario_id = session['usuario_id']
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT nombre, apellido, area FROM docentes WHERE usuario_id = ?", (usuario_id,))
    datos = cursor.fetchone()
    conn.close()

    if datos:
        nombre, apellido, area = datos
        return render_template('perfil.html', nombre=nombre, apellido=apellido, area=area)
    else:
        return "Docente no encontrado", 404
@app.route("/registrar", methods=["GET", "POST"])
def registrar():
    if request.method == "POST":
        usuario = request.form["usuario"]
        clave = request.form["clave"]
        email = request.form["email"]
        nombre = request.form["nombre"]
        apellido = request.form["apellido"]
        area = request.form["area"]

        con = conectar()
        cur = con.cursor()
        try:
            cur.execute("INSERT INTO usuarios (usuario, clave, email, rol) VALUES (?, ?, ?, ?)",
                        (usuario, clave, email, 'docente'))

            cur.execute("SELECT id FROM usuarios WHERE usuario = ?", (usuario,))
            usuario_id = cur.fetchone()[0]

            cur.execute("INSERT INTO docentes (usuario_id, nombre, apellido, area) VALUES (?, ?, ?, ?)",
                        (usuario_id, nombre, apellido, area))

            con.commit()
            mensaje = "Docente registrado correctamente."
        except sqlite3.IntegrityError:
            mensaje = "El usuario ya existe. Elegí otro nombre de usuario."
        finally:
            con.close()

        return render_template("registrar.html", mensaje=mensaje)

    return render_template("registrar.html")
@app.route("/admin")
def admin_panel():
    if session.get("rol") != "admin":
        return "Acceso restringido", 403

    con = conectar()
    cur = con.cursor()
    cur.execute("""
        SELECT docentes.id, usuarios.usuario, docentes.nombre, docentes.apellido, docentes.area, usuarios.email
        FROM docentes
        JOIN usuarios ON docentes.usuario_id = usuarios.id
    """)
    docentes = cur.fetchall()
    con.close()
    return render_template("admin_panel.html", docentes=docentes)

@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar_docente(id):
    if session.get("rol") != "admin":
        return "Acceso restringido", 403

    con = conectar()
    cur = con.cursor()

    if request.method == "POST":
        usuario = request.form["usuario"]
        clave = request.form["clave"]
        email = request.form["email"]
        nombre = request.form["nombre"]
        apellido = request.form["apellido"]
        area = request.form["area"]

        cur.execute("UPDATE usuarios SET usuario=?, clave=?, email=? WHERE id=(SELECT usuario_id FROM docentes WHERE id=?)",
                    (usuario, clave, email, id))
        cur.execute("UPDATE docentes SET nombre=?, apellido=?, area=? WHERE id=?",
                    (nombre, apellido, area, id))

        con.commit()
        con.close()
        return redirect("/admin")

    cur.execute("""
        SELECT docentes.id, usuarios.usuario, usuarios.clave, usuarios.email,
               docentes.nombre, docentes.apellido, docentes.area
        FROM docentes
        JOIN usuarios ON docentes.usuario_id = usuarios.id
        WHERE docentes.id = ?
    """, (id,))
    datos = cur.fetchone()
    con.close()
    return render_template("editar_docente.html", datos=datos)

@app.route("/eliminar/<int:id>")
def eliminar_docente(id):
    if session.get("rol") != "admin":
        return "Acceso restringido", 403

    con = conectar()
    cur = con.cursor()
    cur.execute("DELETE FROM usuarios WHERE id=(SELECT usuario_id FROM docentes WHERE id=?)", (id,))
    con.commit()
    con.close()
    return redirect("/admin")


if __name__ == "__main__":
    app.run(debug=True)
