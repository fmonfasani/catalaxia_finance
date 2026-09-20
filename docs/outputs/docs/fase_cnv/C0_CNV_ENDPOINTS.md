# C0 — Endpoints CNV (evidencia empirica 2026-08-24 01:31 UTC)

## 1. Pagina empresa (DISCOVERY + METADATA basica)

| campo | valor |
|---|---|
| URL | `https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/{cuit}` |
| Metodo | GET |
| Auth | ninguna (publica) |
| Headers | User-Agent estandar |
| Respuesta | HTML server-side, ~2.26 MB para CEPU |
| Identificador | CUIT sin guiones (`33650305499`) |
| Rate | 1 request por empresa completa |

Contenido por fila `<tr>`: fecha publicacion, hora, **titulo estructurado**, presentationId,
link al visor AIF2 con GUID. Agrupado en secciones tematicas (Hechos Relevantes,
Estados Contables, Actas, ...).

Los EEFF propios traen metadata completa embebida en el titulo:

```
NORMA CONTABLE: NIIF - TIPO BALANCE: CONSOLIDADO - PERIODICIDAD: TRIMESTRAL - FECHA CIERRE: 2026-06-30 - ESTADOS CONTABLES - NIIF
```

* `TIPO BALANCE`: INDIVIDUAL / CONSOLIDADO -> resuelve scope sin abrir el visor.
* `PERIODICIDAD`: ANUAL / SEMESTRAL / TRIMESTRAL (o digito 1/3 en formato nuevo).
* `FECHA CIERRE`: ISO yyyy-mm-dd.
* Titulos legacy pre-NIIF: `BALANCE CONSOLIDADO - CPSA EECC 30.06.2017`, `BALANCE SUBSIDIARIA - ...`.
* Los EEFF de CONTROLADAS aparecen bajo el perfil de la controlante:
  `RELAC.: CONTROLADA - CUIT: ... - NOMBRE S.A. - FECH. CIERRE BAL.: DD-MM-YYYY - NORMA CONT.: NCP|NIIF|OTROS`.

## 2. Visor AIF2 (METADATA profunda + datos inline)

| campo | valor |
|---|---|
| URL | `https://aif2.cnv.gov.ar/presentations/publicview/{guid}` |
| Metodo | GET |
| Auth | ninguna (publicview) |
| Respuesta | HTML ~53 KB con metadata JS embebida |
| Rate observado | ~2-5 s por request; usar delay >= 0.5 s |

Variables JS globales embebidas:

```js
var formTypeId = '147'                    // 147 = Estados Contables - NIIF; 1001 = Balance Consolidado - Migracion; 1007 = Hecho Relevante
var formTypeName = 'Estados Contables - NIIF'
var presentationIdGlobal = '3558139'
var societyName = ''
var presentationDate = ''
var presentation = '<modeloDatos>...'     // XML con entidades/propiedades y claveinformativa C####
```

En presentaciones EEFF modernas el XML `modeloDatos` ademas trae:
`UnidadMedida` (ej. "Miles de $"), `FechaCierre`, `TipoBalance`, `Moneda`,
y propiedades de adjuntos:

```json
{"nombreArchivo":"06-2026 - Central Puerto S.A. Final Legalizado.pdf",
  "tamano":"21.31 MB",
  "guid":"3bb0fb72-7729-4990-989e-c17fd3b5fc43",
  "hash":"4a2RVQd9LnaeK2XvcW0fgP9PoFbD4uMja8DZEZoraPk="}
```

El atributo `hash` es el hash que CNV registro en el upload (SHA256 base64).
ADVERTENCIA: ver C0-CNV-006 — NO coincidio con el SHA256 del archivo servido en este test.

## 3. Adjunto (DOWNLOAD end-to-end VERIFICADO)

Flujo real extraido de `/js/site.bo.min.js` (`getPublicBlob`) y probado con exito:

```
PASO 1  GET  https://aif2.cnv.gov.ar/api/ValetKeyProvider/GetPublicValetKey/{blobGuid}?operation=DownloadBlob
        -> 200 application/json  {"valetKeyData": "<token serializado>"}

PASO 2  POST https://blob.cnv.gov.ar/BlobWebService.svc/DownloadBlob/{blobGuid}
        body (form-urlencoded): ValetKey={valetKeyData}
        header: X-CSRF-TOKEN: <RequestVerificationToken del visor>
        -> 200 application/octet-stream (binario crudo)
```

* El token CSRF sale del input hidden `RequestVerificationToken` del HTML del visor.
* `UriArchivo` embebido en el JSON apunta a host interno (`desa-iis.cnv.gov.ar`) — IGNORAR;
  el host publico correcto es `blob.cnv.gov.ar`.
* Probado: `06-2026 - Central Puerto S.A. Final Legalizado.pdf` -> 22.347.603 bytes, `%PDF` valido.
* Otros metodos conocidos del servicio WCF (de fb.publicuploader.js):
  `UploadBlobWithHash/`, `BlobAndGetHash/`, `GetValetKey/{id}?operation=UploadBlobAndGetHash%2F`.

## 4. APIs JSON exploradas y NO disponibles

| probe | resultado |
|---|---|
| `aif2/api/presentations/publicview/{guid}` | 404 |
| `aif2/presentations/api/publicview/{guid}` | 404 |
| `aif2/swagger/v1/swagger.json`, `/api-docs` | 404 |
| `BlobWebService.svc/DownloadBlob/{guid}` SIN valet key | 400 Request Error |
| `desa-iis.cnv.gov.ar:7012/:8012` | DNS no resoluble (host interno dev) |

CONCLUSION: no existe API JSON publica de listado. La fuente de discovery es la pagina empresa
(server-side) y la metadata fina vive en el HTML del visor. Ambas son deterministas y parseables.
