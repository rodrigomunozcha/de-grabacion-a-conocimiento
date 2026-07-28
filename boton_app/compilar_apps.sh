#!/bin/bash
# Compila las dos apps de doble clic a partir de su codigo fuente (.applescript).
#
# Las apps NO vienen incluidas en el repositorio a proposito, por dos razones:
#   1. macOS pone en cuarentena cualquier app descargada de internet, asi que
#      una app bajada de GitHub daria el error "no se puede abrir porque el
#      desarrollador no puede verificarse" y no arrancaria. Compilada aqui, en
#      tu propio Mac, no pasa por esa cuarentena.
#   2. Un .app es un binario que no puedes leer. Los .applescript de al lado si
#      se leen en cualquier editor: son 30 lineas y puedes revisar exactamente
#      que hacen antes de compilarlos.
#
# Uso: bash boton_app/compilar_apps.sh   (desde la raiz del proyecto)

set -e

cd "$(dirname "$0")"

echo "Compilando las apps en: $(pwd)"

rm -rf "Procesar Clases.app" "Configurar Sistema.app"
osacompile -o "Procesar Clases.app" ProcesarClases.applescript
osacompile -o "Configurar Sistema.app" ConfigurarSistema.applescript

echo
echo "Listo. Se crearon:"
echo "  - boton_app/Procesar Clases.app     (procesa las grabaciones de Input)"
echo "  - boton_app/Configurar Sistema.app  (asistente de configuracion)"
echo
echo "Puedes arrastrar ambas al Dock para tenerlas a mano."
