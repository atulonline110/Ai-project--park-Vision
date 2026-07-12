import time
import numpy as np
import pandas as pd
from PIL import Image
import streamlit as st
from ultralytics import YOLO

from database import (
    create_database, 
    get_dashboard_data, 
    save_vehicle, 
    vehicle_exit,
    get_all_slots_status,
    get_vehicle_history,
    get_analytics_data
)

@st.cache_resource
def load_yolo_model():
    return YOLO("yolov8n.pt")

model = load_yolo_model()

st.set_page_config(page_title="Smart Parking AI", page_icon="🚗", layout="wide")
create_database()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🚗 Smart Parking AI")
    st.subheader("Admin Login Portal")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login", use_container_width=True):
        if username == "admin" and password == "1234":
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Invalid Username or Password")
else:
    st.sidebar.title("Navigation Panel")
    page = st.sidebar.radio(
        "Select Page Menu",
        ["Dashboard", "Vehicle Entry", "Vehicle Exit", "AI Detection", "Parking Slots", "History Logs", "Analytics Graphs", "Logout"]
    )

    # --- DASHBOARD PAGE ---
    if page == "Dashboard":
        st.title("📊 Control Dashboard")
        total_active, available, occupied, revenue = get_dashboard_data()

        col1, col2 = st.columns(2)
        with col1:
            st.metric("🚗 Total Active Parked Vehicles", total_active)
            st.metric("🟢 Current Available Slots", available)
        with col2:
            st.metric("🔴 Occupied Slots Count", occupied)
            st.metric("💰 Collected Revenue Record", f"₹ {revenue:,.2f}")

    # --- VEHICLE ENTRY PAGE ---
    elif page == "Vehicle Entry":
        st.header("🚗 Process Parking Registration Entry")
        vehicle_input = st.text_input("Vehicle Number Input").strip().upper()
        vehicle_type = st.selectbox("Vehicle Classification Type", ["Car", "Bike", "Truck"])
        owner_name_input = st.text_input("Driver Name Reference")
        phone_input = st.text_input("Contact Number Reference")

        if st.button("Commit & Allocate Spot", type="primary"):
            if not vehicle_input:
                vehicle_number = f"AUTO-{int(time.time()) % 100000}"
                st.warning(f"No license input. Auto-generated identifier: **{vehicle_number}**")
            else:
                vehicle_number = vehicle_input

            owner_name = owner_name_input.strip() if owner_name_input.strip() else "Guest Driver"
            phone = phone_input.strip() if phone_input.strip() else "N/A"

            slot = save_vehicle(vehicle_number, vehicle_type, owner_name, phone)
            
            if isinstance(slot, str) and slot.startswith("ALREADY_PARKED"):
                allocated_slot = slot.split("_")[-1]
                st.error(f"❌ Entry Rejected: Vehicle **{vehicle_number}** is already actively parked in **Slot {allocated_slot}**.")
            elif slot:
                st.success(f"✅ Vehicle Assigned and Saved Successfully!")
                st.info(f"🅿️ **Assigned Location Spot:** Slot {slot}")
            else:
                st.error("❌ Allocation Failed: No accessible vacancy left.")

    # --- VEHICLE EXIT PAGE ---
    elif page == "Vehicle Exit":
        st.header("🚙 Process Exit Clearances")
        vehicle_number = st.text_input("Provide Departing Vehicle License Number").strip().upper()

        if st.button("Finalize Gate Release", type="primary"):
            if not vehicle_number:
                st.error("Please insert a vehicle plate number.")
            else:
                cleared = vehicle_exit(vehicle_number)
                if cleared:
                    st.success(f"✅ Record cleared. Slot allocated to {vehicle_number} is now vacant.")
                else:
                    st.error("❌ Error locating processing logs: Is this vehicle currently parked here?")

    # --- AI DETECTION PAGE ---
    elif page == "AI Detection":
        st.title("📷 Computer Vision Lot Space Assessment")
        uploaded_file = st.file_uploader("Upload Snapshot Reference", type=["jpg", "jpeg", "png"])

        if uploaded_file is not None:
            image = Image.open(uploaded_file).convert("RGB")
            results = model(np.array(image))
            st.image(results[0].plot(), caption="Processed AI Layout View", use_container_width=True)

            counts = {"car": 0, "bus": 0, "truck": 0, "motorcycle": 0}
            for box in results[0].boxes:
                name = model.names[int(box.cls[0])]
                if name in counts:
                    counts[name] += 1

            total_seen = sum(counts.values())
            st.subheader(f"Vision Summary Diagnostics (Total Seen: {total_seen})")
            col_metrics = st.columns(4)
            for i, (v_type, count) in enumerate(counts.items()):
                col_metrics[i].metric(v_type.title(), count)

    # --- PARKING SLOTS PAGE ---
    elif page == "Parking Slots":
        st.header("🅿️ Live Physical Slot Grid Layout")
        all_slots = get_all_slots_status()
        columns_per_row = 10
        for idx in range(0, len(all_slots), columns_per_row):
            subset = all_slots[idx : idx + columns_per_row]
            ui_cols = st.columns(columns_per_row)
            for structural_index, data_row in enumerate(subset):
                num, stat = data_row
                with ui_cols[structural_index]:
                    if stat == "Available":
                        st.success(f"🟢 **S-{num}**\nFree")
                    else:
                        st.error(f"🔴 **S-{num}**\nFull")

    # --- NEW: HISTORY LOGS PAGE ---
    elif page == "History Logs":
        st.header("📋 Vehicle Parking History Records")
        search_query = st.text_input("Search Filter by Vehicle Number (Optional)").strip().upper()
        
        history_data = get_vehicle_history(search_query if search_query else None)
        
        if history_data:
            df = pd.DataFrame(history_data, columns=[
                "Vehicle Number", "Type", "Owner Name", "Slot Number", "Entry Time", "Exit Time", "Fee Charged (₹)", "Status"
            ])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No matching historical records found.")

    # --- NEW: ANALYTICS GRAPHS PAGE ---
    elif page == "Analytics Graphs":
        st.header("📈 Data & Revenue Analytics Visualization")
        type_counts, revenue_dist = get_analytics_data()

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Distribution of Parked Vehicle Types")
            if type_counts:
                df_counts = pd.DataFrame(type_counts, columns=["Vehicle Type", "Total Registrations"])
                st.bar_chart(data=df_counts, x="Vehicle Type", y="Total Registrations", color="#1f77b4")
            else:
                st.info("Insufficient data to build frequency charts.")

        with col2:
            st.subheader("Revenue Contribution by Vehicle Type")
            # Filter None/Null revenue out
            clean_rev = [(t, r if r else 0.0) for t, r in revenue_dist]
            if clean_rev and sum(r for t, r in clean_rev) > 0:
                df_rev = pd.DataFrame(clean_rev, columns=["Vehicle Type", "Revenue (₹)"])
                st.bar_chart(data=df_rev, x="Vehicle Type", y="Revenue (₹)", color="#2ca02c")
            else:
                st.info("No collected revenue recorded yet to build charts.")

    # --- LOGOUT ---
    elif page == "Logout":
        st.session_state.logged_in = False
        st.rerun()