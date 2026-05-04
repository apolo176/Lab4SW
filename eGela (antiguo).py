# -*- coding: UTF-8 -*-
"""
Módulo eGela
Se encarga de la autenticación en Moodle y de extraer (hacer Web Scraping)
los enlaces a los archivos PDF de la asignatura "Sistemas Web".
"""

from tkinter import messagebox
import requests
from bs4 import BeautifulSoup
import time
import helper
import re


class eGela:
    _login = 0
    _cookie = ""
    _curso = ""
    _refs = []
    _root = None

    def __init__(self, root):
        self._root = root
        # Disfrazamos nuestras peticiones para que eGela piense que somos un navegador real
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    def _update_cookie(self, response):
        """
        Extrae y actualiza la cookie 'MoodleSessionegela' de la cabecera Set-Cookie.
        Esencial para mantener la sesión viva mientras saltamos entre páginas,
        ya que el enunciado no permite usar requests.Session().
        """
        set_cookie = response.headers.get('Set-Cookie', '')
        if set_cookie:
            match_cookie = re.search(r'(MoodleSessionegela=[^;]+)', set_cookie)
            if match_cookie:
                self._cookie = match_cookie.group(1)
                self.headers['Cookie'] = self._cookie

    def check_credentials(self, username, password, event=None):
        """Implementa el flujo de autenticación de 4 pasos de Moodle."""

        # --- FIX DE TKINTER ---
        # Si recibimos el objeto del Entry visual, extraemos su texto con .get()
        if hasattr(username, 'get'):
            username = username.get()
        if hasattr(password, 'get'):
            password = password.get()

        popup, progress_var, progress_bar = helper.progress("check_credentials", "Conectando con eGela...")
        progress = 0
        progress_var.set(progress)
        progress_bar.update()

        # ==========================================
        # PASO 1: GET a la página principal de login
        # Objetivo: Obtener el 'logintoken' oculto y la cookie inicial
        # ==========================================
        print("\n[AUTH eGela] ##### 1. PETICION GET #####")
        url_login = "https://egela.ehu.eus/login/index.php"
        r1 = requests.get(url_login, headers=self.headers, allow_redirects=False)
        self._update_cookie(r1)

        soup = BeautifulSoup(r1.text, 'html.parser')
        logintoken = soup.find('input', {'name': 'logintoken'})['value']
        print(f"\tToken capturado: {logintoken[:15]}...")

        progress = 25
        progress_var.set(progress)
        progress_bar.update()
        time.sleep(1)

        # ==========================================
        # PASO 2: POST enviando credenciales
        # Objetivo: Enviar usuario, contraseña y token. Moodle nos devolverá un 303.
        # ==========================================
        print("\n[AUTH eGela] ##### 2. PETICION POST #####")
        payload = {'logintoken': logintoken, 'username': username, 'password': password}
        self.headers['Content-Type'] = 'application/x-www-form-urlencoded'

        r2 = requests.post(url_login, data=payload, headers=self.headers, allow_redirects=False)
        self._update_cookie(r2)
        del self.headers['Content-Type']  # Limpiamos la cabecera para las siguientes peticiones GET

        # Capturamos la primera redirección. Si Moodle devuelve 200 (error de credenciales), forzamos ir a /my/
        url_redirect_1 = r2.headers.get('Location') or "https://egela.ehu.eus/my/"
        print(f"\tRedirección a: {url_redirect_1}")

        progress = 50
        progress_var.set(progress)
        progress_bar.update()
        time.sleep(1)

        # ==========================================
        # PASO 3: GET validando la sesión (testsession)
        # ==========================================
        print("\n[AUTH eGela] ##### 3. PETICION GET #####")
        r3 = requests.get(url_redirect_1, headers=self.headers, allow_redirects=False)
        self._update_cookie(r3)

        progress = 75
        progress_var.set(progress)
        progress_bar.update()
        time.sleep(1)

        # ==========================================
        # PASO 4: GET a la redirección final (Panel Principal)
        # FIX: Forzamos la petición DIRECTAMENTE al panel principal (/my/).
        # Esto evita quedarnos atrapados en páginas intermedias si hay redirecciones raras.
        # ==========================================
        print("\n[AUTH eGela] ##### 4. PETICION GET (Dashboard) #####")
        r4 = requests.get("https://egela.ehu.eus/my/", headers=self.headers, allow_redirects=True)
        self._update_cookie(r4)

        progress = 100
        progress_var.set(progress)
        progress_bar.update()
        time.sleep(1)
        popup.destroy()

        # Validación final
        COMPROBACION_DE_LOG_IN = "user/profile.php" in r4.text

        if COMPROBACION_DE_LOG_IN:
            print("\t[ÉXITO] Autenticación correcta en eGela.")

            # Buscamos dinámicamente la URL del curso de Sistemas Web
            soup_main = BeautifulSoup(r4.text, 'html.parser')
            # Flexibilizamos la búsqueda para evitar fallos si cambia el HTML de Moodle
            for enlace in soup_main.find_all('a'):
                if enlace.text and 'Sistemas Web' in enlace.text and enlace.get(
                        'href') and 'course/view.php' in enlace.get('href'):
                    self._curso = enlace.get('href')
                    print(f"\tAsignatura encontrada: {self._curso}")
                    break

            # Seguro de vida: comprobamos si realmente la encontró
            if self._curso:
                self._login = 1
                self._root.destroy()
            else:
                print("\t[ERROR] No se encontró el curso 'Sistemas Web' en tu panel.")
                messagebox.showerror("Error", "Login correcto, pero no se encontró la asignatura 'Sistemas Web'.")
        else:
            print("\t[ERROR] Fallo de credenciales en Moodle.")
            messagebox.showinfo("Error de inicio de sesión", "Usuario o contraseña incorrectos.")

    def get_pdf_refs(self):
        """Navega por las pestañas del curso y extrae los enlaces de todos los archivos PDF."""
        popup, progress_var, progress_bar = helper.progress("get_pdf_refs", "Descargando lista de PDFs...")
        progress = 0
        progress_var.set(progress)
        progress_bar.update()

        print("\n[SCRAPING] ##### Petición a la página principal de la asignatura #####")
        r_curso = requests.get(self._curso, headers=self.headers)
        self._update_cookie(r_curso)

        soup_asignatura = BeautifulSoup(r_curso.text, 'html.parser')

        # 1. Mapear la estructura: Obtener los enlaces de todas las pestañas (temas) del curso
        print("[SCRAPING] ##### Analizando estructura de pestañas... #####")
        temas = []
        ul_tabs = soup_asignatura.find('ul', class_='format_onetopic-tabs')
        if ul_tabs:
            for li in ul_tabs.find_all('li', class_='nav-item'):
                a_tag = li.find('a', class_='nav-link')
                if a_tag and a_tag.get('href'):
                    temas.append(a_tag.get('href'))
        else:
            # Plan B: Si la vista Onetopic no está activa, analizamos solo la página principal
            temas.append(self._curso)

        pdf_links = []

        # 2. Exploración profunda: Recorrer cada tema y extraer los enlaces a recursos
        for i, url_tema in enumerate(temas):
            print(f"\tExplorando tema {i + 1}/{len(temas)}...")
            r_tema = requests.get(url_tema, headers=self.headers)
            self._update_cookie(r_tema)
            soup_tema = BeautifulSoup(r_tema.text, 'html.parser')

            # Buscamos elementos de la lista que sean "Archivos"
            recursos = soup_tema.find_all('li', class_='modtype_resource')

            for recurso in recursos:
                a_tag = recurso.find('a')
                if not a_tag: continue

                img = recurso.find('img', class_='activityicon')
                nombre_span = recurso.find('span', class_='instancename')

                if not nombre_span: continue

                # Limpiamos el texto visual ("Archivo" suele salir pegado al nombre)
                nombre = nombre_span.text.replace('Archivo', '').strip()

                # Discriminador: Confirmamos que es un PDF por el nombre o por el ícono de Moodle
                if (img and 'pdf' in img.get('src', '').lower()) or '.pdf' in nombre.lower():
                    url_pdf = a_tag.get('href')

                    # Añadimos la extensión al nombre si no la tiene para que se vea bien en Tkinter
                    if not nombre.lower().endswith('.pdf'):
                        nombre += ".pdf"

                    # Prevención de duplicados (por si una sección principal enlaza a la misma URL)
                    if not any(pdf['pdf_link'] == url_pdf for pdf in pdf_links):
                        pdf_links.append({'pdf_name': nombre, 'pdf_link': url_pdf})

        print(f"\n[SCRAPING] Total de PDFs encontrados: {len(pdf_links)}")

        # 3. Actualizar la barra de progreso de la interfaz simulando la carga
        progress_step = float(100.0 / max(len(pdf_links), 1))

        for pdf in pdf_links:
            self._refs.append(pdf)
            progress += progress_step
            progress_var.set(progress)
            progress_bar.update()
            # Espera corta para que el usuario vea avanzar la barra
            time.sleep(0.05)

        popup.destroy()
        return self._refs

    def get_pdf(self, selection):
        """Descarga el contenido binario de un PDF específico en la memoria RAM."""
        pdf_name = self._refs[selection]['pdf_name']
        url = self._refs[selection]['pdf_link']

        print(f"\n[DESCARGA] ##### Obteniendo PDF: {pdf_name} #####")

        # FIX: Forzar descarga directa. Si es un visor web (view.php), añadimos redirect=1
        if 'view.php' in url and 'redirect=1' not in url:
            url += '&redirect=1'

        # Petición inicial siguiendo posibles redirecciones manualmente para arrastrar la cookie
        r_pdf = requests.get(url, headers=self.headers, allow_redirects=False)

        # Bucle para perseguir redirecciones (301, 302, 303) arrastrando la sesión
        while r_pdf.status_code in [301, 302, 303]:
            self._update_cookie(r_pdf)
            siguiente_url = r_pdf.headers.get('Location')
            r_pdf = requests.get(siguiente_url, headers=self.headers, allow_redirects=False)

        # r_pdf.content contiene el archivo crudo en bytes, listo para subirse a Dropbox
        pdf_content = r_pdf.content
        return pdf_name, pdf_content