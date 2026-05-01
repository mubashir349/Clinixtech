````markdown
# 🏥 ClinixTech: Enterprise Clinic Management & Triage System

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-MVC-lightgrey.svg)
![Oracle](https://img.shields.io/badge/Oracle-Database-red.svg)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-orange.svg)
![Status](https://img.shields.io/badge/Deployment-Active-success.svg)

<p align="center">
  <img src="images/hero_image.png" alt="ClinixTech Enterprise Architecture" width="850"/>
</p>

---

## 📖 Executive Summary

**ClinixTech** is an enterprise-grade Clinic Management and Triage System designed to eliminate administrative inefficiencies in healthcare facilities. Instead of relying on traditional First-Come-First-Serve (FCFS) models, the system applies **Data Structures and Algorithms (DSA)** to prioritize patients based on medical urgency, ensuring critical cases receive immediate attention.

The system is backed by an **Enterprise Oracle Database**, ensuring strong consistency, concurrency control, and ACID-compliant transactions.

This project was developed as a **Complex Engineering Problem (CEP)** for:

- Software Construction and Development (SE-312)  
- Database Management Systems (SE-204)

---

## 🌍 UN Sustainable Development Goals (SDG) Alignment

- **SDG 3 – Good Health & Well-being**  
  Reduces patient wait-time risks using algorithmic priority-based triage.

- **SDG 12 – Responsible Consumption & Production**  
  Ensures a paperless clinical workflow through dynamic PDF generation.

---

## 💻 Software Construction & Development Architecture

ClinixTech follows a strict **Monolithic Model–View–Controller (MVC)** architecture.

- **Controller Layer (Flask):** Handles routing, business logic, and algorithm execution.
- **Patient Triage (Min-Heap):** Uses Python `heapq` to prioritize patients  
  *(Emergency > Urgent > Normal)* with time complexity **O(N log N)**.
- **Prescription Stack (LIFO):** Enables doctors to undo prescriptions before database commit.
- **Authentication & Security:** Password hashing via `werkzeug.security` with Role-Based Access Control (RBAC).
- **PDF Generation:** Secure prescriptions and medical records generated using **ReportLab**.

---

## 🗄️ Database Management Systems Architecture

ClinixTech uses an **Enterprise Oracle Database** following the **ANSI/SPARC Three-Schema Architecture**.

- **BCNF Normalization:** Fully normalized schema with tables such as Patient, Doctor, Appointment, Vitals, and Payment.
- **MVCC:** Oracle Undo and Redo mechanisms allow concurrent transactions without blocking.
- **ACID Transactions:** Atomic multi-step operations with rollback on integrity failure.
- **Advanced SQL:** Supports joins, nested subqueries, aggregations, and audit reporting.
- **B-Tree Indexing:** Composite indexes on `doctor_id`, `status`, and `priority` for optimized query execution.

---

## ⚙️ Local Setup & Installation

### Prerequisites

- Python 3.10+
- Oracle Database (Local or Cloud)
- Git

---

### Clone the Repository

```bash
git clone https://github.com/mubashir349/Clinixtech.git
cd Clinixtech
````

---

### Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate      # Linux / macOS
venv\Scripts\activate         # Windows
```

---

### Install Dependencies

```bash
pip install -r requirements.txt
```

---

### Configure Environment Variables

Create a `.env` file:

```env
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your_secret_key
DATABASE_URL=oracle+cx_oracle://username:password@host:port/?service_name=ORCL
```

---

### Run the Application

```bash
flask run
```

Open in browser:

```
http://127.0.0.1:5000
```

---

## 📊 Key Features

* Algorithmic patient triage using Min-Heap
* Stack-based prescription handling
* Oracle MVCC and ACID compliance
* Secure RBAC authentication
* Optimized SQL with B-Tree indexing
* Fully paperless clinical operations

---

## 📜 License

Developed for academic and educational purposes.

---

## 👨‍💻 Authors

ClinixTech Development Team
Department of Software Engineering

```
```
