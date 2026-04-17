# ClinixTech - Clinic Management System

A comprehensive Hospital/Clinic Management System built with **Flask** and **Oracle Database**. This application features portals for Admins, Doctors, and Patients, handling everything from appointment scheduling to medical records.

## 🚀 Features
* **Admin Portal:** Manage doctors, patients, and clinic records.
* **Doctor Portal:** View schedules and manage patient history.
* **Patient Portal:** Book appointments and view prescriptions.
* **Oracle Backend:** Robust data management using SQLAlchemy and Oracle Sequences.

## 🛠️ Setup Instructions

### 1. Prerequisites
Ensure you have **Oracle Database** (XE or Enterprise) installed and running.

### 2. Database Configuration
Connect to your Oracle instance as `SYSTEM` and run:
```sql
CREATE USER clinic_user IDENTIFIED BY clinic123;
GRANT CONNECT, RESOURCE, CREATE SESSION TO clinic_user;
GRANT UNLIMITED TABLESPACE TO clinic_user;