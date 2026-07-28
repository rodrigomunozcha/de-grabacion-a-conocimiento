# Plantillas de Obsidian

Plantillas para las notas que produce la skill. Respeta el estilo del vault del estudiante si
ya existe (frontmatter con tags, wikilinks, footer de navegación). Si no hay vault
conectado, crea las notas con estas plantillas en la carpeta de trabajo para que él las
mueva.

El nombre del ramo, la carpeta y el tag del ramo salen de lo que el estudiante respondió en la
Fase 0 (la skill le pregunta a qué ramo pertenecen las transcripciones). Los ejemplos de
abajo usan "Introducción a la Economía", pero reemplázalo por el ramo que él indicó.

Convenciones generales:

- Carpeta por ramo, con el nombre que dio el estudiante.
- Frontmatter YAML arriba de cada nota con tags y metadatos.
- Wikilinks `[[Nota]]` para conectar entre notas.
- Fechas en formato `YYYY-MM-DD`.

Hay dos tipos de nota por clase: la **fuente** (Fase 1, el cuaderno limpio) y el
**aprendizaje** (Fase 2, el método MIT). Con varias clases se suman la **síntesis del
ramo** y el **cheat sheet**. La nota de aprendizaje es la que el estudiante usa para estudiar.
La de fuente es el respaldo confiable.

## Nota de fuente (Fase 1)

Nombre sugerido: `Fuente - Clase YYYY-MM-DD - <tema>.md`

```markdown
---
ramo: Introducción a la Economía
tipo: fuente
fecha: 2025-11-04
tema: Impuestos y subsidios
tags: [fuente, economia, impuestos]
origen: transcripción grabación (ASR)
---

# Fuente - Clase 2025-11-04 - Impuestos y subsidios

## Resumen
Tres a cinco frases sobre qué trató el profe en esta clase.

## Desarrollo
El hilo conceptual reconstruido en prosa limpia, en el orden lógico en que el profe lo
construyó. Conserva sus ejemplos y analogías. Marca lo reconstruido, lo dudoso y los
momentos donde el profe no fue claro.

## Gráficos y fórmulas reconstruidos
> [!warning] Reconstrucción a verificar
> Descripción del gráfico/fórmula inferido de lo que dijo el profe. Ejes, curvas, puntos,
> movimientos.

## Definiciones y ejemplos del profe
- **Término:** definición como la dio el profe.
- Ejemplo o analogía concreta y qué concepto ilustra.

## Huecos y dudas
- Qué quedó sin recuperar o confuso y qué buscar para completarlo.

---
Aprendizaje: [[Aprendizaje - Clase 2025-11-04 - Impuestos y subsidios]]
```

## Nota de aprendizaje (Fase 2, método MIT)

Nombre sugerido: `Aprendizaje - Clase YYYY-MM-DD - <tema>.md`
Cuando el cuaderno es un tema que cruza varias clases, usa el tema como nombre:
`Aprendizaje - <tema>.md`.

```markdown
---
ramo: Introducción a la Economía
tipo: aprendizaje
tema: Impuestos y subsidios
tags: [aprendizaje, economia, metodo-mit]
---

# Aprendizaje - Impuestos y subsidios

## 1. Conceptos centrales
(uno por bloque: qué es, por qué importa, se conecta con, fuentes del cuaderno, error
típico, ejemplo práctico)

## 2. Qué dominar para enseñarlo desde cero
(las ideas clave estilo Feynman)

## 3. Diez preguntas para ponerme a prueba
(de menor a mayor dificultad. Si quieres hacer recuerdo activo, intenta responderlas antes
de mirar el paso 4)

## 4. Respuestas modelo
(las 10 respuestas resueltas, como las daría alguien que domina el tema. Sección aparte a
propósito, para poder taparla e intentar recordar primero)

## 5. Sesión de estudio de 90 minutos
(por bloques de tiempo)

## 6. Kit de repaso
(hoja de una página, tabla de errores, 10 preguntas de repaso, plan de 7 días, fuentes)

## Mapa visual (opcional)
(idea central, conceptos, conexiones, errores, ejemplos, preguntas)

---
Fuente: [[Fuente - Clase 2025-11-04 - Impuestos y subsidios]]
```

Nota: las respuestas modelo (paso 4) van resueltas dentro de la nota, no pendientes. Los
extras del método (detectar lagunas, Feynman con corrección) se agregan solo si el estudiante
los pide y aporta su propia explicación o respuestas.

## Nota de síntesis del ramo (varias clases o ramo completo)

Nombre sugerido: `_Síntesis - <ramo>.md`

```markdown
---
ramo: Introducción a la Economía
tipo: síntesis
tags: [síntesis, economia]
---

# Síntesis - Introducción a la Economía

## El hilo del ramo
Cómo se encadenan los temas. Qué concepto sostiene a cuál.

## Mapa de conexiones
Relaciones clave entre temas.

## Índice
- [[Aprendizaje - Impuestos y subsidios]] / [[Fuente - Clase 2025-11-04 - Impuestos y subsidios]]
- ...
```

## Kit reutilizable / cheat sheet (varias clases o ramo completo)

Nombre sugerido: `_Cheat sheet - <ramo>.md`

```markdown
---
ramo: Introducción a la Economía
tipo: cheat-sheet
tags: [cheat-sheet, economia, consulta-rápida]
---

# Cheat sheet - Introducción a la Economía

## Fórmulas
- Nombre: fórmula. Qué representa y cuándo se usa.

## Modelos y gráficos
- Modelo: para qué sirve y qué muestra.

## Frameworks y definiciones clave
- Concepto: definición compacta de consulta.
```

## Nota de índice (si el vault la usa)

Si el vault usa notas de índice por ramo (`_Índice - <ramo>.md`), ofrece actualizarla para
enlazar las notas nuevas, y pide confirmación antes de editarla. No sobrescribas notas
existentes sin permiso.
