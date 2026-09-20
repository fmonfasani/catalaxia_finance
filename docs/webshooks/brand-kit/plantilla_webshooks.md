<!--
Plantilla base para un documento webshooks (.md -> Word/PDF/HTML con el brand-kit).
Copiá este archivo, completá el contenido y generá con build_docx.py (o pandoc).
Los bloques ::: {custom-style=...} solo aplican al Word; en otros formatos se ignoran o
se ven como texto. Para un documento simple, podés borrar la portada de abajo y dejar
que el generador arme portada + índice.
-->

# Título del documento

> Bajada de una línea que resume de qué se trata.

## 1. Sección

Texto de cuerpo. Usá **negrita** para lo importante y `código` para archivos o comandos.

- Ítem de lista.
- Otro ítem — con (`referencia`) si hace falta.

> Nota o aclaración (sale como bloque gris).

### 1.1 Subsección

| Columna A | Columna B |
|---|---|
| valor | valor |
| valor | valor |

## 2. Otra sección

Bloque de código:

~~~bash
comando --de --ejemplo
~~~

---

<!-- Wordmark coloreado (solo Word), por si querés meterlo en el cuerpo:
[web]{custom-style="WSBlue"}[shooks]{custom-style="WSNavy"}[.]{custom-style="WSOrange"}
-->
