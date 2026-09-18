"""
Script para descargar los polígonos de comunas de la Región Metropolitana
desde OpenStreetMap usando Overpass API.

Uso:
    python download_comunas.py

Genera el archivo ../data/comunas_rm.geojson
"""

import json
from pathlib import Path

import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Query Overpass para obtener comunas de la Región Metropolitana
# admin_level=8 son comunas en Chile
OVERPASS_QUERY = """
[out:json][timeout:120];
area["name"="Región Metropolitana de Santiago"]["admin_level"="4"]->.rm;
(
  relation["admin_level"="8"]["boundary"="administrative"](area.rm);
);
out body;
>;
out skel qt;
"""


def query_overpass(query: str) -> dict:
    """Ejecutar query en Overpass API."""
    print("Consultando Overpass API...")
    response = requests.post(OVERPASS_URL, data={"data": query}, timeout=180)
    response.raise_for_status()
    return response.json()


def extract_geometry_from_elements(elements: list) -> dict:
    """Convertir elementos de Overpass a diccionarios de nodos y ways."""
    nodes = {}
    ways = {}
    relations = {}

    for el in elements:
        if el["type"] == "node":
            nodes[el["id"]] = (el["lon"], el["lat"])
        elif el["type"] == "way":
            ways[el["id"]] = el.get("nodes", [])
        elif el["type"] == "relation":
            relations[el["id"]] = el

    return nodes, ways, relations


def build_polygon_from_relation(relation: dict, nodes: dict, ways: dict) -> list:
    """Construir polígono desde una relación de Overpass."""
    # Obtener todos los ways que forman el outer boundary
    outer_ways = []
    for member in relation.get("members", []):
        if member["type"] == "way" and member.get("role", "outer") in ["outer", ""]:
            way_id = member["ref"]
            if way_id in ways:
                outer_ways.append(ways[way_id])

    if not outer_ways:
        return None

    # Ordenar y conectar ways para formar un anillo cerrado
    ring = []
    remaining = outer_ways.copy()

    if remaining:
        current = remaining.pop(0)
        ring.extend(current)

        while remaining:
            last_node = ring[-1]
            found = False
            for i, way in enumerate(remaining):
                if way[0] == last_node:
                    ring.extend(way[1:])
                    remaining.pop(i)
                    found = True
                    break
                elif way[-1] == last_node:
                    ring.extend(reversed(way[:-1]))
                    remaining.pop(i)
                    found = True
                    break
            if not found:
                # No se pudo conectar, agregar el siguiente way
                if remaining:
                    current = remaining.pop(0)
                    ring.extend(current)

    # Convertir node IDs a coordenadas
    coords = []
    for node_id in ring:
        if node_id in nodes:
            coords.append(list(nodes[node_id]))

    # Cerrar el anillo si no está cerrado
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])

    return coords


def convert_to_geojson(nodes: dict, ways: dict, relations: dict) -> dict:
    """Convertir relaciones a GeoJSON."""
    features = []

    for rel_id, relation in relations.items():
        tags = relation.get("tags", {})
        name = tags.get("name", "")

        # Extraer código de comuna si está disponible
        ref = tags.get("ref", "")
        wikidata = tags.get("wikidata", "")

        # Construir polígono
        coords = build_polygon_from_relation(relation, nodes, ways)

        if coords and len(coords) >= 4:
            feature = {
                "type": "Feature",
                "properties": {
                    "nombre_comuna": name,
                    "cod_comuna": ref if ref else str(rel_id),
                    "cod_region": "13",
                    "osm_id": rel_id,
                    "wikidata": wikidata
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coords]
                }
            }
            features.append(feature)
            print(f"  Procesada: {name}")

    return {
        "type": "FeatureCollection",
        "features": features
    }


def main():
    output_path = Path(__file__).parent.parent.parent / "data" / "comunas_rm.geojson"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Consultar Overpass
        result = query_overpass(OVERPASS_QUERY)

        # Extraer elementos
        nodes, ways, relations = extract_geometry_from_elements(result.get("elements", []))

        print(f"Encontradas {len(relations)} relaciones (comunas)")

        # Convertir a GeoJSON
        geojson = convert_to_geojson(nodes, ways, relations)

        # Guardar archivo
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)

        print(f"\nArchivo guardado en: {output_path}")
        print(f"Total de comunas: {len(geojson['features'])}")

    except requests.exceptions.RequestException as e:
        print(f"Error de conexión: {e}")
        print("\nAlternativa: Descarga manualmente los datos desde:")
        print("  https://www.bcn.cl/siit/mapas_vectoriales")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
