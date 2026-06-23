#!/usr/bin/env python3
"""
Crear PDF con guía para colaboradores
Requiere: pip install reportlab
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from datetime import datetime

# ============================================================================
# CREAR PDF
# ============================================================================

def create_pdf():
    """Crear PDF con guía para colaboradores"""

    # Configuración
    pdf_path = "GUIA_COLABORADORES.pdf"
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []

    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=20,
        alignment=1  # Center
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2E5090'),
        spaceAfter=12,
        spaceBefore=12
    )

    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=11,
        spaceAfter=8
    )

    # Título
    story.append(Paragraph("📋 GUÍA PARA COLABORADORES", title_style))
    story.append(Paragraph("Catalaxia Finance - Screener Financiero 218+ Acciones", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))

    # Sección 1: Introducción
    story.append(Paragraph("1. OBJETIVO DEL PROYECTO", heading_style))
    story.append(Paragraph(
        "Mantener un archivo de seguimiento <b>Seguimiento.xlsx</b> que se actualiza "
        "<b>automáticamente</b> según el progreso de las tareas en GitHub. "
        "Los colaboradores solo necesitan hacer commits descriptivos; el sistema "
        "detecta automáticamente cuándo una tarea se completó.",
        body_style
    ))
    story.append(Spacer(1, 0.2*inch))

    # Sección 2: Workflow
    story.append(Paragraph("2. WORKFLOW - 6 PASOS SIMPLES", heading_style))

    steps = [
        ("Paso 1", "Clonar repositorio",
         "git clone https://github.com/fmonfasani/catalaxia_finance.git"),
        ("Paso 2", "Crear rama para tu tarea",
         "git checkout -b feature/nombre-tarea"),
        ("Paso 3", "Editar archivos y hacer commits",
         "git commit -m 'feat: descripción clara'"),
        ("Paso 4", "Push a GitHub",
         "git push origin feature/nombre-tarea"),
        ("Paso 5", "Crear Pull Request",
         "Abrir PR en GitHub y esperar aprobación"),
        ("Paso 6", "Automático después del merge",
         "Sistema detecta y actualiza Seguimiento.xlsx ✅"),
    ]

    for i, (paso, titulo, comando) in enumerate(steps, 1):
        text = f"<b>{paso}:</b> {titulo}<br/><font color='#666666' size='10'>{comando}</font>"
        story.append(Paragraph(text, body_style))
        story.append(Spacer(1, 0.1*inch))

    story.append(Spacer(1, 0.2*inch))

    # Sección 3: Branch naming
    story.append(Paragraph("3. CONVENCIÓN DE NOMBRES DE RAMAS", heading_style))

    branches_data = [
        ["feature/", "Nueva funcionalidad", "feature/agregar-cedears-20"],
        ["fix/", "Corrección de bugs", "fix/error-descarga-precios"],
        ["docs/", "Documentación", "docs/agregar-ejemplos"],
        ["refactor/", "Mejora de código", "refactor/optimizar-ratios"],
    ]

    branches_table = Table(branches_data, colWidths=[1.2*inch, 2.5*inch, 2*inch])
    branches_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E5090')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
    ]))

    story.append(branches_table)
    story.append(Spacer(1, 0.3*inch))

    # Sección 4: Commit messages
    story.append(Paragraph("4. MENSAJE DE COMMITS", heading_style))
    story.append(Paragraph(
        "<b>IMPORTANTE:</b> Los mensajes descriptivos son lo más importante. "
        "El sistema automático analiza los commits para detectar qué tarea se completó.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))

    story.append(Paragraph(
        "<font color='#666666'>feat: agregar 20 CEDEARs nuevos (127 → 147)<br/>"
        "<br/>"
        "- Agregar tickers: ACTA, AGRO, ALTY, ... (20 total)<br/>"
        "- Validar contra lista oficial BYMA<br/>"
        "- Testar descarga de precios con yfinance<br/>"
        "- Aumentar cobertura de acciones</font>",
        body_style
    ))
    story.append(Spacer(1, 0.3*inch))

    # Página 2
    story.append(PageBreak())

    # Sección 5: Cómo funciona la automatización
    story.append(Paragraph("5. ¿CÓMO SE ACTUALIZA Seguimiento.xlsx?", heading_style))

    auto_steps = [
        "1. Haces commit con mensaje descriptivo",
        "2. Haces push a tu rama en GitHub",
        "3. Creas Pull Request",
        "4. Federico aprueba y mergea",
        "5. 🤖 Script automático detecta el merge",
        "6. 🤖 Lee el commit y detecta qué tarea se completó",
        "7. 🤖 Actualiza Seguimiento.xlsx automáticamente",
        "8. ✅ Los gráficos de progreso se regeneran",
    ]

    for step in auto_steps:
        story.append(Paragraph(f"• {step}", body_style))

    story.append(Spacer(1, 0.3*inch))

    # Sección 6: Lo que SÍ y NO hacer
    story.append(Paragraph("6. ✅ QUÉ HACER vs ❌ QUÉ NO HACER", heading_style))

    do_dont_data = [
        ["✅ HACER", "❌ NO HACER"],
        ["Commits descriptivos", "Commits sin mensaje"],
        ["Crear rama feature/fix/docs/", "Trabajar en main"],
        ["Mensajes claros y detallados", "Mensajes genéricos"],
        ["Esperar aprobación antes de merge", "Mergear sin revisar"],
        ["Seguir el workflow", "Editar Seguimiento.xlsx manualmente"],
    ]

    do_dont_table = Table(do_dont_data, colWidths=[3.5*inch, 3.5*inch])
    do_dont_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#28A745')),
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#DC3545')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#D4EDDA')),
        ('BACKGROUND', (1, 1), (1, -1), colors.HexColor('#F8D7DA')),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
    ]))

    story.append(do_dont_table)
    story.append(Spacer(1, 0.3*inch))

    # Sección 7: Tareas actuales
    story.append(Paragraph("7. TAREAS ACTUALES", heading_style))

    tasks_data = [
        ["Fase", "Tarea", "Estado"],
        ["Fase 1", "Descargar listas CEDEARs/ADRs", "✅ COMPLETADA"],
        ["Fase 2", "Descargar precios yfinance", "✅ COMPLETADA"],
        ["Fase 3", "Descargar financieros EDGAR", "✅ COMPLETADA"],
        ["Fase 4", "Calcular 13 ratios", "✅ COMPLETADA"],
        ["Fase 5", "Generar screener final", "✅ COMPLETADA"],
        ["Mejoras", "Mejorar cobertura de precios (78% → 90%)", "⏳ DISPONIBLE"],
        ["Mejoras", "Agregar 50+ CEDEARs nuevos", "⏳ DISPONIBLE"],
    ]

    tasks_table = Table(tasks_data, colWidths=[1.5*inch, 3.5*inch, 1.5*inch])
    tasks_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E5090')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))

    story.append(tasks_table)
    story.append(Spacer(1, 0.3*inch))

    # Sección 8: FAQ
    story.append(Paragraph("8. PREGUNTAS FRECUENTES", heading_style))

    faqs = [
        ("¿Cómo sé si mi tarea se detectó?", "Mira Seguimiento.xlsx. Si aparece como COMPLETADA, está ok."),
        ("¿Puedo editar Seguimiento.xlsx?", "NO. Se actualiza automáticamente. Editar manualmente lo rompe."),
        ("¿Con qué frecuencia se actualiza?", "Automáticamente cada vez que mergean a main (~1 minuto)."),
        ("¿Qué pasa si mi PR no aprueba?", "Haces más commits en la misma rama. La PR se actualiza sola."),
        ("¿Qué necesito instalar?", "pip install -r scripts/screener/requirements.txt"),
    ]

    for pregunta, respuesta in faqs:
        text = f"<b>P: {pregunta}</b><br/>R: {respuesta}"
        story.append(Paragraph(text, body_style))
        story.append(Spacer(1, 0.15*inch))

    story.append(Spacer(1, 0.3*inch))

    # Sección final
    story.append(Paragraph("9. REFERENCIAS", heading_style))
    story.append(Paragraph(
        "• GitHub: https://github.com/fmonfasani/catalaxia_finance<br/>"
        "• CONTRIBUTING.md: Guía técnica completa<br/>"
        "• Contacto: fmonfasani@gmail.com",
        body_style
    ))

    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(
        f"<b>Documento generado:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>"
        "<b>Para:</b> Colaboradores del proyecto Catalaxia Finance",
        body_style
    ))

    # Generar PDF
    doc.build(story)
    print(f"OK - PDF creado: {pdf_path}")
    print(f"  Tamaño: {(Path(pdf_path).stat().st_size / 1024):.1f} KB")

if __name__ == "__main__":
    try:
        from pathlib import Path
        create_pdf()
    except ImportError:
        print("Error: Instalar reportlab primero:")
        print("  pip install reportlab")
