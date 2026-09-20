# -*- coding: utf-8 -*-
"""Ejemplo de SPEC para el motor webshooks_pptx (data -> deck).
Este archivo NO tiene diseño: sólo datos. Cambiás el contenido y el motor
arma el .pptx branded. Corré:  python ejemplo_propuesta.py

Muestra todos los tipos de slide: cover, seccion, resumen, alcance, stack,
tabla, equipo, cronograma, inversion, cierre.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from webshooks_pptx import build

HERE = os.path.dirname(os.path.abspath(__file__))

SPEC = {
    "out": os.path.join(HERE, "ejemplo_propuesta.pptx"),

    # -------- portada (SPEC["cover"]) --------
    "cover": {
        "brand_tag": "Desarrollo de Software · LATAM",
        "title_left": ["Propuesta", "Comercial"],
        "subtitle_left": "Screener fundamental de CEDEARs y acciones argentinas, "
                         "con datos oficiales y trazables.",
        "cliente": "Catalaxia S.A.",
        "fecha": "Julio 2026",
        "headline": ["Convertí data pública", "en decisiones de inversión",
                     "con una plataforma propia."],
        "solution": "Screener web que integra SEC, CNV e IAMC, calcula ~16 ratios "
                    "fundamentales y expone empresa + instrumento (CEDEAR/ADR) en una sola vista.",
        "chips": ["FastAPI", "React", "PostgreSQL", "Docker", "Datos oficiales"],
    },

    "slides": [
        # -------- divisor de sección --------
        {"type": "seccion", "num": "01", "title": "El proyecto en una vista",
         "subtitle": "Qué construimos, para quién y con qué alcance.", "accent": "3B82F6"},

        # -------- resumen (KPIs + qué incluye) --------
        {"type": "resumen",
         "title": "Resumen ejecutivo",
         "subtitle": "Una plataforma de análisis fundamental lista para operar, no un prototipo.",
         "stats": [("733", "instrumentos\nCEDEAR / ADR"), ("~16", "ratios\nfundamentales"),
                   ("3", "fuentes oficiales\nSEC · CNV · IAMC"), ("4", "semanas\nde desarrollo")],
         "incluye_label": "¿Qué incluye?",
         "izq": [["Screener web", "filtros por ratio, sector y país."],
                 ["Ficha de empresa", "estados financieros + ratios calculados."],
                 ["Doble precio", "acción local y ADR/CEDEAR en la misma vista."]],
         "der": [["API propia", "FastAPI documentada (OpenAPI)."],
                 ["Datos trazables", "cada dato guarda su source_url."],
                 ["Deploy reproducible", "Docker + Postgres, un comando."]],
        },

        # -------- alcance (3 columnas) --------  [prioridad del usuario]
        {"type": "alcance",
         "title": "Alcance del trabajo",
         "subtitle": "Qué entra en esta propuesta, agrupado por capa.",
         "cols": [
            {"head": "Datos", "items": [
                ["Extracción", "SEC (10-K/20-F), CNV, IAMC."],
                ["Normalización", "ratios homogéneos entre fuentes."],
                ["Trazabilidad", "source_url por cada campo."],
                ["Cache", "re-ejecución idempotente por bloque."]]},
            {"head": "Producto", "items": [
                ["Screener", "tabla filtrable + orden por ratio."],
                ["Ficha", "empresa + instrumento (2 niveles)."],
                ["Export", "CSV / JSON descargable."],
                ["Auth", "login y roles básicos."]]},
            {"head": "Plataforma", "items": [
                ["API", "FastAPI + OpenAPI."],
                ["DB", "PostgreSQL 16."],
                ["Deploy", "Docker Compose reproducible."],
                ["Handover", "docs + repo + accesos."]]},
         ]},

        # -------- stack (2 tablas + nota) --------  [prioridad del usuario]
        {"type": "stack",
         "title": "Stack técnico",
         "subtitle": "Tecnologías estándar, mantenibles y sin lock-in.",
         "left_title": "BACKEND",
         "backend": [("Lenguaje", "Python 3.11"), ("Framework", "FastAPI"),
                     ("Base de datos", "PostgreSQL 16"), ("ORM / migr.", "SQLAlchemy + Alembic"),
                     ("Datos", "pandas · httpx"), ("Tests", "pytest")],
         "right_title": "FRONTEND / INFRA",
         "frontend": [("UI", "React + Vite"), ("Estilos", "Tailwind CSS"),
                      ("Datos/estado", "TanStack Query"), ("Contenedores", "Docker Compose"),
                      ("Reverse proxy", "Traefik / nginx"), ("CI", "GitHub Actions")],
         "nota_title": "Sin lock-in",
         "nota": "Todo el stack es open-source y estándar de industria: cualquier equipo "
                 "puede continuar el proyecto sin dependencias propietarias.",
        },

        # -------- tabla libre --------
        {"type": "tabla",
         "title": "Entregables por hito",
         "subtitle": "Qué recibís y cuándo.",
         "headers": ["Semana", "Entregable", "Estado al cierre"],
         "cw": [1.4, 4.2, 3.0],
         "rows": [
            ["Semana 1", "Infra + API base + esquema DB", ("Navegable", "43A047")],
            ["Semana 2", "Front real conectado a la API", ("Navegable", "43A047")],
            ["Semana 3", "Screener + ficha + doble precio", ("Funcional", "3B82F6")],
            ["Semana 4", "QA, export, docs y handover", ("Entregado", "F5821F")],
         ]},

        # -------- equipo --------
        {"type": "equipo",
         "title": "Equipo asignado",
         "subtitle": "Roles claros, un punto de contacto.",
         "personas": [
            {"name": "Tech Lead / Backend", "items": [
                ["Responsable", "arquitectura y API."],
                ["Dedicación", "full-time."]]},
            {"name": "Frontend", "items": [
                ["Responsable", "screener y ficha."],
                ["Dedicación", "full-time."]]},
            {"name": "Data Engineer", "items": [
                ["Responsable", "extracción y normalización."],
                ["Dedicación", "part-time."]]},
            {"name": "PM / QA", "items": [
                ["Responsable", "seguimiento y calidad."],
                ["Dedicación", "part-time."]]},
         ]},

        # -------- cronograma --------
        {"type": "cronograma",
         "title": "Cronograma",
         "subtitle": "4 semanas · entregas navegables desde la semana 1.",
         "semanas": [
            {"t": "Semana 1", "items": [["Infra", "VPS + Docker + Postgres."],
                                        ["API base", "endpoints + OpenAPI."],
                                        ["DB", "esquema + migraciones."]]},
            {"t": "Semana 2", "items": [["Front", "layout + routing."],
                                        ["Conexión", "front ↔ API real."],
                                        ["Auth", "login básico."]]},
            {"t": "Semana 3", "items": [["Screener", "filtros + orden."],
                                        ["Ficha", "empresa + instrumento."],
                                        ["Doble precio", "local + ADR."]]},
            {"t": "Semana 4", "items": [["QA", "tests + fixes."],
                                        ["Export", "CSV / JSON."],
                                        ["Handover", "docs + accesos."]]},
         ]},

        # -------- inversión --------
        {"type": "inversion",
         "title": "Inversión",
         "subtitle": "Precio cerrado, sin costos ocultos.",
         "precio_label": "Inversión total del proyecto",
         "precio": "USD 6.800",
         "precio_nota": "Alcance cerrado · 4 semanas",
         "incluye": "Incluye desarrollo, deploy reproducible, documentación y "
                    "2 semanas de soporte post-entrega.",
         "opciones_label": "Opciones de pago",
         "opciones": [
            {"t": "50 / 50", "det": "Anticipo y entrega", "monto": "2 x 3.400", "color": "3B82F6"},
            {"t": "40 / 30 / 30", "det": "Por hitos", "monto": "3 pagos", "color": "43A047"},
            {"t": "Contado", "det": "Pago único al inicio", "monto": "6.460", "color": "F5821F"},
         ]},

        # -------- cierre --------
        {"type": "cierre",
         "title": "Próximos pasos",
         "subtitle": "Del sí al kickoff en 48 horas.",
         "pasos": [
            {"t": "Aprobación", "d": "Confirmás alcance y forma de pago."},
            {"t": "Anticipo", "d": "Primer pago y firma de la propuesta."},
            {"t": "Kickoff", "d": "Accesos, repos y arranque de Semana 1."},
            {"t": "Entrega", "d": "Handover a las 4 semanas + soporte."},
         ],
         "resumen": [("Duración", "4 semanas"), ("Inversión", "USD 6.800"),
                     ("Stack", "FastAPI + React"), ("Entrega", "reproducible + docs"),
                     ("Soporte", "2 semanas"), ("Contacto", "webshooks.com")],
         "validez": "Propuesta válida por 30 días desde su emisión.",
        },
    ],
}

if __name__ == "__main__":
    build(SPEC)
