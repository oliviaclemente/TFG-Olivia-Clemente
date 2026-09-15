"""
desarrollo_seccion_3_6.py
============================
Seccion3.6:redviaria+contenedores+calibracionfinalusandolas
tablasdeviviendaordinariayrusticageneradasporgeocodificacion
real(Tabla_ordinaria_definitiva.xlsx,Tabla_rustica_definitiva.xlsx).
"""
import struct
import math
import csv
import numpy as np
import networkx as nx
from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.metrics import r2_score
from scipy.spatial import ConvexHull
from scipy import stats
import pandas as pd
import openpyxl

SHP_PATH = "Tramo_Vial_Septiembre_2025_25831.shp"
CONT_CSV = "contenedores_coordenadas_para_rutas.csv"
TABLA_ORDINARIA = "Tabla_ordinaria_definitiva.xlsx"
TABLA_RUSTICA = "Tabla_rustica_definitiva.xlsx"


def leer_shapefile_polylines(path):
    with open(path, 'rb') as f:
        f.read(100)
        polylines = []
        while True:
            rec_header = f.read(8)
            if len(rec_header) < 8:
                break
            rec_num, content_len_words = struct.unpack('>ii', rec_header)
            content = f.read(content_len_words * 2)
            shape_type = struct.unpack('<i', content[0:4])[0]
            if shape_type == 0:
                continue
            num_parts, num_points = struct.unpack('<ii', content[36:44])
            parts_idx = list(struct.unpack(f'<{num_parts}i', content[44:44 + 4 * num_parts]))
            pts_start = 44 + 4 * num_parts
            points = struct.unpack(f'<{2 * num_points}d', content[pts_start:pts_start + 16 * num_points])
            coords = [(points[2 * i], points[2 * i + 1]) for i in range(num_points)]
            parts_idx = parts_idx + [num_points]
            for i in range(num_parts):
                polylines.append(coords[parts_idx[i]:parts_idx[i + 1]])
    return polylines


polylines = leer_shapefile_polylines(SHP_PATH)
print(f"[1/8] Red viaria: {len(polylines)} tramos (EPSG:25831, leido de .shp)")

G = nx.Graph()
for coords in polylines:
    for i in range(len(coords) - 1):
        a, b = coords[i], coords[i + 1]
        dist = math.hypot(a[0] - b[0], a[1] - b[1])
        if dist > 0:
            G.add_edge(a, b, weight=dist)
print(f"      Grafo: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")


def latlon_a_utm31n(lat, lon):
    a = 6378137.0
    f = 1 / 298.257222101
    k0 = 0.9996
    lon0 = math.radians(3.0)
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    lat_r = math.radians(lat)
    lon_r = math.radians(lon)
    N = a / math.sqrt(1 - e2 * math.sin(lat_r) ** 2)
    T = math.tan(lat_r) ** 2
    C = ep2 * math.cos(lat_r) ** 2
    A = (lon_r - lon0) * math.cos(lat_r)
    M = a * (
        (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * lat_r
        - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * math.sin(2 * lat_r)
        + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * math.sin(4 * lat_r)
        - (35 * e2 ** 3 / 3072) * math.sin(6 * lat_r)
    )
    x = k0 * N * (A + (1 - T + C) * A ** 3 / 6 + (5 - 18 * T + T ** 2 + 72 * C - 58 * ep2) * A ** 5 / 120) + 500000
    y = k0 * (M + N * math.tan(lat_r) * (A ** 2 / 2 + (5 - T + 9 * C + 4 * C ** 2) * A ** 4 / 24
              + (61 - 58 * T + T ** 2 + 600 * C - 330 * ep2) * A ** 6 / 720))
    return x, y


contenedores = []
with open(CONT_CSV, encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        lat, lon = float(row['latitud']), float(row['longitud'])
        x, y = latlon_a_utm31n(lat, lon)
        contenedores.append({'x': x, 'y': y})

nodes = list(G.nodes)
node_arr = np.array(nodes)


def nearest_node(x, y):
    d2 = (node_arr[:, 0] - x) ** 2 + (node_arr[:, 1] - y) ** 2
    return nodes[int(d2.argmin())]


for c in contenedores:
    c['snap_node'] = nearest_node(c['x'], c['y'])

print(f"[2/8] Contenedores cargados y ajustados a la red: {len(contenedores)}")

unique_nodes = list(set(c['snap_node'] for c in contenedores))
dist_dict = {src: nx.single_source_dijkstra_path_length(G, src, weight="weight")
             for src in unique_nodes}


def real_distance(node_a, node_b):
    return dist_dict[node_a].get(node_b, np.inf)


n = len(contenedores)
dist_matrix = np.zeros((n, n))
snap_nodes = [c['snap_node'] for c in contenedores]
coords_xy = np.array([[c['x'], c['y']] for c in contenedores])

for i in range(n):
    for j in range(i + 1, n):
        d = real_distance(snap_nodes[i], snap_nodes[j])
        dist_matrix[i, j] = dist_matrix[j, i] = d

eucl = np.sqrt(((coords_xy[:, None, :] - coords_xy[None, :, :]) ** 2).sum(axis=2))
mask_inf = np.isinf(dist_matrix)
print(f"[3/8] Distancias reales calculadas. Pares sin conexion: "
      f"{100 * mask_inf.sum() / mask_inf.size:.2f}% sustituidos por distancia recta")
dist_matrix = np.where(mask_inf, eucl, dist_matrix)

km = KMeans(n_clusters=12, random_state=42, n_init=10)
zona_operativa = km.fit_predict(coords_xy)


def nearest_neighbor_tour(d):
    nloc = len(d)
    visited = [False] * nloc
    tour = [0]
    visited[0] = True
    for _ in range(nloc - 1):
        last = tour[-1]
        _, nxt = min((d[last, j], j) for j in range(nloc) if not visited[j])
        tour.append(nxt)
        visited[nxt] = True
    return tour


def tour_length(tour, d):
    return sum(d[tour[i], tour[i + 1]] for i in range(len(tour) - 1))


def two_opt(tour, d, max_iter=150):
    improved = True
    it = 0
    nloc = len(tour)
    while improved and it < max_iter:
        improved = False
        it += 1
        for i in range(1, nloc - 2):
            for j in range(i + 1, nloc - 1):
                a, b, c, e = tour[i - 1], tour[i], tour[j], tour[j + 1]
                delta = (d[a, c] + d[b, e]) - (d[a, b] + d[c, e])
                if delta < -1e-9:
                    tour[i:j + 1] = tour[i:j + 1][::-1]
                    improved = True
    return tour


resultados_zona = []
for z in sorted(set(zona_operativa)):
    idx = [i for i in range(n) if zona_operativa[i] == z]
    sub = dist_matrix[np.ix_(idx, idx)]
    tour = two_opt(nearest_neighbor_tour(sub), sub)
    km_ruta = tour_length(tour, sub) / 1000
    pts = coords_xy[idx]
    area_ha = ConvexHull(pts).volume / 10000
    densidad_op = len(idx) / area_ha
    resultados_zona.append({
        "n": len(idx), "km_ruta": km_ruta,
        "coste_m_por_contenedor": km_ruta * 1000 / len(idx),
        "densidad_operativa": densidad_op,
    })

df_zonas = pd.DataFrame(resultados_zona)
print(f"[4/8] Rutas reales calculadas por zona operativa (12 zonas)")

X_coste = np.log(df_zonas[["densidad_operativa"]].values)
y_coste_log = np.log(df_zonas["coste_m_por_contenedor"].values)
modelo_coste = LinearRegression().fit(X_coste, y_coste_log)
y_pred_loo_coste = cross_val_predict(LinearRegression(), X_coste, y_coste_log, cv=LeaveOneOut())
r2_loo_coste = r2_score(y_coste_log, y_pred_loo_coste)
print(f"[5/8] Modelo coste operativo: coste = {np.exp(modelo_coste.intercept_):.2f} "
      f"* densidad_op^({modelo_coste.coef_[0]:.4f})  |  R2 LOO-CV = {r2_loo_coste:.4f}")

def cargar_tabla(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Tabla"]
    filas = list(ws.iter_rows(min_row=2, values_only=True))
    datos = {}
    for row in filas:
        sec = row[0]
        if sec == "TOTAL" or sec is None:
            continue
        registros, tasa_media = row[4], row[5]
        datos[int(sec)] = {"n": registros, "tasa_total": registros * tasa_media}
    return datos


datos_ordinaria = cargar_tabla(TABLA_ORDINARIA)
datos_rustica = cargar_tabla(TABLA_RUSTICA)

viviendas_por_seccion = {}
tasa_por_seccion = {}
for s in range(1, 13):
    n_o = datos_ordinaria.get(s, {}).get("n", 0)
    t_o = datos_ordinaria.get(s, {}).get("tasa_total", 0.0)
    n_r = datos_rustica.get(s, {}).get("n", 0)
    t_r = datos_rustica.get(s, {}).get("tasa_total", 0.0)
    viviendas_por_seccion[s] = n_o + n_r
    tasa_por_seccion[s] = t_o + t_r

print(f"[6/8] Vivienda ordinaria + rustica combinada, geocodificada: "
      f"{sum(viviendas_por_seccion.values())} registros, "
      f"{sum(tasa_por_seccion.values()):.2f} EUR")

SECCIONES_DATA = {
    1: (4218, 38556426.12), 2: (2240, 4256494.41), 3: (1222, 157800.96), 4: (1701, 157522.67),
    5: (1865, 117509.31), 6: (3089, 961499.01), 7: (2271, 1159982.56), 8: (2950, 380387.66),
    9: (2166, 331746.93), 10: (992, 230557.62), 11: (3931, 2144885.44), 12: (4172, 20292089.52),
}
secciones = list(range(1, 13))
densidad = np.array([SECCIONES_DATA[s][0] / (SECCIONES_DATA[s][1] / 10000) for s in secciones])
ocupacion = np.array([SECCIONES_DATA[s][0] / viviendas_por_seccion[s] for s in secciones])

x = np.log(densidad)
y = np.log(ocupacion)
n_obs = len(x)
x_bar = x.mean()
Sxx = np.sum((x - x_bar) ** 2)
b1 = np.sum((x - x_bar) * (y - y.mean())) / Sxx
a1 = y.mean() - b1 * x_bar
residuos = y - (a1 + b1 * x)
s_resid = np.sqrt(np.sum(residuos ** 2) / (n_obs - 2))
t_crit = stats.t.ppf(0.975, df=n_obs - 2)
se_b1 = s_resid / np.sqrt(Sxx)
ic_low, ic_high = b1 - t_crit * se_b1, b1 + t_crit * se_b1
r2_full = 1 - np.sum(residuos ** 2) / np.sum((y - y.mean()) ** 2)

y_pred_loo = np.zeros(n_obs)
for i in range(n_obs):
    xi, yi = np.delete(x, i), np.delete(y, i)
    xi_bar = xi.mean()
    Sxxi = np.sum((xi - xi_bar) ** 2)
    bi = np.sum((xi - xi_bar) * (yi - yi.mean())) / Sxxi
    ai = yi.mean() - bi * xi_bar
    y_pred_loo[i] = ai + bi * x[i]
r2_loo = 1 - np.sum((y - y_pred_loo) ** 2) / np.sum((y - y.mean()) ** 2)
t_stat = b1 / se_b1
p_valor = 2 * (1 - stats.t.cdf(abs(t_stat), df=n_obs - 2))
ocupacion_pred = {secciones[i]: np.exp(a1 + b1 * x[i]) for i in range(n_obs)}

print(f"\n[7/8] Modelo de ocupacion (log-log, datos geocodificados):")
print(f"      b1 = {b1:.4f}  IC95% = [{ic_low:.4f}, {ic_high:.4f}]")
print(f"      R2 completo = {r2_full:.4f}   R2 LOO-CV = {r2_loo:.4f}")
print(f"      t = {t_stat:.3f}   p = {p_valor:.5f}")

total_habitantes = sum(v[0] for v in SECCIONES_DATA.values())
factor_conversion = len(contenedores) / total_habitantes

coste_pred = {}
for s in secciones:
    hab, area = SECCIONES_DATA[s]
    densidad_pob = hab / (area / 10000)
    dens_cont_estim = densidad_pob * factor_conversion
    coste_pred[s] = np.exp(modelo_coste.intercept_) * dens_cont_estim ** modelo_coste.coef_[0]
coste_medio = np.mean(list(coste_pred.values()))
coste_idx = {s: coste_pred[s] / coste_medio for s in secciones}

total_actual = sum(tasa_por_seccion.values())
total_viviendas = sum(viviendas_por_seccion.values())

cuota_fija = 0.50 * total_actual / total_viviendas
suma_pond_ocup = sum(viviendas_por_seccion[s] * ocupacion_pred[s] for s in secciones)
k1 = 0.25 * total_actual / suma_pond_ocup
suma_pond_coste = sum(viviendas_por_seccion[s] * coste_idx[s] for s in secciones)
k2 = 0.25 * total_actual / suma_pond_coste

print(f"\n[8/8] Calibracion final:")
print(f"      F = {cuota_fija:.2f} EUR | k1 = {k1:.3f} | k2 = {k2:.3f}")
print(f"\n{'Sección':<9}{'Tasa actual (€)':<18}{'Tasa NUEVA (€)':<18}{'Diferencia (€)'}")

total_nuevo = 0
for s in secciones:
    v = viviendas_por_seccion[s]
    actual = tasa_por_seccion[s] / v
    nueva_total = v * cuota_fija + v * ocupacion_pred[s] * k1 + v * coste_idx[s] * k2
    nueva = nueva_total / v
    total_nuevo += nueva_total
    print(f"{s:<9}{actual:<18.2f}{nueva:<18.2f}{nueva - actual:+.2f}")

print(f"\nVerificación R1 - Total actual: {total_actual:.2f} € | Total nuevo: {total_nuevo:.2f} € "
      f"| Diferencia: {total_nuevo - total_actual:.4f} €")