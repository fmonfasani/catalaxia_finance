# Coordinación con el cliente (Marcelo)

> Marcelo es el **cliente** (Catalaxia). **No aprueba** los entregables internos: nuestros
> entregables semanales son una herramienta nuestra de avance. Con Marcelo la coordinación es
> acotada: arrancar bien (kickoff), mostrar avance en 1-2 puntos, y entregar. Este doc evita
> depender de él para no bloquearnos, y a la vez lo mantiene informado.

---

## 1. Qué necesitamos de Marcelo (y cuándo)

| Qué | Cuándo | Por qué |
|---|---|---|
| **Acceso/confirmación de la VPS** (o aval para usar la nuestra) | Antes de S1 | Federico despliega Postgres + API ahí |
| **Dominio / subdominio** para la API (`api.catalaxia.…`) | Semana 1 | HTTPS + front consumiendo la VPS |
| **Confirmación de alcance** (lo de `01`, sin sorpresas) | Kickoff | Evitar change requests a mitad |
| **Un contacto para dudas de negocio** (qué ratios/vistas prioriza) | Continuo | Priorizar bien el frontend |

> Si algo de esto se demora, **no frena al equipo**: seguimos con la VPS propia / dominio provisorio
> y mocks. La dependencia de Marcelo es mínima por diseño.

## 2. Agenda del Kickoff (1 hora, antes de Semana 1)

1. **Objetivo y alcance** (5’) — recorrer `01_ALCANCE_Y_DOD.md` (IN / OUT).
2. **Demo de la data ya validada** (15’) — 572 empresas, ratios oficiales, doble precio, provenance.
   Esto baja el riesgo percibido: el activo ya existe.
3. **Accesos** (10’) — VPS, dominio, credenciales.
4. **Prioridades de negocio** (10’) — qué mira primero (¿screener? ¿CEDEARs? ¿ADRs?).
5. **Forma de trabajo** (10’) — cadencia, cómo se comunica el avance, canal.
6. **Cierre** (10’) — próximos pasos, fecha de la primera muestra.

**Acta:** una página con decisiones + accesos + responsables (plantilla al final).

## 3. Puntos de contacto durante el proyecto

| Momento | Formato | Objetivo |
|---|---|---|
| Kickoff | reunión 1 h | arrancar con todo confirmado |
| Fin Semana 2 | demo corta (15’) o video | mostrar el screener real con 572 empresas |
| Fin Semana 4 | entrega | producto desplegado + walkthrough + garantía 30 días |

(Los viernes internos del equipo son aparte y **no** requieren a Marcelo.)

## 4. Qué le mostramos y qué no
- **Sí:** demos de producto que funciona, la data validada, el avance visible.
- **No:** el detalle interno de rúbricas de rendimiento del equipo (`07`) — eso es uso interno.

## 5. Entrega final (Semana 4)
- Walkthrough del producto en la VPS (screener + detalle + jobs).
- `openapi.json` + accesos + breve README de operación.
- Inicio de la **garantía de 30 días** (soporte correctivo).

---

## Plantilla — Acta de Kickoff

```
Proyecto: Catalaxia Screener AR + US        Fecha: __________
Presentes: __________________________________
Alcance confirmado (IN): sí / con cambios: __________
Fuera de alcance (OUT) aceptado: sí / no
Accesos entregados:  VPS ☐   dominio ☐   credenciales ☐
Prioridad de negocio #1: __________________________
Cadencia acordada: demo S2 ☐   entrega S4 ☐
Responsable por Catalaxia: __________  Por webshooks: Federico
Próximo paso / fecha: __________________________
```
