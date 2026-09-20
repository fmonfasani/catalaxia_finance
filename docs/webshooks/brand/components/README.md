# Componentes webshooks — diagramas branded

Generadores de **piezas visuales** con la marca webshooks, a partir de datos simples.
Salida: **PNG (300 dpi) + SVG** para insertar en Word / PPT / PDF / HTML.

Ejemplos en `examples/` (timeline, pipeline, flow).

## Uso como librería

```python
import sys; sys.path.insert(0, "docs/webshooks/brand/components")
from components import timeline, pipeline, flow

pipeline([
    {"title": "1 · Extracción", "desc": "SEC · CNV · IAMC → raw cache"},
    {"title": "2 · Ratios",     "desc": "~16 ratios"},
    {"title": "3 · Export",     "desc": "CSV + JSON"},
], title="Mi pipeline", subtitle="opcional", name="mi-pipeline", out="ruta/salida")
# -> ruta/salida/mi-pipeline.png  + .svg
```

## Componentes disponibles

| Función | Para qué | Datos |
|---|---|---|
| `timeline(events, ...)` | línea de tiempo / hitos | `[{"label","sub","color?"}, ...]` |
| `pipeline(stages, ...)` | proceso por bloques con flechas | `[{"title","desc","color?"}, ...]` |
| `flow(steps, ...)` | diagrama de flujo vertical | `[{"text","type"}]` · type: `start\|process\|decision\|end` |

Todas aceptan `title`, `subtitle`, `name` (nombre de archivo) y `out` (carpeta de salida).
Los colores salen del tema (`../theme_webshooks.json`); si no se pasa `color`, rota la paleta.

## Cómo insertarlos en un documento

- **Word (docgen):** referenciá el PNG en tu `.md` con `![](ruta/al/componente.png)` — docgen v2 lo
  **embebe** automáticamente.
- **PPT / PDF / HTML:** insertá el PNG (o el SVG para vectorial).

## Regenerar los ejemplos

```bash
cd components
python components.py        # -> examples/*.png|svg   (requiere: matplotlib)
```

## Roadmap
- ✅ timeline · pipeline · flow.
- 🔜 (si hace falta) más moldes: stat-row/KPI, cuadro comparativo, mapa de fases, org-chart.
