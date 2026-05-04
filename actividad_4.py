# -*- coding: UTF-8 -*-
"""
Práctica 4: Dropbox - OAuth
Asignatura: Sistemas Web
Integrantes del grupo: Liviu Deleanu, Eder Torres, Alex Isasi
Descripción: Aplicación con interfaz gráfica (Tkinter) que extrae PDFs de eGela
             mediante Web Scraping y permite subirlos a Dropbox usando su API REST.
"""

# Importaciones estándar de Python para la interfaz gráfica y manipulación del sistema
import tkinter as tk
from tkinter import messagebox
import os
import time
# unquote es crucial para limpiar las URLs (convierte cosas como "%20" en espacios reales)
from urllib.parse import unquote

# Importamos nuestros propios módulos con la lógica de negocio (deben estar en el mismo directorio)
import eGela
import Dropbox
import helper


##########################################################################################################
# SECCIÓN 1: FUNCIONES DE INTERFAZ GRÁFICA (UI HELPERS)
# Aquí definimos funciones auxiliares para no repetir código al crear elementos de la ventana (DRY - Don't Repeat Yourself)
##########################################################################################################

def make_entry(parent, caption, width=None, **options):
    """Crea un label y un campo de entrada de texto (Entry) en la interfaz."""
    # Usamos el gestor de geometría 'pack' para apilar los elementos de arriba a abajo (side=tk.TOP)
    label = tk.Label(parent, text=caption)
    label.pack(side=tk.TOP)

    # **options permite pasar argumentos extra dinámicos (como show="*" para ocultar contraseñas)
    entry = tk.Entry(parent, **options)
    entry.config(width=width)
    # padx da un pequeño margen horizontal, fill=tk.BOTH hace que el input ocupe el ancho disponible
    entry.pack(side=tk.TOP, padx=10, fill=tk.BOTH)
    return entry


def make_listbox(messages_frame):
    """Crea una lista seleccionable (Listbox) con barra de desplazamiento lateral."""
    # Le damos un borde estilo 'ridge' para que visualmente se note que es un contenedor
    messages_frame.config(bd=1, relief="ridge")

    # Scrollbar nativo de Tkinter vinculado al frame
    scrollbar = tk.Scrollbar(messages_frame)

    # selectmode=tk.EXTENDED es clave: permite al usuario hacer Ctrl+Click o Shift+Click para seleccionar varios archivos.
    # exportselection=0 evita que al hacer clic fuera del listbox se pierda la selección actual (típico fallo de usabilidad en Tkinter).
    msg_listbox = tk.Listbox(messages_frame, height=20, width=70, exportselection=0, selectmode=tk.EXTENDED)

    # Vinculamos bidireccionalmente el scrollbar con el listbox
    msg_listbox.configure(yscrollcommand=scrollbar.set)
    scrollbar.configure(command=msg_listbox.yview)

    # Empaquetamos el scrollbar a la derecha y que ocupe todo el alto (fill=tk.Y)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    return msg_listbox


##########################################################################################################
# SECCIÓN 2: LÓGICA PRINCIPAL DE LOS BOTONES
# Estas funciones son los "callbacks" que se ejecutan cuando el usuario interactúa con la UI
##########################################################################################################

def transfer_files():
    """Descarga los PDFs seleccionados de eGela y los sube a Dropbox."""
    # Control de errores defensivo: evitamos que el programa crashee si se le da al botón sin seleccionar nada
    if not selected_items1:
        messagebox.showwarning("Atención", "Selecciona al menos un archivo de eGela para transferir.")
        return

    # Invocamos la barra de progreso del módulo helper
    popup, progress_var, progress_bar = helper.progress("transfer_file", "Transfiriendo archivos...")
    progress = 0
    progress_var.set(progress)
    progress_bar.update()

    # Calculamos el porcentaje que debe avanzar la barra por cada iteración del bucle
    progress_step = float(100.0 / len(selected_items1))

    for each in selected_items1:
        # 1. Scraping: Descargamos el archivo de eGela en memoria (RAM), no en disco físico
        pdf_name, pdf_file = egela.get_pdf(each)

        # update() fuerza a la interfaz a redibujarse, evitando el temido mensaje de "No responde" del SO
        progress_bar.update()
        newroot.update()

        # Limpiamos el nombre por si trae caracteres codificados de la URL (ej. Presentaci%C3%B3n.pdf -> Presentación.pdf)
        clean_name = unquote(pdf_name)

        # 2. Rutas: Construimos la ruta de destino exacta para el API de Dropbox
        if dropbox._path == "/":
            path = "/" + clean_name
        else:
            path = dropbox._path + "/" + clean_name

        print(f"\t[TRANSFERENCIA] Subiendo '{clean_name}' a Dropbox en: {path}")

        # 3. Llamada al API HTTP de Dropbox para subir el payload binario
        dropbox.transfer_file(path, pdf_file)

        # Actualizamos la barra de progreso matemática y visualmente
        progress += progress_step
        progress_var.set(progress)
        progress_bar.update()
        newroot.update()

        # Pequeño delay artificial para no saturar el hilo principal y dejar que la UI respire
        time.sleep(0.1)

    popup.destroy()
    # Refrescamos la vista de la carpeta de Dropbox para que el usuario vea su archivo recién subido
    dropbox.list_folder(msg_listbox2)
    # Movemos el scroll al final de la lista
    msg_listbox2.yview(tk.END)


def delete_files():
    """Elimina los archivos o carpetas seleccionados en la lista de Dropbox."""
    if not selected_items2:
        messagebox.showwarning("Atención", "Selecciona al menos un archivo o carpeta de Dropbox para eliminar.")
        return

    popup, progress_var, progress_bar = helper.progress("delete_file", "Eliminando archivos...")
    progress = 0
    progress_var.set(progress)
    progress_bar.update()
    progress_step = float(100.0 / len(selected_items2))

    for each in selected_items2:
        # Control crucial: El índice 0 suele ser la pseudo-carpeta ".." para volver atrás.
        # Bloqueamos el intento de borrar el directorio padre porque el API de Dropbox devolvería un error 409 (Conflict).
        if dropbox._path != "/" and each == 0:
            print("\t[AVISO] Se ignoró el intento de borrar el directorio padre (..).")
            progress += progress_step
            progress_var.set(progress)
            progress_bar.update()
            continue

        # Extraemos el diccionario del archivo seleccionado desde la variable de estado local
        selected_file = dropbox._files[each]

        # Construimos la ruta absoluta del archivo a borrar según requiere el API
        if dropbox._path == "/":
            path = "/" + selected_file['name']
        else:
            path = dropbox._path + "/" + selected_file['name']

        print(f"\t[ELIMINANDO] Borrando de Dropbox: {path}")

        # Llamada HTTP DELETE o POST (según la versión de la API) para borrar en Dropbox
        dropbox.delete_file(path)

        progress += progress_step
        progress_var.set(progress)
        progress_bar.update()

    popup.destroy()
    # Petición HTTP al API para volver a listar y actualizar la UI local
    dropbox.list_folder(msg_listbox2)


def name_folder(folder_name):
    """Recibe el nombre escrito por el usuario y ejecuta la creación de la carpeta en Dropbox."""
    # Concatenamos la ruta actual con el nombre de la nueva carpeta respetando la estructura Unix '/'
    if dropbox._path == "/":
        dropbox._path = dropbox._path + str(folder_name)
    else:
        dropbox._path = dropbox._path + '/' + str(folder_name)

    print(f"\t[CARPETA] Creando nueva carpeta en: {dropbox._path}")

    # Llamada a la API para crear el recurso de tipo 'folder'
    dropbox.create_folder(dropbox._path)

    # Actualizamos el label dinámico (Tkinter StringVar) de la cabecera
    var.set(dropbox._path)

    # Destruimos la ventanita pop-up hija que abrimos para pedir el nombre
    dropbox._root.destroy()

    # Refrescamos el listado visual
    dropbox.list_folder(msg_listbox2)


def create_folder():
    """Abre un pop-up pidiendo al usuario el nombre de la nueva carpeta."""
    # Toplevel crea una ventana secundaria independiente de la principal ('newroot')
    popup = tk.Toplevel(newroot)
    popup.geometry('200x100')
    popup.title('Nueva Carpeta')
    popup.iconbitmap('./favicon.ico')
    helper.center(popup)

    login_frame = tk.Frame(popup, padx=10, pady=10)
    login_frame.pack(fill=tk.BOTH, expand=True)

    label = tk.Label(login_frame, text="Nombre de la carpeta:")
    label.pack(side=tk.TOP)

    entry_field = tk.Entry(login_frame, width=35)

    # bind intercepta eventos del teclado. Aquí asociamos pulsar Enter (<Return>) a lanzar la función.
    # Usamos una función anónima (lambda) porque necesitamos pasarle por parámetro el contenido del entry.
    entry_field.bind("<Return>", lambda event: name_folder(entry_field.get()))
    entry_field.pack(side=tk.TOP)

    # El botón hace lo mismo que pulsar Enter
    send_button = tk.Button(login_frame, text="Crear", command=lambda: name_folder(entry_field.get()))
    send_button.pack(side=tk.TOP)

    # Guardamos la referencia del popup en el objeto dropbox para poder destruirla luego desde name_folder()
    dropbox._root = popup


def share_files():
    """[MEJORA EXTRA] Genera un enlace público para los archivos seleccionados de Dropbox."""
    if not selected_items2:
        messagebox.showwarning("Atención", "Selecciona al menos un archivo de Dropbox para compartir.")
        return

    for each in selected_items2:
        # Volvemos a evitar interactuar con la pseudo-carpeta de retroceso ".."
        if dropbox._path != "/" and each == 0:
            continue

        if dropbox._path == "/":
            path = "/" + dropbox._files[each]['name']
        else:
            path = dropbox._path + "/" + dropbox._files[each]['name']

        print(f"\t[COMPARTIR] Solicitando enlace público para: {path}")

        # Llamamos a la API propia que habremos implementado en Dropbox.py para generar links de descarga
        link = dropbox.create_shared_link(path)

        # Si la API nos ha devuelto un enlace válido (HTTP 200 OK)
        if link:
            # Vaciamos el portapapeles del SO
            newroot.clipboard_clear()
            # Añadimos el enlace
            newroot.clipboard_append(link)
            # Forzamos la actualización del portapapeles a nivel del Sistema Operativo
            newroot.update()

            messagebox.showinfo("Enlace Compartido", f"Enlace generado y copiado al portapapeles:\n\n{link}")
        else:
            messagebox.showerror("Error", "No se pudo generar el enlace. Revisa la consola.")


##########################################################################################################
# SECCIÓN 3: MANEJADORES DE EVENTOS DE LA INTERFAZ
# Funciones que reaccionan a clics y selecciones (Listeners)
##########################################################################################################

def check_credentials(event=None):
    """Se ejecuta al pulsar el botón 'Login' o presionar Enter en eGela."""
    # Extraemos el texto crudo (get()) de los objetos Entry de Tkinter
    egela.check_credentials(username.get(), password.get())


def on_selecting1(event):
    """Guarda en una variable global los índices de los archivos seleccionados en la lista de eGela."""
    # Declaramos global para poder modificar la variable de estado que usan otras funciones (como transfer_files)
    global selected_items1
    widget = event.widget
    # curselection() devuelve una tupla con los índices seleccionados (ej: (0, 2, 3))
    selected_items1 = widget.curselection()


def on_selecting2(event):
    """Guarda en una variable global los índices de los archivos seleccionados en la lista de Dropbox."""
    global selected_items2
    widget = event.widget
    selected_items2 = widget.curselection()


def on_double_clicking2(event):
    """Maneja la navegación por carpetas en Dropbox mediante doble clic."""
    widget = event.widget
    selection = widget.curselection()

    # Si hace doble clic en el primer elemento (índice 0) y no estamos en la raíz ("/"), significa "Volver atrás"
    if selection[0] == 0 and dropbox._path != "/":
        # os.path.split separa la ruta base de la última carpeta. Ej: split("/padre/hijo") -> ("/padre", "hijo")
        head, tail = os.path.split(dropbox._path)
        dropbox._path = head
    else:
        # Si hace doble clic en un elemento normal, verificamos en los metadatos si es una carpeta
        selected_file = dropbox._files[selection[0]]
        # Comparamos la etiqueta '.tag' que nos devuelve el JSON de la API de Dropbox
        if selected_file['.tag'] == 'folder':
            if dropbox._path == "/":
                dropbox._path = dropbox._path + selected_file['name']
            else:
                dropbox._path = dropbox._path + '/' + selected_file['name']

    # Actualizamos el label visual dinámico de Tkinter con la nueva ruta
    var.set(dropbox._path)
    # Hacemos la petición HTTP a Dropbox para listar el nuevo directorio en el que acabamos de entrar
    dropbox.list_folder(msg_listbox2)


##########################################################################################################
# FLUJO PRINCIPAL 1: LOGIN Y SCRAPING DE EGELA
# Primera fase secuencial del programa: Validar credenciales contra el Moodle de la UPV/EHU
##########################################################################################################
root = tk.Tk()
root.geometry('250x150')
root.iconbitmap('./favicon.ico')
root.title('Login eGela')
helper.center(root)

# Instanciamos nuestra clase controladora de eGela
egela = eGela.eGela(root)

login_frame = tk.Frame(root, padx=10, pady=10)
login_frame.pack(fill=tk.BOTH, expand=True)

# Creamos los campos de texto
username = make_entry(login_frame, "User name:", 16)
password = make_entry(login_frame, "Password:", 16, show="*")
# Asociar Enter a la validación
password.bind("<Return>", check_credentials)

button = tk.Button(login_frame, borderwidth=4, text="Login", width=10, pady=8, command=check_credentials)
button.pack(side=tk.BOTTOM)

# mainloop() es una llamada bloqueante. El script de Python se detiene aquí escuchando eventos de la ventana
# hasta que hagamos un destroy() dentro del método login de la clase eGela.
root.mainloop()

# Mecanismo de seguridad: Si la ventana se cerró en la X sin loguear con éxito, cerramos todo el script (kill)
if not egela._login:
    exit()

# Si ha pasado el bloqueo, hacemos Web Scraping sobre el HTML del curso para sacar el diccionario de PDFs
pdfs = egela.get_pdf_refs()

##########################################################################################################
# FLUJO PRINCIPAL 2: AUTENTICACIÓN OAUTH 2.0 EN DROPBOX
# Segunda fase: Conseguir el Token Bearer de la API de Dropbox
##########################################################################################################
root = tk.Tk()
root.geometry('250x100')
root.iconbitmap('./favicon.ico')
root.title('Login Dropbox')
helper.center(root)

login_frame = tk.Frame(root, padx=10, pady=10)
login_frame.pack(fill=tk.BOTH, expand=True)

# Instanciamos la clase que gestionará las peticiones REST HTTP
dropbox = Dropbox.Dropbox(root)

label = tk.Label(login_frame, text="Login and Authorize\nin Drobpox")
label.pack(side=tk.TOP)

# Este botón dispara el flujo OAuth: abrir navegador -> aceptar permisos -> servidor Flask local intercepta token
button = tk.Button(login_frame, borderwidth=4, text="Login", width=10, pady=8, command=dropbox.do_oauth)
button.pack(side=tk.BOTTOM)

# Volvemos a bloquear el script hasta que el flujo OAuth cierre esta ventana
root.mainloop()

##########################################################################################################
# FLUJO PRINCIPAL 3: INTERFAZ GRÁFICA FINAL (eGela -> Dropbox)
# Tercera fase: Las dos columnas conectadas. Todo está logueado y listo.
##########################################################################################################
newroot = tk.Tk()
newroot.geometry("850x400")
newroot.iconbitmap('./favicon.ico')
newroot.title("eGela -> Dropbox")
helper.center(newroot)

# Configuramos la matriz (Grid) de la ventana.
# Los 'weight' dictan cómo se reparte el espacio extra si el usuario maximiza la ventana.
newroot.rowconfigure(0, weight=1)
newroot.rowconfigure(1, weight=5)
newroot.columnconfigure(0, weight=6)  # Columna izquierda (eGela) ocupa más ancho
newroot.columnconfigure(1, weight=1)  # Columna central (Botón >)
newroot.columnconfigure(2, weight=6)  # Columna derecha (Dropbox)
newroot.columnconfigure(3, weight=1)  # Botonera acciones

# ---- CABECERAS ----
# Etiqueta de la lista izquierda (eGela). Usamos StringVar para que se pueda actualizar dinámicamente si quisiéramos.
var2 = tk.StringVar()
var2.set("PDFs en Sistemas Web")
label2 = tk.Label(newroot, textvariable=var2)
# ipadx e ipady añaden padding interno a la celda del grid
label2.grid(column=0, row=0, ipadx=5, ipady=5)

# Etiqueta de la ruta actual (Dropbox)
var = tk.StringVar()
var.set(dropbox._path)
label = tk.Label(newroot, textvariable=var)
label.grid(row=0, column=2, ipadx=5, ipady=5)

# ---- PANEL IZQUIERDO: EGELA ----
selected_items1 = None
messages_frame1 = tk.Frame(newroot)
msg_listbox1 = make_listbox(messages_frame1)
# Bindeamos el evento de selección para actualizar 'selected_items1'
msg_listbox1.bind('<<ListboxSelect>>', on_selecting1)
msg_listbox1.pack(side=tk.LEFT, fill=tk.BOTH)
messages_frame1.grid(row=1, column=0, ipadx=10, ipady=10, padx=2, pady=2)

# ---- PANEL CENTRAL: BOTÓN TRANSFERIR ----
frame1 = tk.Frame(newroot)
button1 = tk.Button(frame1, borderwidth=4, text=">>>", width=10, pady=8, command=transfer_files)
button1.pack()
frame1.grid(row=1, column=1, ipadx=5, ipady=5)

# ---- PANEL DERECHO: DROPBOX ----
selected_items2 = None
messages_frame2 = tk.Frame(newroot)
msg_listbox2 = make_listbox(messages_frame2)
# Bindeamos eventos de clic simple y doble clic
msg_listbox2.bind('<<ListboxSelect>>', on_selecting2)
msg_listbox2.bind('<Double-Button-1>', on_double_clicking2)
msg_listbox2.pack(side=tk.RIGHT, fill=tk.BOTH)
messages_frame2.grid(row=1, column=2, ipadx=10, ipady=10, padx=2, pady=2)

# ---- BOTONERA DERECHA: ACCIONES DROPBOX ----
frame2 = tk.Frame(newroot)

# Botón Eliminar (Rojo estilo Danger)
button2 = tk.Button(frame2, borderwidth=4, background="#C6185C", fg="white", text="Delete", width=10, pady=8,
                    command=delete_files)
button2.pack(padx=2, pady=2)

# Botón Compartir (Extra - Naranja)
button4 = tk.Button(frame2, borderwidth=4, background="#FF9800", fg="white", text="Share", width=10, pady=8,
                    command=share_files)
button4.pack(padx=2, pady=2)

# Botón Crear Carpeta (Azul claro)
button3 = tk.Button(frame2, borderwidth=4, background="#7C86FF", fg="white", text="Create folder", width=10, pady=8,
                    command=create_folder)
button3.pack(padx=2, pady=2)

frame2.grid(row=1, column=3, ipadx=10, ipady=10)

# ---- INICIALIZACIÓN DE DATOS ----
# Rellenamos la lista izquierda iterando el array de diccionarios que nos dio el Web Scraping en el Paso 1
for each in pdfs:
    # Insertamos el campo 'pdf_name' al final (tk.END) de la listbox de eGela
    msg_listbox1.insert(tk.END, each['pdf_name'])
    msg_listbox1.yview(tk.END)

# Rellenamos la lista derecha disparando una petición HTTP GET a la API para ver la raíz ("/") de nuestro Dropbox
dropbox.list_folder(msg_listbox2)

# Lanzamos la interfaz principal y dejamos el programa en un bucle infinito escuchando nuestros eventos.
newroot.mainloop()