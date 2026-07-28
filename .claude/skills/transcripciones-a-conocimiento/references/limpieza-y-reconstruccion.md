# Limpieza del ASR y reconstrucción

Guía detallada para convertir habla cruda transcrita en una fuente confiable. Esta es la
Fase 1 de la skill: el insumo del método MIT, no el producto final. Léela cuando estés
procesando una clase y necesites el detalle fino. El SKILL.md tiene el flujo general,
esto tiene las heurísticas.

## Cómo se ve el material de entrada

Las transcripciones son de un transcriptor automático sobre la grabación de una clase
presencial. Rasgos típicos que vas a encontrar:

- **Sin puntuación real.** Flujo de habla continuo, párrafos enormes sin punto aparte.
- **Repetición del profe.** Repite palabras para enfatizar o mientras piensa:
  "Desincentivar. Desincentivar." o "Especialmente. Especialmente. Especialmente."
- **Patrón socrático.** El profe pregunta y el curso contesta en coro con una palabra:
  "¿Cuántos agentes hay? Dos. Dos." La transcripción mezcla la pregunta del profe con
  el coro de alumnos sin distinguir quién habla.
- **Errores de transcripción por sonido.** Términos técnicos mal capturados:
  "producto médico" por "producto medio", "al valores" por "ad valorem", "moro arriba"
  por algo sin sentido. También nombres y números poco confiables.
- **Ruido de fondo transcrito como palabras.** Sobre todo antes de que empiece la
  clase o en pausas, el ASR inventa palabras a partir de murmullo: "Glutamato.
  Aspartato. Super hermoso." Eso NO es contenido, es basura.
- **Digresiones.** Chistes, comentarios políticos, coordinación de trabajos, saludos.
  Fuera del tema de la clase.

## Qué descartar (sin piedad)

- Todo lo anterior al inicio real de la clase (saludos, coordinación, charla entre
  alumnos, "¿cómo están?", organización de trabajos o videos).
- Todo lo del cierre: despedidas, coordinación de la próxima clase, conversaciones
  sueltas cuando la clase ya terminó.
- Ruido de ASR sin sentido. Si un tramo no forma una idea coherente y no se conecta
  con el tema, no lo interpretes, sáltalo. No inventes significado para el murmullo.
- Repeticiones: quédate con una sola aparición de la idea.
- Digresiones fuera de tema, salvo que el profe las use como analogía del contenido
  (ver siguiente sección).

## Cuando el profe no fue claro

Ojo con esto, porque es una regla de honestidad. A veces el profe se enreda, arranca una
idea y la deja a medias, se corrige a sí mismo, o explica algo de forma confusa. No lo
maquilles para que suene nítido, porque estarías inventando una claridad que no hubo.

- Rescata lo que sí se entiende de ese tramo.
- Marca lo que quedó confuso o a medias con **(profe no fue claro)** y di qué falta para
  cerrarlo, para que el estudiante lo verifique con la guía, el libro o preguntando.
- No confundas "el profe no fue claro" con "el audio se transcribió mal". El primero es
  que la explicación en sí quedó incompleta. El segundo es que la transcripción es
  dudosa. Usa la marca que corresponda.

## Qué conservar con cuidado

- **Las analogías y ejemplos del profe.** Aunque suenen a digresión, muchas veces son
  la forma en que el profe explica el concepto. El gallo que canta y molesta al vecino
  como ejemplo de externalidad. La "cajita" del impuesto. Estos ejemplos hacen la
  clase memorable y entendible, consérvalos y conéctalos con el concepto.
- **El razonamiento paso a paso.** Cuando el profe construye una idea con preguntas,
  reconstruye la cadena completa de razonamiento, no las respuestas sueltas.

## Cómo reconstruir el patrón socrático

El profe enseña preguntando. Ejemplo real (crudo):

> ¿Cuántos agentes o sujetos económicos hay? Dos. Dos. Para realizar cualquier
> transacción, a lo menos cuántas personas se requieren? Dos. Dos.

Reconstruido:

> El profe parte estableciendo que en el mercado hay dos agentes (consumidor y
> productor), y que toda transacción requiere al menos dos partes. Sobre esa base va a
> introducir al tercer agente, el Estado, cuando aparece el impuesto.

La idea es transformar el ping pong de preguntas y respuestas de una palabra en la
afirmación completa que el profe estaba construyendo, dejando visible su lógica.

## Cómo corregir errores de transcripción

Cuando un término técnico está claramente mal transcrito y el contexto lo deja obvio,
corrígelo y márcalo. Criterio:

- Solo corrige cuando el contexto lo hace casi seguro. "Producto médico" en una clase
  de teoría de producción, junto a "producto marginal", es "producto medio". Corrige y
  marca (dudoso: audio) o una nota entre paréntesis.
- Si no estás seguro de la corrección, deja el término entre comillas y marca la duda.
  No adivines.
- Números y fórmulas: si el audio no permite confiar en una cifra, márcala con "aprox."
  y recomienda revisarla en la guía o los apuntes.

Ejemplos frecuentes en economía (verifica siempre con el contexto, no apliques a
ciegas): "al valores" o "ad valores" suele ser "ad valorem"; "producto médico" suele
ser "producto medio"; confusiones entre "marginal" y "medio" cuando se repiten juntos.

## Cómo reconstruir gráficos de pizarra

Este es el trabajo más delicado. El profe dibuja en la pizarra y el texto solo tiene su
narración. Tu tarea es reconstruir e interpretar el gráfico a partir de lo que dice, y
dejarlo marcado como reconstrucción.

Procedimiento:

1. Junta todas las pistas verbales del gráfico dispersas en el texto (ejes, curvas,
   puntos, movimientos, qué compara).
2. Reconstruye el gráfico estándar que corresponde a esa descripción. Ejemplo: si habla
   de un impuesto que abre una diferencia entre el precio que paga el consumidor y el
   que recibe el productor, con una cantidad menor a la de equilibrio, eso es el gráfico
   de oferta y demanda con una cuña impositiva. Descríbelo: eje de precio y cantidad,
   curvas de oferta y demanda, el equilibrio original, la nueva cantidad menor, el
   precio del consumidor arriba y el del productor abajo, y la recaudación del Estado
   como el área entre ambos precios por la cantidad.
3. Marca todo el bloque como **(reconstrucción, verificar)**. En Obsidian, un callout
   `> [!warning] Reconstrucción a verificar` funciona bien.
4. Si las pistas no alcanzan para reconstruir con confianza, no inventes el gráfico
   completo. Describe lo que sí se sabe y marca el resto como (hueco), diciendo qué
   buscar (apuntes, guía del profe, libro).

La regla de oro: reconstruye con generosidad interpretativa cuando el profe da pistas
suficientes, pero siempre etiquetado como reconstrucción, nunca como cita textual de la
pizarra. El estudiante pidió explícitamente que intentes interpretar cómo hizo el gráfico, así
que no seas tímido para reconstruir, solo sé honesto marcándolo.

## Manejo de clases partidas (parte 1 y parte 2)

Si una clase viene en dos archivos ("parte 1" y "parte 2"), trátala como una sola clase
continua. Lee ambas antes de escribir, y produce una sola nota de clase. La parte 2
suele retomar donde quedó la parte 1, a veces a mitad de una idea.
