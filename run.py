"""
run.py - Single-command runner for ShipFlow DBMS Shipping Management System
"""

import os
import sys
import webbrowser
from app import app
import db

def main():
    print("=" * 70)
    print("   SHIPFLOW - RELATIONAL SHIPPING MANAGEMENT SYSTEM (DBMS)")
    print("=" * 70)
    print(" * Database: SQLite3 (Native Python, zero external DB installation)")
    print(" * Location: " + db.DB_FILE)
    print(" * Backend Operations: DDL, DML, TCL Transactions, Triggers, Views")
    print("-" * 70)
    print(" DEMO ACCOUNTS (Or use the 1-Click Quick Login buttons on the page):")
    print("   1. Administrator:  Username: admin       | Password: admin123")
    print("   2. Dispatcher:     Username: dispatcher  | Password: dispatch123")
    print("   3. Customer:       Username: customer    | Password: customer123")
    print("-" * 70)
    print(" SYSTEM CAPABILITIES:")
    print("   * Destination & Address Routing (DML UPDATE)")
    print("   * Shipping Status Milestones (DML UPDATE + DB Trigger Audit)")
    print("   * Atomic Shipment Booking (TCL Transaction: BEGIN / INSERT / COMMIT)")
    print("   * Live DBMS SQL Inspector Drawer (Real-time backend SQL monitoring)")
    print("   * Full DBMS Inspector Tab (Schemas, Views, Triggers, SQL Sandbox)")
    print("-" * 70)
    print(" Access URL: http://127.0.0.1:5000")
    print("=" * 70)
    
    # Run server
    app.run(host="127.0.0.1", port=5000, debug=True)

if __name__ == "__main__":
    main()
