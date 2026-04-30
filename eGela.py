# -*- coding: UTF-8 -*-
from tkinter import messagebox
import requests
import urllib
from urllib.parse import unquote
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
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    def _update_cookie(self, response):
        """Extrae y actualiza la cookie MoodleSessionegela si el servidor la envía."""
        set_cookie = response.headers.get('Set-Cookie', '')
        if set_cookie:
            match_cookie = re.search(r'(MoodleSessionegela=[^;]+)', set_cookie)
            if match_cookie:
                self._cookie = match_cookie.group(1)
                self.headers['Cookie'] = self._cookie

    def check_credentials(self, username, password, event=None):
        # --- FIX CRUCIAL DE TKINTER ---
        # Extraemos el texto real si las variables son objetos de Tkinter
        if hasattr(username, 'get'):
            username = username.get()
        if hasattr(password, 'get'):
            password = password.get()

        popup, progress_var, progress_bar = helper.progress("check_credentials", "Logging into eGela...")
        progress = 0
        progress_var.set(progress)
        progress_bar.update()

        print("##### 1. PETICION #####")
        url_login = "https://egela.ehu.eus/login/index.php"
        r1 = requests.get(url_login, headers=self.headers, allow_redirects=False)
        self._update_cookie(r1)

        soup = BeautifulSoup(r1.text, 'html.parser')
        logintoken = soup.find('input', {'name': 'logintoken'})['value']

        progress = 25
        progress_var.set(progress)
        progress_bar.update()
        time.sleep(1)

        print("\n##### 2. PETICION #####")
        payload = {'logintoken': logintoken, 'username': username, 'password': password}
        self.headers['Content-Type'] = 'application/x-www-form-urlencoded'

        r2 = requests.post(url_login, data=payload, headers=self.headers, allow_redirects=False)
        self._update_cookie(r2)
        del self.headers['Content-Type']

        # Fallback en caso de credenciales incorrectas (Moodle devuelve 200 en vez de 303)
        url_redirect_1 = r2.headers.get('Location') or "https://egela.ehu.eus/my/"

        progress = 50
        progress_var.set(progress)
        progress_bar.update()
        time.sleep(1)

        print("\n##### 3. PETICION #####")
        r3 = requests.get(url_redirect_1, headers=self.headers, allow_redirects=False)
        self._update_cookie(r3)

        url_redirect_2 = r3.headers.get('Location') or "https://egela.ehu.eus/my/"

        progress = 75
        progress_var.set(progress)
        progress_bar.update()
        time.sleep(1)

        print("\n##### 4. PETICION #####")
        r4 = requests.get(url_redirect_2, headers=self.headers, allow_redirects=True)

        progress = 100
        progress_var.set(progress)
        progress_bar.update()
        time.sleep(1)
        popup.destroy()

        # Comprobación de log in: Buscamos si el usuario tiene sesión iniciada
        COMPROBACION_DE_LOG_IN = "user/profile.php" in r4.text

        if COMPROBACION_DE_LOG_IN:
            print("\t[OK] Autenticación correcta en eGela.")
            self._login = 1
            # Buscamos la URL de Sistemas Web en el dashboard
            soup_main = BeautifulSoup(r4.text, 'html.parser')
            for enlace in soup_main.find_all('a', class_='coursename'):
                if 'Sistemas Web' in enlace.text:
                    self._curso = enlace.get('href')
                    break
            self._root.destroy()
        else:
            print("\t[ERROR] Fallo de credenciales.")
            messagebox.showinfo("Alert Message", "Login incorrect!")

    def get_pdf_refs(self):
        popup, progress_var, progress_bar = helper.progress("get_pdf_refs", "Downloading PDF list...")
        progress = 0
        progress_var.set(progress)
        progress_bar.update()

        print("\n##### PETICION (Página principal de la asignatura en eGela) #####")
        r_curso = requests.get(self._curso, headers=self.headers)

        print("\n##### Analisis del HTML... #####")
        soup = BeautifulSoup(r_curso.text, 'html.parser')

        # Buscamos todos los recursos tipo archivo
        recursos = soup.find_all('li', class_='modtype_resource')
        pdf_links = []

        for recurso in recursos:
            a_tag = recurso.find('a')
            if not a_tag: continue

            img = recurso.find('img', class_='activityicon')
            nombre_span = recurso.find('span', class_='instancename')

            if not nombre_span: continue
            nombre = nombre_span.text.replace('Archivo', '').strip()

            # Filtramos si es un PDF (por icono o nombre)
            if (img and 'pdf' in img.get('src', '').lower()) or '.pdf' in nombre.lower():
                url = a_tag.get('href')
                # Si no termina en .pdf, se lo añadimos para limpieza visual
                if not nombre.lower().endswith('.pdf'):
                    nombre += ".pdf"
                pdf_links.append({'pdf_name': nombre, 'pdf_link': url})

        progress_step = float(100.0 / max(len(pdf_links), 1))

        for pdf in pdf_links:
            self._refs.append(pdf)
            progress += progress_step
            progress_var.set(progress)
            progress_bar.update()
            time.sleep(0.1)

        popup.destroy()
        return self._refs

    def get_pdf(self, selection):
        print("\t##### Descargando PDF... #####")
        pdf_name = self._refs[selection]['pdf_name']
        url = self._refs[selection]['pdf_link']

        # Forzar descarga directa si es un enlace de tipo view.php
        if 'view.php' in url and 'redirect=1' not in url:
            url += '&redirect=1'

        # Hacemos la petición siguiendo posibles redirecciones manualmente para arrastrar la cookie
        r_pdf = requests.get(url, headers=self.headers, allow_redirects=False)
        while r_pdf.status_code in [301, 302, 303]:
            self._update_cookie(r_pdf)
            siguiente_url = r_pdf.headers.get('Location')
            r_pdf = requests.get(siguiente_url, headers=self.headers, allow_redirects=False)

        pdf_content = r_pdf.content
        return pdf_name, pdf_content