
````markdown
# 🏥 ClinixTech: Enterprise Clinic Management & Triage System

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-MVC-lightgrey.svg)
![Oracle](https://img.shields.io/badge/Oracle-Database-red.svg)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-orange.svg)
![Status](https://img.shields.io/badge/Deployment-Active-success.svg)

<p align="center">
  <!-- Replace with actual image path if available -->
  <img src="images/hero_image.png" alt="ClinixTech Enterprise Architecture" width="850"/>
</p>

---

## 📖 Executive Summary

**ClinixTech** is an enterprise-grade Clinic Management and Triage System designed to eliminate administrative bottlenecks in modern healthcare environments. Unlike traditional First-Come-First-Serve (FCFS) systems, ClinixTech applies **Data Structures and Algorithms (DSA)** to mathematically prioritize patients based on medical urgency, ensuring life-critical cases receive immediate attention.

The system is backed by an **Enterprise Oracle Database**, guaranteeing strict data integrity, concurrency control, and ACID-compliant transactions.

This project was developed as a **Complex Engineering Problem (CEP)** to fulfill academic requirements for:

- **Software Construction and Development (SE-312)**
- **Database Management Systems (SE-204)**

---

## 🌍 UN Sustainable Development Goals (SDG) Alignment

- **SDG 3 – Good Health & Well-being**  
  Reduces medical wait-time risks through algorithmic priority-based triage using a Min-Heap.

- **SDG 12 – Responsible Consumption & Production**  
  Enforces a 100% paperless workflow via dynamic server-side PDF generation for prescriptions and medical records.

---

## 💻 Software Construction & Development (SCD) Architecture

ClinixTech follows a strict **Monolithic Model–View–Controller (MVC)** architecture optimized for enterprise deployment.

### Core Components

- **Controller Layer (Flask)**  
  Handles WSGI requests, routes application logic, and invokes clinical algorithms.

- **Algorithmic Patient Triage (Min-Heap)**  
  Uses Python’s `heapq` to dynamically prioritize patients:  
  `Emergency > Urgent > Normal`  
  Time Complexity: **O(N log N)**

- **Prescription Memory Stack (LIFO)**  
  Doctors issue prescriptions using an in-memory stack, enabling instant undo functionality before database commit.

- **Security & Authentication**  
  - Password hashing via `werkzeug.security`  
  - Role-Based Access Control (RBAC)  
  - Route protection using `@login_required` decorators

- **Dynamic Document Generation**  
  Medical histories and prescriptions are generated as secure PDFs using **ReportLab**.

---

## 🗄️ Database Management Systems (DBMS) Architecture

ClinixTech utilizes an **Enterprise Oracle Database** based on the **ANSI/SPARC Three-Schema Architecture**.

### Database Features

- **BCNF Normalization**  
  The database consists of 10 fully normalized tables including:
  - Patient
  - Doctor
  - Appointment
  - Vitals
  - Payment

- **Multi-Version Concurrency Control (MVCC)**  
  Oracle Undo Segments and Redo Logs allow concurrent reads and writes without row-level locking conflicts.

- **ACID Transaction Management**  
  Multi-step operations are executed atomically using `db.session.commit()`.  
  Any integrity violation triggers an automatic rollback.

- **Advanced Analytical SQL**  
  Supports:
  - Nested subqueries  
  - Aggregations (`SUM`, `COUNT`)  
  - Complex `JOIN` operations for reporting and auditing

- **Query Optimization (B-Tree Indexing)**  
  Composite indexes on:
  - `doctor_id`
  - `status`
  - `priority`  
  Ensures Index Range Scans instead of Full Table Scans.

---

## ⚙️ Local Setup & Installation Guide

### Prerequisites

1. **Python 3.10+**
2. **Oracle Database** (Local or Oracle Cloud ATP)
3. **Git**

---

### Step 1: Clone the Repository

```bash
git clone https://github.com/mubashir349/Clinixtech.git
cd Clinixtech
````

---

### Step 2: Create and Activate Virtual Environment

```bash
python -m venv venv
source venv/bin/activate      # Linux / macOS
venv\Scripts\activate         # Windows
```

---

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

---

### Step 4: Configure Environment Variables

Create a `.env` file in the root directory:

```env
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your_secret_key
DATABASE_URL=oracle+cx_oracle://username:password@host:port/?service_name=ORCL
```

---

### Step 5: Run the Application

```bash
flask run
```

Access the system at:

```
http://127.0.0.1:5000
```

---

## 📊 Key Technical Highlights

* Priority Queue implementation using Min-Heap
* Stack-based prescription memory
* Oracle MVCC and ACID compliance
* Secure RBAC authentication system
* Enterprise-grade indexing and query optimization
* Fully paperless clinical workflow

---

## 📌 Academic Relevance

This project satisfies **Complex Engineering Problem (CEP)** criteria by incorporating:

* Advanced algorithmic design
* Enterprise database engineering
* Concurrent transaction handling
* Real-world healthcare constraints
* Secure and scalable system architecture

---

## 📜 License

This project is developed for academic and educational purposes.

---

## 👨‍💻 Authors

Developed by **ClinixTech Development Team**
Department of Software Engineering

---

```


