# Sistema de marca webshooks

Home único de la identidad de webshooks: **tema, logos y (próximamente) componentes y plantillas**.
Todo es **reproducible por script** — no se edita a mano.

## Estructura

```
brand/
  theme_webshooks.json     LA fuente de verdad de la marca (colores, fuente, headings, footer)
  logo/                    logos generados (png/svg/jpg/ico)
  tools/logo_gen.py        genera el kit de logos
  components/  (Fase 3)     moldes: cajas, tablas, timeline, pipeline, flujos
  templates/   (Fase 4)     plantillas por formato (.md/Word/PPT/PDF)
```

## Tema (paleta)

Definido en `theme_webshooks.json`. Colores núcleo:

| Rol | Hex |
|---|---|
| Navy (primario) | `#1A2744` |
| Azul (secundario) | `#3B82F6` |
| Naranja (acento) | `#F5821F` |
| Verde (éxito) | `#43A047` |
| Gris cuerpo | `#3A4458` |

Fuente: **Calibri**. Wordmark: `webshooks.` = **web** (azul) · **shooks** (navy) · **.** (naranja).

## Logos disponibles

| Archivo | Uso |
|---|---|
| `webshooks-logo-horizontal-color.png` | logo principal (isotipo + wordmark), fondo claro |
| `webshooks-logo-horizontal-onnavy.png` | logo principal para **fondo oscuro** |
| `webshooks-logo-horizontal-onwhite.jpg` | JPEG (donde no se admite PNG/transparencia) |
| `webshooks-wordmark-color.png` / `.svg` | solo el nombre, color (SVG = vectorial) |
| `webshooks-wordmark-white.png` / `.svg` | wordmark blanco (fondos oscuros) |
| `webshooks-wordmark-navy.png` | wordmark monocromo navy (1 tinta) |
| `webshooks-mark-color.png` | isotipo `w.` (avatar, sello, esquinas) |
| `webshooks-appicon-512.png` | ícono de app (512×512) |
| `webshooks-favicon.ico` | favicon web (16/32/48/64) |
| `logo/_contact-sheet.png` | hoja de referencia de todas las variantes |

**Cuál usar:** documentos/portadas → *horizontal-color*; header/footer → *wordmark*; web (pestaña) →
*favicon*; app/redes → *appicon* o *mark*; sobre navy → variantes *white* / *onnavy*.

## Regenerar (reproducible)

```bash
cd tools
python logo_gen.py        # -> ../logo/*  (requiere Pillow: pip install pillow)
```
Para cambiar un color o el diseño del isotipo, se edita `theme_webshooks.json` / `logo_gen.py` y se
vuelve a correr. **Un cambio, se propaga a todos los logos.**

## Roadmap

- ✅ **Fase 1** — tema + logos (esto).
- 🔜 **Fase 2** — `docgen v2`: que use este tema + logos y haga portada, índice y footer reales.
- **Fase 3** — componentes: cajas, tablas, listas, timeline, pipeline, diagramas de flujo.
- **Fase 4** — plantillas listas por tipo de documento y formato (.md / Word / PPT / PDF).
