from datetime import datetime
import sqlite3
import math

DATABASE_NAME = "parking.db"

def create_database():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()

        # Vehicles tracking table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehicles(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_number TEXT,
            vehicle_type TEXT,
            owner_name TEXT,
            phone TEXT,
            slot_number INTEGER,
            entry_time TEXT,
            exit_time TEXT,
            parking_fee REAL,
            status TEXT
        )
        """)
        #user table 
        cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
           username TEXT UNIQUE,
           password TEXT
   )
    """)

        # Slots reference table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS parking_slots(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_number INTEGER UNIQUE,
            status TEXT
        )
        """)
        
        # Initialize 50 Slots
        TOTAL_SLOTS = 50
        cursor.execute("SELECT COUNT(*) FROM parking_slots")
        if cursor.fetchone()[0] == 0:
            slots = [(i, "Available") for i in range(1, TOTAL_SLOTS + 1)]
            cursor.executemany(
                "INSERT INTO parking_slots(slot_number, status) VALUES (?, ?)", 
                slots
            )

def get_dashboard_data():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM vehicles WHERE status='Parked'")
        total_active = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM parking_slots WHERE status='Available'")
        available = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM parking_slots WHERE status='Occupied'")
        occupied = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(parking_fee) FROM vehicles WHERE status='Exited'")
        revenue = cursor.fetchone()[0] or 0.0

        return total_active, available, occupied, revenue

def _get_available_slot_internal(cursor):
    cursor.execute("""
        SELECT slot_number FROM parking_slots 
        WHERE status='Available' ORDER BY slot_number ASC LIMIT 1
    """)
    result = cursor.fetchone()
    return result[0] if result else None

def save_vehicle(vehicle_number, vehicle_type, owner_name, phone):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        
        # CRITICAL: Prevent a vehicle from taking multiple slots if it's already parked
        cursor.execute("SELECT slot_number FROM vehicles WHERE vehicle_number=? AND status='Parked'", (vehicle_number,))
        already_parked = cursor.fetchone()
        if already_parked:
            return f"ALREADY_PARKED_AT_{already_parked[0]}"

        slot_number = _get_available_slot_internal(cursor)
        if slot_number is None:
            return False  # Parking full
            
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO vehicles 
            (vehicle_number, vehicle_type, owner_name, phone, slot_number, entry_time, status) 
            VALUES (?, ?, ?, ?, ?, ?, 'Parked')
        """, (vehicle_number, vehicle_type, owner_name, phone, slot_number, current_time))
        
        cursor.execute("UPDATE parking_slots SET status='Occupied' WHERE slot_number=?", (slot_number,))
        return slot_number

def vehicle_exit(vehicle_number):
    HOURLY_RATE = 40.0
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT slot_number, entry_time FROM vehicles 
            WHERE vehicle_number=? AND status='Parked' 
            ORDER BY id DESC LIMIT 1
        """, (vehicle_number,))
        result = cursor.fetchone()

        if not not result:
            slot_number, entry_time_str = result
            exit_time = datetime.now()
            exit_time_str = exit_time.strftime("%Y-%m-%d %H:%M:%S")
            
            entry_time = datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S")
            duration_hours = math.ceil((exit_time - entry_time).total_seconds() / 3600.0)
            parking_fee = max(1.0, duration_hours) * HOURLY_RATE

            cursor.execute("""
                UPDATE vehicles 
                SET status='Exited', exit_time=?, parking_fee=? 
                WHERE vehicle_number=? AND status='Parked'
            """, (exit_time_str, parking_fee, vehicle_number))

            cursor.execute("UPDATE parking_slots SET status='Available' WHERE slot_number=?", (slot_number,))
            return True
        return False

def get_all_slots_status():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT slot_number, status FROM parking_slots ORDER BY slot_number ASC")
        return cursor.fetchall()

def get_vehicle_history(vehicle_number=None):
    """Fetches full historical records or filters by a specific vehicle license plate."""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        if vehicle_number:
            cursor.execute("SELECT vehicle_number, vehicle_type, owner_name, slot_number, entry_time, exit_time, parking_fee, status FROM vehicles WHERE vehicle_number=? ORDER BY id DESC", (vehicle_number,))
        else:
            cursor.execute("SELECT vehicle_number, vehicle_type, owner_name, slot_number, entry_time, exit_time, parking_fee, status FROM vehicles ORDER BY id DESC")
        return cursor.fetchall()

def get_analytics_data():
    """Aggregates vehicle types and revenue distribution data for charting."""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        
        # Vehicle type counts
        cursor.execute("SELECT vehicle_type, COUNT(*) FROM vehicles GROUP BY vehicle_type")
        type_counts = cursor.fetchall()
        
        # Revenue by vehicle type
        cursor.execute("SELECT vehicle_type, SUM(parking_fee) FROM vehicles WHERE status='Exited' GROUP BY vehicle_type")
        revenue_distribution = cursor.fetchall()
        
        return type_counts, revenue_distribution

def register_user(username, password):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users(username, password) VALUES(?, ?)",
                (username, password)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
