I GUÍA PARA COLABORADORES
Catalaxia Finance - Screener Financiero 218+ Acciones
1. OBJETIVO DEL PROYECTO
Mantener un archivo de seguimiento Seguimiento.xlsx que se actualiza automáticamente
según el progreso de las tareas en GitHub. Los colaboradores solo necesitan hacer commits
descriptivos; el sistema detecta automáticamente cuándo una tarea se completó.
2. WORKFLOW - 6 PASOS SIMPLES
Paso 1: Clonar repositorio
git clone https://github.com/fmonfasani/catalaxia_finance.git
Paso 2: Crear rama para tu tarea
git checkout -b feature/nombre-tarea
Paso 3: Editar archivos y hacer commits
git commit -m 'feat: descripción clara'
Paso 4: Push a GitHub
git push origin feature/nombre-tarea
Paso 5: Crear Pull Request
Abrir PR en GitHub y esperar aprobación
Paso 6: Automático después del merge
Sistema detecta y actualiza Seguimiento.xlsx I
3. CONVENCIÓN DE NOMBRES DE RAMAS
feature/
Nueva funcionalidad
feature/agregar-cedears-20
fix/
Corrección de bugs
fix/error-descarga-precios
docs/
Documentación
docs/agregar-ejemplos
refactor/
Mejora de código
refactor/optimizar-ratios
4. MENSAJE DE COMMITS


IMPORTANTE: Los mensajes descriptivos son lo más importante. El sistema automático
analiza los commits para detectar qué tarea se completó.
feat: agregar 20 CEDEARs nuevos (127 → 147)
- Agregar tickers: ACTA, AGRO, ALTY, ... (20 total)
- Validar contra lista oficial BYMA
- Testar descarga de precios con yfinance
- Aumentar cobertura de acciones


5. ¿CÓMO SE ACTUALIZA Seguimiento.xlsx?
• 1. Haces commit con mensaje descriptivo
• 2. Haces push a tu rama en GitHub
• 3. Creas Pull Request
• 4. Federico aprueba y mergea
• 5. I Script automático detecta el merge
• 6. I Lee el commit y detecta qué tarea se completó
• 7. I Actualiza Seguimiento.xlsx automáticamente
• 8. I Los gráficos de progreso se regeneran
6. I QUÉ HACER vs I QUÉ NO HACER
I HACER
I NO HACER
Commits descriptivos
Commits sin mensaje
Crear rama feature/fix/docs/
Trabajar en main
Mensajes claros y detallados
Mensajes genéricos
Esperar aprobación antes de merge
Mergear sin revisar
Seguir el workflow
Editar Seguimiento.xlsx manualmente
7. TAREAS ACTUALES
Fase
Tarea
Estado
Fase 1
Descargar listas CEDEARs/ADRs
I COMPLETADA
Fase 2
Descargar precios yfinance
I COMPLETADA
Fase 3
Descargar financieros EDGAR
I COMPLETADA
Fase 4
Calcular 13 ratios
I COMPLETADA
Fase 5
Generar screener final
I COMPLETADA
Mejoras
Mejorar cobertura de precios (78% → 90%)
I DISPONIBLE
Mejoras
Agregar 50+ CEDEARs nuevos
I DISPONIBLE
8. PREGUNTAS FRECUENTES
P: ¿Cómo sé si mi tarea se detectó?
R: Mira Seguimiento.xlsx. Si aparece como COMPLETADA, está ok.


P: ¿Puedo editar Seguimiento.xlsx?
R: NO. Se actualiza automáticamente. Editar manualmente lo rompe.
P: ¿Con qué frecuencia se actualiza?
R: Automáticamente cada vez que mergean a main (~1 minuto).
P: ¿Qué pasa si mi PR no aprueba?
R: Haces más commits en la misma rama. La PR se actualiza sola.
P: ¿Qué necesito instalar?
R: pip install -r scripts/screener/requirements.txt
9. REFERENCIAS
• GitHub: https://github.com/fmonfasani/catalaxia_finance
• CONTRIBUTING.md: Guía técnica completa
• Contacto: fmonfasani@gmail.com
Documento generado: 2026-06-23 01:12:23
Para: Colaboradores del proyecto Catalaxia Finance
