# Orquestador de estudio

Pipeline que convierte grabaciones de clase en material de estudio. El README explica
qué hace y cómo se instala. Este archivo dice cómo se trabaja sobre él.

## Idioma y estilo

- Todo en español neutro: código, comentarios, documentación, mensajes al usuario y
  commits.
- Sin em-dash (—) ni punto y coma. Usa " - " con espacios a ambos lados, o parte la
  frase en dos.
- Los comentarios explican **por qué**, no qué. El estilo del repo es dejar dicho qué se
  probó y qué falló, para que nadie lo vuelva a intentar. Ver `skill_runner.py`, donde
  cada decisión trae la razón y lo verificado en vivo. Mantén ese nivel.
- Cada mensaje que ve el usuario dice qué hace y qué va a pasar. No des el contexto por
  supuesto: quien usa esto no tiene la terminal abierta.

## Costo cero, no negociable

El sistema corre con el plan Claude Pro y nada más. No introduzcas dependencias de pago,
APIs con tarifa, ni servicios que cobren por uso. Todo el procesamiento pesado
(transcripción con Whisper) es local.

Si una mejora solo funciona pagando, no la implementes: dilo, nombra el sacrificio de la
alternativa gratis, y deja que el usuario decida.

## Privacidad: qué nunca sale de este Mac

Estas rutas están en `.gitignore` y deben seguir estándolo. Contienen material real de
clases y rutas personales:

- `Input/`, `Output/`, `Procesados/` - grabaciones, notas y audios archivados
- `Preclases/` - derivan del material de cada profesor, no se publican
- `orquestador/config.json` - rutas reales de este Mac
- `orquestador/logs/`, `orquestador/transcripciones_pendientes/`, `Estado.txt` y los
  archivos de estado de corrida - algunos traen fragmentos de transcripciones

Antes de cualquier commit, confirma que `git status` no menciona nada de lo anterior.

## Entorno

- **Python 3.13** del instalador oficial, en
  `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3`. No el de macOS.
- **Node 22+**, con el CLI de Claude Code en `node_modules/.bin/claude`.
- Mac con Apple Silicon. Probado en vivo en un M3.
- Las apps de `boton_app/` se compilan en cada Mac con `bash boton_app/compilar_apps.sh`.
  Los `.app` no se suben: macOS los pondría en cuarentena y un binario no se puede
  auditar. Lo que se publica es el `.applescript`.

## La corrida automatizada tiene reglas propias

`orquestador/skill_runner.py` y `orquestador/revisor.py` invocan al modelo de forma
desatendida, sin nadie que apruebe permisos, sobre texto transcrito de audio. Ese texto
no es una fuente confiable y termina dentro del prompt.

Por eso, si tocas esa configuración:

- **Quitar una herramienta de `allowed_tools` no la bloquea.** Con
  `permission_mode="bypassPermissions"` el modelo igual puede usarla. Lo único que
  bloquea de verdad es `disallowed_tools`. Verificado en vivo: la skill escribía notas con
  Bash sin tenerlo en `allowed_tools`.
- **El gate de rutas (`construir_gate_de_rutas`) depende de que Bash siga bloqueado.** Si
  el modelo puede ejecutar comandos, escribe donde quiera sin pasar por el hook.
- **`setting_sources` va explícito en `["project"]`**, para que la corrida no dependa de
  configuración global de la cuenta que podría cambiar sin aviso.
- **Cada invocación del SDK cuesta ~16.000 tokens fijos** de system prompt antes de leer
  nada, más releer la transcripción. Por eso hay una sola invocación por clase. Antes de
  agregar otra, mide qué ahorra.
- **`max_turns` es un seguro contra corridas descontroladas**, no un objetivo. El uso real
  es de 9 a 16 turnos por clase.

## Honestidad del contenido generado

Nadie revisa el material antes de que se convierta en flashcards y entre al vault. La
regla que manda sobre todo lo demás: cuando la transcripción no respalda algo, la salida
correcta no es escribirlo mejor, es quitarlo o marcarlo (reconstrucción a verificar,
dudoso por audio, hueco).

`revisor.py` existe para eso y corre como sesión aparte, sin haber escrito nada. No es
una autocrítica dentro de la misma sesión, y esa separación es deliberada. No la
colapses en una sola llamada.

## Al hacer cambios

- Si tocas el pipeline, corre `tests/`.
- Si cambias qué genera la skill, revisa que `finalizar_clase.py` siga armando el `.docx`
  cuando falta un campo. El principio es que perder una sección es mucho mejor que perder
  la clase.
- Si agregas una etapa, decide qué pasa si falla. El patrón del repo es degradar, no
  abortar: la revisión es opcional por diseño, las flashcards se saltan si Anki está
  cerrado, y el `.docx` se arma sin la sección que no llegó.
