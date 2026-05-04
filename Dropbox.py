# -*- coding: UTF-8 -*-
"""
Módulo Dropbox
Gestiona el flujo de autenticación OAuth 2.0 mediante un socket local y
se comunica con la API RESTful de Dropbox (API v2) para gestionar archivos.
"""

import requests
import urllib
import webbrowser
from socket import AF_INET, socket, SOCK_STREAM
import json
import helper
from tkinter import messagebox

# Credenciales de la App de Dropbox (App Console)
# NOTA: En un entorno real de producción, esto debería ir en un archivo .env o variables de entorno
app_key = 'uhg5h41oo6xo44m'
app_secret = '09jxbyi09dg3ujq'

# Configuración del servidor local para atrapar el callback de OAuth 2.0
server_addr = "localhost"
server_port = 8070
redirect_uri = f"http://{server_addr}:{server_port}"


class Dropbox:
    _access_token = ""
    _path = "/"
    _files = []
    _root = None
    _msg_listbox = None

    def __init__(self, root):
        self._root = root

    def local_server(self):
        """
        Levanta un servidor socket temporal en localhost.
        Su única función es "atrapar" la redirección HTTP 302 que hace el navegador
        tras aceptar los permisos en la web de Dropbox, extrayendo el 'auth_code'.
        """
        server_socket = socket(AF_INET, SOCK_STREAM)
        server_socket.bind((server_addr, server_port))
        server_socket.listen(1)
        print(f"\n\t[SOCKET] Servidor local escuchando en el puerto {server_port}...")

        # Esperamos a que el navegador nos haga la petición GET a /?code=...
        client_connection, client_address = server_socket.accept()
        peticion = client_connection.recv(1024)
        print("\t[SOCKET] Petición recibida del navegador web.")

        # Parseamos la cabecera HTTP bruta para extraer el código
        # La primera línea suele ser: "GET /?code=oqeiX... HTTP/1.1"
        primera_linea = peticion.decode('UTF8').split('\n')[0]
        aux_auth_code = primera_linea.split(' ')[1]

        # Aislamos solo el valor del parámetro 'code'
        auth_code = aux_auth_code.split('code=')[1].split('&')[0]
        print(f"\t[OAUTH] Código de autorización capturado: {auth_code[:10]}...")

        # Devolvemos una web amable al usuario para que sepa que puede cerrar la pestaña
        http_response = "HTTP/1.1 200 OK\r\n\r\n" \
                        "<html>" \
                        "<head><title>Dropbox Auth Exitosa</title></head>" \
                        "<body style='font-family: Arial; text-align: center; margin-top: 50px;'>" \
                        "<h2>Autenticacion completada con exito.</h2>" \
                        "<p>Ya puedes cerrar esta ventana y volver a la aplicacion Python.</p>" \
                        "</body>" \
                        "</html>"

        client_connection.sendall(http_response.encode('utf-8'))
        client_connection.close()
        server_socket.close()

        return auth_code

    def do_oauth(self):
        """Implementa el flujo completo OAuth 2.0 (Authorization Code Flow)"""

        print("\n[OAUTH] Paso 1: Solicitando permisos al usuario en el navegador...")
        auth_url = f"https://www.dropbox.com/oauth2/authorize?client_id={app_key}&redirect_uri={redirect_uri}&response_type=code"
        webbrowser.open_new(auth_url)

        print("[OAUTH] Paso 2: Esperando el código de autorización...")
        auth_code = self.local_server()

        print("\n[OAUTH] Paso 3: Intercambiando el código temporal por un Access Token...")
        token_url = "https://api.dropboxapi.com/oauth2/token"
        datos = {
            'code': auth_code,
            'grant_type': 'authorization_code',
            'client_id': app_key,
            'client_secret': app_secret,
            'redirect_uri': redirect_uri
        }

        respuesta = requests.post(token_url, data=datos)
        contenido_json = json.loads(respuesta.text)

        if 'access_token' in contenido_json:
            self._access_token = contenido_json['access_token']
            print("\t[ÉXITO] Access token obtenido correctamente.")
        else:
            print(f"\t[ERROR] No se pudo obtener el token: {contenido_json}")

        self._root.destroy()

    def get_headers(self, is_json=True):
        """Genera las cabeceras HTTP de autorización para la API de Dropbox."""
        headers = {'Authorization': 'Bearer ' + self._access_token}
        if is_json:
            headers['Content-Type'] = 'application/json'
        return headers

    def list_folder(self, msg_listbox):
        """Obtiene el listado de archivos y carpetas de un directorio dado."""
        print(f"\n[API DROPBOX] GET /list_folder (Ruta: '{self._path}')")
        uri = 'https://api.dropboxapi.com/2/files/list_folder'

        # DETALLE TÉCNICO: Dropbox explota si le pasas "/" como ruta raíz. Exige "".
        api_path = "" if self._path == "/" else self._path
        data = {"path": api_path}

        res = requests.post(uri, headers=self.get_headers(), data=json.dumps(data))

        # Control de errores HTTP
        if res.status_code != 200:
            print(f"\t[ERROR] Fallo al listar carpeta. Código: {res.status_code}")
            print(f"\t[DETALLE]: {res.text}")
            return

        contenido_json = json.loads(res.text)

        # Actualizamos la interfaz gráfica usando el helper del profesor
        self._files = helper.update_listbox2(msg_listbox, self._path, contenido_json)

    def transfer_file(self, file_path, file_data):
        """Sube un archivo binario a Dropbox."""
        print(f"[API DROPBOX] POST /upload (Destino: '{file_path}')")
        uri = 'https://content.dropboxapi.com/2/files/upload'

        # DETALLE TÉCNICO: La API de carga es distinta. No recibe JSON en el body.
        # Recibe el archivo crudo en el body (octet-stream) y los metadatos en una cabecera especial (Dropbox-API-Arg).
        headers = self.get_headers(is_json=False)
        headers['Content-Type'] = 'application/octet-stream'

        api_arg = {
            "path": file_path,
            "mode": "add",  # 'add' evita sobreescribir; si existe, renombra
            "autorename": True,
            "mute": False
        }
        headers['Dropbox-API-Arg'] = json.dumps(api_arg)

        # Hacemos el POST mandando 'file_data' directamente en la propiedad 'data'
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
        """Genera un enlace público de lectura para el archivo indicado."""
        print(f"[API DROPBOX] POST /create_shared_link_with_settings (Archivo: '{file_path}')")
        uri = 'https://api.dropboxapi.com/2/sharing/create_shared_link_with_settings'
        data = {"path": file_path}

        res = requests.post(uri, headers=self.get_headers(), data=json.dumps(data))

        if res.status_code == 200:
            respuesta_json = json.loads(res.text)
            link = respuesta_json.get('url')
            print(f"\t[ÉXITO] Link generado: {link}")
            return link  # Devolvemos el enlace a la interfaz gráfica

        else:
            print(f"\t[ERROR] Fallo al generar enlace. Código: {res.status_code}")
            print(f"\t[DETALLE]: {res.text}")
            return None  # Devolvemos None si algo falla