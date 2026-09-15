import pdfplumber        
import pandas as pd
import re

pdf_path = "20241107_Informe_Informe_Anexos al estudio técnico económico tasa RSU 2025 (1).pdf"

filas = []

#Define el patrón de las filas que quiere encontrar
patron = re.compile(
    r"^(\S+)\s+(\S+)\s+(-|\d{1,3}(?:\.\d{3})*,\d{2})\s*€?\s+([\d,]+)\s+(\d{1,3}(?:\.\d{3})*,\d{2})\s*€?"
)

with pdfplumber.open(pdf_path) as pdf:
    for num_pagina, page in enumerate(pdf.pages, start=1):
        texto = page.extract_text()         #extraer texto de cada página
        if not texto:
            continue

        for linea in texto.split("\n"):     #filas
            linea = linea.strip()

            match = patron.match(linea)
            if match:                       #guarda las filas separadas en columnas
                n_fijo, ref_catastral, valor_catastral, coeficiente, tasa_total = match.groups()

                filas.append({
                    "pagina": num_pagina,
                    "N_Fijo": n_fijo,
                    "Ref_Catastral_Fin": ref_catastral,
                    "VALORCATASTRAL": valor_catastral,
                    "COEFICIENTE_CATASTRAL": coeficiente,
                    "TASA_TOTAL": tasa_total
                })

df = pd.DataFrame(filas)

df.to_csv("datos_rsu_2025.csv", index=False, encoding="utf-8-sig")
df.to_excel("datos_rsu_2025.xlsx", index=False)


df = pd.read_csv("datos_rsu_2025.csv")
print(df['Ref_Catastral_Fin'].head(10).tolist())
