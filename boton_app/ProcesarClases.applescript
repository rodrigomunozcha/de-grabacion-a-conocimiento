-- App "Procesar clases". Doble clic: procesa lo que haya en Input.
-- Arrastrar audios sobre el icono: los copia a Input y los procesa.
-- No abre ninguna ventana de Terminal (todo el aviso es por notificaciones).
--
-- La ruta del proyecto se detecta sola a partir de donde esta esta misma
-- app (dos carpetas arriba: boton_app/Procesar Clases.app -> raiz del
-- proyecto), asi funciona igual si clonas el repo en otra carpeta o en
-- otro Mac. Lo unico que quizas tengas que ajustar a mano es la ruta de
-- python3 de abajo, si tu Python no esta instalado ahi (ver README.md,
-- seccion "Si algo no funciona").

property python3 : "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"

on run
	procesarInput()
end run

on open droppedItems
	set carpetaInput to (rutaProyecto()) & "/Input"
	repeat with unItem in droppedItems
		set rutaOrigen to POSIX path of unItem
		do shell script "cp -n " & quoted form of rutaOrigen & " " & quoted form of (carpetaInput & "/")
	end repeat
	procesarInput()
end open

on rutaProyecto()
	-- "path to me" da la ruta de esta misma app. Subir dos niveles de
	-- carpeta (boton_app, y despues la raiz del proyecto) con dos llamadas
	-- separadas a dirname, cada una con su propio "quoted form of", evita
	-- problemas con espacios en el nombre de las carpetas (ej. "Claude Code").
	set rutaApp to POSIX path of (path to me)
	set carpetaApp to do shell script "dirname " & quoted form of rutaApp
	return do shell script "dirname " & quoted form of carpetaApp
end rutaProyecto

on procesarInput()
	set proyecto to rutaProyecto()
	do shell script "cd " & quoted form of proyecto & " && " & quoted form of python3 & " -m orquestador.procesar_input"
end procesarInput
