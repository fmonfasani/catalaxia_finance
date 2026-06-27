# CNV / Argentina — estados contables argentinos (BYMA-only)

Todo lo argentino que NO está en EDGAR: estados oficiales (CNV/IR) + yfinance BYMA.

```
cnv/
├── scripts/
│   ├── cnv_ir/                 PROYECTO principal: pipeline CNV-IR por pasos (ver su README)
│   ├── cnv_auto.py             estados argentinos vía 6-K de EDGAR
│   ├── extraer_estados_6k.py   piloto 6-K
│   ├── parser_eeff_ar.py       parser EEFF (standalone)
│   ├── cargar_byma_yfinance.py fundamentales BYMA vía yfinance
│   ├── cargar_argentina_cnv.py loader manual
│   └── (experimentales: 10_*, 20_*, ledesma, test_cnv, buscar_cnv_*)
├── datos/   cnv_empresas.xlsx
└── db/      (la base real está en /data/screener.db; tabla cnv_estados)
```

## Lo principal
**`scripts/cnv_ir/`** — el proyecto robusto: descubre EEFF en IR / CNV aif2, parsea
(códigos universales), valida por identidades contables, carga a `cnv_estados`.
Empezar por `scripts/cnv_ir/README.md`.
