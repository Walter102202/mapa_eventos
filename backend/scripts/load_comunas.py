"""
Script para cargar las comunas de la Región Metropolitana en MySQL.

Uso:
    python load_comunas.py [--geojson path/to/comunas.geojson]

Si no se especifica archivo, usa el archivo por defecto en ../data/comunas_rm.geojson
"""

import json
import os
import sys
from pathlib import Path

# Agregar el directorio padre al path para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Cargar variables de entorno
load_dotenv(Path(__file__).parent.parent / ".env")


def get_database_url():
    """Construir URL de conexión a MySQL."""
    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    user = os.getenv("MYSQL_USER", 'root')
    password = os.getenv("MYSQL_PASSWORD", '')
    database = os.getenv("MYSQL_DATABASE", "baches_rm")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"


def load_geojson(filepath: str) -> dict:
    """Cargar archivo GeoJSON."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def insert_comuna(engine, codigo: str, nombre: str, geom_json: str, codigo_region: str = "13"):
    """Insertar una comuna en la base de datos."""
    with engine.connect() as conn:
        # Convertir GeoJSON a geometría MySQL
        query = text("""
            INSERT INTO comunas_rm (codigo_comuna, nombre_comuna, codigo_region, geom)
            VALUES (
                :codigo,
                :nombre,
                :codigo_region,
                ST_GeomFromGeoJSON(:geom_json, 1, 4326)
            )
            ON DUPLICATE KEY UPDATE
                nombre_comuna = :nombre,
                geom = ST_GeomFromGeoJSON(:geom_json, 1, 4326)
        """)
        conn.execute(query, {
            "codigo": codigo,
            "nombre": nombre,
            "codigo_region": codigo_region,
            "geom_json": geom_json
        })
        conn.commit()


def main():
    # Determinar archivo GeoJSON
    if len(sys.argv) > 2 and sys.argv[1] == "--geojson":
        geojson_path = sys.argv[2]
    else:
        geojson_path = Path(__file__).parent.parent.parent / "data" / "comunas_rm.geojson"

    print(f"Cargando comunas desde: {geojson_path}")

    # Verificar que el archivo existe
    if not os.path.exists(geojson_path):
        print(f"Error: No se encontró el archivo {geojson_path}")
        print("\nPor favor descarga los datos de comunas desde:")
        print("  https://www.bcn.cl/siit/mapas_vectoriales")
        print("\nO usa el script download_comunas.py para obtenerlos automáticamente.")
        sys.exit(1)

    # Cargar GeoJSON
    data = load_geojson(geojson_path)

    # Conectar a MySQL
    engine = create_engine(get_database_url())

    # Procesar cada feature
    count = 0
    for feature in data.get("features", []):
        props = feature.get("properties", {})

        # Extraer código y nombre de comuna
        # Los campos pueden variar según la fuente de datos
        codigo = props.get("cod_comuna") or props.get("CUT_COM") or props.get("codigo_comuna") or props.get("COD_COMUNA")
        nombre = props.get("nom_comuna") or props.get("NOM_COM") or props.get("nombre_comuna") or props.get("COMUNA")
        codigo_region = props.get("cod_region") or props.get("CUT_REG") or props.get("codigo_region") or "13"

        # Solo procesar comunas de la Región Metropolitana (código 13)
        if str(codigo_region) != "13":
            continue

        if not codigo or not nombre:
            print(f"Advertencia: Feature sin código o nombre: {props}")
            continue

        # Convertir geometría a JSON string
        geom_json = json.dumps(feature.get("geometry"))

        try:
            insert_comuna(engine, str(codigo), nombre, geom_json, str(codigo_region))
            count += 1
            print(f"  Cargada: {codigo} - {nombre}")
        except Exception as e:
            print(f"  Error cargando {codigo} - {nombre}: {e}")

    print(f"\nTotal de comunas cargadas: {count}")


if __name__ == "__main__":
    main()
