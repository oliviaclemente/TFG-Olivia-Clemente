"""
fig_3_3_densidad_tasa.py
Genera la Figura 3.3: relacion entre densidad de poblacion y tasa
media, por seccion censal (Tabla 3.1 geocodificada: ordinaria + rustica).
"""
import matplotlib.pyplot as plt

secciones = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
densidad = [1.09, 5.26, 77.44, 107.98, 158.71, 32.13, 19.58, 77.55, 65.29, 43.03, 18.33, 2.06]
# Tasa media combinada (ordinaria+rustica geocodificada), por seccion
tasa_media = [135.91, 135.61, 130.84, 130.69, 130.12, 133.60, 131.94, 130.69, 130.14, 130.48, 131.60, 138.98]

fig, ax = plt.subplots(figsize=(9, 6))
ax.scatter(densidad, tasa_media, color="#1f77b4", s=70, zorder=3)

for s, x, y in zip(secciones, densidad, tasa_media):
    ax.annotate(str(s), (x, y), textcoords="offset points", xytext=(6, 4), fontsize=9)

ax.set_title("Relacion entre densidad de poblacion y tasa media, por seccion censal")
ax.set_xlabel("Densidad (hab/ha)")
ax.set_ylabel("Tasa media (EUR)")
ax.grid(True, linestyle="--", alpha=0.4)

plt.tight_layout()
plt.savefig("fig_3_3_densidad_tasa.png", dpi=300)
