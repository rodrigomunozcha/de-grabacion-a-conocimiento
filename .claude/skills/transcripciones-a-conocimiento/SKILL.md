---
name: transcripciones-a-conocimiento
description: >-
  COPIA DEL ORQUESTADOR. Es la que invoca por nombre skill_runner.py en su
  corrida automatizada, sobre una transcripción a la vez, con el ramo y la
  carpeta de destino ya resueltos en el prompt, y termina reportando una línea
  RESULTADO_ORQUESTADOR que el pipeline parsea. Para una petición conversacional
  (alguien que sube transcripciones y pide procesarlas, entenderlas,
  estudiarlas, limpiarlas u ordenarlas) usa la versión del plugin, no esta. Convierte transcripciones crudas de clases grabadas de
  ingeniería comercial en aprendizaje real con el método MIT de estudio activo:
  limpia el texto hasta dejar una fuente confiable, y luego destila las ideas
  centrales, explica desde cero, genera preguntas con respuestas modelo y arma
  sesión de estudio y kit de repaso, guardado como notas de Obsidian conectadas.
---

# Transcripciones a Conocimiento

Esta skill toma transcripciones automáticas de clases grabadas y las usa para que
el estudiante aprenda de verdad. El principio que manda es el del método MIT que él sigue:
la meta no es pedir un resumen, es construir contexto, detectar lo importante, ponerse
a prueba, corregir los errores y armar un plan de repaso. Un buen resumen fiel de la
clase no sirve si el estudiante no termina entendiendo e interiorizando las ideas.

El trabajo tiene dos mitades. Primero entender y limpiar el texto crudo hasta dejar una
fuente confiable (el transcriptor automático mezcla la clase con mucho ruido). Segundo,
aplicar el método MIT sobre esa fuente para producir aprendizaje. La limpieza no es el
producto, es el insumo. El producto es que el estudiante entienda.

El estudiante cursa estudios universitarios. Quiere estas notas para consolidar lo
aprendido, consultarlas después, tener el material del profesor como respaldo para
dudas en ramos futuros o en el trabajo, y para entender de verdad, no para releer al
profe palabra por palabra.

## Reglas de honestidad (mandan sobre todo lo demás)

Vienen del propio estudiante y son innegociables. En este material importan más que nunca,
porque la transcripción es ruidosa y la tentación de rellenar es alta.

- **No inventes contenido que no esté en la transcripción.** Destila y ordena lo que el
  profe trató, no completes con teoría genérica. Si algo no salió en clase, no lo pongas
  como si fuera de la clase. Si aportas contexto externo, márcalo (ver "Marcas").
- **Separa siempre tres cosas:** lo que el profe dijo, lo que tú reconstruyes o
  interpretas (gráficos, lógica que ordenas), y lo que la transcripción no permite
  recuperar. Usa las marcas de confianza.
- **La basura del ASR no es contenido.** Charla previa y posterior a la clase, ruido de
  fondo transcrito como palabras sin sentido ("Glutamato. Aspartato."), saludos y
  digresiones fuera de tema: se descartan. Si un tramo es puro ruido, ignóralo.
- **Reconoce cuando el profe no fue claro.** A veces el profe se enreda, se corrige, o
  deja una idea a medias. No lo maquilles como si hubiera quedado nítido. Rescata lo que
  sí se entiende y marca lo que quedó confuso, para que el estudiante lo verifique.
- **Marca lo dudoso.** Errores probables de transcripción (ej. "producto médico" por
  "producto medio", "al valores" por "ad valorem"): corrígelos pero deja la marca. Nunca
  presentes una corrección como textual del profe.
- **Si el material no alcanza, dilo.** Una nota honesta con huecos marcados vale más que
  una completa e inventada. Un hueco señalado le dice al estudiante qué buscar.
- **Lo que dice entrar en la prueba se cita, no se deduce.** Es la regla más estricta de
  todas, y aplica a la sección "Lo que el profesor pidió". Esa sección es la que el
  estudiante más va a creer y más va a estudiar, así que una inferencia tuya ahí no es un
  error menor: es una guía de estudio falsa. Solo entra lo que el profesor **dijo**, y
  cada punto va acompañado de su frase textual. Si lo dijo a medias o el audio no permite
  estar seguro, se marca. Nunca escribas "probablemente entre" ni completes con lo que
  parece importante.

## Cómo se arma el material

`references/diseno-documento.md` fija la estructura, qué se destaca y qué se corta, con
la evidencia detrás de cada regla. Léelo antes de escribir la nota de aprendizaje. Lo
esencial: **cada cosa se cuenta una sola vez**. Explicar la misma materia con varios
envoltorios no refuerza, estorba, y desplaza a lo que sí rinde.

## Estilo de escritura

- Español claro, directo y natural. Sin tecnicismos innecesarios.
- Nada de guion largo (em dash). Guion normal solo para listas.
- Evita el punto y coma salvo que sea realmente necesario.
- Frases cortas. Si puedes quitar palabras sin perder el sentido, quítalas.

## Alcance: una clase, varias o el ramo completo

La skill escala según lo que el estudiante suba. El conjunto de transcripciones de una corrida
es "el cuaderno" sobre el que se aplica el método.

- **Una clase:** el cuaderno es esa clase. El aprendizaje se enfoca en ese tema.
- **Varias clases o el ramo completo:** cada clase genera su fuente limpia, y el
  aprendizaje se aplica sobre el conjunto. Si son muchas clases de un ramo, agrupa por
  tema para que las ideas centrales no queden demasiado gruesas (un ramo entero tiene
  más de 5 ideas grandes, pero cada tema sí cabe en unas pocas). Además arma una síntesis
  que conecte los temas del ramo.

Si el alcance no está claro por lo que subió, pregúntalo en una línea antes de arrancar.

## Flujo general

El flujo tiene dos fases y corre de principio a fin sin pausas. El estudiante prefiere recibir
el material listo, no tener que ir contestando en el momento.

1. **Fase 0 - Inventario y ubicación.**
2. **Fase 1 - Entender y limpiar cada transcripción** hasta dejar la fuente confiable.
3. **Fase 2 - Aplicar el método MIT** sobre la fuente o fuentes, de corrido:
   - Pasos 1 a 3: conceptos centrales, enseñar desde cero, 10 preguntas.
   - Paso 4: responde tú mismo las 10 preguntas con respuestas modelo (las que daría
     alguien que domina el tema, apoyándote solo en el cuaderno). No esperes a que el estudiante
     conteste.
   - Pasos 5 y 6: sesión de estudio de 90 min y kit de repaso.

Deja las preguntas (paso 3) y las respuestas modelo (paso 4) en secciones separadas
dentro de la nota, para que el estudiante pueda taparse las respuestas e intentar recordar
primero si quiere. El recuerdo activo es lo que hace funcionar el método, pero la decisión
de ponerse a prueba es de él, no algo que la skill le exija.

## Fase 0 - Inventario y ubicación

1. Lista los archivos con una etiqueta corta por clase (tema aparente). Si una clase viene
   en "parte 1" y "parte 2", trátala como una sola clase continua.
2. **Pregunta siempre al estudiante a qué ramo pertenecen estas transcripciones.** No lo
   asumas por el contenido. El nombre que él le da al ramo puede no coincidir con el tema
   (ej. el contenido es microeconomía pero él lo llama "Introducción a la Economía"), y
   distintas corridas serán de ramos distintos. Puedes proponer un nombre si el contenido
   lo sugiere, pero él confirma. Usa su respuesta para tres cosas: el nombre de la carpeta,
   el campo `ramo` del frontmatter y el tag del ramo (sin espacios ni tildes en el tag, ej.
   ramo "Introducción a la Economía" da tag `IntroduccionEconomia`). Confirma también el
   alcance (una clase, varias, ramo).

   **Excepción: invocación automatizada.** Si quien te invoca ya te da el ramo y el
   alcance explícitamente en el prompt (por ejemplo, el sistema de orquestación de
   el estudiante, que ya resolvió el ramo por el día de la semana), no preguntes nada de
   esto: da ambos datos por confirmados y úsalos directo para la carpeta, el
   frontmatter y el tag. Esta excepción no aplica cuando el estudiante te habla
   directamente sin ese contexto ya resuelto: ahí sigue preguntando siempre.

   En invocación automatizada, el título de la nota de aprendizaje lo eliges tú
   (antepone "Fuente - " para la nota de fuente limpia), ya que llegaste a leer
   toda la transcripción a fondo. Que resuma de verdad el contenido, no un
   genérico.
3. Guarda las notas dentro del vault de Obsidian, en la carpeta de ese ramo (créala si no
   existe). Todas las notas de una corrida del mismo ramo van juntas. Si no hay vault
   conectado, crea las notas en la carpeta de trabajo y avisa que quedaron ahí para que
   el estudiante las mueva o conecte su vault. Plantillas exactas en
   `references/formato-obsidian.md`.

   **En invocación automatizada, la carpeta viene resuelta en el prompt.** Ya existe y ya
   es la correcta. Escribe ahí directamente: no la busques, no explores el vault y no
   listes carpetas para confirmarla. Recorrer un vault grande cuesta caro y no aporta
   nada cuando la ruta ya te la dieron. Si quieres enlazar notas anteriores del ramo,
   mira solo dentro de esa carpeta.

   **En invocación automatizada, al terminar todo el proceso**, agrega dos cosas más
   al trabajo normal:

   - **Los 5 conceptos que el profesor repite o enfatiza con más frecuencia** a lo
     largo de la clase (no los 5 conceptos centrales del paso 1 del método MIT, que
     es un criterio distinto: aquí interesa específicamente lo que vuelve una y otra
     vez, señal de que es candidato fuerte para la prueba). Para cada uno, el nombre
     del concepto y una razón breve que hable de frecuencia o énfasis ("aparece en
     la definición, en el ejemplo y se retoma al cierre"), no de importancia general.
   - **Una sección "La materia"** dentro de la nota de aprendizaje, que
     reemplaza a los pasos 1, 2 y 5 del método (ver Fase 2). Es el cuerpo del
     documento: el estudiante debería poder estudiar la clase entera solo con
     ella, sin abrir ninguna otra cosa.

     No es un resumen ni un plan de estudio. Es **la materia ya digerida**:
     - Explica cada tema **desarrollado**, no en una línea. Si el profesor tardó
       veinte minutos en algo, aquí necesita más que una viñeta.
     - **Muchos ejemplos numéricos y concretos**, resueltos paso a paso. Si el
       profesor dio uno, resuélvelo completo y agrega otro parecido para que el
       estudiante compruebe si entendió.
     - **Los casos y ejemplos que usó el profesor van aquí, desarrollados.** Si
       contó el caso de una empresa, la analogía del gallo o la cajita del
       impuesto, este es su lugar, dentro del tema que ilustraban. No los dejes
       solo en la nota de fuente: el documento de estudio tiene que bastarse
       solo, y esos casos suelen ser lo que hace entender la idea.
     - **Cuándo se usa cada cosa.** La duda real no suele ser qué es una
       fórmula, sino cuál toca en cada caso. Dilo explícitamente.
     - **Los errores que se cometen aquí**, y cómo se detectan.
     - Puedes agregar contexto externo que facilite entender, marcándolo como
       **(aporte externo)**, siempre que apoye lo que el profesor enseñó y no lo
       reemplace.
     - Escríbelo para alguien que faltó a la clase y solo tiene esto.

     Ordénala por temas, en el orden en que se entienden mejor, no
     necesariamente en el orden en que el profesor los tocó.

   - **Marcas de énfasis dentro de la nota.** Solo existen dos, y cada una
     significa una cosa. Ver `references/diseno-documento.md` para por qué son
     solo dos: destacar funciona porque es escaso, y un documento donde todo
     resalta no resalta nada.

     - `> [!examen]` para lo que el profesor dijo que entra en una evaluación.
       Úsalo **dentro de la materia**, pegado al tema del que habló, no en un
       bloque aparte. Ejemplo:
       `> [!examen] El profesor dijo que esto entra en el control: "los cuatro supuestos se los voy a preguntar sí o sí".`
       Solo si lo dijo. Esta marca no se pone por importancia percibida.

       **Cómo decidir dónde va.** Cuando termines la materia, recorre uno por
       uno los puntos que pusiste en `evaluacion` (ver los llamados a la acción,
       más abajo). Por cada uno, busca el lugar de la materia donde se explica
       ese tema y ponle la marca ahí, con la cita. Si el punto habla de la
       evaluación en general y no de un contenido de esta clase (porcentajes,
       formato, fechas), no lo marques en ninguna parte: ya está en la primera
       sección y repetirlo solo gasta el destacado.
     - `> [!verificar]` para avisar de algo que puede estar mal (audio dudoso,
       reconstrucción, hueco). Va **junto al contenido afectado**, nunca reunido
       al principio del documento. Ejemplo:
       `> [!verificar] La cifra puede estar mal: el audio dice "quince" pero el ejemplo solo cuadra con cincuenta.`

     No uses ningún otro tipo de callout en la nota de aprendizaje.

   - **Un mapa visual, como datos y no como descripción.** No escribas "el mapa
     tendría en el centro X y tres ramas": el sistema lo dibuja de verdad y lo
     inserta como imagen en el `.docx`. Entrégalo dentro de la nota de
     aprendizaje, en un bloque con este formato exacto:

     ````
     ```mapa
     {"centro": "<idea central, 3 o 4 palabras>",
      "ramas": [{"titulo": "<rama, hasta 5 palabras>",
                 "puntos": ["<punto breve>", "<otro>"]}]}
     ```
     ````

     Entre 3 y 5 ramas, y hasta 3 puntos por rama. Textos cortos: es un dibujo,
     no un párrafo. Si el tema no se presta para un mapa, omite el bloque.

   - **Una nota de contexto previo**, guardada en la misma carpeta con el
     nombre `Contexto - <mismo título>`. Es lo único de todo el material que no
     sale de la transcripción: es el piso mínimo que hay que tener para
     entender la clase. Su función es leerse ANTES de la clase, no después.

     Reglas para que sirva:
     - **Menos de una página.** Si no cabe, sobra contenido.
     - **No supongas nada.** Si la clase usa un concepto de un curso anterior,
       explícalo desde cero en dos o tres líneas. El estudiante puede no
       haberlo visto nunca o tenerlo olvidado.
     - **Práctica, no académica.** Es un torpedo: definiciones cortas, para qué
       sirve cada cosa, y las fórmulas que se van a usar. Nada de historia ni
       de rodeos.
     - **Solo lo que esta clase necesita.** No es un resumen del ramo, es lo
       justo para que el profesor se entienda.
     - Si la clase no necesita ningún contexto previo (es continuación directa
       y todo se explica solo), no crees la nota y reporta `"contexto": ""`.

     **Fórmulas** (aplica a toda la nota, no solo al contexto). Una fórmula
     importante va sola en su línea, entre `$$`, y **escrita en LaTeX**: el
     sistema la dibuja como imagen con tipografía matemática real (barra de
     fracción, radical que se estira, sombreros). Úsalo sin miedo, no cuesta
     nada extra:

     ```
     $$\bar{x} \pm z_{1-\alpha/2} \cdot \frac{\sigma}{\sqrt{n}}$$
     ```

     Para símbolos sueltos dentro de una frase, escribe Unicode directo (σ, μ,
     √, ±, x̄, p̂, Σ, ≈), que se lee bien en el renglón. Si necesitas un
     subíndice dentro de una frase, ponlo entre `$` con la forma `s^{2}`.

     **Dentro de tablas.** Una celda cuyo contenido es una fórmula también se
     dibuja, así que escríbela entre `$` y en LaTeX, igual que las demás:

     ```
     | Situación | Fórmula |
     |---|---|
     | Conozco σ | $\bar{x} \pm z_{1-\alpha/2} \cdot \frac{\sigma}{\sqrt{n}}$ |
     ```
   - **Los llamados a la acción del profesor.** Todo lo que dijo que el curso
     tiene que hacer o saber, con fecha o sin ella: cuándo es la prueba, qué
     hay que entregar, qué capítulo leer, qué cambió del programa, y sobre todo
     **qué dijo que entra en una evaluación**.

     Esta es la parte del material con más riesgo de todo el sistema, porque es
     la que el estudiante va a creer sin cuestionar y la que va a usar para
     decidir qué estudiar. Por eso:

     - **Cada punto lleva la frase textual del profesor.** Si no puedes citarlo,
       no va. Sin excepción.
     - **No deduzcas.** Que un tema sea importante, o que el profesor lo repita
       mucho, no significa que dijo que entra. Para eso ya están los conceptos
       repetidos, que son otra cosa y se presentan como otra cosa.
     - **Si quedó a medias o el audio no permite estar seguro**, inclúyelo con
       `"seguro": false` y di en `textual` lo que alcanzó a escucharse.
     - Las fechas van como el profesor las dijo ("el jueves 12", "la última
       semana de septiembre"). No calcules una fecha exacta que él no dio.
     - Si en la clase no hubo ningún anuncio, devuelve las dos listas vacías.
       Eso es una respuesta correcta y frecuente. No rellenes.

     Va en el JSON de abajo y también como primera sección de la nota de
     aprendizaje, con el título "Lo que el profesor pidió".

   - Como última línea de tu respuesta de texto (sin nada más en esa línea, JSON
     válido en una sola línea):
     `RESULTADO_ORQUESTADOR: {"titulo": "<el titulo que elegiste>", "fuente": "<ruta completa de la nota de fuente limpia>", "aprendizaje": "<ruta completa de la nota de aprendizaje>", "contexto": "<ruta completa de la nota de contexto previo, o cadena vacia si no hacia falta>", "conceptos_repetidos": [{"concepto": "...", "por_que": "..."}, ...5 en total], "llamados": {"avisos": [{"que": "<que hay que hacer>", "cuando": "<como lo dijo el profe, o cadena vacia>", "textual": "<frase textual>", "seguro": true}], "evaluacion": [{"tema": "<que entra>", "textual": "<frase textual>", "seguro": true}]}}`

   Esto es para que el sistema de orquestación pueda ubicar las notas y armar el
   `.docx` de respaldo sin tener que releer la transcripción de nuevo. No agregues
   esta línea cuando el estudiante te habla directamente sin ese contexto automatizado.

Sobre la fecha: no es crítica. Si el año no viene en el archivo, no te detengas en eso ni
llenes la nota de advertencias sobre el año. Usa la fecha del nombre del archivo si está
(ej. "4 Noviembre") y sigue. Lo que sí importa es que cada nota quede bien etiquetada con
el ramo que el estudiante indicó: el campo `ramo` en el frontmatter y su tag, porque así las
encuentra y filtra en Obsidian.

Seguridad con archivos: crea notas nuevas sin pedir permiso. Antes de sobrescribir,
mover, renombrar o borrar una nota existente, pide confirmación explícita.

## Fase 1 - Entender y limpiar: construir la fuente confiable

Esta fase produce, por cada clase, una nota de fuente limpia. Es el "cuaderno" del método
MIT. Para las heurísticas finas (cómo se ve el ruido, cómo reconstruir el patrón
socrático, cómo reconstruir gráficos de pizarra, cómo tratar los momentos poco claros del
profe), lee `references/limpieza-y-reconstruccion.md`. En resumen:

- Lee la transcripción completa antes de escribir. Descarta charla de inicio y de cierre,
  saludos, coordinación de trabajos, chistes y ruido de ASR sin sentido.
- Reconstruye el hilo: el profe enseña preguntando y el curso contesta con una palabra.
  Convierte ese ping pong en la idea completa que estaba armando.
- Conserva lo que hace valiosa la clase de ESE profe: sus ejemplos y analogías (el gallo
  que canta como externalidad, la cajita del impuesto).
- Reconstruye e interpreta los gráficos y fórmulas de pizarra a partir de lo que dice,
  marcados como reconstrucción a verificar.
- Marca los momentos donde el profe no fue claro y los tramos dudosos del audio.

La nota de fuente es legible por sí sola, pero su rol es alimentar la Fase 2.

## Fase 2 - Aplicar el método MIT

Sobre la fuente o fuentes limpias, aplica el método. Para el detalle exacto de cada paso
y sus extras, lee `references/metodo-mit.md`. El método, adaptado a clases, es:

1. **Conceptos centrales.** Las ideas base que sostienen el tema (no un resumen). Con qué
   es, por qué importa, con qué se conecta, error típico, ejemplo práctico, y las fuentes
   del cuaderno que lo respaldan (clase y ubicación aproximada).
2. **Qué dominar para enseñarlo desde cero** (principio de Feynman).
3. **10 preguntas** que expongan si entendió de verdad o solo memorizó, de menor a mayor
   dificultad.
4. **Respuestas modelo** a esas 10 preguntas, con el nivel de alguien que domina el tema y
   apoyadas solo en el cuaderno. En una sección aparte de las preguntas.
5. **Sesión de estudio de 90 minutos** por bloques.
6. **Kit de repaso** (hoja de una página, tabla de errores, 10 preguntas de repaso, plan
   de 7 días, fuentes para destrabarse).

Extras del método que puedes ofrecer o incluir cuando aporten: detectar lagunas después
de que responda, Feynman con corrección de una explicación suya, y un mapa visual del
tema. Están en `references/metodo-mit.md`.

**Los pasos 1, 2 y 5 no son tres secciones, son una.** Los tres explican los mismos
conceptos con distinto envoltorio, y contar la materia varias veces perjudica el
aprendizaje en vez de reforzarlo (ver `references/diseno-documento.md`). Fusiónalos en una
sola sección desarrollada, "La materia", y que gane la versión con ejemplos resueltos.
Lo que aportaban los otros dos pasos entra dentro: el porqué importa y el error típico del
paso 1, y la claridad de explicarlo desde cero del paso 2.

Adaptación importante de honestidad: el método MIT original pide "citar las fuentes". Acá
las fuentes son las transcripciones. Cita la clase y la ubicación aproximada (ej. "clase
4 nov, parte del impuesto"), nunca inventes una página o un minuto exacto que no tengas.

## Qué notas genera

Depende del alcance. Plantillas en `references/formato-obsidian.md`.

- **Una clase:** una nota de fuente limpia + una nota de aprendizaje (método MIT aplicado
  a esa clase).
- **Varias o ramo completo:** una nota de fuente por clase + notas de aprendizaje por
  tema + una nota de síntesis del ramo (conexiones entre temas) + un kit de repaso
  reutilizable del ramo.

La nota de aprendizaje es la estrella (lo que el estudiante usa para estudiar). La de fuente es
el respaldo confiable para consultar cuando dude de algo.

## Marcas de confianza

Úsalas donde el origen no sea obvio, sin saturar:

- Texto normal: lo que el profe efectivamente enseñó, con confianza razonable.
- **(reconstrucción, verificar)**: gráficos y lógica que inferiste del habla.
- **(dudoso: audio)**: término o cifra poco confiable en la transcripción.
- **(profe no fue claro)**: la idea quedó a medias o confusa en la clase.
- **(hueco)**: contenido que el profe usó pero que la transcripción no permite recuperar.
- **(aporte externo)**: contexto que agregas y que no venía en la clase. Solo si aporta y
  siempre marcado.

En Obsidian puedes usar callouts para resaltar, ej. `> [!warning] Reconstrucción a
verificar`. Con moderación.

## Recordatorio final

El valor de esta skill no es un texto ordenado ni un resumen bonito. Es que el estudiante
entienda e interiorice las ideas, y que pueda confiar en el material: lo que dice "el
profe dijo" es de verdad lo que dijo, lo reconstruido está marcado, los huecos están
señalados, y encima tiene con qué ponerse a prueba y repasar. Si en algún punto el
material no da para hacer bien un paso, dilo en vez de rellenar.
