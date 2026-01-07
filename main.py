# main.py
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import sqlite3
from datetime import datetime
import pandas as pd
import io
import os

app = FastAPI(
    title="Sistema de Validación de Boletos QR",
    version="2.0",
    description="API para validar boletos en eventos - Desplegado en Railway"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# Inicializar base de datos
def init_db():
    """Inicializa la base de datos SQLite"""
    conn = sqlite3.connect('boletos.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS boletos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_unico TEXT UNIQUE NOT NULL,
            nombre_cliente TEXT,
            email TEXT,
            evento TEXT DEFAULT 'Evento',
            fecha_evento TEXT,
            tipo_entrada TEXT DEFAULT 'General',
            precio REAL DEFAULT 0,
            asiento TEXT,
            estado TEXT DEFAULT 'activo',
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_uso TIMESTAMP,
            validador_uso TEXT,
            dispositivo_uso TEXT,
            ubicacion_uso TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS escaneos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_unico TEXT NOT NULL,
            fecha_escaneo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resultado TEXT,
            dispositivo TEXT,
            ubicacion TEXT,
            usuario_validador TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

# Inicializar al inicio
init_db()

# RUTAS PRINCIPALES
@app.get("/")
async def home():
    """Página principal - Dashboard"""
    return FileResponse("static/index.html")

@app.get("/scanner")
async def scanner():
    """App móvil para escanear"""
    return FileResponse("static/scanner.html")

@app.get("/admin")
async def admin():
    """Panel de administración"""
    return FileResponse("static/admin.html")

# API ENDPOINTS
@app.get("/api/health")
async def health():
    """Verificar que la API está funcionando"""
    return {"status": "online", "timestamp": datetime.now().isoformat()}

@app.post("/api/importar")
async def importar_csv(file: UploadFile = File(...)):
    """Importar boletos desde CSV"""
    try:
        content = await file.read()
        
        # Detectar encoding
        try:
            text = content.decode('utf-8')
        except:
            text = content.decode('latin-1')
        
        # Leer CSV
        df = pd.read_csv(io.StringIO(text))
        
        conn = sqlite3.connect('boletos.db')
        cursor = conn.cursor()
        
        imported = 0
        errors = []
        
        for idx, row in df.iterrows():
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO boletos 
                    (codigo_unico, nombre_cliente, email, evento, fecha_evento, 
                     tipo_entrada, precio, asiento, estado)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    str(row.get('codigo_unico', f'TICKET-{idx}')).strip(),
                    str(row.get('nombre_cliente', 'Cliente')),
                    str(row.get('email', '')),
                    str(row.get('evento', 'Evento')),
                    str(row.get('fecha_evento', datetime.now().strftime('%Y-%m-%d %H:%M'))),
                    str(row.get('tipo_entrada', 'General')),
                    float(row.get('precio', 0)),
                    str(row.get('asiento', '')),
                    str(row.get('estado', 'activo')).lower()
                ))
                imported += 1
            except Exception as e:
                errors.append(f"Fila {idx}: {str(e)}")
        
        conn.commit()
        conn.close()
        
        return JSONResponse({
            "success": True,
            "message": f"✅ Importados {imported} boletos",
            "imported": imported,
            "errors": errors[:5]
        })
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/validar/{codigo}")
async def validar_boleto(
    codigo: str,
    usuario: str = "validador",
    dispositivo: str = "web",
    ubicacion: str = "general"
):
    """Validar un boleto por código QR"""
    conn = sqlite3.connect('boletos.db')
    cursor = conn.cursor()
    
    # Buscar boleto
    cursor.execute("SELECT * FROM boletos WHERE codigo_unico = ?", (codigo,))
    boleto = cursor.fetchone()
    
    if not boleto:
        resultado = {"estado": "no_encontrado", "mensaje": "❌ Boleto no encontrado"}
        cursor.execute(
            "INSERT INTO escaneos (codigo_unico, resultado, dispositivo, ubicacion, usuario_validador) VALUES (?, ?, ?, ?, ?)",
            (codigo, "no_encontrado", dispositivo, ubicacion, usuario)
        )
        conn.commit()
        conn.close()
        return resultado
    
    # Obtener columnas
    columnas = [desc[0] for desc in cursor.description]
    boleto_dict = dict(zip(columnas, boleto))
    
    # Verificar estado
    if boleto_dict['estado'] == 'usado':
        resultado = {
            "estado": "ya_usado",
            "mensaje": "⚠️ Boleto ya utilizado",
            "fecha_uso": boleto_dict['fecha_uso']
        }
        cursor.execute(
            "INSERT INTO escaneos (codigo_unico, resultado, dispositivo, ubicacion, usuario_validador) VALUES (?, ?, ?, ?, ?)",
            (codigo, "ya_usado", dispositivo, ubicacion, usuario)
        )
        conn.commit()
        conn.close()
        return resultado
    
    # Marcar como usado
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        "UPDATE boletos SET estado = 'usado', fecha_uso = ?, validador_uso = ?, dispositivo_uso = ?, ubicacion_uso = ? WHERE codigo_unico = ?",
        (now, usuario, dispositivo, ubicacion, codigo)
    )
    
    cursor.execute(
        "INSERT INTO escaneos (codigo_unico, resultado, dispositivo, ubicacion, usuario_validador) VALUES (?, ?, ?, ?, ?)",
        (codigo, "valido", dispositivo, ubicacion, usuario)
    )
    
    conn.commit()
    conn.close()
    
    return {
        "estado": "valido",
        "mensaje": "✅ ¡BOLETO VÁLIDO!",
        "fecha_validacion": now,
        "validador": usuario,
        "datos_boleto": boleto_dict
    }

@app.get("/api/estadisticas")
async def estadisticas():
    """Obtener estadísticas en tiempo real"""
    conn = sqlite3.connect('boletos.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM boletos")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM boletos WHERE estado = 'usado'")
    usados = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM boletos WHERE estado = 'activo'")
    activos = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT e.*, b.nombre_cliente, b.evento 
        FROM escaneos e
        LEFT JOIN boletos b ON e.codigo_unico = b.codigo_unico
        ORDER BY e.fecha_escaneo DESC 
        LIMIT 10
    ''')
    
    escaneos = cursor.fetchall()
    columnas = ['id', 'codigo_unico', 'fecha_escaneo', 'resultado', 'dispositivo',
                'ubicacion', 'usuario_validador', 'nombre_cliente', 'evento']
    
    historial = [dict(zip(columnas, escaneo)) for escaneo in escaneos]
    
    conn.close()
    
    return {
        "timestamp": datetime.now().isoformat(),
        "estadisticas": {
            "total_boletos": total,
            "validados": usados,
            "pendientes": activos,
            "porcentaje_validado": round((usados/total*100), 2) if total > 0 else 0
        },
        "ultimos_escaneos": historial
    }

# Para desarrollo local
if __name__ == "__main__":
    import uvicorn
    print("🚀 Sistema de Boletos - Ready for Railway!")
    uvicorn.run(app, host="0.0.0.0", port=8000)