# Sistema de Gestión Integral de Jornada y Control Horario

Una solución web desarrollada a medida para la digitalización del control horario obligatorio en empresas del sector de la construcción. Diseñada específicamente para superar las barreras de adopción tecnológica y brecha digital en personal de obra, combinando flexibilidad operativa con el cumplimiento estricto de la normativa laboral.

---

## 💡 Origen del Proyecto y Valor de Negocio

Frente a la exigencia legal del fichaje digital y las limitaciones de las plataformas SaaS convencionales —demasiado rígidas para perfiles poco familiarizados con la tecnología—, este sistema fue concebido bajo el principio de **usabilidad de fricción cero**. 

Resuelve de forma nativa los descuidos habituales en los fichajes de obra (mediante edición retroactiva de días pasados), integra reglas de jornada no estándar (jornadas partidas según el día de la semana y periodos estivales) y ofrece un flujo de validación humana antes del archivo oficial de informes.

---

## 🛠️ Características Principales

### 👨‍💻 Experiencia del Empleado
* **Calendario Mensual Interactivo:** Vista completa del mes en curso con resaltado automático de la jornada actual.
* **Control Preventivo de Fichaje:**
  * Bloqueo estricto de días futuros.
  * Inhabilitación de franjas horarias que aún no se han alcanzado en el reloj del servidor.
  * Posibilidad de completar registros en días pasados para subsanar olvidos.
* **Asignación Diaria de Centros de Trabajo (Obras):** Los operarios de campo seleccionan mediante un desplegable la obra en la que han prestado servicio cada día.
* **Gestión Intuitiva de Incidencias:** Formulario ágil para registrar *Vacaciones*, *Baja médica* u *Otros motivos*, limpiando automáticamente las franjas horarias para un cómputo limpio.
* **Auditoría Previa y Despacho:**
  * **Visor PDF Integrado:** Generación y visualización previa del informe mensual directamente en el navegador antes de su envío.
  * **Envío a Administración:** Confirmación final por parte del usuario para enviar el PDF al buzón corporativo de secretaría.

---

### 🛡️ Panel de Administración (Secretaría)
* **Gestión de Plantilla (Usuarios):**
  * Listado global con filtros por tipo de trabajador (*Oficina*, *Obra*, *Media Jornada*).
  * Buscador rápido por nombre completo o DNI.
  * Alta, modificación de perfiles y asignación de roles.
* **Gestión de Centros de Trabajo (Obras) e Integridad Histórica:**
  * Alta de nuevas obras para la plantilla de campo.
  * **Mecanismo de Archivado:** Las obras finalizadas se archivan (ocultándolas del desplegable diario de los empleados) sin eliminar sus registros históricos en los informes de meses pasados.
* **Calendario de Festivos Centralizado:** Marcado de días no laborables (nacionales, autonómicos o locales) que se sincronizan con los calendarios de los trabajadores, impidiendo registros en dichas fechas.
* **Motor de Horarios Ad-Hoc:** Configuración de la jornada teórica adaptada a las características de la empresa:
  * *Invierno:* Horario partido (mañana y tarde) en días específicos (Lunes y Miércoles) y jornada diferenciada los Viernes.
  * *Verano:* Configuración de jornadas intensivas y rangos de aplicación.
* **Configuración del Servidor de Correo (SMTP):** Panel para definir las credenciales de envío y el buzón de recepción centralizado de informes.

---

## 🏗️ Stack Tecnológico

* **Backend:** Python / Flask
* **Frontend:** HTML5, CSS3, JavaScript Vanilla
* **Base de Datos:** SQL (vía SQLAlchemy ORM)
* **Generación y Visualización de Documentos:** ReportLab / PDF.js

---

## 🚀 Instalación y Configuración

1. **Clonar el repositorio:**
   ```bash
   git clone [https://github.com/laurasanzlobo/workforce-time-tracker.git](https://github.com/laurasanzlobo/workforce-time-tracker.git)
   cd workforce-time-tracker
   ```

2. **Crear y activar el entorno virtual:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variables de entorno:**
   Crear un archivo `.env` en la raíz del proyecto con las claves correspondientes:
   ```env
   FLASK_APP=run.py
   FLASK_ENV=development
   SECRET_KEY=tu_clave_secreta
   ```

5. **Inicializar la base de datos y arrancar el servidor:**
   Al ejecutar la aplicación por primera vez, el sistema creará automáticamente el archivo de base de datos (`instance/database.db`) y generará el usuario administrador inicial por defecto.

   ```bash
   python3 run.py
   ```

6. **Acceso Inicial al Sistema:**
   Una vez iniciada la aplicación, accede desde el navegador (`http://127.0.0.1:5000`) utilizando las credenciales iniciales de administración:
   * **Usuario:** `admin`
   * **Contraseña:** `admin`