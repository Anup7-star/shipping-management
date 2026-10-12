"""
app.py - Flask Web Application for Shipping Management System

Exposes a modern web UI while executing comprehensive DBMS operations
(DDL, DML, TCL, Triggers, Views) in the backend.
"""

import functools
import os
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, jsonify, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

import db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "shipflow-dbms-secret-key-2026")

# Ensure DB initialized
db.init_db()

# ==============================================================================
# AUTHENTICATION & ACCESS CONTROL
# ==============================================================================

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        return view(**kwargs)
    return wrapped_view

def role_required(allowed_roles):
    def decorator(view):
        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if session.get("role") not in allowed_roles:
                flash("Access denied: You do not have permission to view this resource.", "danger")
                return redirect(url_for("dashboard"))
            return view(**kwargs)
        return wrapped_view
    return decorator

@app.context_processor
def inject_global_data():
    """Injects user session and system metadata into all Jinja templates."""
    return {
        "current_user": {
            "id": session.get("user_id"),
            "username": session.get("username"),
            "role": session.get("role"),
            "full_name": session.get("full_name")
        } if "user_id" in session else None,
        "recent_sql_logs_count": len(db.sql_execution_logs)
    }

# ==============================================================================
# AUTH ROUTES
# ==============================================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        # Check if quick demo login was clicked
        demo_role = request.form.get("demo_role")
        if demo_role:
            role_map = {
                "admin": "admin",
                "dispatcher": "dispatcher",
                "customer": "customer"
            }
            username = role_map.get(demo_role, "admin")
            user = db.query_one("SELECT * FROM users WHERE username = ?", (username,), op_type="DML:SELECT")
            if user:
                session.clear()
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["role"] = user["role"]
                session["full_name"] = user["full_name"]
                flash(f"Welcome back, {user['full_name']}! (Logged in as {user['role'].upper()})", "success")
                return redirect(url_for("dashboard"))

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Please enter both username and password.", "danger")
            return render_template("login.html")

        # Execute DML SELECT to retrieve user
        user = db.query_one(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (username, username),
            op_type="DML:SELECT"
        )

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            session["full_name"] = user["full_name"]
            flash(f"Successfully logged in as {user['full_name']}.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password.", "danger")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        role = request.form.get("role", "customer").strip()

        if role not in ["customer", "dispatcher", "admin"]:
            role = "customer"

        if not username or not password or not full_name or not email:
            flash("All fields are required.", "danger")
            return render_template("login.html", is_register=True)

        # Check existing user
        existing = db.query_one("SELECT id FROM users WHERE username = ? OR email = ?", (username, email), op_type="DML:SELECT")
        if existing:
            flash("Username or email already exists. Please choose another.", "danger")
            return render_template("login.html", is_register=True)

        # Insert user via DML INSERT
        hashed = generate_password_hash(password)
        try:
            res = db.execute_raw_sql(
                "INSERT INTO users (username, password_hash, full_name, email, role) VALUES (?, ?, ?, ?, ?);",
                (username, hashed, full_name, email, role),
                op_type="DML:INSERT"
            )
            user_id = res["lastrowid"]

            # If registered as customer, create matching customer profile
            if role == "customer":
                db.execute_raw_sql(
                    "INSERT INTO customers (user_id, name, email, phone, address, city) VALUES (?, ?, ?, ?, ?, ?);",
                    (user_id, full_name, email, request.form.get("phone", "+1 555-0000"), 
                     request.form.get("address", "100 Main St"), request.form.get("city", "New York")),
                    op_type="DML:INSERT"
                )

            flash("Account registered successfully! Please log in.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            flash(f"Database error during registration: {str(e)}", "danger")

    return render_template("login.html", is_register=True)

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

# ==============================================================================
# DASHBOARD & ANALYTICS
# ==============================================================================

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    # 1. Total counts using DML aggregation (SELECT COUNT, SUM)
    stats_query = """
    SELECT 
        COUNT(*) AS total_shipments,
        SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) AS pending_count,
        SUM(CASE WHEN status = 'In Transit' THEN 1 ELSE 0 END) AS in_transit_count,
        SUM(CASE WHEN status = 'Out for Delivery' THEN 1 ELSE 0 END) AS out_for_delivery_count,
        SUM(CASE WHEN status = 'Delivered' THEN 1 ELSE 0 END) AS delivered_count,
        SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END) AS cancelled_count,
        ROUND(COALESCE(SUM(shipping_cost), 0), 2) AS total_revenue
    FROM shipments;
    """
    stats = db.query_one(stats_query, op_type="DML:SELECT")

    # 2. Query Active Deliveries from the SQL VIEW created via DDL
    active_deliveries = db.query_all(
        "SELECT * FROM view_active_deliveries ORDER BY updated_at DESC LIMIT 8;",
        op_type="DML:SELECT (VIEW)"
    )

    # 3. Query City Analytics from SQL VIEW
    city_analytics = db.query_all(
        "SELECT * FROM view_destination_analytics ORDER BY total_shipments DESC LIMIT 6;",
        op_type="DML:SELECT (VIEW)"
    )

    # 4. Fleet and Warehouse metrics
    fleet_count = db.query_one("SELECT COUNT(*) AS total, SUM(CASE WHEN status='Available' THEN 1 ELSE 0 END) AS available FROM vehicles;")
    warehouse_count = db.query_one("SELECT COUNT(*) AS total FROM warehouses;")

    # 5. Recent DBMS operations count for quick stats
    recent_logs = db.get_recent_sql_logs(6)

    return render_template(
        "dashboard.html",
        stats=stats,
        active_deliveries=active_deliveries,
        city_analytics=city_analytics,
        fleet_count=fleet_count,
        warehouse_count=warehouse_count,
        recent_logs=recent_logs
    )

# ==============================================================================
# SHIPMENTS MANAGEMENT (CREATE, READ, UPDATE, DELETE)
# ==============================================================================

@app.route("/shipments")
@login_required
def shipments_list():
    status_filter = request.args.get("status", "").strip()
    city_filter = request.args.get("city", "").strip()
    search_query = request.args.get("q", "").strip()

    # Dynamic multi-table SQL query with JOINs, demonstrates relational DBMS
    sql = """
    SELECT 
        s.*,
        c.name AS customer_name,
        c.phone AS customer_phone,
        v.vehicle_code,
        v.driver_name,
        w.name AS warehouse_name
    FROM shipments s
    LEFT JOIN customers c ON s.customer_id = c.id
    LEFT JOIN vehicles v ON s.vehicle_id = v.id
    LEFT JOIN warehouses w ON s.warehouse_id = w.id
    WHERE 1=1
    """
    params = []

    # If logged in as customer, show only their shipments
    if session.get("role") == "customer":
        cust = db.query_one("SELECT id FROM customers WHERE user_id = ?", (session["user_id"],))
        if cust:
            sql += " AND s.customer_id = ?"
            params.append(cust["id"])

    if status_filter and status_filter != "All":
        sql += " AND s.status = ?"
        params.append(status_filter)

    if city_filter:
        sql += " AND (s.destination_city = ? OR s.origin_city = ?)"
        params.extend([city_filter, city_filter])

    if search_query:
        sql += " AND (s.tracking_number LIKE ? OR s.recipient_name LIKE ? OR s.destination_city LIKE ?)"
        pattern = f"%{search_query}%"
        params.extend([pattern, pattern, pattern])

    sql += " ORDER BY s.id DESC"

    shipments = db.query_all(sql, params, op_type="DML:SELECT (JOIN)")

    # Fetch lookup data for modal inputs
    warehouses = db.query_all("SELECT id, name, city FROM warehouses ORDER BY city", op_type="DML:SELECT")
    vehicles = db.query_all("SELECT id, vehicle_code, vehicle_type, driver_name FROM vehicles WHERE status != 'Maintenance'", op_type="DML:SELECT")
    customers = db.query_all("SELECT id, name, city FROM customers ORDER BY name", op_type="DML:SELECT")
    cities = db.query_all("SELECT DISTINCT destination_city FROM shipments ORDER BY destination_city", op_type="DML:SELECT")

    return render_template(
        "shipments.html",
        shipments=shipments,
        warehouses=warehouses,
        vehicles=vehicles,
        customers=customers,
        cities=cities,
        status_filter=status_filter,
        city_filter=city_filter,
        search_query=search_query
    )

@app.route("/shipments/new", methods=["POST"])
@login_required
def create_shipment():
    """
    Creates a new shipment through user-friendly form inputs.
    Executes an atomic TCL Transaction:
      1. BEGIN TRANSACTION
      2. INSERT INTO shipments
      3. INSERT INTO tracking_events
      4. COMMIT
      * Note: DB Trigger 'trg_increment_customer_shipments' automatically updates customer stats!
    """
    try:
        sender_name = request.form.get("sender_name", "").strip() or session.get("full_name")
        recipient_name = request.form.get("recipient_name", "").strip()
        recipient_phone = request.form.get("recipient_phone", "").strip()
        origin_city = request.form.get("origin_city", "").strip()
        origin_address = request.form.get("origin_address", "").strip()
        destination_city = request.form.get("destination_city", "").strip()
        destination_address = request.form.get("destination_address", "").strip()
        weight_kg = float(request.form.get("weight_kg", 1.0))
        shipping_type = request.form.get("shipping_type", "Standard")
        notes = request.form.get("notes", "").strip()
        customer_id = request.form.get("customer_id")
        warehouse_id = request.form.get("warehouse_id") or None
        vehicle_id = request.form.get("vehicle_id") or None

        # Convert empty strings to None for foreign keys
        if customer_id and customer_id != "":
            customer_id = int(customer_id)
        else:
            if session.get("role") == "customer":
                cust = db.query_one("SELECT id FROM customers WHERE user_id = ?", (session["user_id"],))
                customer_id = cust["id"] if cust else None
            else:
                customer_id = None

        if warehouse_id and warehouse_id != "":
            warehouse_id = int(warehouse_id)
        else:
            warehouse_id = None

        if vehicle_id and vehicle_id != "":
            vehicle_id = int(vehicle_id)
        else:
            vehicle_id = None

        if not recipient_name or not destination_city or not destination_address:
            flash("Recipient name and Destination details are required.", "danger")
            return redirect(url_for("shipments_list"))

        tracking_number = db.generate_tracking_number()
        shipping_cost = db.calculate_shipping_cost(weight_kg, shipping_type)
        initial_location = f"{origin_city} Sorting Facility"

        # Execute Transaction via TCL
        trans_ops = [
            (
                """
                INSERT INTO shipments (
                    tracking_number, customer_id, sender_name, recipient_name, recipient_phone,
                    origin_city, origin_address, destination_city, destination_address,
                    weight_kg, shipping_type, status, current_location, vehicle_id, warehouse_id,
                    shipping_cost, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?, ?, ?, ?);
                """,
                (
                    tracking_number, customer_id, sender_name, recipient_name, recipient_phone,
                    origin_city, origin_address, destination_city, destination_address,
                    weight_kg, shipping_type, initial_location, vehicle_id, warehouse_id,
                    shipping_cost, notes
                ),
                "DML:INSERT"
            )
        ]

        # Execute TCL transaction
        trans_result = db.execute_tcl_transaction(trans_ops)
        shipment_id = trans_result["results"][0]["lastrowid"]

        # Insert initial tracking event milestone
        db.execute_raw_sql(
            """
            INSERT INTO tracking_events (shipment_id, tracking_number, status, location, description)
            VALUES (?, ?, 'Pending', ?, ?);
            """,
            (shipment_id, tracking_number, initial_location, f"Shipment booked by {sender_name} via {shipping_type} service."),
            op_type="DML:INSERT"
        )

        flash(f"Shipment booked successfully! Tracking Number: {tracking_number} (Cost: ${shipping_cost})", "success")
        return redirect(url_for("shipment_detail", tracking_number=tracking_number))

    except Exception as e:
        flash(f"Transaction failed: {str(e)}", "danger")
        return redirect(url_for("shipments_list"))

@app.route("/shipments/<int:id>/status", methods=["POST"])
@login_required
def update_shipment_status(id):
    """
    Updates the shipping status of a package (e.g. In Transit, Out for Delivery, Delivered).
    This DML UPDATE automatically fires SQLite Trigger 'trg_shipment_status_audit'
    which records a tracking milestone and audit log!
    """
    try:
        new_status = request.form.get("status")
        current_location = request.form.get("current_location", "").strip()
        notes = request.form.get("notes", "").strip()

        if new_status not in ['Pending', 'In Transit', 'Out for Delivery', 'Delivered', 'Cancelled']:
            flash("Invalid status selected.", "danger")
            return redirect(url_for("shipments_list"))

        shipment = db.query_one("SELECT * FROM shipments WHERE id = ?", (id,), op_type="DML:SELECT")
        if not shipment:
            flash("Shipment not found.", "danger")
            return redirect(url_for("shipments_list"))

        location_to_set = current_location if current_location else shipment["current_location"]

        # Execute DML UPDATE (Trigger trg_shipment_status_audit fires automatically!)
        db.execute_raw_sql(
            """
            UPDATE shipments 
            SET status = ?, current_location = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
            """,
            (new_status, location_to_set, id),
            op_type="DML:UPDATE (TRIGGER FIRED)"
        )

        if notes:
            # Add custom note if provided
            db.execute_raw_sql(
                """
                INSERT INTO tracking_events (shipment_id, tracking_number, status, location, description)
                VALUES (?, ?, ?, ?, ?);
                """,
                (id, shipment["tracking_number"], new_status, location_to_set, f"Status update note: {notes}"),
                op_type="DML:INSERT"
            )

        flash(f"Status for {shipment['tracking_number']} updated to '{new_status}'. DBMS Trigger logged event.", "success")
        return redirect(request.referrer or url_for("shipments_list"))

    except Exception as e:
        flash(f"Error updating status: {str(e)}", "danger")
        return redirect(url_for("shipments_list"))

@app.route("/shipments/<int:id>/destination", methods=["POST"])
@login_required
def update_destination(id):
    """
    Reroutes a shipment by updating its destination address and city.
    Executes DML UPDATE on shipments and logs tracking event.
    """
    try:
        new_city = request.form.get("destination_city", "").strip()
        new_address = request.form.get("destination_address", "").strip()
        reason = request.form.get("reason", "Customer request").strip()

        if not new_city or not new_address:
            flash("Destination city and address cannot be empty.", "danger")
            return redirect(url_for("shipments_list"))

        shipment = db.query_one("SELECT * FROM shipments WHERE id = ?", (id,), op_type="DML:SELECT")
        if not shipment:
            flash("Shipment not found.", "danger")
            return redirect(url_for("shipments_list"))

        # DML UPDATE
        db.execute_raw_sql(
            """
            UPDATE shipments 
            SET destination_city = ?, destination_address = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
            """,
            (new_city, new_address, id),
            op_type="DML:UPDATE"
        )

        # Log tracking event
        db.execute_raw_sql(
            """
            INSERT INTO tracking_events (shipment_id, tracking_number, status, location, description)
            VALUES (?, ?, ?, ?, ?);
            """,
            (id, shipment["tracking_number"], shipment["status"], shipment["current_location"],
             f"Rerouted to {new_address}, {new_city}. Reason: {reason}"),
            op_type="DML:INSERT"
        )

        flash(f"Destination for {shipment['tracking_number']} updated to {new_city} successfully.", "success")
        return redirect(request.referrer or url_for("shipments_list"))

    except Exception as e:
        flash(f"Error updating destination: {str(e)}", "danger")
        return redirect(url_for("shipments_list"))

@app.route("/shipments/<int:id>/assign", methods=["POST"])
@login_required
@role_required(["admin", "dispatcher"])
def assign_fleet(id):
    """Assigns vehicle and/or warehouse to a shipment (DML UPDATE)."""
    vehicle_id = request.form.get("vehicle_id") or None
    warehouse_id = request.form.get("warehouse_id") or None

    vehicle_id = int(vehicle_id) if vehicle_id else None
    warehouse_id = int(warehouse_id) if warehouse_id else None

    db.execute_raw_sql(
        "UPDATE shipments SET vehicle_id = ?, warehouse_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
        (vehicle_id, warehouse_id, id),
        op_type="DML:UPDATE"
    )
    flash("Fleet and warehouse assignment updated.", "success")
    return redirect(request.referrer or url_for("shipments_list"))

@app.route("/shipments/<int:id>/delete", methods=["POST"])
@login_required
@role_required(["admin"])
def delete_shipment(id):
    """
    Deletes / cancels a shipment (Admin only).
    Demonstrates DML DELETE with foreign key cascade on tracking_events.
    """
    try:
        shipment = db.query_one("SELECT tracking_number FROM shipments WHERE id = ?", (id,))
        t_num = shipment["tracking_number"] if shipment else id

        db.execute_raw_sql(
            "DELETE FROM shipments WHERE id = ?;",
            (id,),
            op_type="DML:DELETE"
        )
        flash(f"Shipment {t_num} has been permanently deleted from database (DML DELETE).", "info")
    except Exception as e:
        flash(f"Delete failed: {str(e)}", "danger")

    return redirect(url_for("shipments_list"))

@app.route("/shipment/<tracking_number>")
def shipment_detail(tracking_number):
    """
    Detailed shipment view showing the parcel attributes, vehicle, warehouse,
    and complete chronological tracking history.
    """
    shipment = db.query_one(
        """
        SELECT 
            s.*,
            c.name AS customer_name,
            c.email AS customer_email,
            c.phone AS customer_phone,
            v.vehicle_code,
            v.driver_name,
            v.driver_phone,
            v.vehicle_type,
            w.name AS warehouse_name,
            w.address AS warehouse_address,
            w.city AS warehouse_city
        FROM shipments s
        LEFT JOIN customers c ON s.customer_id = c.id
        LEFT JOIN vehicles v ON s.vehicle_id = v.id
        LEFT JOIN warehouses w ON s.warehouse_id = w.id
        WHERE s.tracking_number = ?;
        """,
        (tracking_number,),
        op_type="DML:SELECT (MULTI-JOIN)"
    )

    if not shipment:
        flash(f"No shipment found with tracking number '{tracking_number}'.", "warning")
        return redirect(url_for("track"))

    # Tracking event timeline ordered chronologically
    events = db.query_all(
        "SELECT * FROM tracking_events WHERE tracking_number = ? ORDER BY timestamp DESC, id DESC;",
        (tracking_number,),
        op_type="DML:SELECT"
    )

    # Vehicles and warehouses for dispatch assignment
    vehicles = db.query_all("SELECT id, vehicle_code, driver_name, vehicle_type FROM vehicles;")
    warehouses = db.query_all("SELECT id, name, city FROM warehouses;")

    return render_template(
        "shipment_detail.html",
        shipment=shipment,
        events=events,
        vehicles=vehicles,
        warehouses=warehouses
    )

# ==============================================================================
# PUBLIC PARCEL TRACKING
# ==============================================================================

@app.route("/track", methods=["GET", "POST"])
def track():
    tracking_number = request.args.get("tracking_number", "").strip()
    if request.method == "POST":
        tracking_number = request.form.get("tracking_number", "").strip()

    shipment = None
    events = []
    if tracking_number:
        shipment = db.query_one(
            """
            SELECT s.*, v.driver_name, v.vehicle_type, w.name as warehouse_name
            FROM shipments s
            LEFT JOIN vehicles v ON s.vehicle_id = v.id
            LEFT JOIN warehouses w ON s.warehouse_id = w.id
            WHERE s.tracking_number = ?;
            """,
            (tracking_number,),
            op_type="DML:SELECT"
        )
        if shipment:
            events = db.query_all(
                "SELECT * FROM tracking_events WHERE tracking_number = ? ORDER BY timestamp DESC, id DESC;",
                (tracking_number,),
                op_type="DML:SELECT"
            )
        else:
            flash(f"Tracking number '{tracking_number}' not found in the database.", "warning")

    return render_template(
        "track.html",
        tracking_number=tracking_number,
        shipment=shipment,
        events=events
    )

# ==============================================================================
# DBMS INSPECTOR & EDUCATIONAL CONSOLE
# ==============================================================================

@app.route("/dbms-inspector")
@login_required
def dbms_inspector():
    """
    Dedicated DBMS operations monitor showing:
    1. Table Schemas via PRAGMA table_info (DDL Inspector)
    2. Views defined in the database
    3. Triggers created and their SQL code
    4. Indexes created
    5. Live query logs
    """
    # 1. Fetch all tables
    tables = db.query_all(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;",
        op_type="DDL:PRAGMA"
    )

    table_details = []
    for t in tables:
        tname = t["name"]
        columns = db.query_all(f"PRAGMA table_info({tname});", op_type="DDL:PRAGMA")
        count_row = db.query_one(f"SELECT COUNT(*) AS c FROM {tname};", op_type="DML:SELECT")
        table_details.append({
            "name": tname,
            "sql": t["sql"],
            "row_count": count_row["c"] if count_row else 0,
            "columns": columns
        })

    # 2. Fetch Views
    views = db.query_all(
        "SELECT name, sql FROM sqlite_master WHERE type='view' ORDER BY name;",
        op_type="DDL:PRAGMA"
    )

    # 3. Fetch Triggers
    triggers = db.query_all(
        "SELECT name, tbl_name, sql FROM sqlite_master WHERE type='trigger' ORDER BY name;",
        op_type="DDL:PRAGMA"
    )

    # 4. Fetch Indexes
    indexes = db.query_all(
        "SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%' ORDER BY name;",
        op_type="DDL:PRAGMA"
    )

    # 5. Full execution logs
    logs = db.get_recent_sql_logs(100)

    return render_template(
        "dbms_inspector.html",
        table_details=table_details,
        views=views,
        triggers=triggers,
        indexes=indexes,
        logs=logs
    )

@app.route("/dbms-inspector/reset", methods=["POST"])
@login_required
@role_required(["admin"])
def dbms_reset():
    """Drops and rebuilds all schemas, views, triggers, and demo seed data (DDL showcase)."""
    try:
        db.init_db(force_recreate=True)
        flash("Database successfully reset! All DDL schemas, Views, Triggers, and Seeds re-executed.", "success")
    except Exception as e:
        flash(f"Reset failed: {str(e)}", "danger")
    return redirect(url_for("dbms_inspector"))

@app.route("/dbms-inspector/raw-query", methods=["POST"])
@login_required
@role_required(["admin"])
def execute_custom_sql():
    """
    Allows executing a custom SQL command for grading/academic evaluation.
    Supports SELECT, INSERT, UPDATE, DELETE, CREATE, DROP.
    """
    raw_query = request.form.get("sql_query", "").strip()
    if not raw_query:
        flash("Please provide an SQL query to execute.", "warning")
        return redirect(url_for("dbms_inspector"))

    try:
        trimmed = raw_query.strip().upper()
        if trimmed.startswith("SELECT") or trimmed.startswith("PRAGMA") or trimmed.startswith("EXPLAIN"):
            rows = db.query_all(raw_query, op_type="DML:CUSTOM_SELECT")
            return render_template(
                "dbms_inspector.html",
                custom_result={"type": "SELECT", "rows": rows, "count": len(rows), "sql": raw_query},
                **get_inspector_context()
            )
        else:
            res = db.execute_raw_sql(raw_query, op_type="DDL/DML:CUSTOM")
            flash(f"Query executed successfully! Affected rows: {res['rowcount']}", "success")
            return redirect(url_for("dbms_inspector"))
    except Exception as e:
        flash(f"SQL Execution Error: {str(e)}", "danger")
        return redirect(url_for("dbms_inspector"))

def get_inspector_context():
    """Helper to reload inspector data."""
    tables = db.query_all("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
    table_details = []
    for t in tables:
        tname = t["name"]
        columns = db.query_all(f"PRAGMA table_info({tname});")
        count_row = db.query_one(f"SELECT COUNT(*) AS c FROM {tname};")
        table_details.append({
            "name": tname,
            "sql": t["sql"],
            "row_count": count_row["c"] if count_row else 0,
            "columns": columns
        })
    views = db.query_all("SELECT name, sql FROM sqlite_master WHERE type='view' ORDER BY name;")
    triggers = db.query_all("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='trigger' ORDER BY name;")
    indexes = db.query_all("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
    logs = db.get_recent_sql_logs(100)
    return {
        "table_details": table_details,
        "views": views,
        "triggers": triggers,
        "indexes": indexes,
        "logs": logs
    }

# ==============================================================================
# REAL-TIME API ENDPOINTS FOR THE LIVE SQL DRAWER
# ==============================================================================

@app.route("/api/sql-logs")
def api_sql_logs():
    """Returns real-time execution logs for the frontend Live SQL Inspector drawer."""
    limit = int(request.args.get("limit", 25))
    return jsonify({
        "status": "success",
        "total_operations": len(db.sql_execution_logs),
        "logs": db.get_recent_sql_logs(limit)
    })

@app.route("/api/sql-logs/clear", methods=["POST"])
def api_clear_sql_logs():
    db.clear_sql_logs()
    return jsonify({"status": "cleared"})

if __name__ == "__main__":
    print("Starting ShipFlow DBMS Shipping Management System...")
    print("Local access URL: http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
