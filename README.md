# eGela2Dropbox - Actividad 4: API de Dropbox con OAuth

**Por:** Alex Isasi, Liviu Deleanu y Eder Torres

---

## 📖 Descripción
La aplicación eGela2Dropbox permite subir de manera selectiva los ficheros PDF del aula virtual de la asignatura Sistemas Web en eGela, directamente a un directorio de Dropbox. Está desarrollada en Python e incluye una interfaz gráfica de usuario construida con Tkinter.

## ✨ Funcionalidades Principales
*   **Conexión eGela:** Permite el inicio de sesión en Moodle y el mantenimiento de la sesión.
*   **Web Scraping:** Consigue el listado de todos los recursos PDF del aula virtual. Permite la descarga en memoria de los PDFs seleccionados.
*   **OAuth 2.0:** Implementa la delegación de autenticación y autorización en Dropbox usando un servidor local de captura de tokens.
*   **Integración con API de Dropbox:**
    *   Listado del contenido de las carpetas.
    *   Subida de los ficheros extraídos a Dropbox.
    *   Eliminación de ficheros y carpetas.
    *   Creación de nuevos directorios.
*   🌟 **Mejora Extra:** Se ha añadido una funcionalidad adicional que permite generar un enlace público de lectura para compartir un archivo de Dropbox. Este enlace se copia automáticamente al portapapeles del usuario.

## 📂 Estructura del Proyecto
*   `actividad_4.py`: Script principal que contiene la lógica de interacción de los botones y lanza la interfaz gráfica.
*   `eGela.py`: Módulo responsable de realizar las peticiones web a Moodle, gestionar la cookie de sesión y parsear el HTML con BeautifulSoup.
*   `Dropbox.py`: Módulo que maneja el socket local para el flujo OAuth 2.0 y realiza las peticiones REST a la API de Dropbox.
*   `helper.py`: Funciones auxiliares para controlar elementos visuales como la barra de progreso y el listado de archivos.
*   `requirements.txt`: Fichero con las librerías de terceros necesarias.

## 🚀 Instalación y Uso

Para evitar conflictos con otras librerías de tu sistema, se recomienda levantar el entorno usando un entorno virtual `venv`:
```bash
# 1. Crear el entorno virtual
python -m venv venv

# 2. Activar el entorno virtual
source .venv/bin/activate # Usa .venv/Scripts/activate si estás en Windows

# 3. Instalar las dependencias
pip install -r requirements.txt

# 4. Iniciar la aplicación
python actividad_4.py