# La corrida automatizada tiene reglas propias

Estas reglas aplican al pipeline. Las de idioma, costo cero, privacidad y entorno están
en el `CLAUDE.md` de la raíz y también valen aquí.

`skill_runner.py`, `revisor.py` y `hoja_html.py` invocan al modelo de forma desatendida,
sin nadie que apruebe permisos, sobre texto transcrito de audio. Ese texto no es una
fuente confiable y termina dentro del prompt.

Por eso, si tocas esa configuración:

- **Quitar una herramienta de `allowed_tools` no la bloquea.** Con
  `permission_mode="bypassPermissions"` el modelo igual puede usarla. Lo único que
  bloquea de verdad es `disallowed_tools`. Verificado en vivo: la skill escribía notas con
  Bash sin tenerlo en `allowed_tools`.
- **El gate de rutas (`construir_gate_de_rutas`) depende de que Bash siga bloqueado.** Si
  el modelo puede ejecutar comandos, escribe donde quiera sin pasar por el hook.
- **`setting_sources` va siempre explícito, nunca por defecto.** Si no se pone, el SDK
  rellena `["user", "project"]` por su cuenta. El valor cambia según lo que la sesión
  necesite: `["project"]` en `skill_runner.py`, porque ahí se carga la skill del
  proyecto, y `[]` en `revisor.py` y `hoja_html.py`, que no necesitan
  la skill y arrancan más livianos sin ella.
- **`setting_sources` no aísla la corrida de la cuenta.** Medido con
  `get_context_usage()` del propio SDK: el `MEMORY.md` de memoria automática del usuario
  (1.021 tokens) entra igual, con `["project"]` y también con `[]`. No hay opción para
  apagarlo. Vale para todas las etapas, incluido el revisor, que se diseñó para llegar
  sin contexto previo. Lo que guardes en esa memoria viaja en cada corrida.
- **Este archivo no se carga en la corrida, el de la raíz sí.** El `CLAUDE.md` raíz pesa
  1.208 tokens en cada llamada que lleve `["project"]`. Este, comprobado, no se carga ni
  siquiera después de leer la transcripción, que está en esta misma carpeta. Por eso el
  detalle fino del pipeline vive aquí y no allá.
- **Cada invocación del SDK cuesta ~16.000 tokens fijos** de system prompt antes de leer
  nada, más releer la transcripción. Por eso el pipeline mide cada llamada, no porque
  haya una sola. Una clase con hallazgos usa cuatro:
  1. La que escribe las notas (`aplicar_skill`).
  2. El revisor, que es sesión aparte a propósito (ver abajo).
  3. La corrección, que **retoma la sesión de la primera con `resume`** justamente para
     no volver a pagar la lectura de la transcripción.
  4. La hoja de repaso (`hoja_html.py`), que reemplazó al `.docx` el 11-09-2026. Es sesión
     aparte y **sin ninguna herramienta**: recibe las notas dentro del prompt y devuelve
     el HTML, que Python sanea con lista blanca antes de guardarlo. Se agregó porque el
     estudiante no leía los `.docx` de 20 a 25 páginas, y condensar exige criterio, no una
     conversión. Su costo queda en `logs/uso.jsonl` con la etapa `hoja`. Primera
     medición (Sistemas, 01-09-2026): un turno, 3 minutos y 0,55 dólares equivalentes,
     menos que la revisión. Desde el 14-09-2026 es lo único que el pipeline genera
     además de las notas: el `.docx` y las flashcards de Anki salieron del todo.

  Antes de agregar una quinta, mide qué ahorra.
- **`max_turns` es un seguro contra corridas descontroladas**, no un objetivo. Cada
  etapa tiene el suyo según el trabajo que hace, y los cuatro son constantes con
  nombre: `MAX_TURNS` (30, escribir la clase) y `MAX_TURNS_CORRECCION` (30, corregir)
  en `skill_runner.py`, 25 en `revisor.py` y 3 en `hoja_html.py`
  (no usa herramientas, así que responde en un turno). Si una etapa se pasa
  de su tope, algo se salió de lo esperado y cortar es lo correcto. Subir el número no
  es el arreglo.

## Honestidad del contenido generado

Nadie revisa el material antes de que entre al vault y se condense en la hoja. La
regla que manda sobre todo lo demás: cuando la transcripción no respalda algo, la salida
correcta no es escribirlo mejor, es quitarlo o marcarlo (reconstrucción a verificar,
dudoso por audio, hueco).

`revisor.py` existe para eso y corre como sesión aparte, sin haber escrito nada. No es
una autocrítica dentro de la misma sesión, y esa separación es deliberada. No la
colapses en una sola llamada, aunque ahorre tokens: es el único punto del pipeline que
mira las notas sin haberlas escrito.

La tarjeta "Lo que el profesor pidió" de la hoja de repaso la arma Python, no el modelo.
Sale de la nota de aprendizaje, y si no hay de dónde sacarla dice que no se pudo
comprobar. No se la devuelvas al modelo ni la armes desde el campo `llamados` cuando viene
en null: el `.docx` hacía eso y afirmaba "el profesor no anunció fechas ni evaluación"
aunque la nota trajera los anuncios. Pasó en cuatro clases, y en Sistemas del 01-09-2026
negaba el anuncio de la prueba del martes siguiente y de los capítulos que entraban.

## Al hacer cambios

- Si tocas el pipeline, corre las pruebas:

  ```bash
  /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 tests/test_orquestador.py
  ```

  No es pytest. Es un runner propio que llama a cada función de prueba a mano desde el
  bloque `if __name__ == "__main__"` de `tests/test_orquestador.py`. **Si agregas una
  función de prueba, agrégala también a esa lista**, o no corre nunca y nadie se entera.
- Si cambias qué genera la skill, revisa que `finalizar_clase.py` siga armando la hoja
  cuando falta un campo. El principio es que perder una sección es mucho mejor que perder
  la clase.
- Si agregas una etapa, decide qué pasa si falla. El patrón del repo es degradar, no
  abortar: la revisión es opcional por diseño, y la hoja se arma aunque falte una
  sección, avisando cuál. La excepción es cuando falta
  el insumo esencial: sin transcripción no hay nada que degradar, y ahí sí se corta.
- **Degradar nunca puede significar afirmar en falso.** Una sección que falta es
  aceptable. Una sección que dice "no hay nada" sin haberlo comprobado, no: el estudiante
  no puede distinguirla de la verdad. Si una etapa no pudo averiguar algo, tiene que
  decirlo distinto de "averigüé que no hay", y **no cachear ese resultado**, o el próximo
  intento se saltará la pregunta para siempre. Ya falló en `extraer_llamados`, del
  antiguo `regenerar.py` (retirado el 14-09-2026, sigue en el historial de git): un
  corte de red quedaba guardado como "el profesor no pidió nada".
- **Un error tardío del SDK no descarta el trabajo hecho.** Si el modelo alcanzó a emitir
  su línea de resultado, la corrida terminó y esa respuesta vale, aunque después llegue
  un 429. Nunca hagas `raise` ni `return` dentro del bucle `async for`: anota el error,
  sal del bucle, e intenta parsear. Las cuatro llamadas siguen ese patrón.
