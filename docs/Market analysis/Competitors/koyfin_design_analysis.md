# Koyfin — Análisis Riguroso de Frontend

**URL:** https://app.koyfin.com/fa/00000000-3c6b-403d-8336-0c36676ca980/eq-o1antf  
**Página analizada:** AAPL — Income Statement  
**Fecha de análisis:** 2026-09-07  
**Método:** DOM inspection + computed CSS vars + accessibility tree vía Claude in Chrome

---

## 1. Stack técnico

| Capa | Tecnología |
|------|-----------|
| Framework JS | React (no Vue) |
| CSS | CSS Modules con hashing (LightningCSS bundler) |
| Fuente primaria | `aktiv-grotesk` + `inter` (fallback) |
| Iconos | Font Awesome 6 Pro (regular, light, duotone, sharp, brands — licencia paga) |
| Chatbot | Google Dialogflow Messenger (`df-messenger-*`) |
| Upload widget | Uploadcare (`--uc-*` vars) |
| Design system base | **Untitled UI** dark mode (tokens identificables por naming) |
| Animaciones | `--animation-speed: .2s` (CSS transition uniform) |

Koyfin usa React con CSS Modules en lugar de una biblioteca de UI opinionated como Vuetify. Esto le da más libertad de customización pero require más trabajo propio. El design system subyacente es **Untitled UI** — reconocible por el naming de tokens (`--color-fg-primary`, `--color-bg-primary`, `--color-border-*`, escala `--color-gray-dark-*`).

---

## 2. Sistema de colores

### Fondo base
```
--color-base-black:    #191e24   → fondo principal (rgb 25, 30, 37)
--color-base-white:    #ffffff
```
Dark-first. No hay modo claro visible en el dashboard — la UI asume que los usuarios de datos financieros prefieren oscuro (estándar Bloomberg/trading terminal).

### Sistema de elevación (depth layers)
```
--color-elevation-dark-50:   #181d28   ← nivel base
--color-elevation-dark-70:   #1d222d
--color-elevation-dark-80:   #1f242f
--color-elevation-dark-90:   #222631
--color-elevation-dark-110:  #272b36
--color-elevation-dark-120:  #292e38
--color-elevation-dark-140:  #2e323d
--color-elevation-dark-150:  #30353f
--color-elevation-dark-160:  #333741   ← más elevado
```
**9 niveles de elevación** expresados como variaciones de gris azulado muy sutiles. Esto es arquitectura de diseño sofisticada — cada panel, modal, tooltip y header tiene su propio nivel. Sin sombras (box-shadow): la jerarquía visual se comunica solo por tono de fondo.

### Brand color (azul)
```
--color-brand-400:  #3789f2   ← acento interactivo (links, seleccionados)
--color-brand-500:  #0f71f0
--color-brand-600:  #0d5ec8   ← CTA primario
--color-brand-700:  #0a4ba0
--color-brand-900:  #052650
```
Azul clásico fintech — confiable, neutral, no distrae de los datos. Contrasta fuertemente con el naranja de TIKR (diferenciación deliberada).

### Escala de grises (dark)
```
--color-gray-dark-300:  #cecfd2   ← texto primario
--color-gray-dark-400:  #94969c   ← texto secundario / icons
--color-gray-dark-500:  #85888e   ← texto terciario / disabled
--color-gray-dark-600:  #61646c
--color-gray-dark-650:  #41454f   ← borders secundarios
--color-gray-dark-700:  #333741   ← borders primarios / header de tabla
--color-gray-dark-800:  #1f242f   ← superficies cards
--color-gray-dark-900:  #121926   ← fondo de tabla celdas
--color-gray-dark-950:  #0c111d   ← fondo más oscuro
```

### Semántica de texto
```
--color-text-primary:           #f5f5f6   (gray-dark-50 — casi blanco)
--color-text-secondary:         #cecfd2   (gray-dark-300)
--color-text-tertiary:          #94969c   (gray-dark-400)
--color-text-quarterary:        #61646c   (gray-dark-600)
--color-text-disabled:          #61646c
--color-text-error-primary:     #f97066   (error-400)
--color-text-success-primary:   #2ab666   (success-400)
```

### Estados de color financiero
```
--color-success-500:  #00a848   → verde (valores positivos)
--color-success-400:  #2ab666
--color-error-500:    #f04438   → rojo (valores negativos)
--color-error-400:    #f97066
--color-warning-500:  #f79009   → amarillo (alertas)
```

### Tokens de tabla (el componente más importante)
```
--color-table-cell-bg:        var(--color-gray-dark-900)  → #121926
--color-table-cell-bg-alt:    var(--color-gray-dark-800)  → #1f242f   (zebra)
--color-table-cell-bg-hover:  var(--color-gray-dark-800)
--color-table-cell-border:    var(--color-gray-dark-800)
--color-table-cell-text:      var(--color-gray-dark-400)
--color-table-cell-text-hover:var(--color-gray-dark-300)
--color-table-header-bg:      var(--color-gray-dark-700)  → #333741
--color-table-header-border:  var(--color-gray-dark-650)  → #41454f
--color-table-header-text:    var(--color-gray-dark-300)
--color-table-cell-blink-up:  var(--color-success-950)    → flash verde (precio sube)
--color-table-cell-blink-down:var(--color-error-950)      → flash rojo (precio baja)
```
Los tokens `blink-up` / `blink-down` son particularmente notables: implementan el efecto de flash de celda que muestran los terminales Bloomberg cuando un precio cambia en tiempo real.

---

## 3. Tipografía

| Propiedad | Valor |
|-----------|-------|
| Fuente primaria | `aktiv-grotesk` (licencia paga, Dalton Maag) |
| Fuente fallback | `inter` |
| Iconos | Font Awesome 6 Pro (pago) — ~7 variantes de peso |
| UI font size base | 13px (muy compacto) |
| Input font size | 13px |
| Text size base | 16px |

`aktiv-grotesk` es una elección premium y diferenciada — es la fuente sans-serif favorita de marcas fintech serias (usada por compañías como Stripe y Linear). Más refinada que Inter pero con el mismo carácter neutro-técnico.

Font Awesome 6 Pro (pago) vs Material Icons (gratis de TIKR): Koyfin invirtió en iconografía más variada y de mayor calidad — duotone icons, variantes light/thin para interfaces densas de datos.

---

## 4. Geometría y espaciado

| Patrón | Valor |
|--------|-------|
| Border-radius base | 6px |
| Border-radius cards | 6px |
| Border-radius pills | 50px |
| Border-radius modals | 12px |
| Animación default | 0.2s |

6px vs los 4px de TIKR: más moderno sin perder la sobriedad técnica. Los pills (50px) son para tags y badges de estado. El sistema es simple: 3 valores (6px / 12px / 50px) según el nivel de contención del componente.

---

## 5. Componentes observados

### Botones (sistema 3×3)
Koyfin tiene un sistema de botones muy completo:
- **3 variantes de estilo**: primary (solid azul), secondary (borde azul), tertiary (ghost)
- **3 variantes de color**: brand (azul), gray (neutro), transparent
- **Estados**: default, hover, pressed, focus, disabled
- Total: ~9 tipos de botón consistentes

```
Primary brand button:
  bg:      var(--color-brand-400)  → #3789f2
  hover:   var(--color-brand-500)  → #0f71f0
  pressed: var(--color-brand-700)  → #0a4ba0
  text:    #ffffff
  radius:  6px

Secondary brand button:
  bg:      var(--color-gray-dark-900)  
  border:  var(--color-brand-400)
  text:    var(--color-brand-400)
  hover-bg:var(--color-brand-900)

Tertiary (ghost):
  bg:      transparent
  text:    var(--color-brand-400)
  hover:   var(--color-brand-800) background
```

### Navegación lateral
```
CSS class: navi-panel-layout__naviPanelLayout
          navi-panel-list-item
```
Panel colapsable izquierdo — igual al app shell de TIKR. Es el estándar de la industria para dashboards financieros. La clase CSS hasheada (`navi-panel-layout`) confirma CSS Modules.

### Tablas financieras
No usa `<table>` HTML — usa grids CSS con divs. Esto es consistente con la tendencia moderna de evitar el DOM de tabla para mayor control de renderizado y virtualización. Los 78 botones en la página corresponden mayoritariamente a controles de toolbar de la tabla (sort, filtros, export, customización de columnas).

### AI Chatbot
Google Dialogflow Messenger integrado con:
- Font: `aktiv-grotesk`  
- Color primario: `#0080ff` (azul Koyfin)
- User messages: fondo `#0080ff33` (azul 20% opacity)
- Bot messages: gradiente `linear-gradient(134.13deg, #f5faff 0.73%, #faf5ff 33.25%, #fff8f5 65.76%, #fffbf5 99.27%)`

Esto sugiere que Koyfin tiene asistente conversacional para análisis financiero — funcionalidad que va más allá de lo que TIKR ofrece.

---

## 6. Layout

```
App shell: flex-direction row
├── Panel nav izquierdo (colapsable)
│   └── navi-panel-list-item × N
└── Content area (flex: 1)
    ├── Toolbar header (con 78 botones de control)
    ├── Data grid (tablas financieras)
    └── Charts panel
```

Igual estructura macro que TIKR (sidebar + content), pero la densidad del toolbar y la ausencia de `<table>` HTML sugiere un componente de datos mucho más interactivo y customizable.

---

## 7. Observaciones de calidad

### Fortalezas

1. **Sistema de elevación sin sombras** — 9 niveles de profundidad solo con variación de color. Más sofisticado que sombras (se ve mejor en dark mode y escala mejor).
2. **Design tokens semánticos completos** — `--color-fg-primary`, `--color-bg-brand-solid`, `--color-border-secondary`. Vocabulario de diseño completamente sistemático, probablemente generado desde Figma tokens.
3. **Tokens de tabla específicos** — incluyendo `blink-up`/`blink-down` para animaciones de precio en tiempo real.
4. **Sistema de botones completo** — 3×3 matriz + estados = zero ambigüedad para desarrolladores.
5. **`aktiv-grotesk`** — fuente premium que comunica seriedad y cuidado de marca.
6. **Font Awesome 6 Pro** — cobertura de iconos muy superior a Material Icons.
7. **9 niveles de elevación** — arquitectura de depth muy pensada para interfaces complejas.

### Debilidades / Oportunidades

1. **Sin light mode visible** — dark-only puede alienar usuarios que prefieren claro (mercado más amplio).
2. **Font paga (aktiv-grotesk)** — costo de licencia, no accesible para proyectos open source o pequeños.
3. **CSS Modules hasheados** — dificulta customización y theming por parte del usuario.
4. **78 botones en un screenshot** — señal de UI muy densa e intimidante para usuarios nuevos. Curva de aprendizaje alta.
5. **Google Dialogflow** — dependencia de Google para el chatbot; privacidad de datos de análisis financiero potencialmente problemática.
6. **Sin modo print/export visual** — no se observaron estilos de impresión.

---

## 8. Puntuación

| Dimensión | Puntuación | Nota |
|-----------|-----------|------|
| Sistema de colores | 9.5/10 | Untitled UI dark, tokens semánticos completos, elevación sin sombras |
| Tipografía | 9/10 | aktiv-grotesk premium, FA6 Pro, escala compacta funcional |
| Componentes | 9/10 | Sistema de botones 3×3 muy completo, tabla con blink tokens |
| Dark mode | 9/10 | Dark-first, bien ejecutado, faltan estilos light |
| Densidad de datos | 8/10 | Alta densidad, pero 78 botones por página puede abrumar |
| Identidad visual | 8/10 | Sobria, profesional, azul seguro (menos diferenciadora que el naranja de TIKR) |
| Arquitectura CSS | 9/10 | Untitled UI tokens + CSS Modules = mantenimiento excelente |
| **Global** | **8.8/10** | Producto de alta calidad con base de diseño muy sólida |

---

# Comparación TIKR vs Koyfin vs Catalaxia

## Tabla comparativa

| Dimensión | TIKR (7.4/10) | Koyfin (8.8/10) | Catalaxia (propuesta) |
|-----------|--------------|----------------|----------------------|
| Framework | Vue.js 2 + Vuetify 2 | React + CSS Modules | Next.js 14 + Tailwind + shadcn/ui ✅ |
| Design system | Material Design v1 (viejo) | Untitled UI dark | shadcn/ui (Radix) + tokens propios |
| Fuente | Inter | aktiv-grotesk + Inter | Inter (libre, familiar) |
| Iconos | Material Icons (gratis) | Font Awesome 6 Pro (pago) | Lucide Icons (gratis, moderno) |
| Colores | Naranja (#f90) diferenciador | Azul (#3789f2) neutral | A definir (ver recomendación) |
| Border-radius | 4px (conservador) | 6px (moderno) | 6px — igual que Koyfin |
| Dark mode | Completo (bien hecho) | Dark-first | Ambos modos desde el inicio |
| Tablas | HTML table + Vuetify | Div grid + CSS Modules | shadcn/ui DataTable (TanStack) |
| Gráficos | Highcharts (pago) | No identificado | Recharts (gratis) o Tremor |
| Tokens blink | ❌ No observado | ✅ blink-up/blink-down | ✅ Implementar para precios live |
| Elevación | Sombras (box-shadow) | Color-only (9 niveles) | Color-only — sin sombras en dark |
| AI chatbot | ❌ | Google Dialogflow | - |
| Light mode | ✅ (crema #fffcf7) | ❌ (dark only) | ✅ Ambos desde el inicio |

---

## Recomendaciones concretas para Catalaxia

### 1. Color de acento — no naranja ni azul genérico
TIKR usa naranja (distintivo pero discordante internamente).  
Koyfin usa azul (neutral, seguro, pero "igual a todos").  
**Recomendación:** Un verde esmeralda o un violeta como acento principal. Verde comunica "datos positivos" y es consistente con el contexto financiero argentino. Alternativa: mantener azul pero en tono más vibrante (`#2563eb` Tailwind blue-600).

### 2. Sistema de elevación sin sombras (como Koyfin)
En dark mode, las sombras se ven mal. Usar variaciones de gris como Koyfin:
```css
/* Propuesta para Catalaxia */
--surface-base:     #0f172a;   /* slate-900 */
--surface-raised:   #1e293b;   /* slate-800 */
--surface-overlay:  #334155;   /* slate-700 */
--surface-popover:  #475569;   /* slate-600 */
```

### 3. Tabla financiera con tokens de estado
Implementar los mismos tokens que Koyfin para la tabla del screener:
```css
--table-cell-bg:        var(--surface-raised);
--table-cell-bg-alt:    var(--surface-overlay);     /* zebra */
--table-header-bg:      var(--surface-overlay);
--table-cell-blink-up:  #052e1c;  /* flash verde sutil */
--table-cell-blink-down:#55160c;  /* flash rojo sutil */
```

### 4. Sistema de botones simplificado (no 3×3 como Koyfin)
Para v1 de Catalaxia, 3 variantes son suficientes:
- **Primary**: fondo sólido (acento)
- **Secondary**: ghost con borde (acento)  
- **Destructive**: para acciones de riesgo (rojo)

### 5. Border-radius 6px como Koyfin (no 4px como TIKR)
En Tailwind: `rounded-md` (6px) por defecto, `rounded-lg` (8px) para modals/cards.

### 6. shadcn/ui es la decisión correcta
Comparando los stacks:
- Vuetify 2 (TIKR): deuda técnica, Material v1
- CSS Modules custom (Koyfin): más trabajo, más flexibilidad
- **shadcn/ui + Tailwind (Catalaxia)**: el mejor punto medio — componentes accesibles de Radix UI, personalización total vía tokens CSS, sin bundle overhead de componentes no usados

### 7. Lucide sobre Material Icons (TIKR) o FA6 Pro (Koyfin)
Lucide es consistente, libre, y cubre el 95% de casos de un screener financiero. Si se necesita más cobertura, `phosphor-icons` es la alternativa libre más completa.

### 8. Lo que Catalaxia debe tener que ninguno tiene bien
- **Light mode real** — Koyfin no lo tiene, TIKR lo tiene pero en crema (polarizante). Un light mode Tailwind slate limpio sería diferenciador.
- **Español-first** — ninguno de los dos tiene i18n real para mercado argentino.
- **Contexto CEDEAR específico** — ratio de paridad, brecha cambiaria, ajuste por inflación (IPC) — funcionalidad que TIKR y Koyfin directamente no tienen para el mercado local.
- **Menos ruido, más señal** — los 78 botones de Koyfin abruman. Para v1, Catalaxia puede ganar siendo más simple y directa.
