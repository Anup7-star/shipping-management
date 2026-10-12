"""
db.py - Database Access Layer & DBMS Operations Monitor for Shipping Management System

Demonstrates core DBMS concepts:
1. DDL: CREATE TABLE, CREATE INDEX, CREATE VIEW, CREATE TRIGGER, DROP TABLE
2. DML: INSERT, UPDATE, DELETE, complex SELECT with JOIN, GROUP BY, HAVING
3. TCL: BEGIN TRANSACTION, COMMIT, ROLLBACK
4. Database Triggers: Automatic audit trail & customer shipment count increments
5. Live SQL Audit Log: Tracks all executed queries, operation types, rows affected, and execution time
"""

import sqlite3
import time
import os
import random
import string
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shipping_system.db")

# In-memory execution log buffer for the Live SQL Inspector (keeps last 200 operations)
sql_execution_logs = []

def log_sql_operation(operation_type, sql_query, params=None, duration_ms=0.0, rows_affected=0, status="SUCCESS", error=None):
    """Logs an executed SQL operation for the Live DBMS Inspector."""
    clean_sql = " ".join(sql_query.strip().split())
    log_entry = {
        "id": len(sql_execution_logs) + 1,
        "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
        "type": operation_type.upper(),  # DDL, DML:INSERT, DML:UPDATE, DML:DELETE, DML:SELECT, TCL
        "sql": clean_sql,
        "params": str(params) if params else None,
        "duration_ms": round(duration_ms, 2),
        "rows_affected": rows_affected,
        "status": status,
        "error": str(error) if error else None
    }
    sql_execution_logs.append(log_entry)
    # Keep buffer size manageable
    if len(sql_execution_logs) > 300:
        sql_execution_logs.pop(0)

def get_recent_sql_logs(limit=50):
    """Returns most recent SQL operations in reverse chronological order."""
    return list(reversed(sql_execution_logs))[:limit]

def clear_sql_logs():
    """Clears the live SQL log history."""
    global sql_execution_logs
    sql_execution_logs = []

def get_db_connection():
    """Returns a SQLite connection with foreign keys enabled and row dictionary factory."""
    conn = sqlite3.connect(DB_FILE, timeout=10.0)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn

def execute_raw_sql(sql, params=None, op_type=None):
    """
    Executes a single SQL command with performance logging and error handling.
    """
    if op_type is None:
        trimmed = sql.strip().upper()
        if trimmed.startswith(("CREATE", "ALTER", "DROP", "PRAGMA")):
            op_type = "DDL"
        elif trimmed.startswith("INSERT"):
            op_type = "DML:INSERT"
        elif trimmed.startswith("UPDATE"):
            op_type = "DML:UPDATE"
        elif trimmed.startswith("DELETE"):
            op_type = "DML:DELETE"
        elif trimmed.startswith("SELECT"):
            op_type = "DML:SELECT"
        elif trimmed.startswith(("BEGIN", "COMMIT", "ROLLBACK")):
            op_type = "TCL"
        else:
            op_type = "SQL"

    start_time = time.perf_counter()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        conn.commit()
        duration_ms = (time.perf_counter() - start_time) * 1000
        rows = cursor.rowcount if cursor.rowcount >= 0 else 0
        log_sql_operation(op_type, sql, params, duration_ms, rows, "SUCCESS")
        last_id = cursor.lastrowid
        return {"status": "SUCCESS", "lastrowid": last_id, "rowcount": rows}
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        log_sql_operation(op_type, sql, params, duration_ms, 0, "FAILED", e)
        conn.rollback()
        raise e
    finally:
        conn.close()

def query_all(sql, params=None, op_type="DML:SELECT"):
    """Executes a SELECT query and returns all matching rows as dictionaries."""
    start_time = time.perf_counter()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        rows = [dict(row) for row in cursor.fetchall()]
        duration_ms = (time.perf_counter() - start_time) * 1000
        log_sql_operation(op_type, sql, params, duration_ms, len(rows), "SUCCESS")
        return rows
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        log_sql_operation(op_type, sql, params, duration_ms, 0, "FAILED", e)
        raise e
    finally:
        conn.close()

def query_one(sql, params=None, op_type="DML:SELECT"):
    """Executes a SELECT query and returns the first matching row as a dictionary."""
    start_time = time.perf_counter()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        row = cursor.fetchone()
        duration_ms = (time.perf_counter() - start_time) * 1000
        found = 1 if row else 0
        log_sql_operation(op_type, sql, params, duration_ms, found, "SUCCESS")
        return dict(row) if row else None
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        log_sql_operation(op_type, sql, params, duration_ms, 0, "FAILED", e)
        raise e
    finally:
        conn.close()

def execute_tcl_transaction(operations):
    """
    Executes multiple DML operations in an atomic TCL transaction.
    operations is a list of tuples: (sql, params, op_type)
    Demonstrates BEGIN TRANSACTION, COMMIT, and automatic ROLLBACK on failure.
    """
    start_time = time.perf_counter()
    conn = get_db_connection()
    cursor = conn.cursor()
    log_sql_operation("TCL:BEGIN", "BEGIN TRANSACTION;", None, 0.1, 0, "SUCCESS")
    
    total_affected = 0
    try:
        cursor.execute("BEGIN TRANSACTION;")
        results = []
        for sql, params, op_type in operations:
            op_start = time.perf_counter()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            op_duration = (time.perf_counter() - op_start) * 1000
            rows = cursor.rowcount if cursor.rowcount >= 0 else 0
            total_affected += rows
            log_sql_operation(op_type, sql, params, op_duration, rows, "SUCCESS")
            results.append({"lastrowid": cursor.lastrowid, "rowcount": rows})
            
        cursor.execute("COMMIT;")
        duration_ms = (time.perf_counter() - start_time) * 1000
        log_sql_operation("TCL:COMMIT", "COMMIT;", None, duration_ms, total_affected, "SUCCESS")
        return {"status": "SUCCESS", "results": results, "total_affected": total_affected}
    except Exception as e:
        cursor.execute("ROLLBACK;")
        duration_ms = (time.perf_counter() - start_time) * 1000
        log_sql_operation("TCL:ROLLBACK", "ROLLBACK;", None, duration_ms, 0, "FAILED", e)
        raise e
    finally:
        conn.close()

# ==============================================================================
# DDL SCHEMA DEFINITION & INITIALIZATION
# ==============================================================================

DDL_STATEMENTS = [
    # 1. Users Table (Authentication & Role Based Access Control)
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'dispatcher', 'customer')),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # 2. Customers Table
    """
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        address TEXT NOT NULL,
        city TEXT NOT NULL,
        total_shipments INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
    );
    """,

    # 3. Warehouses Table
    """
    CREATE TABLE IF NOT EXISTS warehouses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        city TEXT NOT NULL,
        state TEXT NOT NULL,
        address TEXT NOT NULL,
        capacity_sqft INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # 4. Vehicles / Fleet Table
    """
    CREATE TABLE IF NOT EXISTS vehicles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_code TEXT UNIQUE NOT NULL,
        vehicle_type TEXT NOT NULL CHECK(vehicle_type IN ('Van', 'Truck', 'Air Cargo', 'Express Bike')),
        driver_name TEXT NOT NULL,
        driver_phone TEXT NOT NULL,
        current_city TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Available' CHECK(status IN ('Available', 'In Transit', 'Maintenance')),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # 5. Shipments Table (Core Entity)
    """
    CREATE TABLE IF NOT EXISTS shipments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tracking_number TEXT UNIQUE NOT NULL,
        customer_id INTEGER,
        sender_name TEXT NOT NULL,
        recipient_name TEXT NOT NULL,
        recipient_phone TEXT NOT NULL,
        origin_city TEXT NOT NULL,
        origin_address TEXT NOT NULL,
        destination_city TEXT NOT NULL,
        destination_address TEXT NOT NULL,
        weight_kg REAL NOT NULL CHECK(weight_kg > 0),
        shipping_type TEXT NOT NULL CHECK(shipping_type IN ('Standard', 'Express', 'Overnight', 'Freight')),
        status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'In Transit', 'Out for Delivery', 'Delivered', 'Cancelled')),
        current_location TEXT NOT NULL,
        vehicle_id INTEGER,
        warehouse_id INTEGER,
        shipping_cost REAL NOT NULL CHECK(shipping_cost >= 0),
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL,
        FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE SET NULL,
        FOREIGN KEY (warehouse_id) REFERENCES warehouses(id) ON DELETE SET NULL
    );
    """,

    # 6. Tracking Events (Detailed Event Milestones)
    """
    CREATE TABLE IF NOT EXISTS tracking_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shipment_id INTEGER NOT NULL,
        tracking_number TEXT NOT NULL,
        status TEXT NOT NULL,
        location TEXT NOT NULL,
        description TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (shipment_id) REFERENCES shipments(id) ON DELETE CASCADE
    );
    """,

    # 7. System Audit Logs (DB-level change log)
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT NOT NULL,
        entity_name TEXT NOT NULL,
        entity_id INTEGER,
        details TEXT,
        logged_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # --------------------------------------------------------------------------
    # INDEXES (DDL for query performance)
    # --------------------------------------------------------------------------
    """CREATE INDEX IF NOT EXISTS idx_shipments_tracking ON shipments(tracking_number);""",
    """CREATE INDEX IF NOT EXISTS idx_shipments_status ON shipments(status);""",
    """CREATE INDEX IF NOT EXISTS idx_shipments_dest_city ON shipments(destination_city);""",
    """CREATE INDEX IF NOT EXISTS idx_tracking_events_tracking ON tracking_events(tracking_number);""",

    # --------------------------------------------------------------------------
    # VIEWS (DDL for abstraction and analytical reporting)
    # --------------------------------------------------------------------------
    """
    CREATE VIEW IF NOT EXISTS view_active_deliveries AS
    SELECT 
        s.id AS shipment_id,
        s.tracking_number,
        s.sender_name,
        s.recipient_name,
        s.origin_city,
        s.destination_city,
        s.status,
        s.shipping_type,
        s.weight_kg,
        s.shipping_cost,
        v.vehicle_code,
        v.driver_name,
        v.vehicle_type,
        w.name AS warehouse_name,
        s.created_at,
        s.updated_at
    FROM shipments s
    LEFT JOIN vehicles v ON s.vehicle_id = v.id
    LEFT JOIN warehouses w ON s.warehouse_id = w.id
    WHERE s.status IN ('Pending', 'In Transit', 'Out for Delivery');
    """,

    """
    CREATE VIEW IF NOT EXISTS view_destination_analytics AS
    SELECT 
        destination_city,
        COUNT(id) AS total_shipments,
        SUM(CASE WHEN status = 'Delivered' THEN 1 ELSE 0 END) AS delivered_count,
        SUM(CASE WHEN status != 'Delivered' AND status != 'Cancelled' THEN 1 ELSE 0 END) AS active_count,
        ROUND(SUM(shipping_cost), 2) AS total_revenue,
        ROUND(AVG(weight_kg), 2) AS avg_weight_kg
    FROM shipments
    GROUP BY destination_city;
    """,

    # --------------------------------------------------------------------------
    # TRIGGERS (DDL for automated event-driven database behaviors)
    # --------------------------------------------------------------------------
    """
    CREATE TRIGGER IF NOT EXISTS trg_shipment_status_audit
    AFTER UPDATE OF status ON shipments
    FOR EACH ROW
    WHEN OLD.status <> NEW.status
    BEGIN
        -- Automatically log an entry in tracking_events
        INSERT INTO tracking_events (shipment_id, tracking_number, status, location, description, timestamp)
        VALUES (
            NEW.id,
            NEW.tracking_number,
            NEW.status,
            NEW.current_location,
            'Status automatically updated from ' || OLD.status || ' to ' || NEW.status || ' via DBMS trigger',
            CURRENT_TIMESTAMP
        );
        
        -- Automatically log into audit_logs
        INSERT INTO audit_logs (action, entity_name, entity_id, details)
        VALUES (
            'UPDATE_STATUS',
            'shipments',
            NEW.id,
            'Changed status from ' || OLD.status || ' to ' || NEW.status
        );
    END;
    """,

    """
    CREATE TRIGGER IF NOT EXISTS trg_increment_customer_shipments
    AFTER INSERT ON shipments
    FOR EACH ROW
    WHEN NEW.customer_id IS NOT NULL
    BEGIN
        UPDATE customers 
        SET total_shipments = total_shipments + 1 
        WHERE id = NEW.customer_id;
    END;
    """
]

def generate_tracking_number():
    """Generates a professional tracking code like SHP-849201."""
    digits = ''.join(random.choices(string.digits, k=6))
    return f"SHP-{digits}"

def calculate_shipping_cost(weight_kg, shipping_type):
    """Business rule to compute cost based on weight and service level."""
    rates = {
        "Standard": 5.0,    # Base rate
        "Express": 12.0,
        "Overnight": 25.0,
        "Freight": 8.0
    }
    per_kg = {
        "Standard": 2.5,
        "Express": 4.5,
        "Overnight": 7.0,
        "Freight": 1.5
    }
    base = rates.get(shipping_type, 5.0)
    kg_rate = per_kg.get(shipping_type, 2.5)
    return round(base + (weight_kg * kg_rate), 2)

def init_db(force_recreate=False):
    """
    Executes DDL statements to create tables, indexes, views, and triggers.
    If force_recreate=True, drops existing tables and reseeds demo data.
    """
    if force_recreate and os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
            log_sql_operation("DDL:DROP", "DROP DATABASE (Reinitializing shipping_system.db);", None, 1.0, 0, "SUCCESS")
        except Exception:
            pass

    for stmt in DDL_STATEMENTS:
        execute_raw_sql(stmt, op_type="DDL")

    # Check if database has users; if not, seed initial demo dataset
    user_count = query_one("SELECT COUNT(*) as count FROM users")
    if not user_count or user_count["count"] == 0:
        seed_demo_data()

def seed_demo_data():
    """Seeds rich, realistic demo data demonstrating DML INSERT operations."""
    # 1. Users
    users_data = [
        ("admin", generate_password_hash("admin123"), "System Administrator", "admin@shipflow.com", "admin"),
        ("dispatcher", generate_password_hash("dispatch123"), "Sarah Jenkins (Dispatcher)", "sarah@shipflow.com", "dispatcher"),
        ("customer", generate_password_hash("customer123"), "John Miller (Customer)", "john.miller@example.com", "customer"),
        ("dispatcher2", generate_password_hash("dispatch123"), "Alex Rivera (Field Fleet)", "alex@shipflow.com", "dispatcher")
    ]
    for u in users_data:
        execute_raw_sql(
            "INSERT INTO users (username, password_hash, full_name, email, role) VALUES (?, ?, ?, ?, ?);",
            u, op_type="DML:INSERT"
        )

    # 2. Customers
    cust_user = query_one("SELECT id FROM users WHERE username = 'customer'")
    cust_id = cust_user["id"] if cust_user else None

    customers_data = [
        (cust_id, "John Miller", "john.miller@example.com", "+1 555-0192", "742 Evergreen Terrace", "Springfield"),
        (None, "Global Tech Corp", "orders@globaltech.com", "+1 555-0482", "100 Innovation Way", "San Jose"),
        (None, "Apex Retailers Ltd", "shipping@apexretail.com", "+1 555-0819", "45 Commercial Blvd", "Chicago"),
        (None, "Emma Watson", "emma.w@mail.com", "+1 555-0371", "12 Birchwood Lane", "Seattle"),
        (None, "David Lee", "david.lee@market.com", "+1 555-0922", "88 Market Street", "New York")
    ]
    for c in customers_data:
        execute_raw_sql(
            "INSERT INTO customers (user_id, name, email, phone, address, city) VALUES (?, ?, ?, ?, ?, ?);",
            c, op_type="DML:INSERT"
        )

    # 3. Warehouses
    warehouses_data = [
        ("WH-NY-01", "Metropolitan Cargo Hub", "New York", "NY", "820 Logistics Parkway", 150000),
        ("WH-CHI-02", "Midwest Distribution Center", "Chicago", "IL", "400 Terminal Road", 200000),
        ("WH-SF-03", "Pacific Gateway Facility", "San Francisco", "CA", "12 Bayfront Expressway", 120000),
        ("WH-MIA-04", "Sunbelt Logistics Depot", "Miami", "FL", "95 Port Boulevard", 95000)
    ]
    for w in warehouses_data:
        execute_raw_sql(
            "INSERT INTO warehouses (code, name, city, state, address, capacity_sqft) VALUES (?, ?, ?, ?, ?, ?);",
            w, op_type="DML:INSERT"
        )

    # 4. Vehicles
    vehicles_data = [
        ("VEH-101", "Van", "Mike Tyson", "+1 555-4401", "New York", "In Transit"),
        ("VEH-102", "Truck", "Robert Downey", "+1 555-4402", "Chicago", "Available"),
        ("VEH-103", "Air Cargo", "Amelia Earhart", "+1 555-4403", "San Francisco", "In Transit"),
        ("VEH-104", "Express Bike", "Peter Parker", "+1 555-4404", "New York", "Available"),
        ("VEH-105", "Truck", "Bruce Wayne", "+1 555-4405", "Miami", "Available")
    ]
    for v in vehicles_data:
        execute_raw_sql(
            "INSERT INTO vehicles (vehicle_code, vehicle_type, driver_name, driver_phone, current_city, status) VALUES (?, ?, ?, ?, ?, ?);",
            v, op_type="DML:INSERT"
        )

    # 5. Shipments with realistic initial data
    sample_shipments = [
        ("SHP-100231", 1, "John Miller", "Alice Cooper", "+1 555-8811", "Springfield", "742 Evergreen Terr", "Chicago", "500 N Michigan Ave", 4.5, "Express", "In Transit", "Midwest Transit Hub", 2, 2, 32.25, "Fragile computer parts"),
        ("SHP-100232", 2, "Global Tech Corp", "Marcus Reed", "+1 555-7722", "San Jose", "100 Innovation Way", "New York", "350 5th Ave (Empire Bldg)", 12.0, "Standard", "Out for Delivery", "New York Distribution Hub", 1, 1, 35.00, "Pallet of server adapters"),
        ("SHP-100233", 3, "Apex Retailers Ltd", "Clara Oswald", "+1 555-6633", "Chicago", "45 Commercial Blvd", "Miami", "1100 Ocean Drive", 2.2, "Overnight", "Pending", "Chicago Fulfillment", None, 2, 40.40, "Urgent retail contract documents"),
        ("SHP-100234", 4, "Emma Watson", "Henry Cavill", "+1 555-5544", "Seattle", "12 Birchwood Lane", "San Francisco", "101 California St", 8.0, "Standard", "Delivered", "San Francisco Destination", 3, 3, 25.00, "Delivered to reception desk"),
        ("SHP-100235", 1, "John Miller", "Diana Prince", "+1 555-3322", "Springfield", "742 Evergreen Terr", "Miami", "450 Biscayne Blvd", 1.5, "Express", "Delivered", "Miami Sunbelt Depot", 5, 4, 18.75, "Signed by recipient"),
        ("SHP-100236", 5, "David Lee", "Tony Stark", "+1 555-9988", "New York", "88 Market Street", "San Francisco", "10880 Wilshire Blvd", 18.5, "Freight", "In Transit", "En Route Interstate 80", 3, 3, 35.75, "Heavy mechanical equipment")
    ]

    for s in sample_shipments:
        execute_raw_sql(
            """
            INSERT INTO shipments (
                tracking_number, customer_id, sender_name, recipient_name, recipient_phone,
                origin_city, origin_address, destination_city, destination_address,
                weight_kg, shipping_type, status, current_location, vehicle_id, warehouse_id,
                shipping_cost, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            s, op_type="DML:INSERT"
        )
        
        # Add initial tracking event
        shipment_row = query_one("SELECT id FROM shipments WHERE tracking_number = ?", (s[0],))
        if shipment_row:
            execute_raw_sql(
                """
                INSERT INTO tracking_events (shipment_id, tracking_number, status, location, description)
                VALUES (?, ?, ?, ?, ?);
                """,
                (shipment_row["id"], s[0], s[11], s[12], f"Initial package recorded at {s[12]}"),
                op_type="DML:INSERT"
            )

    log_sql_operation("DML:INSERT", "Initial demo seed data completed successfully.", None, 5.0, len(sample_shipments), "SUCCESS")

# Initialize database on module load if not present
if not os.path.exists(DB_FILE):
    init_db()
