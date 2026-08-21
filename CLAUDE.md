# Orquestador de estudio

Pipeline que convierte grabaciones de clase en material de estudio. El README explica
qué hace y cómo se instala. Este archivo dice cómo se trabaja sobre él.

Aquí van las reglas que valen para todo el repositorio. Las reglas de la corrida
automatizada, que son de detalle fino y solo aplican al pipeline, están en
`orquestador/CLAUDE.md`.

## Idioma y estilo

- Todo en español neutro: código, comentarios, documentación, mensajes al usuario y
  commits.
- Sin em-dash (—) ni punto y coma. Usa " - " con espacios a ambos lados, o parte la
  frase en dos.
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

## Entorno

- **Python 3.13** del instalador oficial, en
  `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3`. No el de macOS.
- **Node 22+**, con el CLI de Claude Code en `node_modules/.bin/claude`.
- Mac con Apple Silicon. Probado en vivo en un M3.
- Las apps de `boton_app/` se compilan en cada Mac con `bash boton_app/compilar_apps.sh`.
  Los `.app` no se suben: macOS los pondría en cuarentena y un binario no se puede
  auditar. Lo que se publica es el `.applescript`. Mismo criterio para el binario de
  `barra_menu/`.
