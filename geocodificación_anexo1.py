import pandas as pd
import geopandas as gpd
import requests
import xml.etree.ElementTree as ET
import time
import os

from shapely.geometry import Point
from tqdm import tqdm



ARCHIVO_EXCEL = "datos_rsu_2025.xlsx"
ARCHIVO_SALIDA = "datos_rsu_2025_con_zonas.xlsx"
ARCHIVO_CACHE = "coordenadas_catastro.csv"

COLUMNA_REFERENCIA = "Ref_Catastral_Fin"
SRS = "EPSG:4326"

COLUMNAS_CACHE = [
    "REF_PARCELA",
    "X",
    "Y",
    "DIRECCION_CATASTRO",
    "ESTADO_CATASTRO",
    "ZONA"
]


def preparar_cache(cache):

    for columna in COLUMNAS_CACHE:
        if columna not in cache.columns:
            cache[columna] = pd.NA

    cache = cache[COLUMNAS_CACHE].copy()

    # Normalizar referencia catastral
    cache["REF_PARCELA"] = (
        cache["REF_PARCELA"]
        .astype("string")
        .str.strip()
    )

    cache["X"] = pd.to_numeric(cache["X"], errors="coerce")
    cache["Y"] = pd.to_numeric(cache["Y"], errors="coerce")

    cache["ZONA"] = pd.to_numeric(
        cache["ZONA"],
        errors="coerce"
    ).astype("Int64")

    # Si Catastro devolvió (0,0), esas coordenadas no son válidas
    mascara_cero = (
        (cache["X"] == 0)
        & (cache["Y"] == 0)
    )

    cache.loc[
        mascara_cero,
        "ESTADO_CATASTRO"
    ] = "COORDENADAS_INVALIDAS"

    cache.loc[
        mascara_cero,
        ["X", "Y"]
    ] = pd.NA

    cache.loc[
        mascara_cero,
        "ZONA"
    ] = pd.NA

    cache = cache.drop_duplicates(
        subset="REF_PARCELA",
        keep="last"
    )

    return cache



df = pd.read_excel(
    ARCHIVO_EXCEL,
    sheet_name="Sheet1"
)

print("Número de registros:", len(df))


df["REF_PARCELA"] = (
    df[COLUMNA_REFERENCIA]
    .astype("string")
    .str.strip()
    .str[:14]
)

print(
    df[
        [COLUMNA_REFERENCIA, "REF_PARCELA"]
    ].head()
)


referencias_unicas = (
    df["REF_PARCELA"]
    .dropna()
    .loc[lambda s: s.str.len() == 14]   #eliminar duplicados
    .drop_duplicates()
    .tolist()
)

print("\nParcelas únicas:", len(referencias_unicas))


def obtener_coordenadas(refcat):

    url = (
        "https://ovc.catastro.meh.es/"
        "ovcservweb/ovcswlocalizacionrc/"
        "ovccoordenadas.asmx/Consulta_CPMRC"
    )

    parametros = {
        "Provincia": "",
        "Municipio": "",
        "SRS": SRS,
        "RC": refcat
    }

    try:

        respuesta = requests.get(
            url,
            params=parametros,
            timeout=30
        )

        respuesta.raise_for_status()
        root = ET.fromstring(respuesta.content)

        x = None
        y = None
        direccion = None

        for elemento in root.iter():

            etiqueta = elemento.tag.split("}")[-1]

            if etiqueta == "xcen":
                x = elemento.text

            elif etiqueta == "ycen":
                y = elemento.text

            elif etiqueta == "ldt":
                direccion = elemento.text

        if x is None or y is None:
            return None, None, direccion, "SIN_COORDENADAS"

        x = float(x.replace(",", "."))
        y = float(y.replace(",", "."))

        if x == 0 and y == 0:
            return None, None, direccion, "COORDENADAS_INVALIDAS"

        return (
            x,
            y,
            direccion,
            "OK"
        )

    except Exception as e:

        return None, None, None, str(e)


if os.path.exists(ARCHIVO_CACHE):

    print("\nCargando coordenadas previamente obtenidas...")

    cache = pd.read_csv(
        ARCHIVO_CACHE,
        dtype={"REF_PARCELA": str}
    )

else:

    cache = pd.DataFrame(
        columns=COLUMNAS_CACHE
    )


cache = preparar_cache(cache)

cache.to_csv(
    ARCHIVO_CACHE,
    index=False,
    encoding="utf-8-sig"
)


ya_consultadas = set(
    cache.loc[
        cache["ESTADO_CATASTRO"].isin(
            ["OK", "SIN_COORDENADAS"]
        ),
        "REF_PARCELA"
    ]
    .dropna()
    .astype(str)
    .tolist()
)


pendientes = [
    ref
    for ref in referencias_unicas
    if ref not in ya_consultadas
]

print("\nParcelas pendientes:", len(pendientes))


nuevos_resultados = []

for ref in tqdm(
    pendientes,
    desc="Consultando Catastro"
):

    x, y, direccion, estado = obtener_coordenadas(ref)

    nuevos_resultados.append({
        "REF_PARCELA": ref,
        "X": x,
        "Y": y,
        "DIRECCION_CATASTRO": direccion,
        "ESTADO_CATASTRO": estado,
        "ZONA": pd.NA
    })

    time.sleep(0.25)

    if len(nuevos_resultados) % 50 == 0:

        temporal = pd.concat(
            [
                cache,
                pd.DataFrame(nuevos_resultados)
            ],
            ignore_index=True
        )

        temporal = preparar_cache(temporal)

        temporal.to_csv(
            ARCHIVO_CACHE,
            index=False,
            encoding="utf-8-sig"
        )


if nuevos_resultados:

    cache = pd.concat(
        [
            cache,
            pd.DataFrame(nuevos_resultados)
        ],
        ignore_index=True
    )

    cache = preparar_cache(cache)

    cache.to_csv(
        ARCHIVO_CACHE,
        index=False,
        encoding="utf-8-sig"
    )

#coordenadas

df = df.merge(
    cache[
        [
            "REF_PARCELA",
            "X",
            "Y",
            "DIRECCION_CATASTRO",
            "ESTADO_CATASTRO"
        ]
    ],
    on="REF_PARCELA",
    how="left"
)


geometry = []

for x, y in zip(
    df["X"],
    df["Y"]
):

    if pd.notna(x) and pd.notna(y):

        geometry.append(
            Point(float(x), float(y))
        )

    else:

        geometry.append(None)


parcelas = gpd.GeoDataFrame(
    df,
    geometry=geometry,
    crs="EPSG:4326"
)


print("\nDescargando secciones censales del INE...")

url_ine = (
    "https://www.ine.es/geoserver/ogc/features/v1/"
    "collections/"
    "WMS_INE_SECCIONES_G01:Secciones_2025/"
    "items"
)

#caja geográfica que contiene Xàbia
parametros_ine = {
    "f": "application/geo+json",
    "bbox": "0.10,38.70,0.26,38.86",
    "limit": 100
}

respuesta = requests.get(
    url_ine,
    params=parametros_ine,
    timeout=60
)

respuesta.raise_for_status()

datos_ine = respuesta.json()

zonas = gpd.GeoDataFrame.from_features(
    datos_ine["features"],
    crs="EPSG:4326"
)


zonas["CUMUN"] = (       #normalizar
    zonas["CUMUN"]
    .astype(str)
    .str.strip()
    .str.zfill(5)
)

zonas["CUSEC"] = (
    zonas["CUSEC"]
    .astype(str)
    .str.strip()
    .str.zfill(10)
)


# INE de Xàbia= 03082
zonas = zonas[
    zonas["CUMUN"] == "03082"
].copy()


print("\nTODAS LAS SECCIONES DE XÀBIA:")

print(
    zonas["CUSEC"]
    .sort_values()
    .to_string(index=False)
)

mapa_zonas = {      

    "0308203004": 1,
    "0308202002": 2,
    "0308201002": 3,
    "0308201001": 4,
    "0308201003": 5,
    "0308203002": 6,
    "0308203003": 7,
    "0308201004": 8,
    "0308202001": 9,
    "0308202003": 10,
    "0308203005": 11,
    "0308203001": 12

}


# número de zona
zonas["ZONA"] = zonas["CUSEC"].map(mapa_zonas)

zonas = zonas[
    zonas["ZONA"].notna()
].copy()


zonas["ZONA"] = zonas["ZONA"].astype(int)


# Comprobación
if len(zonas) != 12:

    print(
        "\nADVERTENCIA: se esperaban 12 zonas "
        "y se han encontrado",
        len(zonas)
    )

else:

    print(
        "\nPerfecto: se han encontrado las 12 zonas."
    )


resultado = gpd.sjoin(
    parcelas,
    zonas[
        [
            "ZONA",
            "geometry"
        ]
    ],
    how="left",
    predicate="within"
)

if "index_right" in resultado.columns:      #no columna aux

    resultado = resultado.drop(
        columns=["index_right"]
    )


resultado["ZONA"] = pd.to_numeric(
    resultado["ZONA"],
    errors="coerce"
).astype("Int64")

zona_por_parcela = (
    resultado[
        [
            "REF_PARCELA",
            "ZONA"
        ]
    ]
    .dropna(
        subset=[
            "REF_PARCELA",
            "ZONA"
        ]
    )
    .drop_duplicates(
        subset="REF_PARCELA",
        keep="first"
    )
    .set_index("REF_PARCELA")["ZONA"]
)


zona_nueva = cache["REF_PARCELA"].map(
    zona_por_parcela
)

cache["ZONA"] = (
    pd.to_numeric(
        zona_nueva,
        errors="coerce"
    )
    .combine_first(
        pd.to_numeric(
            cache["ZONA"],
            errors="coerce"
        )
    )
    .astype("Int64")
)


cache = preparar_cache(cache)

cache.to_csv(
    ARCHIVO_CACHE,
    index=False,
    encoding="utf-8-sig"
)


print(
    resultado["ZONA"]
    .value_counts(
        dropna=False
    )
    .sort_index()
)


sin_zona = resultado[
    resultado["ZONA"].isna()
]

print(
    "\nRegistros sin zona:",
    len(sin_zona)
)


sin_coordenadas = resultado[
    resultado["X"].isna()
    | resultado["Y"].isna()
]

print(
    "Registros sin coordenadas de Catastro:",
    len(sin_coordenadas)
)


con_coordenadas_sin_zona = resultado[
    resultado["X"].notna()
    & resultado["Y"].notna()
    & resultado["ZONA"].isna()
]

print(
    "Con coordenadas pero fuera de las 12 zonas:",
    len(con_coordenadas_sin_zona)
)


resultado_excel = pd.DataFrame(
    resultado.drop(
        columns="geometry"
    )
)

resultado_excel.to_excel(
    ARCHIVO_SALIDA,
    index=False
)

parcelas_sin_coordenadas = (
    resultado.loc[
        resultado["X"].isna()
        | resultado["Y"].isna(),
        "REF_PARCELA"
    ]
    .dropna()
    .drop_duplicates()
)


columnas_diagnostico = [       #coordenads pero sin zona 
    COLUMNA_REFERENCIA,
    "REF_PARCELA",
    "X",
    "Y",
    "DIRECCION_CATASTRO",
    "ESTADO_CATASTRO"
]

print(
    resultado.loc[
        resultado["X"].notna()
        & resultado["Y"].notna()
        & resultado["ZONA"].isna(),
        columnas_diagnostico
    ].to_string(index=False)
)
