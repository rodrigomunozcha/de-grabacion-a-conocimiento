-- App "Configurar Sistema". Doble clic: abre una ventana de Terminal con
-- el asistente de configuracion (orquestador/setup.py), para completar o
-- actualizar carpetas, el vault de Obsidian y el ramo de cada dia de la
-- semana. Es la unica parte del sistema que si pasa por Terminal (el
-- asistente necesita que escribas respuestas), pero no hace falta saber
-- ningun comando: esta app ya lo abre y lo deja listo para contestar.
-- Se puede volver a abrir cuando quieras cambiar algo (rutas, horario,
-- fecha de inicio de semestre).
--
-- La ruta del proyecto se detecta sola, igual que en "Procesar Clases.app"
-- (mismo truco, ver ese script para el detalle). Si tu python3 no esta en
-- la ruta de abajo, ajustala (ver README.md, seccion "Si algo no funciona").

property python3 : "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"

on run
	set rutaApp to POSIX path of (path to me)
	set carpetaApp to do shell script "dirname " & quoted form of rutaApp
	set proyecto to do shell script "dirname " & quoted form of carpetaApp

	tell application "Terminal"
		activate
		do script "cd " & quoted form of proyecto & " && " & quoted form of python3 & " -m orquestador.setup"
	end tell
end run
