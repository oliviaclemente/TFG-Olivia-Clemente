from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
import csv


carpeta = Path(__file__).resolve().parent

archivos = list(carpeta.glob("*.kmz")) + list(carpeta.glob("*.kml"))

if not archivos:
    raise FileNotFoundError("No se ha encontrado ningún archivo .kmz o .kml en esta carpeta.")

archivo = archivos[0]

print(f"Leyendo archivo: {archivo.name}")



if archivo.suffix.lower() == ".kmz":
    carpeta_extraida = carpeta / "kmz_extraido"
    carpeta_extraida.mkdir(exist_ok=True)

    with zipfile.ZipFile(archivo, "r") as kmz:
        kmz.extractall(carpeta_extraida)

    kml_path = carpeta_extraida / "doc.kml"

else:
    kml_path = archivo



tree = ET.parse(kml_path)
root = tree.getroot()

ns = {"kml": "http://www.opengis.net/kml/2.2"}

datos = []


def recorrer(elemento, capa_actual=""):
    
    if elemento.tag.endswith("Folder"):
        nombre_folder = elemento.find("kml:name", ns)
        if nombre_folder is not None and nombre_folder.text:
            capa_actual = nombre_folder.text.strip()

    
    if elemento.tag.endswith("Placemark"):
        nombre = elemento.find("kml:name", ns)
        descripcion = elemento.find("kml:description", ns)
        coordenadas = elemento.find(".//kml:coordinates", ns)

        if coordenadas is not None and coordenadas.text:
            coord_texto = coordenadas.text.strip()

            # En KML el orden es: longitud, latitud, altura
            partes = coord_texto.split(",")
            longitud = float(partes[0])
            latitud = float(partes[1])

            datos.append({
                "tipo_contenedor": capa_actual,
                "nombre_punto": nombre.text.strip() if nombre is not None and nombre.text else "",
                "descripcion": descripcion.text.strip() if descripcion is not None and descripcion.text else "",
                "latitud": latitud,
                "longitud": longitud
            })

    for hijo in list(elemento):
        recorrer(hijo, capa_actual)


recorrer(root)



salida_csv = carpeta / "contenedores_coordenadas_para_rutas.csv"

with open(salida_csv, "w", newline="", encoding="utf-8-sig") as f:
    columnas = ["tipo_contenedor", "nombre_punto", "descripcion", "latitud", "longitud"]
    writer = csv.DictWriter(f, fieldnames=columnas)
    writer.writeheader()
    writer.writerows(datos)

