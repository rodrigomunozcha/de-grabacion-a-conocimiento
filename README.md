# Orquestador de estudio

Convierte grabaciones de clase en material de estudio completo, sin que tengas que hacer
nada más que soltar el audio y hacer un clic. Por cada clase que grabes, el sistema:

1. Transcribe el audio (en tu propio Mac, sin costo y sin subir el audio a ningún lado).
2. Limpia esa transcripción y la convierte en apuntes de verdad (no un resumen plano):
   ideas centrales explicadas desde cero, preguntas con respuesta modelo, sesión de
   estudio y kit de repaso. Todo queda guardado como notas conectadas en tu vault de
   Obsidian.
3. Revisa ese trabajo con un segundo agente independiente, que compara las notas contra
   la transcripción cruda y busca contenido sin respaldo. Si encuentra algo grave, manda
   a corregirlo antes de seguir, y deja el aviso pegado al párrafo del que habla.
4. Arma un `.docx` con diseño pensado para leer y estudiar, que incluye:
   - **Lo que el profesor pidió**, de primero: fechas de prueba, entregas, y lo que dijo
     que entra en evaluación. Cada punto con la frase textual del profesor, porque esta
     es la sección que más se cree y no puede salir de una deducción.
   - **Contexto previo**: menos de una página con lo que hay que saber antes para
     entender la clase, sin suponer que ya lo sabes.
   - **La materia ya digerida**, con los casos y ejemplos del profesor resueltos paso a
     paso y cuándo se usa cada cosa.
   - **Fórmulas dibujadas** con tipografía matemática real, no como texto plano.
   - **Un mapa de la clase**, dibujado de verdad, no descrito en palabras.

   Cada cosa se cuenta una sola vez. El documento no repite la misma materia con varios
   envoltorios, porque eso desplaza a lo que sí sirve para aprender (ver "El diseño del
   documento" más abajo).
5. Archiva el audio original, ordenado por ramo y fecha.
6. Agrega las preguntas y respuestas como flashcards en Anki.
7. Te avisa con una notificación nativa de macOS cuando termina (o si algo falló).

Todo el uso del día a día pasa por dos apps de doble clic. Nunca necesitas abrir
Terminal para usarlo, solo para instalarlo la primera vez.

## Antes de empezar: qué necesitas

Revisa esta lista antes de instalar nada. Si te falta algo de aquí, el sistema no va a
poder hacer su trabajo.

- **Un Mac con Apple Silicon** (M1, M2, M3 o más nuevo). Probado en vivo en un M3.
- **[Homebrew](https://brew.sh)** instalado (el gestor de paquetes de macOS).
- **ffmpeg**, instalado con Homebrew:
  ```bash
  brew install ffmpeg
  ```
- **Python 3.13**, instalado desde [python.org](https://www.python.org/downloads/) (no
  el que trae macOS por defecto). Este proyecto asume que queda en:
  `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3` (la ruta estándar del
  instalador oficial). Si en tu Mac queda en otro lado, ver la sección
  "Si algo no funciona" más abajo.
- **Node.js** (22 o más nuevo), instalado con Homebrew o desde
  [nodejs.org](https://nodejs.org).
- **Una cuenta de Claude con plan Pro (o superior)**, para poder iniciar sesión en
  Claude Code sin pagar por uso de API.
- **[terminal-notifier](https://github.com/julienXX/terminal-notifier)**, instalado con
  Homebrew:
  ```bash
  brew install terminal-notifier
  ```
- **[Anki](https://apps.ankiweb.net)** de escritorio, con el addon **AnkiConnect**
  instalado (Herramientas -> Complementos -> Obtener complementos -> código
  `2055492159`). Anki tiene que estar *abierto* mientras se procesa una clase para que
  las flashcards se agreguen (si no lo está, el sistema avisa y sigue sin Anki).
- **Un vault de Obsidian** ya creado en algún lado de tu Mac (o de iCloud/OneDrive).
- **Una herramienta propia de transcripción local** (Whisper corriendo en tu Mac) que
  exponga una función `transcribe(ruta_audio, language_profile, context_text)`. Este
  repo se apoya en una herramienta separada del autor original para ese paso (no incluida
  aquí). Si no tienes una propia, necesitas adaptar `orquestador/transcripcion.py` para
  que llame a la tuya.

## Instalación

1. Clona este repositorio y entra a la carpeta:
   ```bash
   git clone <url-de-este-repo> "Claude Code"
   cd "Claude Code"
   ```
2. Instala las dependencias de Node (el motor de Claude Code):
   ```bash
   npm install
   ```
3. Instala las dependencias de Python:
   ```bash
   /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m pip install -r requirements.txt
   ```
4. Inicia sesión en Claude Code con tu cuenta Pro (una sola vez):
   ```bash
   node_modules/.bin/claude
   ```
   Sigue el flujo de login que te muestre. Puedes cerrar esa sesión con `/exit` apenas
   confirme que quedaste conectado.
5. Compila las dos apps de doble clic:
   ```bash
   bash boton_app/compilar_apps.sh
   ```
   Las apps no vienen incluidas en el repositorio a propósito: macOS pone en cuarentena
   cualquier app descargada de internet (daría el error "no se puede abrir porque el
   desarrollador no puede verificarse"), y además un `.app` es un binario que no puedes
   revisar. Al compilarlas aquí, en tu Mac, no pasan por esa cuarentena, y lo que
   descargaste fue el código fuente (`boton_app/*.applescript`, unas 30 líneas cada uno)
   que sí puedes leer antes de ejecutar.

   Cuando terminen de compilarse, puedes arrastrar ambas al Dock.

## Primer uso: configurar tus ramos y carpetas

Dentro de la carpeta `boton_app/` hay una app llamada **"Configurar Sistema"**. Haz
doble clic en ella. Se va a abrir una ventana de Terminal sola, con un asistente que te
va preguntando (con Enter aceptas el valor sugerido entre corchetes):

- Dónde están tus carpetas `Input`, `Output` y `Procesados` (los valores por defecto ya
  apuntan dentro de este mismo proyecto, normalmente no hace falta cambiarlos).
- La ruta de tu vault de Obsidian.
- La ruta de tu herramienta de transcripción.
- La fecha de inicio de tu semestre (el lunes de la primera semana de clases).
- El nombre del ramo para cada día de la semana (lunes a viernes), y en qué idioma se
  dicta cada uno.

Puedes volver a abrir esta misma app cuando quieras cambiar cualquiera de estos datos
(otro semestre, un ramo nuevo, cambiaste de vault). No borra nada de lo ya procesado.

## Uso diario

1. Deja tu grabación (`.m4a`, `.mp3` o `.wav`) en la carpeta `Input/`, o directamente
   arrástrala sobre el ícono de **"Procesar Clases"** (dentro de `boton_app/`): la copia
   sola a `Input/` y empieza a procesar.
2. Si ya la dejaste en `Input/` a mano, solo haz doble clic en **"Procesar Clases"**.
3. Espera la notificación. Puede tardar unos minutos (transcribir + aplicar el método de
   estudio). Vas a recibir avisos de progreso y uno final con el nombre de la clase; si
   haces clic en la notificación final, se abre el `.docx` generado.
4. Si el día de la semana de la grabación no corresponde a ningún ramo de tu horario
   (por ejemplo una recuperación en otro día), va a aparecer una ventana preguntando qué
   hacer con ese archivo.

Todo lo que pasó queda también anotado en `Estado.txt` (en la raíz del proyecto), por si
te lo perdiste o quieres confirmar que no quedó pegado. Se abre con doble clic, como
cualquier archivo de texto.

### Ver cómo va, y detenerlo si hace falta

Mientras se procesa una clase aparece un ícono en la barra superior del Mac, junto al
reloj. Muestra en qué paso va (de 5), cuánto lleva y una estimación de lo que falta.
Desaparece solo al terminar.

La estimación solo se da donde hay con qué calcularla: la transcripción se estima desde
la duración del audio y la velocidad medida en tus corridas anteriores; las etapas de IA
usan el promedio de tu propio historial. Si todavía no hay datos, no muestra un número
en vez de inventarlo.

Al hacer clic en el ícono también aparece **"Detener y deshacer todo"**. No solo corta el
proceso: revierte lo que se haya alcanzado a hacer (las notas escritas, el documento
generado, las flashcards agregadas) y devuelve tu grabación a donde estaba, sin procesar.
Queda como si nunca hubieras hecho clic.

Hay unos pocos segundos, mientras se guarda el audio en su carpeta definitiva, en los que
detener podría dejar el archivo a medio camino. Durante ese rato el botón se muestra en
gris explicando por qué, y si pides detener justo ahí, se aplica apenas termina.

Si el Mac se apaga en mitad de un procesamiento, la corrida queda a medias. Se deshace con:

```bash
python3 -m orquestador.bitacora
```

## Si algo no funciona

- **La app no hace nada al hacer doble clic:** confirma que tu Python 3.13 está
  instalado en la ruta esperada. Si lo tienes en otro lado, edita la línea
  `property python3 : "..."` al principio de `boton_app/ProcesarClases.applescript` y
  de `boton_app/ConfigurarSistema.applescript` con la ruta real de tu `python3` (la
  puedes ver con `which python3` en Terminal), y vuelve a compilarlas:
  ```bash
  bash boton_app/compilar_apps.sh
  ```
- **"Ya hay algo corriendo":** hubo un clic mientras otro procesamiento seguía en curso.
  Espera a que termine y vuelve a intentar.
- **"Todavía copiando":** el archivo de audio parece seguir transfiriéndose (por
  ejemplo, un AirDrop grande). Espera un momento y haz clic de nuevo.
- **Faltaron las flashcards:** Anki no estaba abierto en el momento de procesar. Ábrelo y
  agrega las preguntas a mano desde la nota de aprendizaje (siguen ahí completas).
- **Un error puntual en una clase:** revisa `orquestador/logs/errores.log` (o haz clic en
  la notificación de error, te lleva directo ahí).
- **Moviste una carpeta de ramo dentro del vault:** no hay que hacer nada. El sistema
  recuerda dónde está la carpeta de cada ramo (en `config.json`, bajo `carpetas_ramo`),
  y si la ruta guardada ya no existe, la vuelve a buscar sola. Si un ramo todavía no
  tiene carpeta, la crea al lado de las de los otros ramos.

## Estructura del proyecto

```
Input/              Donde dejas las grabaciones nuevas
Output/              .docx generados, uno por clase, ordenados por ramo
Procesados/          Audios ya procesados, archivados por ramo
boton_app/           Las apps de doble clic (Procesar Clases, Configurar Sistema)
orquestador/         El código del pipeline
  config.json         Tu configuracion real (rutas, ramos). No se sube al repo.
  config.example.json Plantilla de referencia para armar tu propio config.json
  revisor.py          El segundo agente que revisa las notas antes de archivarlas
  carpetas.py         Ubica la carpeta de cada ramo en tu vault (y la recuerda)
  regenerar.py        Rehace el .docx de una clase ya procesada, con el diseño actual
  logs/uso.jsonl      Cuanto consumio cada llamada al modelo
.claude/skills/       La skill que aplica el método de estudio sobre cada transcripción
```

## Privacidad

`orquestador/config.json` (tus rutas reales), las carpetas `Input/`, `Output/` y
`Procesados/` (tus grabaciones y notas reales), y los archivos de estado interno quedan
fuera del repositorio (ver `.gitignore`). Nada de tu contenido de clases se sube a
GitHub.

### Si vas a publicar tu propia copia

- **Tu email queda público y para siempre en el historial de commits.** Antes del primer
  commit, conviene usar el email anónimo que ofrece GitHub (lo encuentras en
  Settings -> Emails -> "Keep my email addresses private", con la forma
  `12345+usuario@users.noreply.github.com`):
  ```bash
  git config user.email "TU_ID+TU_USUARIO@users.noreply.github.com"
  ```
- **Revisa que `config.json` siga ignorado** antes de publicar (`git status` no debe
  mencionarlo). Contiene las rutas reales de tu Mac.

### Sobre el paso automático con IA

El paso que aplica el método de estudio corre de forma desatendida (nadie está mirando
para aprobar permisos), y trabaja sobre texto transcrito de audio, que no es una fuente
confiable. Por eso esa llamada está acotada de tres formas: no puede ejecutar comandos
de shell, solo puede leer y escribir dentro de este proyecto y de tu vault de Obsidian, y
tiene un tope de turnos para no consumir cuota sin control. Si cambias esa configuración
(en `orquestador/skill_runner.py`), ten presente que quitar una herramienta de
`allowed_tools` no basta para bloquearla: hace falta `disallowed_tools`.

### La revisión

Como nadie mira el material antes de que se convierta en flashcards, hay una segunda
llamada que lo revisa (`orquestador/revisor.py`). Es una corrida aparte, no una
autocrítica dentro de la misma sesión: llega sin haber escrito nada y compara las notas
contra la transcripción cruda. Busca contenido inventado, reconstrucciones presentadas
como textuales, huecos tapados y respuestas modelo que contradicen la clase. No corrige
ni escribe: solo puede leer.

Si encuentra algo de gravedad alta (contenido que la transcripción no respalda), se
retoma la sesión original de la skill para que corrija sus propias notas. Los hallazgos
de gravedad media quedan anotados en
`orquestador/transcripciones_pendientes/<clase>_revision.json` y no disparan una
corrección: siempre hay algo que mejorar, y corregir por cada detalle duplicaría el costo
de cada clase.

Toda esta etapa es opcional por diseño. Si la revisión falla, la clase se termina de
procesar igual con lo que escribió la skill, y recibes un aviso de que quedó sin revisar.

### El diseño del documento

`.claude/skills/transcripciones-a-conocimiento/references/diseno-documento.md` fija la
estructura del documento, qué se destaca y qué se corta, con la evidencia detrás de cada
regla. La idea que manda: cada cosa se cuenta una sola vez. Explicar la misma materia
con varios envoltorios no refuerza, desplaza a lo que sí rinde.

Si cambias ese diseño, puedes rehacer los documentos de las clases ya procesadas sin
volver a transcribir ni a analizar nada:

```bash
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m orquestador.regenerar
```

Sin argumentos te lista las clases disponibles. Por defecto escribe un archivo aparte y
no toca el documento que ya tenías. Con `--pisar` lo reemplaza.

### Cuánto consume

Cada llamada al modelo queda anotada en `orquestador/logs/uso.jsonl`. Para ver el
promedio por etapa después de unas cuantas clases:

```bash
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m orquestador.uso
```
