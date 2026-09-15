import pandas as pd
import geopandas as gpd
import requests
import xml.etree.ElementTree as ET
import time
import os

from shapely.geometry import Point
from tqdm import tqdm

ARCHIVO_EXCEL = "vivienda_turistica_p380-1.xlsx"

ARCHIVO_SALIDA = "vivienda_turistica_p380-1_con_zonas.xlsx"
ARCHIVO_CACHE_GENERAL = "coordenadas_catastro.csv"

ARCHIVO_CACHE_TURISTICAS = "coordenadas_catastro_turisticas.csv"

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

    cache["REF_PARCELA"] = (
        cache["REF_PARCELA"]
        .astype("string")
        .str.strip()
    )

    cache["X"] = pd.to_numeric(
        cache["X"],
        errors="coerce"
    )

    cache["Y"] = pd.to_numeric(
        cache["Y"],
        errors="coerce"
    )

    cache["ZONA"] = pd.to_numeric(
        cache["ZONA"],
        errors="coerce"
    ).astype("Int64")

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
    sheet_name=0,
    dtype={COLUMNA_REFERENCIA: str}
)

print("Número de registros turísticos:", len(df))

if COLUMNA_REFERENCIA not in df.columns:
    raise ValueError(
        f"No existe la columna '{COLUMNA_REFERENCIA}'. "
        f"Columnas disponibles: {list(df.columns)}"
    )


df["REF_PARCELA"] = (
    df[COLUMNA_REFERENCIA]
    .astype("string")
    .str.strip()
    .str[:14]
)


referencias_unicas = (
    df["REF_PARCELA"]
    .dropna()
    .loc[
        lambda s: s.str.len() == 14
    ]
    .drop_duplicates()
    .tolist()
)

print(
    "\nParcelas turísticas únicas:",
    len(referencias_unicas)
)


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

        root = ET.fromstring(
            respuesta.content
        )

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
            return (
                None,
                None,
                direccion,
                "SIN_COORDENADAS"
            )

        x = float(
            x.replace(",", ".")
        )

        y = float(
            y.replace(",", ".")
        )

        if x == 0 and y == 0:
            return (
                None,
                None,
                direccion,
                "COORDENADAS_INVALIDAS"
            )

        return (
            x,
            y,
            direccion,
            "OK"
        )

    except Exception as e:

        return (
            None,
            None,
            None,
            str(e)
        )


if os.path.exists(
    ARCHIVO_CACHE_GENERAL
):


    cache = pd.read_csv(
        ARCHIVO_CACHE_GENERAL,
        dtype={
            "REF_PARCELA": str
        }
    )

else:

    print(
        "\nNo existe coordenadas_catastro.csv. "
        "Se creará desde cero."
    )

    cache = pd.DataFrame(
        columns=COLUMNAS_CACHE
    )


cache = preparar_cache(
    cache
)


ya_consultadas = set(
    cache.loc[
        cache[
            "ESTADO_CATASTRO"
        ].isin(
            [
                "OK",
                "SIN_COORDENADAS"
            ]
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


print(
    "\nParcelas turísticas ya disponibles en cache:",
    len(referencias_unicas) - len(pendientes)
)

print(
    "Parcelas turísticas pendientes:",
    len(pendientes)
)


nuevos_resultados = []

for ref in tqdm(
    pendientes,
    desc="Consultando Catastro"
):

    x, y, direccion, estado = (
        obtener_coordenadas(ref)
    )


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
                pd.DataFrame(
                    nuevos_resultados
                )
            ],
            ignore_index=True
        )

        temporal = preparar_cache(
            temporal
        )

        temporal.to_csv(
            ARCHIVO_CACHE_GENERAL,
            index=False,
            encoding="utf-8-sig"
        )


if nuevos_resultados:

    cache = pd.concat(
        [
            cache,
            pd.DataFrame(
                nuevos_resultados
            )
        ],
        ignore_index=True
    )

    cache = preparar_cache(
        cache
    )

    cache.to_csv(
        ARCHIVO_CACHE_GENERAL,
        index=False,
        encoding="utf-8-sig"
    )


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

    if (
        pd.notna(x)
        and pd.notna(y)
    ):

        geometry.append(
            Point(
                float(x),
                float(y)
            )
        )

    else:

        geometry.append(
            None
        )


viviendas = gpd.GeoDataFrame(
    df,
    geometry=geometry,
    crs="EPSG:4326"
)


url_ine = (
    "https://www.ine.es/geoserver/"
    "ogc/features/v1/"
    "collections/"
    "WMS_INE_SECCIONES_G01:"
    "Secciones_2025/"
    "items"
)

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

zonas = (
    gpd.GeoDataFrame
    .from_features(
        datos_ine["features"],
        crs="EPSG:4326"
    )
)


zonas["CUMUN"] = (
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

zonas = zonas[
    zonas["CUMUN"] == "03082"
].copy()


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

zonas["ZONA"] = (
    zonas["CUSEC"]
    .map(mapa_zonas)
)

zonas = zonas[
    zonas["ZONA"].notna()
].copy()

zonas["ZONA"] = (
    zonas["ZONA"]
    .astype(int)
)

print("\nZonas obtenidas:")

print(
    zonas[
        [
            "CUSEC",
            "ZONA"
        ]
    ]
    .sort_values("ZONA")
)


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
    viviendas,
    zonas[
        [
            "ZONA",
            "geometry"
        ]
    ],
    how="left",
    predicate="within"
)

if "index_right" in resultado.columns:

    resultado = resultado.drop(
        columns=[
            "index_right"
        ]
    )

resultado["ZONA"] = (
    pd.to_numeric(
        resultado["ZONA"],
        errors="coerce"
    )
    .astype("Int64")
)


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
    .set_index(
        "REF_PARCELA"
    )["ZONA"]
)

zona_nueva = (
    cache["REF_PARCELA"]
    .map(
        zona_por_parcela
    )
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

cache = preparar_cache(
    cache
)

cache.to_csv(
    ARCHIVO_CACHE_GENERAL,
    index=False,
    encoding="utf-8-sig"
)


cache_turisticas = (
    cache[
        cache[
            "REF_PARCELA"
        ].isin(
            referencias_unicas
        )
    ]
    .copy()
)

cache_turisticas = (
    cache_turisticas[
        COLUMNAS_CACHE
    ]
)

cache_turisticas.to_csv(
    ARCHIVO_CACHE_TURISTICAS,
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
    "\nRegistros turísticos sin zona:",
    len(sin_zona)
)

sin_coordenadas = resultado[
    resultado["X"].isna()
    | resultado["Y"].isna()
]

print(
    "Registros turísticos sin coordenadas:",
    len(sin_coordenadas)
)

con_coordenadas_sin_zona = resultado[
    resultado["X"].notna()
    & resultado["Y"].notna()
    & resultado["ZONA"].isna()
]

print(
    "Con coordenadas pero fuera de las 12 zonas:",
    len(
        con_coordenadas_sin_zona
    )
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

print(
    "\nParcelas turísticas únicas sin coordenadas:",
    len(
        parcelas_sin_coordenadas
    )
)

if len(parcelas_sin_coordenadas) > 0:

    print(
        "\nPrimeras referencias problemáticas:"
    )

    print(
        parcelas_sin_coordenadas
        .head(20)
        .to_string(
            index=False
        )
    )



columnas_diagnostico = [
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
    ].to_string(
        index=False
    )
)

