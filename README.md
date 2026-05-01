

```markdown
# 🏥 ClinixTech: Enterprise Clinic Management & Triage System

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-MVC-lightgrey.svg)
![Oracle](https://img.shields.io/badge/Oracle-Database-red.svg)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-orange.svg)
![Status](https://img.shields.io/badge/Deployment-Active-success.svg)

<p align="center">
  <!-- IMPORTANT: Replace 'images/hero_image.png' with the actual path to your image in the repo -->
  <img src="images/hero_image.png" alt="ClinixTech Enterprise Architecture" width="850"/>
</p>

## 📖 Executive Summary
**ClinixTech** is an enterprise-grade Clinic Management and Triage System developed to solve critical administrative paralysis in modern healthcare facilities. Moving beyond traditional First-Come-First-Serve (FCFS) models, ClinixTech utilizes advanced Data Structures and Algorithms (DSA) to mathematically triage patients, while relying on a highly concurrent Enterprise Oracle Database to ensure absolute data integrity.

This project was developed as a Complex Engineering Problem (CEP) fulfilling requirements for both **Software Construction and Development (SE-312)** and **Database Management Systems (SE-204)**.

### 🌍 UN Sustainable Development Goals (SDG) Alignment
* **SDG 3 (Good Health & Well-being):** Eliminates medical wait-time fatalities via Min-Heap algorithmic priority triaging.
* **SDG 12 (Responsible Consumption):** Mandates a 100% paperless clinical environment through dynamic server-side PDF generation for records and prescriptions.

---

## 💻 Software Construction & Development (SCD) Architecture
ClinixTech abandons standard procedural coding in favor of a strict **Monolithic Model-View-Controller (MVC)** design pattern, optimized for cloud deployment.

* **Controller Layer (Flask):** The central routing engine. Intercepts WSGI requests and executes core clinical algorithms.
* **Algorithmic Triage (Min-Heap):** Utilizes Python's `heapq` to dynamically sort the Doctor's waiting list based on urgency (Emergency > Urgent > Normal), running in $O(N \log N)$ time.
* **Prescription Memory (LIFO Stack):** Doctors interact with an in-memory LIFO Stack to issue medications, allowing instant "Undo" (Pop) functionality before committing to the database.
* **Security & Authentication:** Cryptographic password hashing implemented via `werkzeug.security`. Route protection enforced via strict `@login_required` decorators mapped to specific Role-Based Access Controls (RBAC).
* **Document Generation:** Integrates the `ReportLab` engine to dynamically compile patient histories and prescriptions into secure, downloadable PDF byte-streams.

---

## 🗄️ Database Management Systems (DBMS) Architecture
The data layer relies on an **Enterprise Oracle Database** acting through the ANSI/SPARC Three-Schema Architecture, replacing standard lightweight SQLite setups.

* **Schema Normalization (BCNF):** The database consists of 10 rigidly defined tables (e.g., `Patient`, `Doctor`, `Appointment`, `Vitals`, `Payment`). The conceptual schema is fully normalized to Boyce-Codd Normal Form (BCNF) to eliminate insertion, deletion, and update anomalies.
* **Multi-Version Concurrency Control (MVCC):** Leverages Oracle's native Undo Segments and Redo Logs to ensure that Admin auditing transactions do not lock rows required by Doctors updating live patient queues.
* **ACID Transaction Management:** Multi-step insertions (e.g., booking an appointment while generating a billing invoice) are wrapped in atomic `db.session.commit()` blocks. Any `IntegrityError` triggers an immediate rollback to prevent orphan records.
* **Advanced Analytical SQL:** Capable of running complex nested subqueries, aggregations (`SUM`, `COUNT`), and explicit `LEFT/INNER JOINS` to generate Admin audit logs and financial metrics.
* **B-Tree Query Optimization:** Strategic Composite B-Tree Indexes are deployed on high-traffic columns (`doctor_id`, `status`, `priority`) to shift execution plans from costly *Full Table Scans* to *Index Range Scans*.

---

## ⚙️ Local Setup & Installation Guide

Follow these steps to configure the ClinixTech environment locally.

### Prerequisites
1. **Python 3.10+** installed on your system.
2. **Oracle Database** (or Oracle Cloud ATP) configured and running.
3. Git installed.

### Step 1: Clone the Repository
```bash
git clone [https://github.com/mubashir349/Clinixtech.git](https://github.com/mubashir349/Clinixtech.git)
cd Clinixtech
```

### Step 2: Create a Virtual Environment
It is highly recommended to isolate the project dependencies.
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### Step 3: Install Dependencies
Install all required libraries via the requirements manifest.
```bash
pip install -r requirements.txt
```
*(Key dependencies include: `Flask`, `Flask-SQLAlchemy`, `oracledb` (Thin Mode), `ReportLab`, `Werkzeug`)*

### Step 4: Environment Variables (`.env`)
Create a `.env` file in the root directory to securely store your Oracle credentials and Flask secrets. **Never commit this file to version control.**
```env
# Flask Configuration
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your_super_secret_key_here

# Oracle Database Configuration (Thin Mode)
ORACLE_USER=your_oracle_username
ORACLE_PASSWORD=your_oracle_password
ORACLE_HOST=your_host_address (e.g., localhost or cloud IP)
ORACLE_PORT=1521
ORACLE_SERVICE_NAME=your_service_name (e.g., XEPDB1 or ORCL)
```

### Step 5: Initialize and Run
Start the WSGI server:
```bash
python app.py
```
Access the application in your browser at `http://127.0.0.1:5000/`.

---

## 🧪 DBMS Evaluation & Optimization Demo
For SE-204 evaluation purposes, this repository includes an evaluation script (`Clinixtech.sql`) capable of generating a massive dummy dataset to prove Oracle Query Optimization.

1. Open Oracle SQL Developer.
2. Run the **Phase 1 PL/SQL Block** found in `Clinixtech.sql` to instantly seed **15,000+ appointments and payments**.
3. Run an `EXPLAIN PLAN` on a search query to view the unoptimized **TABLE ACCESS FULL** cost.
4. Execute the B-Tree Index creation scripts.
5. Rerun the `EXPLAIN PLAN` to demonstrate the optimized **INDEX RANGE SCAN** cost reduction.

---

## 🚀 Deployment Strategy
ClinixTech utilizes a dual-deployment infrastructure:
* **Application Hosting:** Containerized and deployed via **Render Cloud PaaS**, binding the Flask WSGI server to production environments.
* **Documentation:** Static system documentation and architectural outlines are hosted via **GitHub Pages**.

🔗 **Live Application:** [clinixtech.onrender.com](https://clinixtech.onrender.com)
🔗 **Documentation:** [mubashir349.github.io/Clinixtech](https://mubashir349.github.io/Clinixtech/)

---

## 👨‍💻 Development Team
Developed by:
* **Raazia Imran Reshamwala** 
* **Mubashir** 
* **Rameen** 
* **Eshaal** 

---
*ClinixTech*
```
