# Comprehensive Workforce & Time Tracking System

A custom-built web application designed for the mandatory digitalization of time tracking in construction companies. Specifically engineered to overcome technology adoption barriers and the digital divide among field staff, combining operational flexibility with strict compliance with labor regulations.

---

## 💡 Project Origin & Business Value

In response to legal requirements for digital time recording and the limitations of standard SaaS platforms —often too rigid for workers unfamiliar with complex tech—, this system was developed under the principle of **zero-friction usability**.

It natively solves common field reporting issues (allowing retroactive entry for missed days), integrates non-standard work schedules (split shifts depending on the day of the week and summer intensive hours), and features a human-in-the-loop validation process before final document archiving.

---

## 🛠️ Key Features

### 👨‍💻 Employee Experience
* **Interactive Monthly Calendar:** Full view of the current month with automated visual highlight on today's date.
* **Preventive Punch-In Control:**
  * Strict restriction on future dates.
  * Time slots disabled until reached on the server clock.
  * Option to complete entries for past days to fix accidental omissions.
* **Daily Job Site Assignment:** Field workers select their active construction site for each day using a simple dropdown menu.
* **Intuitive Absence Management:** Quick selection form to record *Vacation*, *Sick Leave*, or *Other Reasons*, automatically clearing time fields for clean hour calculation.
* **Audit & Dispatch Workflow:**
  * **Integrated PDF Viewer:** In-browser preview of the generated monthly report before submitting.
  * **Direct Email Dispatch:** Final confirmation trigger to dispatch the verified report directly to the administrative office inbox.

---

## 🛡️ Administrative Control Panel (Office / Management)
* **Workforce Management:**
  * Global employee list filtered by employment type (*Office*, *Site/Field*, *Part-Time*).
  * Quick search bar by full name or National ID.
  * User onboarding, profile editing, and role assignments.
* **Site Management & Historical Data Integrity:**
  * Creation of new job sites for field worker selection.
  * **Archiving System:** Completed sites are archived (hidden from workers' daily dropdowns) while preserving past historical logs on generated reports.
* **Centralized Holiday Calendar:** Configuration of non-working days (national, regional, or local holidays) synchronized across worker calendars to prevent accidental logs.
* **Ad-Hoc Schedule Engine:** Tailored theoretical schedule definitions matching corporate policies:
  * *Winter Schedule:* Split shifts (morning and afternoon) on specific weekdays (e.g., Mondays & Wednesdays) and distinct hours on Fridays.
  * *Summer Schedule:* Intensive morning shifts and customizable seasonal date ranges.
* **SMTP Mail Server Configuration:** Control panel to manage outgoing mail credentials and central destination inbox settings.

---

## 🏗️ Tech Stack

* **Backend:** Python / Flask
* **Frontend:** HTML5, CSS3, Vanilla JavaScript
* **Database:** SQL (via SQLAlchemy ORM)
* **Document Rendering & Preview:** ReportLab / PDF.js

---

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/laurasanzlobo/workforce-time-tracker.git](https://github.com/laurasanzlobo/workforce-time-tracker.git)
   cd workforce-time-tracker
   ```

2. **Create and activate the virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   Create a `.env` file in the root directory with the appropriate configuration:
   ```env
   FLASK_APP=run.py
   FLASK_ENV=development
   SECRET_KEY=your_secret_key
   ```

5. **Initialize the database and start the server:**
   Upon first execution, the system will automatically create the local database file (`instance/database.db`) and seed the default administrator account.

   ```bash
   python3 run.py
   ```

6. **Initial System Access:**
   Once running, access the web interface via browser (`http://127.0.0.1:5000`) using the default administrative credentials:
   * **Username:** `admin`
   * **Password:** `admin`