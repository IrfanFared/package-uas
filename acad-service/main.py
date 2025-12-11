from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends, status
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
from contextlib import contextmanager

app = FastAPI(title="Product Service", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'products'),
    'user': os.getenv('DB_USER', 'productuser'),
    'password': os.getenv('DB_PASSWORD', 'productpass')
}

def row_to_dict(row):
    if row is None:
        return None
    return dict(row)

class Mahasiswa(BaseModel):
    nim: str
    nama: str
    jurusan: str
    angkatan: int = Field(ge=0)

# Database connection pool
@contextmanager
def get_db_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

@app.on_event("startup")
async def startup_event():
    try:
        with get_db_connection() as conn:
            print("Acad Service: Connected to PostgreSQL")
    except Exception as e:
        print(f"Acad Service: PostgreSQL connection error: {e}")

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "Acad Service is running",
        "timestamp": datetime.now().isoformat()
    }

# ... (kode impor di atas tetap sama) ...

# Tambahkan endpoint ini di bawah @app.get("/api/acad/mahasiswa")
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    # Di microservice real, kita decode tokennya. 
    # Untuk UAS ini, minimal kita cek apakah token ada/terkirim.
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


@app.get("/api/acad/nilai/{nim}")
async def get_ips_mahasiswa(nim: str, token: str = Depends(verify_token)):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Query untuk mengambil MK yang diambil mahasiswa, SKS, dan Bobot Nilainya
            query = """
            SELECT 
                m.nama_mk,
                m.sks,
                k.nilai as nilai_huruf,
                b.bobot as nilai_angka
            FROM krs k
            JOIN mata_kuliah m ON k.kode_mk = m.kode_mk
            JOIN bobot_nilai b ON k.nilai = b.nilai
            WHERE k.nim = %s
            """
            
            cursor.execute(query, (nim,))
            rows = cursor.fetchall()
            
            if not rows:
                raise HTTPException(status_code=404, detail="Data nilai mahasiswa tidak ditemukan")

            # Logika perhitungan IPS
            total_sks = 0
            total_poin = 0
            
            detail_nilai = []

            for row in rows:
                sks = row['sks']
                bobot = row['nilai_angka']
                
                total_sks += sks
                total_poin += (sks * bobot)
                
                detail_nilai.append(row)

            # Menghindari pembagian dengan nol
            ips = total_poin / total_sks if total_sks > 0 else 0.0

            return {
                "nim": nim,
                "total_sks": total_sks,
                "ips": round(ips, 2), # Pembulatan 2 desimal
                "detail_transkrip": detail_nilai
            }
            
    except Exception as e:
        # Jika error bukan HTTPException, raise sebagai 500
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))