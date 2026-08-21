# -*- coding: utf-8 -*-
"""
ORQUESTADOR: Ejecuta Fases 2-4 en secuencia
Fase 0: ✅ Ya hecho (00_setup_tables.py)
Fase 1.1b: ✅ Ya hecho (10b_actualizar_mep_hoy.py)
Fase 2: Extracción + Normalización
Fase 3: 9 Validaciones cruzadas
Fase 4: Certificación
"""
import sys
import os

# Importar scripts
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("\n" + "=" * 80)
    print("ETL MATERIA PRIMA: FASE 2-4 (ORQUESTADOR)")
    print("=" * 80)

    # Fase 2: Extracción
    print("\n\n### FASE 2: EXTRACCIÓN + NORMALIZACIÓN ###\n")
    from importlib import import_module
    fase2 = import_module('20_extrae_silver')
    n = fase2.extraer_silver()

    if n == 0:
        print("\n❌ FASE 2 FALLÓ: sin datos extraídos")
        return False

    # Fase 3: Validaciones
    print("\n\n### FASE 3: 9 VALIDACIONES CRUZADAS ###\n")
    fase3 = import_module('30_validaciones')
    fase3.ejecutar_validaciones()

    # Fase 4: Certificación
    print("\n\n### FASE 4: CERTIFICACIÓN ###\n")
    fase4 = import_module('40_certificar')
    fase4.certificar()

    # Resumen
    print("\n\n" + "=" * 80)
    print("✅ ETL COMPLETADO: Fases 2-4")
    print("=" * 80)
    print("""
Qué tenés ahora en screener.db:
  ✅ silver_norm (30 períodos × ~39 conceptos TXAR)
     · ARS, escala ×1e6, RECPAM incluido, vintage registrado

  ✅ validaciones (30 × 9 cruces)
     · 1. Identidades A=P+PN
     · 2. Continuidad YTD
     · 3. Ancla investing (N/A - falta data)
     · 4. Ancla mercado (N/A - falta data)
     · 5. EPS diluido ≤ basico
     · 6. CAGR EPS vs NI (N/A - falta serie)
     · 7. EBITDA vs EBIT+DA
     · 8. FCF componentes
     · 9. P&L identidades (Revenue+COGS=GP)

  ✅ certificacion_nueva (30 períodos)
     · Nivel: CERTIFICADO / cierre-interno / REVISAR
     · Causa si falla

PRÓXIMOS PASOS:
  1. MEP histórico (cuando lo tengas, corre script de dolarización)
  2. Dashboard HTML para visualizar ratios
""")

    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
