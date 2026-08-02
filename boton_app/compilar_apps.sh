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

# Icono de la barra de menu. Es opcional: si swiftc no esta (no estan las
# herramientas de linea de comandos de Xcode), el pipeline funciona igual,
# solo que sin senal visible mientras trabaja.
if command -v swiftc >/dev/null 2>&1; then
  echo "Compilando el icono de la barra de menu..."
  swiftc -O -o ../barra_menu/BarraEstado ../barra_menu/BarraEstado.swift
  ICONO="  - barra_menu/BarraEstado            (icono de progreso en la barra superior)"
else
  echo "Aviso: swiftc no esta disponible, se omite el icono de la barra de menu."
  echo "       Se instala con: xcode-select --install"
  ICONO="  (sin icono de barra de menu: falta swiftc)"
fi

echo
echo "Listo. Se crearon:"
echo "  - boton_app/Procesar Clases.app     (procesa las grabaciones de Input)"
echo "  - boton_app/Configurar Sistema.app  (asistente de configuracion)"
echo "$ICONO"
echo
echo "Puedes arrastrar las dos apps al Dock para tenerlas a mano."
