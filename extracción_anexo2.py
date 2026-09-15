from pathlib import Path
import re
import pdfplumber
import pandas as pd

pdf = "20241107_Informe_Informe_Anexos al estudio técnico económico tasa RSU 2025 (1).pdf"

pagina_inicio = 380

filas = []

patron = re.compile(
    r"^(\S+)\s+"                 # N_Fijo
    r"(\S+)\s+"                  # Código VT
    r"([A-Z0-9]{20})\s+"         # Referencia catastral
    r"(\d+)\s+"                  # Aforo
    r"([\d.]+,\d{2})\s+€\s+"     # Valor catastral
    r"([\d,]+)\s+"               # Coeficiente catastral
    r"([\d.]+,\d{2})\s+€\s+"     # Tasa vivienda
    r"(\d+)\s+"                  # Plus vivienda turística
    r"([\d.]+,\d{2})\s+€"        # Tasa total
)

with pdfplumber.open(pdf) as documento:
    for pagina in documento.pages[pagina_inicio - 1:]:
        texto = pagina.extract_text() or ""

        if "PROPUESTA TASA VIVIENDAS TURÍSTICAS 2025" not in texto:
            continue

        for linea in texto.splitlines():
            linea = linea.strip()
            m = patron.match(linea)

            if m:
                filas.append({
                    "N_Fijo": m.group(1),
                    "CODIGO_VT": m.group(2),
                    "Ref_Catastral_Fin": m.group(3),
                    "AFORO": int(m.group(4)),
                    "VALORCATASTRAL": m.group(5),
                    "COEFICIENTE_CATASTRAL": m.group(6),
                    "TASA_VIVIENDA": m.group(7),
                    "PLUS_VIVIENDA_TURISTICA": int(m.group(8)),
                    "TASA_TOTAL": m.group(9),
                })

df = pd.DataFrame(filas)

def numero(x):
    return pd.to_numeric(
        str(x).replace(".", "").replace(",", "."),
        errors="coerce"
    )

for col in ["VALORCATASTRAL", "COEFICIENTE_CATASTRAL", "TASA_VIVIENDA", "TASA_TOTAL"]:
    df[col + "_NUM"] = df[col].apply(numero)

df["FINCA"] = df["Ref_Catastral_Fin"].str[:7]
df["HOJA"] = df["Ref_Catastral_Fin"].str[7:14]
df["INMUEBLE"] = df["Ref_Catastral_Fin"].str[14:18]
df["CONTROL"] = df["Ref_Catastral_Fin"].str[18:20]
df["HOJA_BASE"] = df["HOJA"].str[:6]

zonas = {}

for h in ["BC5931","BC5932","BC5933","BC5934","BC5935","BC5936","BC5937","BC5938","BC5942","BC5943","BC5944","BC5945","BC5946","BC5947","BC5948"]:
    zonas[h] = "Casco urbano / Pueblo"

for h in ["BC5950","BC5951","BC5952","BC5953","BC5954","BC5955","BC5956","BC5957","BC5958"]:
    zonas[h] = "Arenal / Canal / Montañar"

for h in ["BC5960","BC5961","BC5962","BC5963","BC5964","BC5965"]:
    zonas[h] = "Puerto / Aduanas"

for h in ["BC5900","BC5905","BC5907","BC5908","BC5912","BC5913","BC5914","BC5915","BC5916","BC5917","BC5918"]:
    zonas[h] = "Montgó / Toscamar"

for h in ["BC5922","BC5923","BC5924","BC5925","BC5926","BC5927","BC5928"]:
    zonas[h] = "Rafalet / Lluca / Covatelles"

for h in ["BC5970","BC5971","BC5972","BC5973"]:
    zonas[h] = "Tosalet / Cap Martí"

for h in ["BC5974","BC5980","BC5981"]:
    zonas[h] = "Portitxol / Toscal / Trencall"

for h in ["BC5982","BC5983","BC5984","BC5990","BC5991","BC5992","BC5993"]:
    zonas[h] = "Costa Nova / Balcón al Mar / Ambolo"

for h in ["BC4955","BC4988","BC4989","BC4997","BC4998","BC4999","BC4889"]:
    zonas[h] = "Les Fonts / Castellans"

df["ZONA"] = df["HOJA_BASE"].map(zonas).fillna("Sin clasificar / revisar")

resumen_zonas = (
    df.groupby("ZONA", as_index=False)
    .agg(
        VIVIENDAS_TURISTICAS=("CODIGO_VT", "count"),
        AFORO_TOTAL=("AFORO", "sum"),
        VALOR_CATASTRAL_TOTAL=("VALORCATASTRAL_NUM", "sum"),
        TASA_VIVIENDA_TOTAL=("TASA_VIVIENDA_NUM", "sum"),
        PLUS_TURISTICO_TOTAL=("PLUS_VIVIENDA_TURISTICA", "sum"),
        TASA_TOTAL=("TASA_TOTAL_NUM", "sum")
    )
    .sort_values("VIVIENDAS_TURISTICAS", ascending=False)
)

resumen_aforo = (
    df.groupby("AFORO", as_index=False)
    .agg(
        VIVIENDAS_TURISTICAS=("CODIGO_VT", "count"),
        TASA_TOTAL=("TASA_TOTAL_NUM", "sum")
    )
    .sort_values("AFORO")
)

df.to_csv("vivienda_turistica_p380.csv", index=False, encoding="utf-8-sig")
df.to_excel("vivienda_turistica_p380.xlsx",index=False)