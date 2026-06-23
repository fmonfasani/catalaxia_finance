# 📋 Guía para Colaboradores - Catalaxia Finance

Esta guía explica cómo trabajar en el proyecto catalaxia_finance y cómo se actualiza automáticamente el archivo **Seguimiento.xlsx**.

---

## 🎯 Objetivo Final

Mantener un **archivo de seguimiento actualizado automáticamente** que refleje:
- ✅ Tareas completadas
- 🔄 Tareas en progreso  
- ⏳ Tareas pendientes
- 📊 Progreso por fase/módulo

---

## 📁 Estructura del Proyecto

```
catalaxia_finance/
├─ docs/screener/          ← Documentación
├─ scripts/screener/       ← Código Python (Scripts 01-08)
├─ Seguimiento.xlsx        ← ARCHIVO AUTOMÁTICO (no editar manualmente)
└─ CONTRIBUTING.md         ← Instrucciones de contribución
```

---

## 🔄 WORKFLOW PARA COLABORADORES

### Paso 1: Clonar el repositorio

```bash
git clone https://github.com/fmonfasani/catalaxia_finance.git
cd catalaxia_finance
```

### Paso 2: Crear rama para tu tarea

```bash
# Crear rama descriptiva
git checkout -b feature/nombre-tarea

# Ejemplo:
git checkout -b feature/mejorar-ratios-calculo
git checkout -b fix/error-precios-yfinance
git checkout -b docs/agregar-ejemplos
```

**Naming convention:**
- `feature/` - Nueva funcionalidad
- `fix/` - Arreglo de bugs
- `docs/` - Documentación
- `refactor/` - Mejoras de código

### Paso 3: Realizar cambios

Editar archivos, agregar código, documentación, etc.

```bash
# Revisar cambios
git status

# Agregar cambios
git add scripts/screener/archivo_modificado.py
git add docs/screener/archivo_nuevo.md

# Hacer commit con mensaje descriptivo
git commit -m "feat: agregar soporte para más CEDEARs

- Aumentar lista de 127 a 150 CEDEARs
- Validar tickers contra BYMA
- Documentar nuevas adiciones"
```

**Formato de commits:**
```
<tipo>: <descripción corta>

<descripción detallada (opcional)>
<lista de cambios>
<referencias a issues>
```

Tipos válidos: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

### Paso 4: Crear Pull Request

```bash
# Push a la rama
git push origin feature/nombre-tarea

# En GitHub: Crear PR con descripción clara
```

**Descripción de PR debe incluir:**
- ✅ Qué se cambió y por qué
- 🧪 Cómo testearlo
- 📝 Checklist de completitud

### Paso 5: Merge y actualización automática

Una vez aprobada la PR:
1. ✅ Se mergea a `main`
2. 🤖 Script automático detecta el cambio
3. 📊 Seguimiento.xlsx se actualiza automáticamente

---

## 📊 Cómo funciona el Seguimiento.xlsx

### Actualización AUTOMÁTICA

El archivo **NO se edita manualmente**. Se actualiza automáticamente basado en:

1. **Commits en GitHub**
   - Detecta qué tarea se completó por el tipo de commit
   - Actualiza estado de la tarea

2. **PRs abiertas/cerradas**
   - PR abierta = Tarea en progreso 🔄
   - PR mergeada = Tarea completada ✅
   - PR rechazada = Tarea en review ⚠️

3. **Branches del repositorio**
   - Branch activa = Tarea en progreso
   - Branch eliminada = Tarea completada

### Estructura del archivo

```
Seguimiento.xlsx
├─ Sheet "Tareas"
│  ├─ Columnas: Tarea | Fase | Estado | Responsable | Progreso | Fecha
│  ├─ Estado: PENDIENTE | EN PROGRESO | COMPLETADA | BLOQUEADA
│  └─ Actualizado: Automáticamente cada commit
│
├─ Sheet "Progreso"
│  ├─ Gráficos de avance por fase
│  ├─ % completado
│  └─ Métricas del proyecto
│
└─ Sheet "Commits"
   ├─ Log de commits recientes
   ├─ Quién cambió qué
   └─ Cuándo
```

---

## ✅ TAREAS Y RESPONSABLES

### Fase 1: Extracción de Datos (Completada ✅)
- [x] Script 01: Descargar listas CEDEARs/ADRs → Completado
- [x] Script 02: Descargar precios yfinance → Completado  
- [x] Validar 147 acciones descargadas → Completado

### Fase 2: Financieros EDGAR (Completada ✅)
- [x] Script 06: Descargar datos EDGAR → Completado
- [x] Procesar 115 empresas con Revenue → Completado

### Fase 3: Cálculo de Ratios (Completada ✅)
- [x] Script 07: Calcular 13 ratios → Completado
- [x] Validar ratios en 159 acciones → Completado

### Fase 4: Screener Final (Completada ✅)
- [x] Script 08: Generar Excel + reportes → Completado
- [x] Crear 7 tabs con rankings → Completado

### Fase 5: Mejoras y Mantenimiento (En progreso 🔄)
- [ ] Mejorar cobertura de precios (78% → 90%)
- [ ] Agregar 50+ CEDEARs nuevos
- [ ] Implementar actualización mensual
- [ ] Crear dashboard interactivo
- [ ] Documentación en Español

---

## 🤖 SCRIPT DE AUTOMATIZACIÓN

Existe un script que actualiza **Seguimiento.xlsx** automáticamente:

```bash
# Ejecutar manualmente (opcional)
python scripts/actualizar_seguimiento.py

# O automáticamente al hacer:
git push origin main
```

**Qué hace el script:**
1. Lee el historial de commits
2. Lee PRs de GitHub API
3. Clasifica tareas por estado
4. Genera Excel actualizado
5. Guarda en Seguimiento.xlsx

---

## 📝 EJEMPLO: Flujo completo de una tarea

### Tarea: "Aumentar CEDEARs de 127 a 200"

**Paso 1: Crear rama**
```bash
git checkout -b feature/agregar-cedears-200
```

**Paso 2: Editar código**
- Editar `scripts/screener/01_descargar_cedears_adrs.py`
- Agregar 73 CEDEARs nuevos a la lista
- Testar que se descarguen precios correctamente

**Paso 3: Commit descriptivo**
```bash
git add scripts/screener/01_descargar_cedears_adrs.py
git commit -m "feat: agregar 73 CEDEARs nuevos (127 → 200)

- Agregar tickers faltantes (ACTA, AGRO, ALTY, etc.)
- Validar contra lista oficial BYMA
- Aumentar cobertura de 78% a 92%
- Todos los nuevos tickers validados en yfinance

Fixes: #45
Tests: python 01_descargar_cedears_adrs.py ✓"
```

**Paso 4: Push y PR**
```bash
git push origin feature/agregar-cedears-200
# En GitHub: Crear PR
```

**Paso 5: Seguimiento automático**
- ✅ PR abierta = Estado cambia a "EN PROGRESO"
- ✅ PR mergeada = Estado cambia a "COMPLETADA"
- ✅ Seguimiento.xlsx se actualiza automáticamente
- ✅ Gráficos de progreso se regeneran

---

## 🚀 CONSEJOS PARA COLABORADORES

### ✅ HACER:
- ✅ Commits frecuentes y pequeños
- ✅ Mensajes descriptivos
- ✅ Revisar cambios antes de commit
- ✅ Crear PRs claras con descripción
- ✅ Testar localmente antes de push
- ✅ Seguir naming convention de branches

### ❌ NO HACER:
- ❌ Editar Seguimiento.xlsx manualmente
- ❌ Commits sin mensaje
- ❌ Mergear sin revisión
- ❌ Hacer push directo a main
- ❌ Commits enormes con muchos cambios
- ❌ Ignorar la documentación

---

## 🔗 REFERENCIAS

- **Repo:** https://github.com/fmonfasani/catalaxia_finance
- **Documentación:** docs/screener/PLAN_SCREENER_218_ACCIONES.md
- **Scripts:** scripts/screener/*.py
- **Seguimiento:** Seguimiento.xlsx (actualizado automáticamente)

---

## ❓ PREGUNTAS FRECUENTES

**P: ¿Quién actualiza el Seguimiento.xlsx?**  
R: Se actualiza automáticamente al hacer push. No editar manualmente.

**P: ¿Cómo reporto progreso?**  
R: Con commits descriptivos. El script detecta automáticamente el tipo de cambio.

**P: ¿Puedo trabajar en la rama main?**  
R: NO. Crear siempre una rama feature/fix/docs/. Main solo recibe PRs mergeadas.

**P: ¿Cada cuánto se actualiza el Seguimiento?**  
R: Automáticamente con cada push. Máximo 1 minuto de delay.

**P: ¿Necesito instalar algo especial?**  
R: Solo: `pip install -r scripts/screener/requirements.txt`

---

**Última actualización:** 2026-06-23  
**Status:** Documentación activa  
**Dudas:** Contactar a Federico (fmonfasani@gmail.com)
