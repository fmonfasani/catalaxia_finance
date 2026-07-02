# Arquitectura del Sistema de Descubrimiento Automático de Empresas Only-BYMA

**Documento:** `ARQUITECTURA_DESCUBRIMIENTO_ONLYBYMA.md`  
**Versión:** 1.0  
**Fecha:** Junio 2026  
**Proyecto:** Catalaxia Finance  

---

## Tabla de Contenidos

1. [Análisis Crítico del Pipeline Actual](#1-análisis-crítico-del-pipeline-actual)
2. [Debilidades Detectadas](#2-debilidades-detectadas)
3. [Riesgos Identificados](#3-riesgos-identificados)
4. [Arquitectura Objetivo](#4-arquitectura-objetivo)
5. [Pipeline Completo Paso a Paso](#5-pipeline-completo-paso-a-paso)
6. [Componentes del Sistema](#6-componentes-del-sistema)
7. [Flujo de Datos](#7-flujo-de-datos)
8. [Estrategias de Fallback](#8-estrategias-de-fallback)
9. [Actualización Automática](#9-actualización-automática)
10. [Modelo de Datos Maestro](#10-modelo-de-datos-maestro)
11. [Algoritmos de Reconciliación](#11-algoritmos-de-reconciliación)
12. [Roadmap de Implementación](#12-roadmap-de-implementación)
13. [Riesgos Técnicos y Operativos](#13-riesgos-técnicos-y-operativos)
14. [Recomendaciones Finales](#14-recomendaciones-finales)

---

## 1. Análisis Crítico del Pipeline Actual

### 1.1 Arquitectura existente

El pipeline actual está compuesto por scripts independientes que evolucionaron orgánicamente:

```
┌─ CSV manual (acciones_solo_byma.csv) ─────────────────────────┐
│  57 empresas listadas a mano, sin validación cruzada           │
└──────────────────────────┬────────────────────────────────────┘
                           ▼
┌─ discovery CNV ───────────────────────────────────────────────┐
│  10_empresas.py → 79.772 presentaciones → links_eeff.csv      │
│  18.492 EEFF identificados por heurística (es_eeff=1)         │
└──────────────────────────┬────────────────────────────────────┘
                           ▼
┌─ extracción AIF2 ────────────────────────────────────────────┐
│  parser_cnv_aif2.py → solo formTypeId=147                     │
│  7/8 tickers con datos OK (ALUA, CVH, GBAN, LEDE, METR,      │
│  MOLA, TRAN)                                                  │
└──────────────────────────┬────────────────────────────────────┘
                           ▼
┌─ extracción IR PDF ──────────────────────────────────────────┐
│  cnv_ir/pipeline.py → descubre en IR websites                 │
│  ~14 PDFs cacheados, geo-bloqueado fuera AR                   │
└──────────────────────────┬────────────────────────────────────┘
                           ▼
┌─ cnv_auto.py (6-K EDGAR) ────────────────────────────────────┐
│  9/16 ADR con datos trimestrales                              │
└──────────────────────────┬────────────────────────────────────┘
                           ▼
                    ┌──────────────┐
                    │ cnv_estados  │
                    │ (367 rows)   │
                    └──────────────┘
```

### 1.2 Problemas estructurales

1. **No hay un repositorio único de entidades.** `empresas.csv`, `acciones_solo_byma.csv`, `links_eeff.csv` y `empresas` (SQLite) coexisten sin sincronización.

2. **El descubrimiento es one-shot.** No hay mecanismo para detectar nuevas empresas que comiencen a cotizar, fusiones, cambios de ticker o deslistados.

3. **La validación cruzada es inexistente.** No se cruza CUIT, ticker, ISIN, CNV ID entre fuentes. Una empresa puede estar duplicada, con datos contradictorios, o perdida.

4. **No hay estado del proceso.** No se sabe qué empresas se procesaron, cuáles fallaron, por qué fallaron, y si el fallo es permanente o transitorio.

5. **Los fallos son silenciosos.** Si un IR website cambia de URL, el pipeline simplemente no encuentra datos. Sin alertas.

6. **Dependencia de una sola fuente.** Si CNV AIF2 cambia su HTML (por ejemplo, elimina el formTypeId=147), el pipeline entero se detiene para ese ticker.

7. **Sin estrategia de reintento.** Rate limiting, timeouts, errores 5xx — todos tratan igual, sin backoff.

8. **El universo de empresas está fragmentado.** 19 tickers objetivo, 56 en acciones_solo_byma.csv, 57 en empresas.csv, 16 adr_arg. No hay un mapping explícito de cuáles son cuáles y cómo se relacionan.

---

## 2. Debilidades Detectadas

| # | Debilidad | Impacto | Evidencia |
|---|-----------|---------|-----------|
| D1 | CSV manual como fuente única de verdad | No escala, se desactualiza | GRIM no estaba en links_eeff.csv pero sí en links_eeff_refined.csv (44 entradas) |
| D2 | FormTypeId fijo para parsing | Pierde datos de formatos alternativos | GCLA (Controladas) y GRIM (Migración) no parseables |
| D3 | Sin heartbeat de fuentes | No se detecta cuando una fuente cambia | IR website de GRIM devuelve 404 silenciosamente |
| D4 | Sin modelado de estado | No hay trazabilidad de qué falló y por qué | No hay diferencia entre "no existen datos" y "falló la descarga" |
| D5 | Sin normalización de identificadores | Múltiples IDs sin relación entre sí | ticker, CUIT, CNV ID, CIK coexistene sin mapa maestro |
| D6 | Sin detección de cambios | Una empresa puede cambiar de ticker y perderse | Tickers reasignados (GOLD/B, CHA) documentados en historia |
| D7 | Sin umbrales de calidad | Datos inválidos pueden pasar | Una identidad 0% es ideal, pero 5% debería alertar, no bloquear |
| D8 | Acoplamiento descubrimiento-extracción | El mismo script descubre y parsea | No se puede re-correr extracción sin re-descubrir |

---

## 3. Riesgos Identificados

### 3.1 Riesgos Técnicos

| Riesgo | Probabilidad | Impacto | Mitigación Propuesta |
|--------|-------------|---------|---------------------|
| CNV AIF2 cambia estructura HTML | Media | Alto | Parser versionado + tests HTML contra snapshot |
| CNV AIF2 agrega geo-bloqueo | Baja | Crítico | Fallback a IR PDF + EDGAR 6-K + yfinance |
| IR website cambia URL o desaparece | Alta | Medio | Fuente terciaria: Bolsar, Caja de Valores, scraping histórico |
| SEC EDGAR cambia API | Baja | Alto | Monitoreo heartbeat semanal + parser XML/XBRL directo |
| Yahoo Finance cambia API | Media | Medio | Fuentes alternativas: Investing.com API, Alpha Vantage, Barchart |
| Rate limiting en CNV/SEC | Alta | Bajo | Backoff exponencial + jitter + cola de prioridad |
| Certificado SSL vencido (fuentes AR) | Media | Bajo | verify=False con logging + reintento con verificación |

### 3.2 Riesgos Operativos

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Empresa cambia de ticker | Datos huérfanos | Tabla timeline_ticker + alerta en discrepancia |
| Empresa se fusiona | Doble conteo o pérdida | Detección por CUIT + ISIN invariantes |
| Empresa se deslista | Código muerto | Flag activo/inactivo, retención de histórico |
| Nuevo emisor no detectado | Sesgo en universo | Monitoreo periódico de CNV + BYMA + Bolsar |
| Cambio contable (NIC 29) | Ratios no comparables | fecha_reexpresion obligatoria en todos los datos |

---

## 4. Arquitectura Objetivo

### 4.1 Principios de Diseño

1. **Single Source of Truth (SSOT):** Una tabla maestra de empresas, derivada de múltiples fuentes, con trazabilidad de origen.
2. **Inmunidad al cambio de fuente:** Ningún pipeline depende de una única fuente. Todas las fuentes son "primer intento con fallback".
3. **Estado explícito:** Cada operación registra su resultado (éxito, fallo transitorio, fallo permanente), timestamp, y mensaje.
4. **Pipeline = DAG de etapas independientes:** Cada etapa tiene input, output, y puede re-ejecutarse independientemente.
5. **Calidad como parte del flujo:** Validación no es un paso opcional. Cada etapa valida su output antes de pasarlo a la siguiente.
6. **Descubrimiento continuo:** No es una tarea one-shot. Se ejecuta periódicamente y detecta delta.

### 4.2 Arquitectura de Alto Nivel

```
┌─────────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR (Scheduler)                       │
│                  Apache Airflow / Prefect / cron                     │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
  ┌────────────────────────┼────────────────────────────┐
  ▼                        ▼                            ▼
┌─────────────┐    ┌──────────────┐    ┌──────────────────┐
│ DISCOVERY   │    │ RECONCILIER  │    │ MASTER STORE     │
│ Layer       │───▶│ Layer        │───▶│ (empresa_master) │
│ (multi-     │    │ (cross-      │    │                  │
│  source)    │    │  reference)  │    │                  │
└─────────────┘    └──────────────┘    └──────────────────┘
       │                                        │
       ▼                                        ▼
┌─────────────┐                     ┌──────────────────┐
│ FETCHER    │                     │ ETL EEFF         │
│ Layer      │────────────────────▶│ Layer            │
│ (EEFF      │                     │ (AIF2, IR, 6-K)  │
│  download) │                     │                  │
└─────────────┘                     └──────────────────┘
                                            │
                                            ▼
                                    ┌──────────────────┐
                                    │ cnv_estados      │
                                    │ + calidad_flags   │
                                    └──────────────────┘
                                            │
                                            ▼
                                    ┌──────────────────┐
                                    │ RATIOS &         │
                                    │ DASHBOARD        │
                                    └──────────────────┘
```

### 4.3 Capas vs. Componentes Acoplados

| Capa | Responsabilidad | NO debe hacer |
|------|----------------|---------------|
| **Discovery** | Encontrar candidatos, extraer pares (id, fuente) | Validar, persistir |
| **Reconcilier** | Cruzar fuentes, detectar conflictos, resolver identidad | Descubrir, extraer datos financieros |
| **Master Store** | Persistir entidad maestra, trackear cambios, versionar | Decidir qué empresa es válida |
| **Fetcher** | Descargar EEFF desde fuente específica | Interpretar, validar |
| **ETL EEFF** | Parsear, mapear códigos, calcular identidad, cargar a DB | Descubrir fuentes |

---

## 5. Pipeline Completo Paso a Paso

### 5.1 Discovery

```
INPUT: URL/API de cada fuente
OUTPUT: tabla discovery_raw (fuente, id_externo, metadata, timestamp)

Etapas:
  1. Scrape CNV listado de emisores (CNV API o HTML)
  2. Scrape BYMA listado de cotizaciones
  3. Scrape Bolsar listado de especies
  4. Consultar OpenFIGI por mercado=XBOG (Bolsa de Buenos Aires)
  5. Consultar Yahoo Finance por exchange=.BA (BYMA)
  6. Consultar SEC company_tickers por país=Argentina
  7. Consultar Wikidata query por empresas listadas en BYMA
  8. (Opcional) Crawlear Caja de Valores
```

### 5.2 Normalización

```
INPUT: discovery_raw (pares id-fuente no normalizados)
OUTPUT: discovery_normalized (structura canónica)

Por cada par (id, fuente):
  1. Aplicar normalizador de la fuente (ej: CNV-ID→int, ticker→strip)
  2. Extraer metadatos disponibles (nombre, CUIT, estado)
  3. Descartar duplicados intra-fuente
  4. Asignar score de confianza inicial (basado en fuente)
```

### 5.3 Enriquecimiento

```
INPUT: discovery_normalized
OUTPUT: discovery_enriched (más identificadores secundarios)

Para cada candidato:
  1. Buscar CUIT por CNV ID → Razon Social → AFIP
  2. Buscar ISIN por ticker BYMA → OpenFIGI o Bolsar
  3. Buscar CIK por ticker USA → SEC company_tickers
  4. Buscar FIGI por ISIN → OpenFIGI
  5. Buscar LEI por CUIT → GLEIF
  6. Buscar cotización USA por relación ADR → EDGAR
```

### 5.4 Validación Cruzada

```
INPUT: discovery_enriched
OUTPUT: discovery_validated (candidatos con score, conflictos)

Para cada par de candidatos (A, B) que comparten ≥1 id:
  1. Comparar nombre → fuzzy match score
  2. Comparar CUIT → exact match
  3. Comparar ISIN → exact match (si ambos tienen)
  4. Si coinciden: fusionar candidatos (merge)
  5. Si no coinciden: marcar conflicto, log, require revisión
```

### 5.5 Consolidación

```
INPUT: discovery_validated
OUTPUT: empresa_master (entidad maestra única)

Por cada cluster de candidatos fusionados:
  1. Elegir ticker BYMA como primary_key
  2. Elegir nombre oficial = CNV (fuente regulatoria)
  3. Guardar todos los identificadores con origen y timestamp
  4. Calcular score de completitud (% de IDs resueltos)
  5. Marcar estado: activo, potencial (no confirmado), baja
```

### 5.6 Persistencia

```
INPUT: empresa_master
OUTPUT: SQLite empresa_master table + versioned snapshots

Escribir a DB:
  1. empresa_master (entidad actual)
  2. empresa_master_history (snapshot por timestamp)
  3. discovery_log (trazabilidad de cada descubrimiento)
  4. conflict_log (alertas de validación cruzada)
```

### 5.7 Actualización

```
INPUT: base de entidades actual
OUTPUT: delta report

Ejecución periódica:
  1. Re-ejecutar discovery completo (todas las fuentes)
  2. Comparar contra snapshot anterior
  3. Detectar: nuevas, bajas, cambios de ticker, cambios de nombre
  4. Generar reporte de cambios
  5. Notificar si hubo cambios inesperados
```

### 5.8 Monitoreo

```
INPUT: logs de todas las etapas
OUTPUT: health dashboard

Métricos por etapa:
  - Tiempo de ejecución
  - Tasa de éxito/fracaso
  - Cantidad de entidades descubiertas
  - Cantidad de conflictos detectados
  - Cantidad de cambios desde última ejecución
  - Heartbeat de cada fuente (status code, response time)
```

### 5.9 Consumo por ETL Financiero

```
INPUT: empresa_master (campo: fuente_eeff_primaria)
OUTPUT: cnv_estados poblado

Para cada empresa activa:
  1. Leer fuente_eeff_primaria recomendada
  2. Ejecutar Fetcher correspondiente
  3. Validar con reglas de identidad contable
  4. Cargar a cnv_estados
  5. Si falla: probar fuente_eeff_secundaria
  6. Si todas fallan: marcar empresa como "sin datos"
```

---

## 6. Componentes del Sistema

### 6.1 Catálogo de Fuentes

```python
class Fuente:
    id: str              # "cnv_listado", "byma_listado", "bolsar", etc.
    tipo: str            # "api", "html", "csv", "rss", "json"
    url_base: str        
    heartbeat_url: str   # URL para check de salud
    rate_limit: int      # requests/minuto
    timeout: int         # segundos
    parser: str          # módulo python que parsea esta fuente
    prioridad: int       # 1=regulatoria, 2=secundaria, 3=terciaria
    fallback_of: str     # si esta falla, probar esta otra
```

Fuentes identificadas:

| Fuente | Tipo | Info que aporta | Prioridad | Fallback |
|--------|------|----------------|-----------|----------|
| CNV Listado | HTML | CNV ID, CUIT, Razon Social | 1 | — |
| CNV AIF2 | HTML/JS | GUID presentaciones, formTypeId | 1 | IR PDF |
| BYMA Cotizaciones | HTML | ticker, sector, estado | 1 | Bolsar |
| Bolsar Especies | HTML | ticker, ISIN, tipo | 2 | OpenFIGI |
| OpenFIGI | API | FIGI, ISIN, mercado | 2 | — |
| Yahoo Finance | API | ticker, exchange, sector | 3 | — |
| SEC EDGAR | API | CIK, ticker USA, grupo | 2 | — |
| Wikidata | SPARQL | razon social, ISIN, sitio web | 3 | — |
| Caja de Valores | HTML | ISIN, especie | 3 | — |
| AFIP (CUIT) | Web/API | Razon Social, domicilio | 3 | — |

### 6.2 Módulo Discovery

```python
class DiscoveryEngine:
    def __init__(self):
        self.sources = [CnvSource(), BymaSource(), BolsarSource(), 
                       OpenFigiSource(), YahooSource(), SecSource()]
    
    def discover_all(self) -> list[Candidate]:
        """Ejecuta todas las fuentes en paralelo, recolecta candidatos."""
        candidates = []
        for source in self.sources:
            try:
                result = source.fetch()
                candidates.extend(result)
            except SourceUnavailableError:
                log.warning(f"Source {source.name} unavailable, using fallback")
                if source.fallback:
                    candidates.extend(source.fallback().fetch())
        return candidates
```

### 6.3 Módulo Reconcilier

```python
class EntityReconcilier:
    """Cruza candidatos de múltiples fuentes para identificar entidades únicas."""
    
    def reconcile(self, candidates: list[Candidate]) -> list[EntityCluster]:
        clusters = []
        # Phase 1: agrupar por IDs exactos (CUIT, ISIN, CNV ID, CIK)
        for id_type in ['cuit', 'isin', 'cnv_id', 'cik']:
            groups = self.group_by_exact_id(candidates, id_type)
            for g in groups:
                clusters.append(EntityCluster(g))
        
        # Phase 2: agrupar por nombre (fuzzy match para faltantes)
        unmatched = [c for c in candidates if not c.clustered]
        for c1, c2 in itertools.combinations(unmatched, 2):
            if self.fuzzy_name_match(c1.name, c2.name) > 0.85:
                cluster = self.merge_clusters(c1.cluster, c2.cluster)
        
        # Phase 3: detectar conflictos intra-cluster
        for cluster in clusters:
            cluster.detect_conflicts()
        
        return clusters
    
    def detect_conflicts(self, cluster):
        """Un cluster debe tener 1 CUIT, 1 ISIN, 1 CNV ID, 1 ticker BYMA."""
        conflicts = []
        if len(set(c.cuit for c in cluster if c.cuit)) > 1:
            conflicts.append(Conflict('cuit', cluster))
        if len(set(c.ticker for c in cluster if c.ticker)) > 1:
            conflicts.append(Conflict('ticker', cluster))
        return conflicts
```

### 6.4 Módulo Master Store

```python
class MasterStore:
    """Persiste, versiona y expone la entidad maestra."""
    
    TABLE_EMPRESA_MASTER = """
    CREATE TABLE IF NOT EXISTS empresa_master (
        empresa_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker_byma     TEXT NOT NULL,
        ticker_byma_full TEXT,               -- con sufijo 'm' si aplica
        ticker_usa      TEXT,               -- si tiene ADR
        cuit            TEXT UNIQUE,
        cnv_id          TEXT,
        isin            TEXT,
        figi            TEXT,
        lei             TEXT,
        cik             TEXT,
        nombre_oficial  TEXT NOT NULL,
        nombre_alternativo TEXT,
        sector          TEXT,
        subsector       TEXT,
        estado          TEXT DEFAULT 'activo',  -- activo, baja, fusion, cambio_ticker
        fecha_alta      TEXT,
        fecha_baja      TEXT,
        fuente_eeff_primaria  TEXT,         -- 'cnv-aif2', 'cnv-ir', 'edgar-6k', 'edgar-xbrl'
        fuente_eeff_secundaria TEXT,
        score_completitud REAL,             -- 0.0 a 1.0
        ultima_verificacion TEXT,
        conflictos_detectados TEXT,         -- JSON array
        UNIQUE(ticker_byma, cuit)
    )
    """
    
    TABLE_EMPRESA_HISTORY = """
    CREATE TABLE IF NOT EXISTS empresa_master_history (
        history_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id      INTEGER,
        snapshot_date   TEXT NOT NULL,
        cambio_tipo     TEXT,              -- 'alta', 'baja', 'modificacion', 'conflicto'
        campo_cambiado  TEXT,
        valor_anterior  TEXT,
        valor_nuevo     TEXT,
        FOREIGN KEY (empresa_id) REFERENCES empresa_master(empresa_id)
    )
    """
```

### 6.5 Módulo Fetcher Registry

```python
FetcherRegistry = {
    'cnv-aif2': {
        'class': 'CnvAif2Fetcher',
        'handles_form_types': ['147', '349'],
        'needs_guid': True,
        'rate_limit': 4,  # requests/min
        'geo_blocked': False,
        'fallback': ['cnv-ir', 'edgar-6k'],
    },
    'cnv-ir': {
        'class': 'CnvIRFetcher',
        'handles_form_types': ['all'],
        'needs_url': True,
        'rate_limit': 2,
        'geo_blocked': True,
        'fallback': ['edgar-6k'],
    },
    'edgar-6k': {
        'class': 'Edgar6KFetcher',
        'handles_ciks': True,
        'needs_cik': True,
        'rate_limit': 10,
        'geo_blocked': False,
        'fallback': [],
    },
    'edgar-xbrl': {
        'class': 'EdgarXBRLFetcher',
        'handles_ciks': True,
        'needs_cik': True,
        'rate_limit': 10,
        'geo_blocked': False,
        'fallback': [],
    },
    'yfinance': {
        'class': 'YFinanceFetcher',
        'handles_tickers': True,
        'rate_limit': 60,
        'geo_blocked': False,
        'fallback': [],
    },
}
```

---

## 7. Flujo de Datos

### 7.1 Diagrama de Secuencia (Descubrimiento)

```
CNV Listado    BYMA HTML     OpenFIGI     SEC EDGAR    Wikidata
    │             │             │             │            │
    ▼             ▼             ▼             ▼            ▼
┌──────┐     ┌──────┐     ┌──────┐     ┌──────┐     ┌──────┐
│CnvSrc│     │BymaSrc│     │FigiSrc│     │SecSrc│     │WikSrc│
└──┬───┘     └──┬───┘     └──┬───┘     └──┬───┘     └──┬───┘
   │            │            │            │            │
   └────────────┴────────────┴────────────┴────────────┘
                        │
                        ▼
              ┌─────────────────┐
              │ DiscoveryEngine  │
              │ (recolecta +     │
              │  normaliza)      │
              └────────┬────────┘
                       │ discovery_raw
                       ▼
              ┌─────────────────┐
              │ Enricher         │
              │ (busca CUIT,     │
              │  ISIN, LEI, CIK) │
              └────────┬────────┘
                       │ discovery_enriched
                       ▼
              ┌─────────────────┐
              │ Reconcilier      │
              │ (fuzzy merge,    │
              │  detecta conflic)│
              └────────┬────────┘
                       │ entity_clusters
                       ▼
              ┌─────────────────┐
              │ MasterStore      │
              │ (persiste +      │
              │  versiona)       │
              └─────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ empresa_master   │
              │ (SSOT)           │
              └─────────────────┘
```

### 7.2 Diagrama de Secuencia (ETL EEFF)

```
empresa_master
      │
      ▼
┌─────────────────────┐
│ Routing Logic        │
│ (determina fuente    │
│  primaria + fallback)│
└─────────────────────┘
      │
      ├── ADR con CIK ──────► edgar-xbrl (facts table)
      ├── ADR sin XBRL ────► edgar-6k (cnv_estados)
      ├── formTypeId=147 ──► cnv-aif2 (cnv_estados)
      ├── formTypeId=otro ─► cnv-ir (cnv_estados)
      └── sin EEFF CNV ───► yfinance (facts table, solo precio)
                │
                ▼
      ┌─────────────────┐
      │ Parser +         │
      │ Validator         │
      │ (identidad, flags)│
      └────────┬─────────┘
               │
               ▼
      ┌─────────────────┐
      │ cnv_estados /    │
      │ facts            │
      └─────────────────┘
               │
               ▼
      ┌─────────────────┐
      │ Ratio Calculator │
      └─────────────────┘
```

---

## 8. Estrategias de Fallback

### 8.1 Descubrimiento

| Falla | Acción | Tiempo de recuperación |
|-------|--------|----------------------|
| CNV listado no responde | Usar BYMA + Bolsar + OpenFIGI | 1 ciclo (24h) |
| BYMA HTML cambiado | Usar Bolsar + Yahoo Finance | 1-5 días (parser update) |
| OpenFIGI API rate limit | Cachear resultados 7 días | Inmediato (cache) |
| SEC EDGAR API down | Usar snapshot local + yfinance | 1 ciclo |
| Wikidata query timeout | Omitir, log | Inmediato |

### 8.2 Extracción EEFF

| Falla | Acción |
|-------|--------|
| CNV AIF2 formType no soportado | Caer a CNV IR PDF |
| CNV IR PDF geo-bloqueado | Caer a EDGAR 6-K (si ADR), o yfinance |
| EDGAR 6-K sin HTML parseable | Caer a EDGAR 20-F (anual) |
| EDGAR 20-F no disponible | Caer a yfinance.info (último año) |
| Ninguna fuente funciona | Marcar como SIN_DATOS, log, alerta semanal |

### 8.3 Parsing

| Falla | Acción |
|-------|--------|
| PDF sin texto (imagen) | OCR con Tesseract |
| OCR con baja confianza (<0.7) | Rechazar, log, alerta |
| HTML sin códigos universales | Buscar tablas HTML alternativas |
| Códigos parseados no validan identidad | Reintentar con otro parser (lenient mode) |
| Identidad < 2% | OK (aceptar) |
| Identidad 2-10% | Marcar flag, aceptar |
| Identidad > 10% | Rechazar, log |

### 8.4 Validación de Ratios

| Falla | Acción |
|-------|--------|
| PER negativo | Marcar flag, no excluir (pérdidas existen) |
| ROE > 200% | Marcar flag, verificar equity |
| Deuda/EBITDA negativo | Marcar flag, verificar EBITDA |
| Margen Neto > 100% | Rechazar, log |
| EPS 0 o None | No calcular PER (NULL) |

---

## 9. Actualización Automática

### 9.1 Estrategia de Scheduling

```
Diario (cada 24h):
  ├── Heartbeat de fuentes (verificar que responden)
  ├── Detectar cambios en CNV/BYMA listados
  └── Generar alertas si hay cambios

Semanal (cada 7 días):
  ├── Full discovery cycle (todas las fuentes)
  ├── Reconciliation completa
  ├── Detectar: nuevas empresas, bajas, cambios
  └── Actualizar empresa_master

Mensual:
  ├── Full EEFF extraction cycle
  ├── Ratios recalculation
  ├── Dashboard regeneration
  └── Reporte de calidad de datos
```

### 9.2 Detección de Cambios

```python
def detectar_cambios(snapshot_anterior, snapshot_actual):
    cambios = []
    
    # Nuevas
    nuevas = set(s_actual.keys()) - set(s_anterior.keys())
    for t in nuevas:
        cambios.append({
            'tipo': 'alta',
            'ticker': t,
            'nombre': s_actual[t]['nombre'],
            'detectado_en': s_actual[t]['fuente']
        })
    
    # Bajas
    bajas = set(s_anterior.keys()) - set(s_actual.keys())
    for t in bajas:
        cambios.append({
            'tipo': 'baja',
            'ticker': t,
            'nombre': s_anterior[t]['nombre'],
            'ultima_vista': s_anterior[t]['timestamp']
        })
    
    # Cambios de ticker
    for t in s_actual:
        if t in s_anterior:
            old = s_anterior[t]
            new = s_actual[t]
            if old.get('cuit') == new.get('cuit') and old.get('ticker') != new.get('ticker'):
                cambios.append({
                    'tipo': 'cambio_ticker',
                    'cuit': old['cuit'],
                    'ticker_anterior': old['ticker'],
                    'ticker_nuevo': new['ticker'],
                })
    
    return cambios
```

### 9.3 Algoritmo de Reconciliación por Prioridad

```python
RESOLUTION_RULES = {
    'nombre_oficial': {
        'fuente_prioritaria': 'cnv_listado',  # CNV es regulatoria
        'fallback': 'byma_listado',
        'conflicto': 'usar el de mayor frecuencia entre fuentes'
    },
    'sector': {
        'fuente_prioritaria': 'byma_listado',
        'fallback': 'openfigi',
        'conflicto': 'usar BYMA sobre OpenFIGI'
    },
    'cuit': {
        'fuente_prioritaria': 'cnv_listado',
        'fallback': None,  # Solo CNV tiene CUIT
        'conflicto': 'INVALIDAR empresa si CUIT no coincide'
    },
    'isin': {
        'fuente_prioritaria': 'bolsar',
        'fallback': 'openfigi',
        'conflicto': 'usar Bolsar (fuente oficial del mercado)'
    },
}
```

---

## 10. Modelo de Datos Maestro

### 10.1 Tabla `empresa_master`

```sql
CREATE TABLE empresa_master (
    -- Clave primaria
    empresa_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Identificadores principales
    ticker_byma         TEXT NOT NULL,          -- ej: 'GRIM'
    ticker_byma_full    TEXT,                   -- ej: 'GRIM' (sin sufijo 'm')
    ticker_usa          TEXT,                   -- ej: 'PAM' (Pampa ADR)
    
    -- Identificadores regulatorios
    cuit                TEXT,                   -- 11 dígitos, ej: '30500781293'
    cnv_id              TEXT,                   -- ID interno CNV
    isin                TEXT,                   -- Código internacional
    figi                TEXT,                   -- OpenFIGI
    lei                 TEXT,                   -- Legal Entity Identifier
    cik                 TEXT,                   -- SEC CIK (si tiene ADR)
    
    -- Metadatos corporativos
    nombre_oficial      TEXT NOT NULL,          -- Razón social registrada
    nombre_alternativo  TEXT,                   -- Nombre de fantasía
    sector              TEXT,                   -- GICS o similar
    subsector           TEXT,
    pais_origen         TEXT DEFAULT 'AR',
    moneda_reporte      TEXT DEFAULT 'ARS',     -- Moneda de EEFF
    
    -- Estado
    estado              TEXT DEFAULT 'activo'
        CHECK (estado IN ('activo', 'baja', 'fusion', 'cambio_ticker', 'potencial')),
    fecha_alta          TEXT,
    fecha_baja          TEXT,
    motivo_baja         TEXT,
    
    -- Fuente de EEFF (determinada por el routing)
    fuente_eeff_primaria    TEXT,   -- 'cnv-aif2', 'cnv-ir', 'edgar-6k', 'edgar-xbrl', 'yfinance'
    fuente_eeff_secundaria  TEXT,
    tiene_eeff_historico INTEGER DEFAULT 0,
    ultimo_periodo_eeff TEXT,       -- último period_end cargado
    
    -- Calidad
    score_completitud   REAL DEFAULT 0.0,       -- 0.0 a 1.0
    ultima_verificacion TEXT,                    -- timestamp
    conflictos_detectados TEXT,                  -- JSON array
    
    -- Trazabilidad
    creado_en           TEXT DEFAULT (datetime('now')),
    actualizado_en      TEXT DEFAULT (datetime('now')),
    
    UNIQUE(ticker_byma, cuit),
    UNIQUE(cuit) ON CONFLICT IGNORE,
    UNIQUE(cnv_id) ON CONFLICT IGNORE
);
```

### 10.2 Tabla `empresa_master_identifiers`

```sql
CREATE TABLE empresa_master_identifiers (
    identifier_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id      INTEGER NOT NULL,
    id_type         TEXT NOT NULL,  -- 'cuit', 'isin', 'figi', 'lei', 'cik', 'cnv_id', 'ticker_usa'
    id_value        TEXT NOT NULL,
    fuente          TEXT NOT NULL,  -- qué fuente aportó este ID
    timestamp_desc  TEXT,
    UNIQUE(id_type, id_value),
    FOREIGN KEY (empresa_id) REFERENCES empresa_master(empresa_id)
);
```

### 10.3 Tabla `empresa_master_history`

```sql
CREATE TABLE empresa_master_history (
    history_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id      INTEGER,
    snapshot_date   TEXT NOT NULL,
    cambio_tipo     TEXT NOT NULL,  -- 'alta', 'baja', 'modificacion', 'conflicto_resuelto'
    campo_cambiado  TEXT,
    valor_anterior  TEXT,
    valor_nuevo     TEXT,
    ejecucion_id    TEXT,           -- correlacionar con corrida de pipeline
    FOREIGN KEY (empresa_id) REFERENCES empresa_master(empresa_id)
);
```

### 10.4 Tabla `source_heartbeat`

```sql
CREATE TABLE source_heartbeat (
    heartbeat_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name     TEXT NOT NULL,
    status          TEXT NOT NULL,  -- 'ok', 'slow', 'down', 'changed'
    response_time_ms INTEGER,
    http_status     INTEGER,
    error_message   TEXT,
    timestamp       TEXT DEFAULT (datetime('now'))
);
```

---

## 11. Algoritmos de Reconciliación

### 11.1 Fuzzy Matching de Nombres

```python
def fuzzy_name_match(nombre_a: str, nombre_b: str) -> float:
    """Retorna 0.0 a 1.0."""
    if not nombre_a or not nombre_b:
        return 0.0
    
    # Normalización lingüística
    a = normalizar(nombre_a)  # quitar acentos, mayúsculas, 'SA', 'S.A.'
    b = normalizar(nombre_b)
    
    if a == b:
        return 1.0
    
    # Token matching con stopwords
    tokens_a = set(a.split()) - STOPWORDS
    tokens_b = set(b.split()) - STOPWORDS
    
    if not tokens_a or not tokens_b:
        return 0.0
    
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    
    jaccard = len(intersection) / len(union)
    
    # Penalizar si un nombre es mucho más corto que el otro
    if len(tokens_a) < 3 or len(tokens_b) < 3:
        jaccard *= 0.9
    
    return jaccard
```

### 11.2 Resolución de Conflictos

```python
def resolver_conflictos(conflictos: list[Conflict]) -> list[Resolution]:
    resoluciones = []
    
    for c in conflictos:
        if c.tipo == 'cuit_discrepante':
            # CUIT proviene de CNV (regulatorio) → siempre usar CNV
            resoluciones.append(Resolution(
                conflicto=c,
                resolucion='usar_cnv',
                confianza=1.0
            ))
        
        elif c.tipo == 'nombre_discrepante':
            # Elegir el que más fuentes coinciden
            fuentes_por_nombre = defaultdict(int)
            for candidato in c.candidatos:
                fuentes_por_nombre[candidato.nombre_normalizado] += 1
            ganador = max(fuentes_por_nombre, key=fuentes_por_nombre.get)
            
            resoluciones.append(Resolution(
                conflicto=c,
                resolucion=f'usar_mayoria: {ganador}',
                confianza=fuentes_por_nombre[ganador] / len(c.candidatos)
            ))
        
        elif c.tipo == 'ticker_discrepante':
            # Ticker BYMA es clave única → alerta humana
            resoluciones.append(Resolution(
                conflicto=c,
                resolucion='REQUIERE_REVISION_HUMANA',
                confianza=0.0
            ))
    
    return resoluciones
```

### 11.3 Determinación de Fuente Primaria de EEFF

```python
def determinar_fuente_eeff(empresa: dict) -> tuple[str, str]:
    """
    Retorna (fuente_primaria, fuente_secundaria).
    Lógica de decisión basada en identificadores disponibles.
    """
    tiene_cik = bool(empresa.get('cik'))
    tiene_formtype147 = bool(empresa.get('cnv_formtype_147'))
    tiene_ir_website = bool(empresa.get('ir_url'))
    
    if tiene_cik:
        # Tiene ADR en USA → EDGAR es mejor
        if empresa.get('ticker_usa'):
            return ('edgar-xbrl', 'edgar-6k')
        else:
            return ('edgar-6k', 'cnv-aif2')
    
    if tiene_formtype147:
        return ('cnv-aif2', 'cnv-ir')
    
    if tiene_ir_website:
        return ('cnv-ir', 'yfinance')
    
    # Sin fuente clara → yfinance (solo precio + último año)
    return ('yfinance', None)
```

---

## 12. Roadmap de Implementación

### Fase 1: Fundación (2-3 semanas)

**Objetivo:** Unificar todas las fuentes de descubrimiento en un solo proceso.

```
Semana 1:
  └── Crear tabla empresa_master + empresa_master_identifiers
  └── Implementar DiscoveryEngine con CNV + BYMA + Bolsar
  └── Implementar normalización básica

Semana 2:
  └── Implementar Enricher (CUIT, ISIN, CIK)
  └── Implementar Reconcilier versión 1
  └── Migrar datos existentes a empresa_master

Semana 3:
  └── Implementar empresa_master_history
  └── Implementar heartbeat de fuentes
  └── Validar contra las 56 empresas de acciones_solo_byma.csv
```

### Fase 2: Extracción Robusta (2-3 semanas)

**Objetivo:** Hacer que los fetchers sean resilientes y tengan fallback.

```
Semana 4:
  └── Refactorizar parser_cnv_aif2.py → CnvAif2Fetcher
  └── Agregar soporte para más formTypeId (349, 1001, 1002)
  └── Implementar fallback chain AIF2 → IR → 6-K

Semana 5:
  └── Refactorizar cnv_ir/pipeline.py → CnvIRFetcher
  └── Agregar OCR como fallback de text extraction
  └── Implementar caché de PDFs con TTL de 90 días

Semana 6:
  └── Refactorizar cnv_auto.py → Edgar6KFetcher
  └── Implementar parser de 20-F para ADR sin 6-K HTML
  └── Mapear todas las 16 ADR argentinos
```

### Fase 3: Calidad y Monitoreo (2 semanas)

**Objetivo:** Detectar problemas antes de que generen datos incorrectos.

```
Semana 7:
  └── Implementar validación de identidad contable automatizada
  └── Sistema de flags de calidad (por empresa, por concepto)
  └── Alertas en Slack/email cuando calidad baja de umbral

Semana 8:
  └── Dashboard de monitoreo (Streamlit o HTML)
  └── Métricas: cobertura, actualidad, calidad, fuente utilizada
  └── Pruebas de regresión con snapshot de HTML AIF2
```

### Fase 4: Automatización Completa (2-3 semanas)

**Objetivo:** Pipeline autónomo sin intervención manual.

```
Semana 9:
  └── Implementar scheduler (APScheduler / cron)
  └── Discovery automático diario
  └── Delta detection con notificaciones

Semana 10:
  └── Full EEFF extraction semanal
  └── Ratio recalculation post-extracción
  └── Dashboard auto-generado

Semana 11:
  └── Documentación completa
  └── Tests unitarios + integración
  └── Rollback procedure
```

### Fase 5: Escalamiento (2 semanas)

**Objetivo:** Probar que funciona con 500 y 5.000 empresas.

```
Semana 12:
  └── Simular 500 empresas (añadir empresas sin ADR ni CNV)
  └── Performance profiling
  └── Optimizar queries + caché

Semana 13:
  └── Simular 5.000 empresas (universo EDGAR completo)
  └── Rate limiting distribuido
  └── Documentar límites conocidos
```

---

## 13. Riesgos Técnicos y Operativos

### 13.1 Matriz de Riesgos

| # | Riesgo | Prob | Impacto | Severidad | Mitigación |
|---|--------|------|---------|-----------|------------|
| R1 | CNV AIF2 cambia completamente su API | Baja | Crítico | Fallback IR + EDGAR + yfinance |
| R2 | BYMA deja de publicar listado público | Media | Alto | OpenFIGI + Yahoo + Bolsar |
| R3 | ARS/USD disparado distorsiona ratios | Alta | Medio | Monitoreo de fx, flag en ratios |
| R4 | NIC 29 cambia criterio de re-expresión | Baja | Alto | fecha_reexpresion explícita, recálculo batch |
| R5 | Nuevas empresas no detectadas por meses | Media | Medio | Múltiples fuentes, warning si discrepancia |
| R6 | Base de datos se corrompe | Baja | Crítico | Backup diario automático, integridad checksum |
| R7 | Dependencia externa (yfinance, SEC) muere | Media | Alto | Fallback chain antes de que se rompa |
| R8 | Costo de almacenamiento crece sin límite | Alta | Bajo | Política de retención: 5 años raw, 10 años ratios |

### 13.2 SLA por Etapa

| Etapa | SLA | Métrica |
|-------|-----|---------|
| Discovery | 24h | Tiempo desde que una empresa aparece en fuente hasta que está en master |
| EEFF último año | 48h | Tiempo desde que CNV publica un EEFF hasta que está en cnv_estados |
| Ratios | 72h | Tiempo desde EEFF en DB hasta ratios calculados |
| Heartbeat | 1h | Máximo tiempo sin verificar una fuente |
| Data quality check | 24h | Tiempo desde dato cargado hasta que pasa todas las validaciones |

### 13.3 Runbook de Incidentes

```
Incidente: Fuente caída (CNV AIF2 down)
  1. Heartbeat detecta → status='down'
  2. Scheduler activa fallback a cnv-ir para todas las empresas
  3. Alerta a equipo
  4. Si > 4h: escalar a fallback terciario (yfinance)
  5. Cuando fuente se recupera: re-procesar con prioridad

Incidente: Data quality alert (identidad > 10%)
  1. Fetcher registra flag en cnv_estados
  2. Empresa marcada en empresa_master.conflictos_detectados
  3. Reporte semanal agrupa todos los flags
  4. Si mismo ticker falla 3 corridas seguidas → alerta humana

Incidente: Nueva empresa no detectada
  1. Reporte semanal compara fuentes
  2. Si empresa aparece en BYMA pero no en CNV → marcar como 'potencial'
  3. Si empresa aparece en CNV pero no en BYMA → marcar como 'baja'
  4. Si empresa aparece en > 1 fuente pero no en master → alerta
```

---

## 14. Recomendaciones Finales

### 14.1 Qué Hacer Inmediatamente

1. **Unificar los CSVs en empresa_master.** `acciones_solo_byma.csv`, `empresas.csv`, y la tabla `empresas` de SQLite deben migrarse a `empresa_master`. Esto es requisito para todo lo demás.

2. **Agregar heartbeat de fuentes.** Antes de escalar, saber qué fuentes están vivas. Un script de 50 líneas que haga GET a cada fuente y registre status.

3. **Implementar el registro de conflictos.** Cuando el pipeline encuentre una discrepancia (como GRIM en links_eeff.csv vs links_eeff_refined.csv), debe registrarla. Sino, se pierde información crítica.

### 14.2 Qué Hacer en el Corto Plazo

4. **Refactorizar los parsers como clases independientes.** Separar discovery de fetching de parsing. Cada uno debe poder ejecutarse independientemente.

5. **Agregar soporte para formTypeId=349** en el parser AIF2. Ya se sabe que funciona (GCLA lo necesita).

6. **Implementar la fallback chain completa.** AIF2 → IR PDF → EDGAR 6-K → yfinance.

### 14.3 Qué Hacer en el Mediano Plazo

7. **Automatizar el discovery semanal.** Que corra sin supervisión, genere reporte de cambios, y actualice la base maestra.

8. **Construir el dashboard de monitoreo.** Para ver cobertura, calidad, actualidad de datos de un vistazo.

9. **Implementar detección de cambios de ticker.** Usar CUIT como invariante: si un ticker aparece y desaparece pero el CUIT es el mismo, probablemente hubo cambio de ticker.

### 14.4 Principios para el Futuro

- **Nunca asumir que una fuente es permanente.** Toda fuente tiene un fallback diseñado antes de integrarla.
- **La trazabilidad no es opcional.** Toda decisión automática debe poder auditarse.
- **Un dato faltante es mejor que un dato incorrecto.** NULL explícito con razón documentada > número inventado.
- **La calidad se mide, no se asume.** Cada etapa debe reportar sus métricas de calidad.
- **El pipeline debe sobrevivir a sus fuentes.** Si CNV, BYMA y EDGAR caen simultáneamente, el sistema debe poder regenerar el dashboard con los últimos datos conocidos + una marca de "desactualizado".
