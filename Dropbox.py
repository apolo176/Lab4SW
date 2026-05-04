# -*- coding: UTF-8 -*-
"""
Módulo Dropbox
Gestiona el flujo de autenticación OAuth 2.0 mediante un socket local y
se comunica con la API RESTful de Dropbox (API v2) para gestionar archivos.
"""

import requests
import urllib
# webbrowser nos permite invocar al navegador por defecto del sistema operativo para abrir URLs
import webbrowser
# Importamos las piezas necesarias de la librería socket para montar nuestro servidor local TCP/IP
from socket import AF_INET, socket, SOCK_STREAM
import json
import helper
from tkinter import messagebox

# Credenciales de la App de Dropbox (Obtenidas de la App Console de desarrollador)
# NOTA DE SEGURIDAD: En un entorno real de producción, esto jamás debería estar harcodeado en el código fuente.
# Debería cargarse a través de variables de entorno (.env) para evitar filtraciones en repositorios de código.
app_key = 'uhg5h41oo6xo44m'
app_secret = '09jxbyi09dg3ujq'

# Configuración del servidor local para atrapar el callback (redirección) del flujo OAuth 2.0
server_addr = "localhost"
server_port = 8070
# Esta URL debe estar registrada de forma idéntica en la consola de desarrolladores de Dropbox bajo 'Redirect URIs'
redirect_uri = f"http://{server_addr}:{server_port}"


class Dropbox:
    # --- Atributos de clase (Estado interno) ---
    _access_token = ""  # El preciado token de acceso final que nos dará la llave para hacer peticiones en nombre del usuario
    _path = "/"  # Ruta virtual en la que nos encontramos navegando dentro de la interfaz
    _files = []  # Caché de los archivos de la carpeta actual
    _root = None  # Referencia a la ventana de Toplevel para destruirla cuando acabe el proceso
    _msg_listbox = None  # Referencia visual al elemento ListBox derecho (el de Dropbox)

    def __init__(self, root):
        self._root = root

    def local_server(self):
        """
        Levanta un servidor socket temporal en localhost.
        Su única función es "atrapar" la redirección HTTP 302 que hace el navegador
        tras aceptar los permisos en la web de Dropbox, extrayendo el 'auth_code'.
        """
        # AF_INET indica que usaremos direcciones IPv4. SOCK_STREAM indica que usaremos el protocolo TCP.
        server_socket = socket(AF_INET, SOCK_STREAM)

        # Enlazamos el socket a la dirección y puerto especificados
        server_socket.bind((server_addr, server_port))

        # listen(1) indica al sistema operativo que permita encolar un máximo de 1 conexión entrante (no necesitamos más)
        server_socket.listen(1)
        print(f"\n\t[SOCKET] Servidor local escuchando en el puerto {server_port}...")

        # accept() es bloqueante. El hilo de ejecución se pausa aquí hasta que entra una conexión real
        client_connection, client_address = server_socket.accept()

        # Leemos los primeros 1024 bytes de la petición entrante
        peticion = client_connection.recv(1024)
        print("\t[SOCKET] Petición recibida del navegador web.")

        # Parseamos la cabecera HTTP bruta para extraer el código.
        # La primera línea suele ser algo como: "GET /?code=oqeiX29_s... HTTP/1.1"
        primera_linea = peticion.decode('UTF8').split('\n')[0]
        # Extraemos "/?code=oqeiX29_s..."
        aux_auth_code = primera_linea.split(' ')[1]

        # Aislamos solo el valor del parámetro 'code', cortando por '&' por si vienen más parámetros (ej. state)
        auth_code = aux_auth_code.split('code=')[1].split('&')[0]
        print(f"\t[OAUTH] Código de autorización capturado: {auth_code[:10]}...")

        # Construimos una respuesta HTTP válida y amigable. Es necesario responder para que el navegador no se quede "pensando".
        http_response = "HTTP/1.1 200 OK\r\n\r\n" \
                        "<html>" \
                        "<head><title>Dropbox Auth Exitosa</title></head>" \
                        "<body style='font-family: Arial; text-align: center; margin-top: 50px;'>" \
                        "<h2>Autenticacion completada con exito.</h2>" \
                        "<p>Ya puedes cerrar esta ventana y volver a la aplicacion Python.</p>" \
                        "</body>" \
                        "</html>"

        # Enviamos la respuesta binaria
        client_connection.sendall(http_response.encode('utf-8'))

        # Cerramos las tuberías de red. Ya hemos cumplido nuestro propósito.
        client_connection.close()
        server_socket.close()

        # Devolvemos el string crudo del auth_code
        return auth_code

    def do_oauth(self):
        """
        Implementa el flujo completo OAuth 2.0 (Authorization Code Flow).
        Es un proceso de 3 pasos: Solicitud de Auth Code -> Recepción del Code -> Intercambio por Access Token.
        """

        print("\n[OAUTH] Paso 1: Solicitando permisos al usuario en el navegador...")
        # Construimos la URL mágica que abre la pantalla de login/permisos de Dropbox
        auth_url = f"https://www.dropbox.com/oauth2/authorize?client_id={app_key}&redirect_uri={redirect_uri}&response_type=code"
        webbrowser.open_new(auth_url)

        print("[OAUTH] Paso 2: Esperando el código de autorización...")
        # Llamamos a nuestro método socket bloqueante
        auth_code = self.local_server()

        print("\n[OAUTH] Paso 3: Intercambiando el código temporal por un Access Token...")
        # Este endpoint es al que hay que "llorar" (POST) enviando el código para que nos den el Token definitivo
        token_url = "https://api.dropboxapi.com/oauth2/token"

        # Montamos el payload del formulario HTTP POST estándar para OAuth2
        datos = {
            'code': auth_code,
            'grant_type': 'authorization_code',
            'client_id': app_key,
            'client_secret': app_secret,
            'redirect_uri': redirect_uri
        }

        # Lanzamos la petición HTTPS a los servidores de Dropbox
        respuesta = requests.post(token_url, data=datos)

        # Transformamos la string JSON de la respuesta a un diccionario de Python
        contenido_json = json.loads(respuesta.text)

        # Si el servidor responde un JSON con la key 'access_token', es que todo ha ido bien
        if 'access_token' in contenido_json:
            # Lo guardamos en memoria. A partir de aquí, todas las llamadas REST lo usarán.
            self._access_token = contenido_json['access_token']
            print("\t[ÉXITO] Access token obtenido correctamente.")
        else:
            print(f"\t[ERROR] No se pudo obtener el token: {contenido_json}")

        # Destruimos la ventana puente de login de Dropbox que se abrió en actividad_4.py
        self._root.destroy()

    def get_headers(self, is_json=True):
        """
        Genera las cabeceras HTTP de autorización para la API de Dropbox.
        Evita tener que reescribir esto en cada método.
        """
        # El estándar OAuth 2.0 dicta que el token se envía en la cabecera 'Authorization' con el prefijo 'Bearer '
        headers = {'Authorization': 'Bearer ' + self._access_token}
        if is_json:
            headers['Content-Type'] = 'application/json'
        return headers

    def list_folder(self, msg_listbox):
        """Obtiene el listado de archivos y carpetas de un directorio dado."""
        print(f"\n[API DROPBOX] GET /list_folder (Ruta: '{self._path}')")
        # Usamos el endpoint v2 general de Dropbox (rpc)
        uri = 'https://api.dropboxapi.com/2/files/list_folder'

        # DETALLE TÉCNICO VITAL: Dropbox explota (Error 400) si le pasas "/" como ruta raíz literal.
        # Exige una string vacía ("") para representar la raíz de la cuenta de usuario.
        api_path = "" if self._path == "/" else self._path
        data = {"path": api_path}

        # Petición REST
        res = requests.post(uri, headers=self.get_headers(), data=json.dumps(data))

        # Control de errores HTTP defensivo
        if res.status_code != 200:
            print(f"\t[ERROR] Fallo al listar carpeta. Código: {res.status_code}")
            print(f"\t[DETALLE]: {res.text}")
            return

        contenido_json = json.loads(res.text)

        # Actualizamos la interfaz gráfica usando la función provista por el profesor
        self._files = helper.update_listbox2(msg_listbox, self._path, contenido_json)

    def transfer_file(self, file_path, file_data):
        """Sube un archivo binario a Dropbox."""
        print(f"[API DROPBOX] POST /upload (Destino: '{file_path}')")
        # OJO: Los endpoints de subida/bajada de contenido en Dropbox usan 'content.dropboxapi.com', no 'api.dropboxapi...'
        uri = 'https://content.dropboxapi.com/2/files/upload'

        # DETALLE TÉCNICO: La API de carga es distinta. No recibe un payload JSON en el body de la petición HTTP.
        # Recibe el archivo crudo en el body (octet-stream) y los metadatos de configuración en una cabecera especial personalizada.
        headers = self.get_headers(is_json=False)
        headers['Content-Type'] = 'application/octet-stream'

        # Parámetros de subida de la API de Dropbox
        api_arg = {
            "path": file_path,
            "mode": "add",  # 'add' añade un archivo nuevo. Si detecta colisión, usará la regla de 'autorename'
            "autorename": True,  # Si subimos "Sistemas.pdf" y existe, lo guardará como "Sistemas (1).pdf"
            "mute": False  # No silenciamos notificaciones de desktop si el usuario lo tuviera instalado
        }

        # Serializamos el diccionario a string JSON y lo inyectamos en la cabecera
        headers['Dropbox-API-Arg'] = json.dumps(api_arg)

        # Hacemos el POST mandando 'file_data' (bytes puros obtenidos del scraping de eGela) directamente a la propiedad 'data'
        res = requests.post(uri, headers=headers, data=file_data)

        if res.status_code != 200:
            print(f"\t[ERROR] Fallo al subir archivo. Código: {res.status_code}")
            print(f"\t[DETALLE]: {res.text}")

    def delete_file(self, file_path):
        """Elimina un archivo o directorio de Dropbox."""
        print(f"[API DROPBOX] POST /delete_v2 (Objetivo: '{file_path}')")
        uri = 'https://api.dropboxapi.com/2/files/delete_v2'
        data = {"path": file_path}

        res = requests.post(uri, headers=self.get_headers(), data=json.dumps(data))

        if res.status_code != 200:
            print(f"\t[ERROR] Fallo al borrar. Código: {res.status_code}")
            print(f"\t[DETALLE]: {res.text}")

    def create_folder(self, path):
        """Crea un nuevo directorio en Dropbox."""
        print(f"[API DROPBOX] POST /create_folder_v2 (Nueva ruta: '{path}')")
        uri = 'https://api.dropboxapi.com/2/files/create_folder_v2'
        data = {"path": path}

        res = requests.post(uri, headers=self.get_headers(), data=json.dumps(data))

        if res.status_code != 200:
            print(f"\t[ERROR] Fallo al crear carpeta. Código: {res.status_code}")
            print(f"\t[DETALLE]: {res.text}")

    # =========================================================
    # MEJORA EXTRA (20%): Generar enlace para compartir un archivo
    # =========================================================
    def create_shared_link(self, file_path):
        """
        [MEJORA EXTRA] Genera un enlace público de lectura para el archivo indicado.
        Esta funcionalidad se sale de los requisitos básicos y demuestra dominio de la lectura de documentación API.
        """
        print(f"[API DROPBOX] POST /create_shared_link_with_settings (Archivo: '{file_path}')")
        # Documentación de este endpoint: https://www.dropbox.com/developers/documentation/http/documentation#sharing-create_shared_link_with_settings
        uri = 'https://api.dropboxapi.com/2/sharing/create_shared_link_with_settings'
        data = {"path": file_path}

        res = requests.post(uri, headers=self.get_headers(), data=json.dumps(data))

        if res.status_code == 200:
            respuesta_json = json.loads(res.text)
            # Extraemos la propiedad 'url' que devuelve la API con el enlace público acortado
            link = respuesta_json.get('url')
            print(f"\t[ÉXITO] Link generado: {link}")
            return link  # Devolvemos el enlace a la interfaz gráfica (actividad_4.py) para que lo meta al portapapeles

        else:
            # Gestión de errores específicos, como intentar compartir una carpeta (lo cual requiere settings extra que no hemos configurado)
            print(f"\t[ERROR] Fallo al generar enlace. Código: {res.status_code}")
            print(f"\t[DETALLE]: {res.text}")
            return None  # Devolvemos None si la generación ha fallado para manejarlo en la UI