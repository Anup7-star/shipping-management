# ShipFlow - Enterprise Shipping Management System & DBMS Engine

A modern, full-stack logistics and parcel shipping management platform built in Python (Flask) with an authentic relational database engine (**SQLite3**). 

The platform is designed so that users, dispatchers, and customers interact through **intuitive, user-friendly forms** (selecting destinations, setting shipping statuses, entering package weights, recipient addresses, and fleet assignments) without having to write raw SQL commands. In the background, **every user action executes full DBMS operations**: **DDL, DML, TCL Transactions, Database Triggers, and Views**.

---

## ⚡ Key Highlights & DBMS Mapping

| User Action in UI | DBMS Classification | Exact Relational Operation Executed |
| :--- | :--- | :--- |
| **System Boot / Reset** | **DDL** (Data Definition Language) | `CREATE TABLE` (7 relational entities), `CREATE INDEX` (B-Trees), `CREATE VIEW`, `CREATE TRIGGER` |
| **User Login & Registration** | **DML & Security** | `SELECT * FROM users WHERE username = ?`, `INSERT INTO users ...` with salted pbkdf2 password hashing |
| **Book New Shipment** | **TCL + DML** (Atomic Transaction) | `BEGIN TRANSACTION;` <br> `INSERT INTO shipments (...)` <br> `INSERT INTO tracking_events (...)` <br> `COMMIT;` (or `ROLLBACK` on error) |
| **Update Shipping Status** (e.g. *Pending* ➔ *In Transit* ➔ *Out for Delivery* ➔ *Delivered*) | **DML + DB Trigger** | `UPDATE shipments SET status = ?, current_location = ? WHERE id = ?;`<br>Automatically fires DB Trigger `trg_shipment_status_audit` to log milestones and system audit entries. |
| **Reroute Parcel / Change Destination** | **DML** | `UPDATE shipments SET destination_city = ?, destination_address = ? WHERE id = ?;` |
| **Fleet & Warehouse Assignment** | **Relational FK Assignment** | `UPDATE shipments SET vehicle_id = ?, warehouse_id = ? WHERE id = ?;` (Foreign keys to `vehicles` & `warehouses`) |
| **Cancel / Delete Shipment** | **DML DELETE** | `DELETE FROM shipments WHERE id = ?;` (Cascades to child milestones) |
| **Dashboard Analytics & Filtering** | **DML Queries & Views** | `SELECT * FROM view_active_deliveries;` <br> `SELECT ... GROUP BY destination_city HAVING ...;` |
| **Live SQL Drawer & DBMS Inspector** | **DBMS Metadata** | Queries `sqlite_master`, `PRAGMA table_info`, execution times, and affected row counts. |

---

## 🚀 How to Run the Project

### Option 1: Direct Python Command
Open PowerShell or Command Prompt in this folder (`c:\New folder\pat4`) and run:
```bash
python run.py
```

### Option 2: Windows Batch Runner
Double-click `start.bat` in Windows Explorer.

Then open your browser and navigate to:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 🔑 Demo Login Accounts

For hassle-free testing, the login screen includes **1-Click Quick Demo Login buttons**:

| Role | Username | Password | Access Privileges |
| :--- | :--- | :--- | :--- |
| **System Administrator** | `admin` | `admin123` | Full control: Book, Update Status, Reroute, Delete, Reset DDL schemas, Run Raw SQL Sandbox |
| **Logistics Dispatcher** | `dispatcher` | `dispatch123` | Operational access: Update shipping status, assign fleet/drivers and warehouses |
| **Customer / Client** | `customer` | `customer123` | Book personal shipments, view their packages, and track live parcels |

---

## 🖥️ Screen Walkthrough & Features

### 1. Modern Login & Register Portal (`/login`)
- Clean user interface with pre-filled 1-click demo buttons.
- Supports registering new customer, dispatcher, or admin accounts with secure password hashing.

### 2. Logistics Control Center Dashboard (`/dashboard`)
- Metric KPI cards (`COUNT(*)`, `SUM(shipping_cost)`) for Total Orders, In Transit, Out for Delivery, Delivered, and Revenue.
- **Active Parcels Pipeline**: Live table populated from the database view `view_active_deliveries`.
- **Top Destinations Analytics**: Aggregated summary populated from `view_destination_analytics` using `GROUP BY destination_city`.

### 3. Shipments Directory (`/shipments`)
- Search by tracking number, recipient name, or city.
- Filter by shipping status (`Pending`, `In Transit`, `Out for Delivery`, `Delivered`, `Cancelled`).
- **"Book New Shipment" Modal**: User-friendly form (Destination City, Address, Recipient, Weight, Shipping Class) that executes an atomic **TCL Transaction** in the backend.
- **"Quick Status Update" Modal**: Change status and location; immediately fires the database trigger.
- **"Reroute Destination" Modal**: Change delivery destination address.

### 4. Parcel Detail & Visual Milestone Tracker (`/shipment/<tracking_number>`)
- Interactive step-by-step progress pipeline (Booked ➔ In Transit ➔ Out for Delivery ➔ Delivered).
- Chronological tracking history table recording every scan milestone.
- Foreign key assignment form for fleet vehicles (`Van`, `Truck`, `Air Cargo`) and hub warehouses.

### 5. Public Parcel Tracker (`/track`)
- Accessible to any client or guest: enter a tracking number (e.g., `SHP-100231`) to inspect parcel status and current station.

### 6. Live DBMS SQL Inspector Drawer (⚡ Available on Every Page)
- Click the top right **"Backend SQL"** button to toggle a real-time slide-out drawer.
- Shows every query executed by your UI clicks in real time:
  - Query category badge: `[DDL]`, `[DML:INSERT]`, `[DML:UPDATE]`, `[DML:SELECT]`, `[TCL:COMMIT]`
  - Execution duration in milliseconds (e.g., `0.45ms`)
  - Rows affected
  - Exact SQL syntax with bound parameters.

### 7. Dedicated DBMS Schema & Query Inspector (`/dbms-inspector`)
- **Tables & Schemas (DDL)**: Shows column metadata (`CID`, data type, not null, default values, primary keys) for all 7 tables via `PRAGMA table_info`.
- **Views (CREATE VIEW)**: Inspects virtual views definitions.
- **Triggers**: Shows trigger conditions and stored procedural code for `trg_shipment_status_audit` and `trg_increment_customer_shipments`.
- **Indexes**: Displays B-Tree indexes created on search columns.
- **SQL Sandbox / Query Tester**: Allows running custom queries (joins, group by, subqueries) with table results formatted in the UI.

---

## 🧪 Automated Test Suite

To verify all database schemas, transactions, status transitions, and routes:
```bash
python test_app.py
```
*Result: 7 tests passed with 100% OK.*
