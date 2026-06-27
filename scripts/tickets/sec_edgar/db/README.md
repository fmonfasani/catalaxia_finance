# db — datos en formato base de datos (SEC EDGAR)

La base **real** vive en `/data/screener.db` (raíz del repo, gitignoreada, ~700 MB).
Los scripts la encuentran solos (buscan la carpeta `data/` hacia arriba).

Esta carpeta queda para **dumps/exports DB específicos del grupo** (ej. un `.db`
de solo S&P 500) si hiciera falta. Hoy está vacía a propósito.
