"""
fig_3_6_tasa_comparacion.py
Genera la Figura 3.6: tasa media actual frente a tasa propuesta, por
seccion censal (F=66.93, k1=21.499, k2=23.095), ordenada por diferencia.
"""
import numpy as np
import matplotlib.pyplot as plt

# Ordenado de mayor a menor diferencia (Tasa nueva - Tasa actual)
secciones = [1, 12, 2, 5, 4, 3, 8, 9, 10, 7, 11, 6]
tasa_actual =    [135.91, 138.98, 135.61, 130.12, 130.69, 130.84, 130.69, 130.14, 130.48, 131.94, 131.60, 133.60]
tasa_propuesta = [174.67, 151.44, 130.94, 123.92, 121.79, 120.38, 120.38, 119.81, 118.96, 119.72, 119.95, 118.85]

x = np.arange(len(secciones))
width = 0.35

fig, ax = plt.subplots(figsize=(11, 6))
ax.bar(x - width / 2, tasa_actual, width, label="Tasa actual", color="gray")
ax.bar(x + width / 2, tasa_propuesta, width, label="Tasa propuesta", color="#1f77b4")

ax.set_xticks(x)
ax.set_xticklabels([f"Sec.{s}" for s in secciones], rotation=45, ha="right")
ax.set_ylabel("Tasa media (EUR)")
ax.set_title("Tasa media actual frente a tasa propuesta, por seccion censal")
ax.legend()
ax.grid(True, axis="y", linestyle="--", alpha=0.4)

plt.tight_layout()
plt.savefig("fig_3_6_tasa_comparacion.png", dpi=300)
