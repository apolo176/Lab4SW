import requests
import urllib
import webbrowser
from socket import AF_INET, socket, SOCK_STREAM
import json
import helper
from tkinter import messagebox

app_key = 'uhg5h41oo6xo44m'
app_secret = '09jxbyi09dg3ujq'
server_addr = "localhost"
server_port = 8070
redirect_uri = "http://" + server_addr + ":" + str(server_port)


class Dropbox:
    _access_token = ""
    _path = "/"
    _files = []
    _root = None
    _msg_listbox = None

    def __init__(self, root):
        self._root = root

    def local_server(self):
        server_socket = socket(AF_INET, SOCK_STREAM)
        server_socket.bind((server_addr, server_port))
        server_socket.listen(1)
        print("\tLocal server listening on port " + str(server_port))

        client_connection, client_address = server_socket.accept()
        peticion = client_connection.recv(1024)
        print("\tRequest from the browser received at local server:")

        primera_linea = peticion.decode('UTF8').split('\n')[0]
        aux_auth_code = primera_linea.split(' ')[1]
        auth_code = aux_auth_code.split('code=')[1].split('&')[0]
        print("\tauth_code: " + auth_code)

        http_response = "HTTP/1.1 200 OK\r\n\r\n" \
                        "<html>" \
                        "<head><title>Dropbox Auth</title></head>" \
                        "<body>The authentication flow has completed. You can close this window.</body>" \
                        "</html>"
        client_connection.sendall(http_response.encode('utf-8'))
        client_connection.close()
        server_socket.close()

        return auth_code

    def do_oauth(self):
        print("\nStep 1.- Send authorization request to Dropbox")
        auth_url = f"https://www.dropbox.com/oauth2/authorize?client_id={app_key}&redirect_uri={redirect_uri}&response_type=code"
        webbrowser.open_new(auth_url)

        print("\nStep 2.- Wait for auth code")
        auth_code = self.local_server()

        print("\nStep 3.- Exchange code for token")
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
            print("\tAccess token obtained successfully.")
        else:
            print("\tError obtaining token:", contenido_json)

        self._root.destroy()

    def get_headers(self, is_json=True):
        headers = {'Authorization': 'Bearer ' + self._access_token}
        if is_json:
            headers['Content-Type'] = 'application/json'
        return headers

    def list_folder(self, msg_listbox):
        print(f"/list_folder (Ruta solicitada: '{self._path}')")
        uri = 'https://api.dropboxapi.com/2/files/list_folder'

        # Dropbox requiere "" (string vacío) para la ruta raíz, no "/"
        api_path = "" if self._path == "/" else self._path
        data = {"path": api_path}

        # Usamos data=json.dumps() para evitar conflictos con nuestras cabeceras manuales
        res = requests.post(uri, headers=self.get_headers(), data=json.dumps(data))

        # Control de errores a prueba de balas
        if res.status_code != 200:
            print(f"\t[ERROR DROPBOX] Fallo al listar carpeta. Código: {res.status_code}")
            print(f"\t[DETALLE]: {res.text}")
            return

        contenido_json = json.loads(res.text)
        self._files = helper.update_listbox2(msg_listbox, self._path, contenido_json)

    def transfer_file(self, file_path, file_data):
        print(f"/upload: {file_path}")
        uri = 'https://content.dropboxapi.com/2/files/upload'

        headers = self.get_headers(is_json=False)
        headers['Content-Type'] = 'application/octet-stream'

        api_arg = {
            "path": file_path,
            "mode": "add",
            "autorename": True,
            "mute": False
        }
        headers['Dropbox-API-Arg'] = json.dumps(api_arg)

        res = requests.post(uri, headers=headers, data=file_data)
        if res.status_code != 200:
            print(f"\t[ERROR DROPBOX] Fallo al subir archivo. Código: {res.status_code}")
            print(f"\t[DETALLE]: {res.text}")

    def delete_file(self, file_path):
        print(f"/delete_v2: {file_path}")
        uri = 'https://api.dropboxapi.com/2/files/delete_v2'
        data = {"path": file_path}

        res = requests.post(uri, headers=self.get_headers(), data=json.dumps(data))
        if res.status_code != 200:
            print(f"\t[ERROR DROPBOX] Fallo al borrar archivo. Código: {res.status_code}")
            print(f"\t[DETALLE]: {res.text}")

    def create_folder(self, path):
        print(f"/create_folder_v2: {path}")
        uri = 'https://api.dropboxapi.com/2/files/create_folder_v2'
        data = {"path": path}

        res = requests.post(uri, headers=self.get_headers(), data=json.dumps(data))
        if res.status_code != 200:
            print(f"\t[ERROR DROPBOX] Fallo al crear carpeta. Código: {res.status_code}")
            print(f"\t[DETALLE]: {res.text}")

        # =========================================================
        # MEJORA EXTRA (20%): Generar enlace para compartir un archivo
        # =========================================================
        def create_shared_link(self, file_path):
            print(f"/create_shared_link_with_settings: {file_path}")
            uri = 'https://api.dropboxapi.com/2/sharing/create_shared_link_with_settings'
            data = {"path": file_path}

            res = requests.post(uri, headers=self.get_headers(), data=json.dumps(data))

            if res.status_code == 200:
                respuesta_json = json.loads(res.text)
                link = respuesta_json.get('url')
                print(f"\t¡Link compartido generado!: {link}")

                # --- AÑADIR AL PORTAPAPELES ---
                if self._root:
                    self._root.clipboard_clear()
                    self._root.clipboard_append(link)
                    self._root.update()  # Asegura que se copie al sistema operativo

                messagebox.showinfo("Enlace Compartido", f"Enlace generado y copiado al portapapeles:\n\n{link}")
            else:
                print(f"\t[ERROR DROPBOX] Fallo al generar enlace. Código: {res.status_code}")
                print(f"\t[DETALLE]: {res.text}")
                messagebox.showerror("Error", "No se pudo generar el enlace. Revisa la consola.")