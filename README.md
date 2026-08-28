# Orquestador de estudio

Suelta el audio de tu clase, haz un clic, y el sistema transcribe, destila las ideas en
apuntes reales (no un resumen plano), revisa su propio trabajo con un segundo agente
independiente, arma un `.docx` para leer y estudiar, archiva el audio, agrega las
preguntas a Anki, y te avisa cuando termina. Todo en tu propio Mac, sin subir nada a
ningún lado.

## Así se ve

<table>
<tr>
<td width="50%">
<img src="docs/images/ejemplo-formulas.png" alt="Fórmulas dibujadas con tipografía matemática real">
<br><sub>Las fórmulas se dibujan con tipografía matemática real, no como texto plano.</sub>
</td>
<td width="50%">
<img src="docs/images/ejemplo-conceptos-repetidos.png" alt="Tabla de conceptos más repetidos durante la clase">
<br><sub>El sistema nota qué se repitió durante la clase y por qué, no solo transcribe.</sub>
</td>
</tr>
<tr>
<td width="50%">
<img src="docs/images/ejemplo-mapa-clase.png" alt="Mapa de la clase dibujado automáticamente">
<br><sub>El mapa de la clase se dibuja de verdad, no se describe en palabras.</sub>
</td>
<td width="50%">
<img src="docs/images/notificacion-macos.png" alt="Notificación nativa de macOS al terminar">
<br><sub>Notificación nativa de macOS al terminar, con clic para abrir el documento.</sub>
</td>
</tr>
</table>

*(Ejemplo con datos de una clase ficticia. Nada de contenido real de clases sale de este
Mac, ver [Privacidad](#privacidad).)*

## Cómo funciona por dentro

1. **Transcribe** el audio con Whisper, corriendo en tu propio Mac.
2. Un agente **destila** la transcripción en apuntes: ideas centrales explicadas desde
   cero, preguntas con respuesta modelo, sesión de estudio y kit de repaso.
3. Un **segundo agente independiente**, en una sesión aparte que llega sin haber escrito
   nada, revisa esas notas contra la transcripción cruda y busca contenido sin respaldo.
   Si encuentra algo grave, manda a corregirlo antes de seguir.
4. Arma el `.docx`, archiva el audio por ramo y fecha, agrega las preguntas a Anki, y
   avisa con una notificación nativa de macOS (o si algo falló).

Todo el uso del día a día pasa por dos apps de doble clic. Nunca necesitas abrir Terminal
para usarlo, solo para instalarlo la primera vez.

El ramo sale del nombre que le pusiste al archivo, y el día de la semana queda como
respaldo. Antes de empezar, una ventana te muestra todas las grabaciones que encontró y a
qué ramo va cada una: confirmas de una vez, y de ahí en adelante no hay más
interrupciones. Lo que el sistema no reconoce - la reunión de un ramo anexo, una
conversación que quieras poder citar después - te lo pregunta ahí, en vez de archivarlo
por su cuenta.

## Decisiones técnicas

**El revisor es una sesión aparte, a propósito.** Nadie mira el material antes de que se
convierta en flashcards, así que la revisión no puede ser una autocrítica dentro de la
misma sesión que escribió las notas: eso sería el agente revisando su propio trabajo con
el mismo sesgo. Llega sin contexto previo y compara contra la transcripción cruda.

**Todo corre local, por diseño y no por casualidad.** El sistema se apoya en el plan
Claude Pro y en Whisper corriendo en el Mac, sin APIs de pago ni servicios que cobren por
uso. Eso significa además que ninguna grabación ni apunte de una clase real sale de tu
equipo.

**Cada llamada al modelo se mide.** Un `CLAUDE.md` propio del pipeline documenta cuánto
cuesta cada etapa y por qué son tres llamadas (escribir, revisar, corregir) y no una sola
ni cuatro. Antes de agregar una etapa nueva, el criterio es medir qué ahorra, no asumirlo.

Guía completa de instalación, uso diario y detalles técnicos de cada decisión en
[docs/INSTALACION.md](docs/INSTALACION.md).

## La skill que hace el trabajo

El pipeline mueve archivos y llama al modelo, pero quien decide qué se escribe es una
skill de Claude Code que vive en
[`.claude/skills/transcripciones-a-conocimiento/`](.claude/skills/transcripciones-a-conocimiento).
Son unas mil líneas repartidas en cinco archivos, y se pueden leer sin instalar nada.

| Archivo | Qué contiene |
|---|---|
| [`SKILL.md`](.claude/skills/transcripciones-a-conocimiento/SKILL.md) | El flujo completo, en fases, y las reglas de honestidad que mandan sobre todo lo demás |
| [`references/limpieza-y-reconstruccion.md`](.claude/skills/transcripciones-a-conocimiento/references/limpieza-y-reconstruccion.md) | Cómo convertir habla transcrita en una fuente confiable: qué descartar, cómo reconstruir el patrón socrático, cómo corregir errores del transcriptor, qué hacer con un gráfico de pizarra que solo se menciona |
| [`references/metodo-mit.md`](.claude/skills/transcripciones-a-conocimiento/references/metodo-mit.md) | Los seis pasos del método de estudio activo: conceptos centrales, enseñar desde cero, preguntas, respuestas modelo, sesión de estudio y kit de repaso |
| [`references/diseno-documento.md`](.claude/skills/transcripciones-a-conocimiento/references/diseno-documento.md) | Cómo se arma el `.docx`: estructura fija, presupuesto de énfasis, tipografía, cuándo cortar |
| [`references/formato-obsidian.md`](.claude/skills/transcripciones-a-conocimiento/references/formato-obsidian.md) | Las plantillas de las notas que quedan en el vault |

**La regla que manda sobre el resto** está en las primeras líneas de `SKILL.md`: cuando la
transcripción no respalda algo, la salida correcta no es escribirlo mejor, es quitarlo o
marcarlo. Una sección que falta es aceptable. Una que afirma algo que nadie dijo, no,
porque quien estudia después no puede distinguirla de la verdad.

### Si la quieres usar en tu propio Claude Code

Esta copia está acoplada al pipeline y **no funciona suelta tal cual**. Espera recibir el
ramo y la carpeta de destino ya resueltos en el prompt, y termina emitiendo una línea
`RESULTADO_ORQUESTADOR` que `skill_runner.py` parsea para saber dónde quedaron las notas.
Invocada a mano, nadie le pasa esos datos y nadie lee esa línea.

Para usarla por tu cuenta hay que quitarle esas dos amarras: que pregunte a qué ramo
pertenece la transcripción en vez de recibirlo, y que termine mostrando las notas en vez
de reportar una línea para una máquina. El resto (la limpieza, el método, el diseño del
documento) no depende del pipeline y sirve igual.

## Estructura del proyecto

```
Input/               Donde dejas las grabaciones nuevas
Output/               .docx generados, uno por clase, ordenados por ramo
Procesados/           Audios ya procesados, archivados por ramo
boton_app/            Las apps de doble clic (Procesar Clases, Configurar Sistema)
orquestador/          El código del pipeline
  config.json          Tu configuracion real (rutas, ramos). No se sube al repo.
  config.example.json  Plantilla de referencia para armar tu propio config.json
  revisor.py           El segundo agente que revisa las notas antes de archivarlas
  ramo_por_nombre.py   Lee el ramo del nombre del archivo, antes de mirar el calendario
  pantalla_confirmacion.py  Pregunta por todas las grabaciones juntas antes de empezar
  carpetas.py          Ubica la carpeta de cada ramo en tu vault (y la recuerda)
  regenerar.py         Rehace el .docx de una clase ya procesada, con el diseño actual
  logs/uso.jsonl       Cuanto consumio cada llamada al modelo
ventana_confirmacion/  La ventana nativa que confirma el ramo (Swift, se compila aquí)
.claude/skills/        La skill que decide qué se escribe (ver la sección de arriba)
  transcripciones-a-conocimiento/
    SKILL.md             El flujo en fases y las reglas de honestidad
    references/          Limpieza del ASR, método de estudio, diseño del .docx, Obsidian
docs/                  Instalación completa, uso diario y detalles técnicos
```

## Privacidad

`orquestador/config.json` (tus rutas reales), las carpetas `Input/`, `Output/` y
`Procesados/` (tus grabaciones y notas reales), y los archivos de estado interno quedan
fuera del repositorio (ver `.gitignore`). Nada de tu contenido de clases se sube a
GitHub. Detalle de qué cuidar si publicas tu propia copia, en
[docs/INSTALACION.md](docs/INSTALACION.md#si-vas-a-publicar-tu-propia-copia).
