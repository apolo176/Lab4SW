# -*- coding: UTF-8 -*-
"""
Práctica 4: Dropbox - OAuth
Asignatura: Sistemas Web
Integrantes del grupo: Liviu Deleanu, Eder Torres, Alex Isasi
Descripción: Aplicación con interfaz gráfica (Tkinter) que extrae PDFs de eGela
             mediante Web Scraping y permite subirlos a Dropbox usando su API REST.
"""

import tkinter as tk
from tkinter import messagebox
import os
import time
from urllib.parse import unquote

# Importamos nuestros propios módulos con la lógica de negocio
import eGela
import Dropbox
import helper


##########################################################################################################
# SECCIÓN 1: FUNCIONES DE INTERFAZ GRÁFICA (UI HELPERS)
##########################################################################################################

def make_entry(parent, caption, width=None, **options):
    """Crea un label y un campo de entrada de texto (Entry) en la interfaz."""
    label = tk.Label(parent, text=caption)
    label.pack(side=tk.TOP)
    entry = tk.Entry(parent, **options)
    entry.config(width=width)
    entry.pack(side=tk.TOP, padx=10, fill=tk.BOTH)
    return entry


def make_listbox(messages_frame):
    """Crea una lista seleccionable (Listbox) con barra de desplazamiento lateral."""
    messages_frame.config(bd=1, relief="ridge")
    scrollbar = tk.Scrollbar(messages_frame)
    # selectmode=tk.EXTENDED permite seleccionar múltiples archivos a la vez (con Shift o Ctrl)
    msg_listbox = tk.Listbox(messages_frame, height=20, width=70, exportselection=0, selectmode=tk.EXTENDED)
    msg_listbox.configure(yscrollcommand=scrollbar.set)
    scrollbar.configure(command=msg_listbox.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    return msg_listbox


##########################################################################################################
# SECCIÓN 2: LÓGICA PRINCIPAL DE LOS BOTONES
##########################################################################################################

def transfer_files():
    """Descarga los PDFs seleccionados de eGela y los sube a Dropbox."""
    # Control de errores: evitar fallo si el usuario no ha seleccionado nada
    if not selected_items1:
        messagebox.showwarning("Atención", "Selecciona al menos un archivo de eGela para transferir.")
        return

    # Inicializamos la barra de progreso
    popup, progress_var, progress_bar = helper.progress("transfer_file", "Transfiriendo archivos...")
    progress = 0
    progress_var.set(progress)
    progress_bar.update()

    # Calculamos cuánto avanza la barra por cada archivo
    progress_step = float(100.0 / len(selected_items1))

    for each in selected_items1:
        # 1. Descargamos el archivo de eGela en memoria (RAM)
        pdf_name, pdf_file = egela.get_pdf(each)
        progress_bar.update()
        newroot.update()

        # Limpiamos el nombre por si trae caracteres codificados de la URL (ej. %20 -> espacio)
        clean_name = unquote(pdf_name)

        # 2. Construimos la ruta de destino en Dropbox
        if dropbox._path == "/":
            path = "/" + clean_name
        else:
            path = dropbox._path + "/" + clean_name

        print(f"\t[TRANSFERENCIA] Subiendo '{clean_name}' a Dropbox en: {path}")

        # 3. Subimos el archivo usando la API de Dropbox
        dropbox.transfer_file(path, pdf_file)

        # Actualizamos la barra de progreso
        progress += progress_step
        progress_var.set(progress)
        progress_bar.update()
        newroot.update()
        time.sleep(0.1)

    popup.destroy()
    # Refrescamos la vista de la carpeta de Dropbox para que aparezcan los nuevos archivos
    dropbox.list_folder(msg_listbox2)
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
        # Prevenimos que el usuario intente borrar el directorio padre ".." que es solo visual
        if dropbox._path != "/" and each == 0:
            print("\t[AVISO] Se ignoró el intento de borrar el directorio padre (..).")
            progress += progress_step
            progress_var.set(progress)
            progress_bar.update()
            continue

        selected_file = dropbox._files[each]

        # Construimos la ruta completa del archivo a borrar
        if dropbox._path == "/":
            path = "/" + selected_file['name']
        else:
            path = dropbox._path + "/" + selected_file['name']

        print(f"\t[ELIMINANDO] Borrando de Dropbox: {path}")
        dropbox.delete_file(path)

        progress += progress_step
        progress_var.set(progress)
        progress_bar.update()

    popup.destroy()
    dropbox.list_folder(msg_listbox2)


def name_folder(folder_name):
    """Recibe el nombre escrito por el usuario y ejecuta la creación de la carpeta en Dropbox."""
    if dropbox._path == "/":
        dropbox._path = dropbox._path + str(folder_name)
    else:
        dropbox._path = dropbox._path + '/' + str(folder_name)

    print(f"\t[CARPETA] Creando nueva carpeta en: {dropbox._path}")
    dropbox.create_folder(dropbox._path)

    # Actualizamos el label visual de la ruta actual
    var.set(dropbox._path)
    # Destruimos la ventanita pop-up
    dropbox._root.destroy()
    # Refrescamos el listado
    dropbox.list_folder(msg_listbox2)


def create_folder():
    """Abre un pop-up pidiendo al usuario el nombre de la nueva carpeta."""
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
    # Vinculamos la tecla Enter (Return) para que ejecute la creación enviando el texto
    entry_field.bind("<Return>", lambda event: name_folder(entry_field.get()))
    entry_field.pack(side=tk.TOP)

    send_button = tk.Button(login_frame, text="Crear", command=lambda: name_folder(entry_field.get()))
    send_button.pack(side=tk.TOP)

    dropbox._root = popup


def share_files():
    """[MEJORA EXTRA] Genera un enlace público para los archivos seleccionados de Dropbox."""
    if not selected_items2:
        messagebox.showwarning("Atención", "Selecciona al menos un archivo de Dropbox para compartir.")
        return

    for each in selected_items2:
        # Prevenimos compartir el ".."
        if dropbox._path != "/" and each == 0:
            continue

        if dropbox._path == "/":
            path = "/" + dropbox._files[each]['name']
        else:
            path = dropbox._path + "/" + dropbox._files[each]['name']

        print(f"\t[COMPARTIR] Solicitando enlace público para: {path}")
        dropbox.create_shared_link(path)


##########################################################################################################
# SECCIÓN 3: MANEJADORES DE EVENTOS DE LA INTERFAZ
##########################################################################################################

def check_credentials(event=None):
    """Se ejecuta al pulsar el botón 'Login' o presionar Enter en eGela."""
    egela.check_credentials(username, password)


def on_selecting1(event):
    """Guarda en una variable global los índices de los archivos seleccionados en la lista de eGela."""
    global selected_items1
    widget = event.widget
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

    # Si hace doble clic en el primer elemento (índice 0) y no estamos en la raíz, volvemos atrás
    if selection[0] == 0 and dropbox._path != "/":
        head, tail = os.path.split(dropbox._path)
        dropbox._path = head
    else:
        # Si hace doble clic en una carpeta normal, entramos en ella
        selected_file = dropbox._files[selection[0]]
        if selected_file['.tag'] == 'folder':
            if dropbox._path == "/":
                dropbox._path = dropbox._path + selected_file['name']
            else:
                dropbox._path = dropbox._path + '/' + selected_file['name']

    # Actualizamos el label de la ruta y refrescamos la lista
    var.set(dropbox._path)
    dropbox.list_folder(msg_listbox2)


##########################################################################################################
# FLUJO PRINCIPAL 1: LOGIN Y SCRAPING DE EGELA
##########################################################################################################
root = tk.Tk()
root.geometry('250x150')
root.iconbitmap('./favicon.ico')
root.title('Login eGela')
helper.center(root)

egela = eGela.eGela(root)

login_frame = tk.Frame(root, padx=10, pady=10)
login_frame.pack(fill=tk.BOTH, expand=True)

username = make_entry(login_frame, "User name:", 16)
password = make_entry(login_frame, "Password:", 16, show="*")
password.bind("<Return>", check_credentials)

button = tk.Button(login_frame, borderwidth=4, text="Login", width=10, pady=8, command=check_credentials)
button.pack(side=tk.BOTTOM)

# Detiene el script aquí hasta que se destruya la ventana (es decir, el login sea exitoso)
root.mainloop()

# Si el usuario cierra la ventana sin loguearse, terminamos la ejecución
if not egela._login:
    exit()

# Extraemos las referencias a los PDFs (Web Scraping)
pdfs = egela.get_pdf_refs()

##########################################################################################################
# FLUJO PRINCIPAL 2: AUTENTICACIÓN OAUTH 2.0 EN DROPBOX
##########################################################################################################
root = tk.Tk()
root.geometry('250x100')
root.iconbitmap('./favicon.ico')
root.title('Login Dropbox')
helper.center(root)

login_frame = tk.Frame(root, padx=10, pady=10)
login_frame.pack(fill=tk.BOTH, expand=True)

# Instanciamos la clase que gestionará la API
dropbox = Dropbox.Dropbox(root)

label = tk.Label(login_frame, text="Login and Authorize\nin Drobpox")
label.pack(side=tk.TOP)
button = tk.Button(login_frame, borderwidth=4, text="Login", width=10, pady=8, command=dropbox.do_oauth)
button.pack(side=tk.BOTTOM)

# Detiene el script aquí hasta capturar el token de Dropbox
root.mainloop()

##########################################################################################################
# FLUJO PRINCIPAL 3: INTERFAZ GRÁFICA FINAL (eGela -> Dropbox)
##########################################################################################################
newroot = tk.Tk()
newroot.geometry("850x400")
newroot.iconbitmap('./favicon.ico')
newroot.title("eGela -> Dropbox")
helper.center(newroot)

# Configuramos la matriz (Grid) de la ventana para que se expanda bien
newroot.rowconfigure(0, weight=1)
newroot.rowconfigure(1, weight=5)
newroot.columnconfigure(0, weight=6)
newroot.columnconfigure(1, weight=1)
newroot.columnconfigure(2, weight=6)
newroot.columnconfigure(3, weight=1)

# ---- CABECERAS ----
# Etiqueta de la lista izquierda (eGela)
var2 = tk.StringVar()
var2.set("PDFs en Sistemas Web")
label2 = tk.Label(newroot, textvariable=var2)
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
msg_listbox2.bind('<<ListboxSelect>>', on_selecting2)
msg_listbox2.bind('<Double-Button-1>', on_double_clicking2)
msg_listbox2.pack(side=tk.RIGHT, fill=tk.BOTH)
messages_frame2.grid(row=1, column=2, ipadx=10, ipady=10, padx=2, pady=2)

# ---- BOTONERA DERECHA: ACCIONES DROPBOX ----
frame2 = tk.Frame(newroot)

# Botón Eliminar
button2 = tk.Button(frame2, borderwidth=4, background="#C6185C", fg="white", text="Delete", width=10, pady=8,
                    command=delete_files)
button2.pack(padx=2, pady=2)

# Botón Compartir (Extra)
button4 = tk.Button(frame2, borderwidth=4, background="#FF9800", fg="white", text="Share", width=10, pady=8,
                    command=share_files)
button4.pack(padx=2, pady=2)

# Botón Crear Carpeta
button3 = tk.Button(frame2, borderwidth=4, background="#7C86FF", fg="white", text="Create folder", width=10, pady=8,
                    command=create_folder)
button3.pack(padx=2, pady=2)

frame2.grid(row=1, column=3, ipadx=10, ipady=10)

# ---- INICIALIZACIÓN DE DATOS ----
# Rellenamos la lista izquierda con los PDFs extraídos en el Paso 1
for each in pdfs:
    msg_listbox1.insert(tk.END, each['pdf_name'])
    msg_listbox1.yview(tk.END)

# Rellenamos la lista derecha llamando a la API para ver la raíz de Dropbox
dropbox.list_folder(msg_listbox2)

# Lanzamos la interfaz principal
newroot.mainloop()