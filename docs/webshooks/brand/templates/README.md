# Plantillas webshooks — Motor de presentaciones (data → deck)

Generá presentaciones **.pptx branded** describiendo sólo el **contenido** (un `SPEC` en
Python). El diseño (colores, tipografía, layouts, header/footer, logo) lo pone el motor a
partir de `../theme_webshooks.json`. **Cambiás los datos, no el diseño.**

- Motor: [`webshooks_pptx.py`](webshooks_pptx.py)
- Ejemplo completo (todos los tipos de slide): [`ejemplo_propuesta.py`](ejemplo_propuesta.py)
- Salida del ejemplo: `ejemplo_propuesta.pptx` (16:9, 13.333 × 7.5")

## Uso

```bash
cd docs/webshooks/brand/templates
python ejemplo_propuesta.py        # -> ejemplo_propuesta.pptx
```

Para tu propia propuesta, copiá `ejemplo_propuesta.py`, editá el `SPEC` y corré el archivo.

```python
from webshooks_pptx import build

SPEC = {
    "out": "mi_propuesta.pptx",
    "cover": { ... },              # portada (opcional)
    "slides": [
        {"type": "resumen", ...},  # una entrada por slide, en orden
        {"type": "alcance", ...},
    ],
}
build(SPEC)
```

## Tipos de slide

Cada item de `slides` es un dict con `"type"` + sus campos. Todos aceptan `title` y
`subtitle` (menos `cover` y `seccion`).

| `type` | Para qué | Campos principales |
|---|---|---|
| `cover` (en `SPEC["cover"]`) | Portada a 2 paneles | `title_left[]`, `subtitle_left`, `cliente`, `fecha`, `headline[]`, `solution`, `chips[]`, `brand_tag` |
| `seccion` | Divisor de sección navy | `num`, `title`, `subtitle`, `accent` |
| `resumen` | KPIs + "qué incluye" | `stats[(num,label)]`, `izq[]`, `der[]` (bullets `[titulo, desc]`) |
| `alcance` | 2–4 columnas con header de color | `cols[{head, items[[t,d]]}]` |
| `stack` | 2 tablas clave-valor + nota | `backend[(k,v)]`, `frontend[(k,v)]`, `left_title`, `right_title`, `nota` |
| `tabla` | Tabla libre con header navy + zebra | `headers[]`, `rows[[...]]`, `cw[]` (anchos rel.), `fs`, `rh` |
| `equipo` | Hasta 4 tarjetas de rol | `personas[{name, items[[t,d]]}]` |
| `cronograma` | N tarjetas-columna (semanas/fases) | `semanas[{t, items[[t,d]], color?}]` |
| `inversion` | Precio + opciones de pago | `precio`, `precio_label`, `precio_nota`, `incluye`, `opciones[{t,det,monto,color}]` |
| `cierre` | Pasos numerados + resumen navy | `pasos[{t,d}]`, `resumen[(k,v)]`, `validez` |

### Convenciones de datos

- **Bullets** `[titulo, desc]` → el título queda en negrita navy y la descripción en gris.
  Un string suelto también vale (bullet simple).
- **Celda destacada** en `tabla`: pasá `(texto, "43A047")` (color en hex sin `#`) para pintar
  esa celda; el resto usa el color por defecto.
- **`headline`** de la portada: lista de líneas; la **última** se pinta en azul (remate).
  Usá 2 o más líneas.
- **Colores**: los `accent`/`color` opcionales son hex sin `#` (`"3B82F6"`). Si no los pasás,
  el motor rota la paleta de marca (azul → naranja → verde → azul oscuro).

## Cómo se ve

El ejemplo genera 10 slides: portada · sección · resumen (KPIs) · alcance (3 col) · stack ·
tabla · equipo · cronograma · inversión · cierre. Todas con header (wordmark + regla naranja),
footer `webshooks.com` + número de página, y la paleta v4.

## Insertar componentes (timeline / pipeline / flujo)

Los diagramas de [`../components/`](../components/) salen como PNG. Para meterlos en una slide,
usá un `type` propio o el molde `tabla`/`resumen` como base y agregá la imagen con
python-pptx (`slide.shapes.add_picture`). *(Molde de slide-con-imagen: pendiente en el roadmap.)*

## Relación con el resto del brand-kit

```
docs/webshooks/brand/
  theme_webshooks.json      ← fuente de verdad (colores, fuentes, logo)   [compartido]
  logo/                     ← logos generados
  components/               ← timeline · pipeline · flujo  (PNG/SVG)
  templates/                ← ESTE motor: data → .pptx branded
scripts/docgen/             ← el equivalente para Word: .md → .docx branded
```

Mismo tema para PPT (acá) y Word (docgen): un solo cambio de color se propaga a todo.

## Roadmap

- ✅ Motor spec-driven con 10 tipos de slide (cover, sección, resumen, alcance, stack, tabla,
  equipo, cronograma, inversión, cierre).
- 🔜 Molde de slide con imagen (para incrustar componentes) y export directo PPTX→PDF.
- 🔜 (si hace falta) tipos extra: comparativa 2-col, quote/testimonio, portada de anexos.
