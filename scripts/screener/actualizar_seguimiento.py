#!/usr/bin/env python3
"""
Script: Actualizar Seguimiento.xlsx automáticamente

Lee commits de GitHub y estado de PRs, actualiza:
- Estado de tareas (PENDIENTE, EN PROGRESO, COMPLETADA)
- % de progreso por fase
- Log de cambios recientes
- Métricas del proyecto

Ejecutar:
  python actualizar_seguimiento.py

O automáticamente con hook post-push:
  git hook post-receive → python actualizar_seguimiento.py
"""

import pandas as pd
import subprocess
from datetime import datetime
from pathlib import Path
import json

# ============================================================================
# PASO 1: LEER COMMITS DE GIT
# ============================================================================

def get_recent_commits(repo_path=".", limit=50):
    """Obtener últimos commits del repo"""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-n", str(limit)],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        commits = []
        for line in result.stdout.strip().split('\n'):
            if line:
                hash_commit, mensaje = line.split(' ', 1)
                commits.append({
                    'hash': hash_commit,
                    'mensaje': mensaje,
                    'tipo': get_commit_type(mensaje),
                    'fecha': datetime.now().strftime('%Y-%m-%d')
                })
        return commits
    except Exception as e:
        print(f"Error leyendo commits: {e}")
        return []

def get_commit_type(mensaje):
    """Extraer tipo de commit (feat, fix, docs, etc)"""
    if mensaje.startswith('feat'):
        return 'Feature'
    elif mensaje.startswith('fix'):
        return 'Bug Fix'
    elif mensaje.startswith('docs'):
        return 'Documentation'
    elif mensaje.startswith('refactor'):
        return 'Refactor'
    elif mensaje.startswith('test'):
        return 'Test'
    else:
        return 'Other'

# ============================================================================
# PASO 2: DEFINIR TAREAS
# ============================================================================

TAREAS = [
    # Fase 1: Extracción
    {'id': 'FASE1-1', 'nombre': 'Script 01: Descargar listas CEDEARs/ADRs', 'fase': 'Fase 1', 'estado': 'COMPLETADA'},
    {'id': 'FASE1-2', 'nombre': 'Script 02: Descargar precios yfinance', 'fase': 'Fase 1', 'estado': 'COMPLETADA'},

    # Fase 2: Financieros
    {'id': 'FASE2-1', 'nombre': 'Script 06: Descargar datos EDGAR', 'fase': 'Fase 2', 'estado': 'COMPLETADA'},

    # Fase 3: Ratios
    {'id': 'FASE3-1', 'nombre': 'Script 07: Calcular 13 ratios', 'fase': 'Fase 3', 'estado': 'COMPLETADA'},

    # Fase 4: Screener final
    {'id': 'FASE4-1', 'nombre': 'Script 08: Generar screener final', 'fase': 'Fase 4', 'estado': 'COMPLETADA'},
    {'id': 'FASE4-2', 'nombre': 'Documentación screener (8 archivos)', 'fase': 'Fase 4', 'estado': 'COMPLETADA'},

    # Fase 5: Mejoras y mantenimiento
    {'id': 'FASE5-1', 'nombre': 'Mejorar cobertura de precios (78% → 90%)', 'fase': 'Fase 5', 'estado': 'PENDIENTE'},
    {'id': 'FASE5-2', 'nombre': 'Agregar 50+ CEDEARs nuevos', 'fase': 'Fase 5', 'estado': 'PENDIENTE'},
    {'id': 'FASE5-3', 'nombre': 'Implementar actualización mensual automática', 'fase': 'Fase 5', 'estado': 'PENDIENTE'},
    {'id': 'FASE5-4', 'nombre': 'Crear dashboard interactivo', 'fase': 'Fase 5', 'estado': 'PENDIENTE'},
]

# ============================================================================
# PASO 3: DETECTAR CAMBIOS EN COMMITS
# ============================================================================

def detect_completed_tasks(commits):
    """Detectar tareas completadas por commits"""
    completed = []

    for commit in commits:
        msg = commit['mensaje'].lower()

        # Detectar qué tarea se completó
        if 'script 01' in msg or 'descargar_cedears_adrs' in msg:
            completed.append('FASE1-1')
        if 'script 02' in msg or 'descargar_precios' in msg:
            completed.append('FASE1-2')
        if 'script 06' in msg or 'descargar_datos_edgar' in msg:
            completed.append('FASE2-1')
        if 'script 07' in msg or 'calcular_ratios' in msg:
            completed.append('FASE3-1')
        if 'script 08' in msg or 'generar_screener' in msg:
            completed.append('FASE4-1')
        if 'documentación' in msg or 'readme' in msg:
            completed.append('FASE4-2')

    return list(set(completed))

# ============================================================================
# PASO 4: GENERAR DATAFRAME Y GUARDAR EXCEL
# ============================================================================

def generate_excel(commits):
    """Generar archivo Seguimiento.xlsx"""

    # Detectar tareas completadas
    completed = detect_completed_tasks(commits)

    # Actualizar estado de tareas
    for tarea in TAREAS:
        if tarea['id'] in completed:
            tarea['estado'] = 'COMPLETADA'

    # Calcular progreso
    total = len(TAREAS)
    completadas = sum(1 for t in TAREAS if t['estado'] == 'COMPLETADA')
    progreso_total = (completadas / total) * 100 if total > 0 else 0

    # Crear DataFrame de Tareas
    df_tareas = pd.DataFrame(TAREAS)
    df_tareas['Progreso'] = df_tareas['estado'].apply(lambda x: 100 if x == 'COMPLETADA' else (50 if x == 'EN PROGRESO' else 0))

    # Crear DataFrame de Commits
    df_commits = pd.DataFrame(commits[:20])  # Últimos 20 commits

    # Crear DataFrame de Progreso por Fase
    fases = df_tareas.groupby('fase').agg({
        'estado': 'count',
        'Progreso': 'mean'
    }).round(0)
    fases.columns = ['Total Tareas', '% Progreso']
    fases = fases.reset_index()

    # Guardar en Excel
    excel_path = 'Seguimiento.xlsx'

    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        # Sheet 1: Tareas
        df_tareas.to_excel(writer, sheet_name='Tareas', index=False)

        # Sheet 2: Progreso por Fase
        fases.to_excel(writer, sheet_name='Progreso', index=False)

        # Sheet 3: Commits Recientes
        if not df_commits.empty:
            df_commits.to_excel(writer, sheet_name='Commits', index=False)

        # Sheet 4: Resumen
        resumen_data = {
            'Métrica': [
                'Total Tareas',
                'Completadas',
                'En Progreso',
                'Pendientes',
                '% Completado',
                'Última Actualización'
            ],
            'Valor': [
                total,
                completadas,
                sum(1 for t in TAREAS if t['estado'] == 'EN PROGRESO'),
                sum(1 for t in TAREAS if t['estado'] == 'PENDIENTE'),
                f"{progreso_total:.1f}%",
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ]
        }
        df_resumen = pd.DataFrame(resumen_data)
        df_resumen.to_excel(writer, sheet_name='Resumen', index=False)

    print(f"✓ Seguimiento.xlsx actualizado")
    print(f"  - Total tareas: {total}")
    print(f"  - Completadas: {completadas} ({progreso_total:.1f}%)")
    print(f"  - Commits procesados: {len(commits)}")
    print(f"  - Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ============================================================================
# PASO 5: EJECUTAR
# ============================================================================

if __name__ == "__main__":
    print("🔄 Actualizando Seguimiento.xlsx...")
    print("")

    # Obtener commits recientes
    commits = get_recent_commits()

    if commits:
        # Generar Excel
        generate_excel(commits)
        print("")
        print("✅ Seguimiento.xlsx actualizado exitosamente")
    else:
        print("❌ No se pudieron leer los commits")
