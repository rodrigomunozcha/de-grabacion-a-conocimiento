# Orquestador de estudio

Pipeline que convierte grabaciones de clase en material de estudio. El README explica
qué hace y cómo se instala. Este archivo dice cómo se trabaja sobre él.

Aquí van las reglas que valen para todo el repositorio. Las reglas de la corrida
automatizada, que son de detalle fino y solo aplican al pipeline, están en
`orquestador/CLAUDE.md`.

## Español neutro, siempre

Es la máxima principal del usuario, por encima de cualquier detalle técnico. Aplica a
**todo**: la conversación con él, el código, los comentarios, la documentación, los
mensajes de commit y los textos que el sistema le muestra.

**Nada de voseo rioplatense.** Es la forma concreta en que ya falló:

| Nunca | Siempre |
|---|---|
| tenés, querés, podés, hacés | tienes, quieres, puedes, haces |
| escribís, apretás, elegís | escribes, aprietas, eliges |
| agregá, apretá, mirá, revisá | agrega, aprieta, mira, revisa |
| vos, sos, contame, decime | tú, eres, cuéntame, dime |

Tampoco mexicanismos, españolismos ni chilenismos, aunque él sea chileno. Neutro
significa que funciona en cualquier país hispanohablante.

Sin em-dash (—) ni punto y coma. Usa " - " con espacios a ambos lados, o parte la
frase en dos.

El riesgo real no está en el código, que se revisa con calma. Está en los mensajes de
cierre al final de una sesión larga, cuando baja la guardia. Ahí fue donde falló.

## Estilo y claridad

- Los comentarios explican **por qué**, no qué. El estilo del repo es dejar dicho qué se
  probó y qué falló, para que nadie lo vuelva a intentar. Ver `skill_runner.py`, donde
  cada decisión trae la razón y lo verificado en vivo. Mantén ese nivel.
- **Esta regla gana sobre el comportamiento por defecto de no comentar.** Los bloques
  largos de comentario de este repo son deliberados: son el registro de lo que ya se
  intentó. No los recortes por prolijidad ni los conviertas en una línea.
- Cada mensaje que ve el usuario dice qué hace y qué va a pasar. No des el contexto por
  supuesto: quien usa esto no tiene la terminal abierta.

## Costo cero, no negociable

El sistema corre con el plan Claude Pro y nada más. No introduzcas dependencias de pago,
APIs con tarifa, ni servicios que cobren por uso. Todo el procesamiento pesado
(transcripción con Whisper) es local.

Si una mejora solo funciona pagando, no la implementes: dilo, nombra el sacrificio de la
alternativa gratis, y deja que el usuario decida.

## Privacidad: qué nunca sale de este Mac

**La fuente de verdad es `.gitignore`**, y cada exclusión trae escrito ahí su motivo. No
repitas esa lista en otro lado: dos listas se separan y una queda mintiendo.

Lo que protege, en general: grabaciones y notas de clases reales, material que deriva de
los apuntes de cada profesor, rutas propias de este Mac, y archivos de estado que traen
fragmentos de transcripción.

Dos reglas que se siguen de eso:

- Antes de cualquier commit, confirma que `git status` no menciona nada ignorado.
- Si agregas una carpeta que va a guardar material de clases, estado de corrida o rutas
  personales, agrégala a `.gitignore` en el mismo cambio, con el porqué escrito.

## Antes de cada commit

**Nunca uses `git add -A` ni `git add .`.** Agrega archivos por nombre, uno por uno.
Un `git add -A` metió 848 líneas de trabajo de un día entero (el respaldo del título, el
gate de rutas, el manejo de errores del SDK, el veredicto de la revisión, las pruebas)
dentro de un commit que solo hablaba de fechas de archivo (`911e2c6`, 21-08-2026).
Nadie lo notó porque nadie miró la lista de archivos antes de confirmar.

Por eso hay un hook de pre-commit versionado en `.githooks/pre-commit`: antes de cada
commit muestra los archivos en stage agrupados por carpeta y exige una confirmación
explícita. No intenta adivinar si un commit mezcla temas por su tamaño: se probó contra
los commits reales de este repo y el commit problemático (13 archivos, 1039 líneas) es
más chico que dos commits legítimos de un solo tema (18 archivos/1901 líneas, y 16
archivos/1141 líneas). El tamaño no es una señal confiable. Lo único que el hook
garantiza es que alguien mire antes de confirmar.

Para activarlo, una vez por clon del repositorio:

```bash
git config core.hooksPath .githooks
```

Sin activar, el hook no hace nada: es opt-in porque tocar `core.hooksPath` es una
decisión de quien clona, no algo que deba imponerse solo.

## Entorno

- **Python 3.13** del instalador oficial, en
  `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3`. No el de macOS.
- **Node 22+**, con el CLI de Claude Code en `node_modules/.bin/claude`.
- Mac con Apple Silicon. Probado en vivo en un M3.
- Las apps de `boton_app/` se compilan en cada Mac con `bash boton_app/compilar_apps.sh`.
  Los `.app` no se suben: macOS los pondría en cuarentena y un binario no se puede
  auditar. Lo que se publica es el `.applescript`. Mismo criterio para el binario de
  `barra_menu/`.
