# -*- coding: UTF-8 -*-
"""
Módulo eGela
Se encarga de la autenticación en Moodle y de extraer (hacer Web Scraping)
los enlaces a los archivos PDF de la asignatura "Sistemas Web".
"""

# Importaciones para UI y peticiones HTTP
from tkinter import messagebox
import requests
# BeautifulSoup es el estándar de la industria en Python para parsear y extraer datos de documentos HTML/XML
from bs4 import BeautifulSoup
import time
import helper
# Expresiones regulares (re) para buscar patrones específicos en texto plano (ej: cookies)
import re


class eGela:
    # --- Atributos de clase (Estado interno) ---
    _login = 0  # Bandera (flag) para saber si la sesión es válida
    _cookie = ""  # Guardará el valor de 'MoodleSessionegela'
    _curso = ""  # Guardará la URL directa al curso de Sistemas Web
    _refs = []  # Lista de diccionarios con el nombre y URL de cada PDF
    _root = None  # Referencia a la ventana de login de Tkinter para poder cerrarla

    def __init__(self, root):
        self._root = root
        # Disfrazamos nuestras peticiones (User-Agent spoofing) para que el firewall de Moodle/eGela
        # no bloquee nuestras peticiones pensando que somos un bot malicioso o un script de Python.
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    def _hacer_get_manual(self, url):
        """
        Sigue las redirecciones de forma manual para no perder la cookie MoodleSessionegela.
        Moodle a veces hace redirecciones (HTTP 303 See Other) y si usamos requests con
        allow_redirects=True, puede perder la cabecera Cookie por el camino.
        """
        # Hacemos la petición inicial bloqueando las redirecciones automáticas de 'requests'
        r = requests.get(url, headers=self.headers, allow_redirects=False)

        # Inspeccionamos si el servidor nos manda una nueva cookie en la cabecera de respuesta
        set_cookie = r.headers.get('Set-Cookie', '')
        if set_cookie:
            # Usamos Regex para atrapar solo la cadena de la cookie (ej: MoodleSessionegela=a1b2c3d4)
            match_cookie = re.search(r'(MoodleSessionegela=[^;]+)', set_cookie)
            if match_cookie:
                self._cookie = match_cookie.group(1)
                # Actualizamos nuestras cabeceras para las siguientes peticiones
                self.headers['Cookie'] = self._cookie

        # Bucle While: Seguimos el rastro de migas de pan (redirecciones) HTTP 3xx
        while r.status_code in [301, 302, 303, 307, 308]:
            siguiente_url = r.headers.get('Location')
            # Las URLs de redirección a veces son relativas (ej: /mod/resource), las convertimos a absolutas
            if not siguiente_url.startswith('http'):
                siguiente_url = "https://egela.ehu.eus" + siguiente_url

            # Hacemos la siguiente petición del rastro manual
            r = requests.get(siguiente_url, headers=self.headers, allow_redirects=False)

            # Volvemos a comprobar si Moodle nos refresca la cookie
            set_cookie = r.headers.get('Set-Cookie', '')
            if set_cookie:
                match_cookie = re.search(r'(MoodleSessionegela=[^;]+)', set_cookie)
                if match_cookie:
                    self._cookie = match_cookie.group(1)
                    self.headers['Cookie'] = self._cookie

        # Devolvemos el objeto Response (r) final, el que devuelve el HTTP 200 OK
        return r

    def check_credentials(self, username, password, event=None):
        """Implementa el flujo de autenticación calcado."""

        # --- FIX DE TKINTER ---
        # A veces Tkinter pasa el objeto Entry en lugar de la string, nos aseguramos de extraer el texto
        if hasattr(username, 'get'):
            username = username.get()
        if hasattr(password, 'get'):
            password = password.get()

        # Invocamos la barra de progreso
        popup, progress_var, progress_bar = helper.progress("check_credentials", "Conectando con eGela...")
        progress = 0
        progress_var.set(progress)
        progress_bar.update()

        # ==========================================
        # PASO 1: GET a la página principal de login
        # Objetivo: Obtener el logintoken oculto en el formulario HTML y la primera cookie
        # ==========================================
        print("\n[AUTH eGela] ##### 1. PETICION GET #####")
        url_login = "https://egela.ehu.eus/login/index.php"
        r1 = requests.get(url_login, headers=self.headers, allow_redirects=False)

        # Capturamos la cookie inicial
        set_cookie = r1.headers.get('Set-Cookie', '')
        if set_cookie:
            match = re.search(r'(MoodleSessionegela=[^;]+)', set_cookie)
            if match:
                self._cookie = match.group(1)
                self.headers['Cookie'] = self._cookie

        # Parseamos el DOM para buscar la etiqueta <input name="logintoken" value="...">
        soup1 = BeautifulSoup(r1.text, 'html.parser')
        logintoken_input = soup1.find('input', {'name': 'logintoken'})
        # Extraemos el string del token. Es un mecanismo CSRF (Cross-Site Request Forgery) de seguridad de Moodle.
        logintoken = logintoken_input['value'] if logintoken_input else ""

        progress = 25
        progress_var.set(progress)
        progress_bar.update()
        time.sleep(1)

        # ==========================================
        # PASO 2: POST enviando credenciales
        # Objetivo: Enviar el formulario emulando un navegador
        # ==========================================
        print("\n[AUTH eGela] ##### 2. PETICION POST #####")
        # El payload debe coincidir exactamente con los nombres de los inputs del formulario de Moodle
        payload_dict = {'logintoken': logintoken, 'username': username, 'password': password}
        # Esta cabecera le dice al servidor que los datos viajan codificados como si fueran de un formulario HTML clásico
        self.headers['Content-Type'] = 'application/x-www-form-urlencoded'

        r2 = requests.post(url_login, data=payload_dict, headers=self.headers, allow_redirects=False)

        # Moodle suele regenerar la cookie de sesión tras un login exitoso por seguridad (evitar fijación de sesión)
        set_cookie = r2.headers.get('Set-Cookie', '')
        if set_cookie:
            match = re.search(r'(MoodleSessionegela=[^;]+)', set_cookie)
            if match:
                self._cookie = match.group(1)
                self.headers['Cookie'] = self._cookie

        # Limpiamos el Content-Type para futuras peticiones GET y guardamos la URL de redirección
        del self.headers['Content-Type']
        url_redirect_1 = r2.headers.get('Location', '')

        progress = 50
        progress_var.set(progress)
        progress_bar.update()
        time.sleep(1)

        # ==========================================
        # PASO 3: GET validando la sesión (testsession)
        # ==========================================
        print("\n[AUTH eGela] ##### 3. PETICION GET #####")
        # Moodle nos pasa por un script intermedio para validar la nueva cookie
        r3 = requests.get(url_redirect_1, headers=self.headers, allow_redirects=False)
        url_redirect_2 = r3.headers.get('Location', '')

        progress = 75
        progress_var.set(progress)
        progress_bar.update()
        time.sleep(1)

        # ==========================================
        # PASO 4: GET a la redirección final (Panel Principal)
        # ==========================================
        print("\n[AUTH eGela] ##### 4. PETICION GET #####")
        # Llegamos al "Dashboard" o "Área personal" del estudiante
        r4 = requests.get(url_redirect_2, headers=self.headers, allow_redirects=False)

        progress = 100
        progress_var.set(progress)
        progress_bar.update()
        time.sleep(1)
        popup.destroy()

        # ==========================================
        # PASO 5: VALIDACIÓN DE LOGIN
        # Objetivo: Comprobar si realmente estamos logueados y buscar el curso
        # ==========================================
        soup_perfil = BeautifulSoup(r4.text, 'html.parser')
        url_perfil = None
        # Si existe un enlace que apunte a 'user/profile.php', significa que hemos cargado una vista de usuario logueado
        for enlace in soup_perfil.find_all('a', href=True):
            if 'user/profile.php' in enlace['href']:
                url_perfil = enlace['href']
                break

        if url_perfil:
            print("\t[ÉXITO] Autenticación correcta en eGela.")

            # Buscamos la asignatura "Sistemas Web" rastreando los enlaces con la clase CSS 'coursename'
            soup_main = BeautifulSoup(r4.text, 'html.parser')
            for enlace in soup_main.find_all('a', class_='coursename'):
                if 'Sistemas Web' in enlace.text:
                    # Guardamos la URL base de este curso en concreto para usarla en el scraping
                    self._curso = enlace.get('href')
                    print(f"\tAsignatura encontrada: {self._curso}")
                    break

            if self._curso:
                # Login 100% exitoso. Marcamos el flag y destruimos la ventana de login para avanzar de fase en actividad_4.py
                self._login = 1
                self._root.destroy()
            else:
                print("\t[ERROR] Login correcto, pero no se encontró la asignatura.")
                messagebox.showerror("Error", "Login correcto pero no se encontró la asignatura 'Sistemas Web'.")
                self._root.destroy()  # Cerramos para abortar el programa limpiamente
        else:
            print("\t[ERROR] Fallo de credenciales en Moodle.")
            # Si Moodle nos devolvió de nuevo al formulario de login, es que las credenciales están mal
            messagebox.showinfo("Error de inicio de sesión", "Usuario o contraseña incorrectos.")

    def get_pdf_refs(self):
        """Navega por las pestañas del curso y extrae los enlaces de todos los archivos PDF."""
        popup, progress_var, progress_bar = helper.progress("get_pdf_refs", "Descargando lista de PDFs...")
        progress = 0
        progress_var.set(progress)
        progress_bar.update()

        print("\n[SCRAPING] ##### Petición a la página principal de la asignatura #####")
        # Usamos nuestro método manual para navegar al curso manteniendo la sesión viva
        r_curso = self._hacer_get_manual(self._curso)

        soup_asignatura = BeautifulSoup(r_curso.text, 'html.parser')

        # 1. Analizar la estructura Moodle de tipo 'Onetopic' (Pestañas horizontales)
        print("[SCRAPING] ##### Analizando estructura de pestañas... #####")
        temas = []
        # Buscamos el contenedor <ul> de las pestañas
        ul_tabs = soup_asignatura.find('ul', class_='format_onetopic-tabs')
        if ul_tabs:
            # Iteramos sobre cada <li> (cada pestaña) y guardamos su href
            for li in ul_tabs.find_all('li', class_='nav-item'):
                a_tag = li.find('a', class_='nav-link')
                if a_tag and a_tag.get('href'):
                    temas.append(a_tag.get('href'))
        else:
            # Plan B: Si la asignatura no usa pestañas (formato temas en scroll), la página principal es todo lo que hay
            temas.append(self._curso)

        pdf_links = []

        # 2. Recorrer cada tema (pestaña) y extraer los enlaces a los recursos
        for i, url_tema in enumerate(temas):
            print(f"\tExplorando tema {i + 1}/{len(temas)}...")
            r_tema = self._hacer_get_manual(url_tema)
            soup_tema = BeautifulSoup(r_tema.text, 'html.parser')

            # En Moodle, los archivos se listan bajo la clase 'modtype_resource'
            recursos = soup_tema.find_all('li', class_='modtype_resource')

            for recurso in recursos:
                # Buscamos el link principal <a> dentro del bloque del recurso
                a_tag = recurso.find('a')
                if not a_tag: continue

                # Buscamos el icono para filtrar por tipo de archivo visualmente
                img = recurso.find('img', class_='activityicon')
                # Extraemos el texto visible para el usuario
                nombre_span = recurso.find('span', class_='instancename')
                if not nombre_span: continue

                # Limpieza de strings: Moodle suele añadir la palabra oculto "Archivo" al final para lectores de pantalla
                nombre = nombre_span.text.replace('Archivo', '').strip()

                # Filtro doble: Si el icono dice que es PDF, o el nombre contiene ".pdf"
                if (img and 'pdf' in img.get('src', '').lower()) or '.pdf' in nombre.lower():
                    url_pdf = a_tag.get('href')

                    # Añadimos la extensión al nombre si el profesor se olvidó de ponerla en eGela
                    if not nombre.lower().endswith('.pdf'):
                        nombre += ".pdf"

                    # Prevención de duplicados: A veces eGela lista el mismo recurso en varias vistas
                    if not any(pdf['pdf_link'] == url_pdf for pdf in pdf_links):
                        pdf_links.append({'pdf_name': nombre, 'pdf_link': url_pdf})

        print(f"\n[SCRAPING] Total de PDFs encontrados: {len(pdf_links)}")

        progress_step = float(100.0 / max(len(pdf_links), 1))

        # Cargamos nuestro atributo de clase final (_refs) y actualizamos barra de progreso
        for pdf in pdf_links:
            self._refs.append(pdf)
            progress += progress_step
            progress_var.set(progress)
            progress_bar.update()
            time.sleep(0.05)

        popup.destroy()
        # Devolvemos la lista de diccionarios que espera el módulo actividad_4.py para pintar la listbox1
        return self._refs

    def get_pdf(self, selection):
        """Descarga el contenido binario de un PDF específico en la memoria RAM."""
        # 'selection' es el índice de la tupla devuelta por curselection() de Tkinter
        pdf_name = self._refs[selection]['pdf_name']
        url = self._refs[selection]['pdf_link']

        print(f"\n[DESCARGA] ##### Obteniendo PDF: {pdf_name} #####")

        # TRUCO: Las URLs de eGela 'view.php?id=XXXX' a veces muestran una pantalla intermedia.
        # Añadir '&redirect=1' le fuerza a Moodle a devolvernos directamente el Content-Type application/pdf
        if 'view.php' in url and 'redirect=1' not in url:
            url += '&redirect=1'

        # Utilizamos nuestra función manual porque un error de redirección aquí corrompería el archivo descargado
        r_pdf = self._hacer_get_manual(url)

        # r.content devuelve los bytes binarios puros del archivo. No lo guardamos a disco físico,
        # lo retenemos en RAM para enviarlo directamente a Dropbox.
        pdf_content = r_pdf.content
        return pdf_name, pdf_content