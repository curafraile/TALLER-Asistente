import os
from flask import Flask, render_template, request, redirect, session, Response
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import urllib.parse as urlparse

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "clave_secreta")

# 🔗 Configuración de la conexión a Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Faltan las variables de entorno SUPABASE_URL y SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 🔧 Crear tablas y usuario si no existen
def inicializar_db():
    conn = None
    try:
        # Extraer las partes de la URL de Supabase para conectar con psycopg2
        url = urlparse.urlparse(SUPABASE_URL)
        dbname = os.path.basename(url.path)
        user = url.username
        password = url.password
        host = url.hostname
        port = url.port
        conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port)
        cur = conn.cursor()

        # Tabla de usuarios
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                usuario TEXT UNIQUE NOT NULL,
                clave TEXT NOT NULL,
                email TEXT,
                rol TEXT CHECK(rol IN ('docente', 'admin')) DEFAULT 'docente'
            )
        """)

        # Tabla de docentes
        cur.execute("""
            CREATE TABLE IF NOT EXISTS docentes (
                id SERIAL PRIMARY KEY,
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
                id SERIAL PRIMARY KEY,
                nombre TEXT NOT NULL,
                presente TEXT NOT NULL,
                usuario_id INTEGER
            )
        """)

        # Tabla de notas
        cur.execute("""
            CREATE TABLE IF NOT EXISTS notas (
                id SERIAL PRIMARY KEY,
                alumno TEXT NOT NULL,
                nota TEXT NOT NULL,
                usuario_id INTEGER
            )
        """)
        conn.commit()

        # Verificar si ya existe el usuario 'admin'
        cur.execute("SELECT COUNT(*) FROM usuarios WHERE usuario = 'admin'")
        if cur.fetchone()[0] == 0:
            # Crear usuario 'admin' con la contraseña hasheada
            clave_hasheada = generate_password_hash("1234")
            cur.execute("""
                INSERT INTO usuarios (usuario, clave, email, rol)
                VALUES (%s, %s, %s, %s)
            """, ("admin", clave_hasheada, "admin@escuela.edu", "admin"))
            conn.commit()

    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")
    finally:
        if conn:
            conn.close()

# Inicializar la base de datos al inicio
inicializar_db()

def conectar():
    # Conecta a la base de datos de Supabase usando la biblioteca supabase-py
    return supabase

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
        db = conectar()

        # Usar la biblioteca de Supabase para buscar el usuario
        response = db.from_("usuarios").select("id, clave, rol").eq("usuario", usuario).execute()
        
        if response.data:
            user_data = response.data[0]
            if check_password_hash(user_data["clave"], clave):
                session["usuario_id"] = user_data["id"]
                session["usuario"] = usuario
                session["rol"] = user_data["rol"]
                return redirect("/")
            else:
                return render_template("login.html", error="Credenciales incorrectas")
        else:
            return render_template("login.html", error="Credenciales incorrectas")
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/")
def index():
    db = conectar()
    response = db.from_("docentes").select("nombre, apellido").eq("usuario_id", session["usuario_id"]).execute()
    
    if response.data:
        datos = response.data[0]
        nombre = datos["nombre"]
        apellido = datos["apellido"]
    else:
        nombre, apellido = "", ""

    return render_template("index.html", nombre=nombre, apellido=apellido)

@app.route("/asistencia", methods=["GET", "POST"])
def asistencia():
    db = conectar()
    if request.method == "POST":
        nombre = request.form["nombre"]
        presente = request.form.get("presente", "no")
        data = {
            "nombre": nombre,
            "presente": presente,
            "usuario_id": session["usuario_id"]
        }
        db.from_("asistencia").insert(data).execute()

    response = db.from_("asistencia").select("*").eq("usuario_id", session["usuario_id"]).execute()
    datos = response.data
    return render_template("asistencia.html", datos=datos)

@app.route("/notas", methods=["GET", "POST"])
def notas():
    db = conectar()
    if request.method == "POST":
        alumno = request.form["alumno"]
        nota = request.form["nota"]
        data = {
            "alumno": alumno,
            "nota": nota,
            "usuario_id": session["usuario_id"]
        }
        db.from_("notas").insert(data).execute()

    response = db.from_("notas").select("*").eq("usuario_id", session["usuario_id"]).execute()
    datos = response.data
    return render_template("notas.html", datos=datos)

@app.route("/exportar_asistencia")
def exportar_asistencia():
    db = conectar()
    response = db.from_("asistencia").select("*").eq("usuario_id", session["usuario_id"]).execute()
    datos = response.data
    
    def generar():
        yield "id,nombre,presente\n"
        for fila in datos:
            yield f"{fila['id']},{fila['nombre']},{fila['presente']}\n"
    return Response(generar(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=asistencia.csv"})

@app.route("/exportar_notas")
def exportar_notas():
    db = conectar()
    response = db.from_("notas").select("*").eq("usuario_id", session["usuario_id"]).execute()
    datos = response.data
    
    def generar():
        yield "id,alumno,nota\n"
        for fila in datos:
            yield f"{fila['id']},{fila['alumno']},{fila['nota']}\n"
    return Response(generar(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=notas.csv"})
    
@app.route('/perfil')
def perfil():
    if 'usuario_id' not in session:
        return redirect("/login")
    
    db = conectar()
    response = db.from_("docentes").select("nombre, apellido, area").eq("usuario_id", session["usuario_id"]).execute()
    
    if response.data:
        datos = response.data[0]
        return render_template('perfil.html', nombre=datos['nombre'], apellido=datos['apellido'], area=datos['area'])
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
        
        db = conectar()
        try:
            # Hash de la contraseña antes de insertar
            clave_hasheada = generate_password_hash(clave)
            
            # Insertar en la tabla usuarios
            response = db.from_("usuarios").insert({
                "usuario": usuario, 
                "clave": clave_hasheada, 
                "email": email, 
                "rol": "docente"
            }).execute()
            
            # Obtener el ID del usuario insertado
            usuario_id = response.data[0]["id"]
            
            # Insertar en la tabla docentes
            db.from_("docentes").insert({
                "usuario_id": usuario_id,
                "nombre": nombre,
                "apellido": apellido,
                "area": area
            }).execute()
            
            mensaje = "Docente registrado correctamente."
        except Exception as e:
            mensaje = f"Error: El usuario ya existe o hubo un problema. {str(e)}"
            
        return render_template("registrar.html", mensaje=mensaje)
    
    return render_template("registrar.html")

@app.route("/admin")
def admin_panel():
    if session.get("rol") != "admin":
        return "Acceso restringido", 403

    db = conectar()
    response = db.from_("docentes").select("id, nombre, apellido, area, usuarios(usuario, email)").join("usuarios").execute()
    docentes = response.data
    
    return render_template("admin_panel.html", docentes=docentes)

@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar_docente(id):
    if session.get("rol") != "admin":
        return "Acceso restringido", 403
    
    db = conectar()
    
    if request.method == "POST":
        usuario = request.form["usuario"]
        clave = request.form["clave"]
        email = request.form["email"]
        nombre = request.form["nombre"]
        apellido = request.form["apellido"]
        area = request.form["area"]
        
        # Obtener el usuario_id del docente
        response = db.from_("docentes").select("usuario_id").eq("id", id).execute()
        usuario_id = response.data[0]["usuario_id"]
        
        # Actualizar la tabla de usuarios (clave hasheada si se cambia)
        updates_usuarios = {"usuario": usuario, "email": email}
        if clave: # Solo actualizar la clave si se proporciona una nueva
            updates_usuarios["clave"] = generate_password_hash(clave)
        db.from_("usuarios").update(updates_usuarios).eq("id", usuario_id).execute()
        
        # Actualizar la tabla de docentes
        updates_docentes = {"nombre": nombre, "apellido": apellido, "area": area}
        db.from_("docentes").update(updates_docentes).eq("id", id).execute()
        
        return redirect("/admin")
        
    response = db.from_("docentes").select("id, nombre, apellido, area, usuarios(id, usuario, clave, email)").join("usuarios").eq("id", id).execute()
    datos = response.data[0]
    
    return render_template("editar_docente.html", datos=datos)

@app.route("/eliminar/<int:id>")
def eliminar_docente(id):
    if session.get("rol") != "admin":
        return "Acceso restringido", 403
    
    db = conectar()
    
    # Obtener el usuario_id del docente
    response = db.from_("docentes").select("usuario_id").eq("id", id).execute()
    usuario_id = response.data[0]["usuario_id"]
    
    # Eliminar el registro en la tabla de usuarios
    # La eliminación en la tabla 'docentes' se hará en cascada
    db.from_("usuarios").delete().eq("id", usuario_id).execute()

    return redirect("/admin")
    
if __name__ == "__main__":
    app.run(debug=True)
