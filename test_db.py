import db

def run_tests():
    print("=== Testing Database Schema & Operations ===")
    
    # 1. Test Tables
    tables = db.query_all("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    table_names = [t["name"] for t in tables]
    print(f"Tables created: {table_names}")
    assert "shipments" in table_names
    assert "users" in table_names
    assert "tracking_events" in table_names
    assert "customers" in table_names

    # 2. Test Views
    views = db.query_all("SELECT name FROM sqlite_master WHERE type='view'")
    print(f"Views created: {[v['name'] for v in views]}")
    active_deliveries = db.query_all("SELECT * FROM view_active_deliveries")
    print(f"Active deliveries via VIEW: {len(active_deliveries)} records")

    # 3. Test Triggers
    triggers = db.query_all("SELECT name FROM sqlite_master WHERE type='trigger'")
    print(f"Triggers created: {[t['name'] for t in triggers]}")

    # 4. Test Shipment insertion & Trigger verification
    cust = db.query_one("SELECT id, total_shipments FROM customers LIMIT 1")
    initial_shipments = cust["total_shipments"]
    
    t_num = db.generate_tracking_number()
    cost = db.calculate_shipping_cost(5.0, "Express")
    
    # Insert new shipment
    res = db.execute_raw_sql(
        """
        INSERT INTO shipments (
            tracking_number, customer_id, sender_name, recipient_name, recipient_phone,
            origin_city, origin_address, destination_city, destination_address,
            weight_kg, shipping_type, status, current_location, shipping_cost
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (t_num, cust["id"], "Test Sender", "Test Recipient", "+1 555-1234",
         "Boston", "10 Beacon St", "Austin", "500 Congress Ave",
         5.0, "Express", "Pending", "Boston Sorting Facility", cost),
        op_type="DML:INSERT"
    )
    shipment_id = res["lastrowid"]
    print(f"Created shipment ID: {shipment_id} with Tracking: {t_num}")

    # Verify customer counter trigger fired
    updated_cust = db.query_one("SELECT total_shipments FROM customers WHERE id = ?", (cust["id"],))
    print(f"Customer shipment count updated by trigger: {initial_shipments} -> {updated_cust['total_shipments']}")
    assert updated_cust["total_shipments"] == initial_shipments + 1

    # Test status update triggering audit
    db.execute_raw_sql(
        "UPDATE shipments SET status = 'In Transit', current_location = 'New York Terminal' WHERE id = ?;",
        (shipment_id,),
        op_type="DML:UPDATE"
    )
    
    events = db.query_all("SELECT * FROM tracking_events WHERE shipment_id = ?", (shipment_id,))
    print(f"Tracking events generated (including Trigger): {len(events)}")
    assert len(events) >= 1

    # Test TCL Transaction
    trans_ops = [
        ("UPDATE shipments SET status = 'Out for Delivery' WHERE id = ?", (shipment_id,), "DML:UPDATE"),
        ("INSERT INTO audit_logs (action, entity_name, entity_id, details) VALUES (?, ?, ?, ?)", 
         ("DISPATCH", "shipments", shipment_id, "Dispatched for final delivery"), "DML:INSERT")
    ]
    tcl_res = db.execute_tcl_transaction(trans_ops)
    print("TCL Transaction executed:", tcl_res["status"])

    # Test Live Logs
    logs = db.get_recent_sql_logs(5)
    print(f"Recent SQL logs logged: {len(logs)} entries. Latest type: {logs[0]['type']}")
    print("All DBMS Tests Passed Successfully!")

if __name__ == "__main__":
    run_tests()
