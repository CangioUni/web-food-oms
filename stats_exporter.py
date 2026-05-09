import argparse
import datetime
import os
import uuid
import sqlite3
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from fpdf import FPDF
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import collections

# Attempt to reuse main.py models. For standalone script, we need to bind the DB properly.
try:
    from main import Order, OrderItem, MenuItem, Category, engine
    SessionLocal = sessionmaker(bind=engine)
except ImportError:
    # Fallback to pure sqlite3 if main.py is not reachable or fails
    SessionLocal = None
    pass

class StatsExporter:
    def __init__(self, db_path="orders.db", session_factory=None):
        if session_factory:
            self.Session = session_factory
        else:
            self.engine = create_engine(f"sqlite:///{db_path}")
            self.Session = sessionmaker(bind=self.engine)

    def _get_business_day(self, dt):
        """
        Returns the business day date.
        If time is before 06:00, it belongs to the previous calendar day.
        """
        if dt.hour < 6:
            return (dt - datetime.timedelta(days=1)).date()
        return dt.date()

    def get_available_days(self):
        session = self.Session()
        from main import Order
        orders = session.query(Order.timestamp).all()
        session.close()

        days = set()
        for (ts,) in orders:
            if ts:
                # Handle potential string dates from sqlite
                if isinstance(ts, str):
                    try:
                        ts = datetime.datetime.fromisoformat(ts.split('.')[0])
                    except ValueError:
                        continue
                bday = self._get_business_day(ts)
                days.add(bday.isoformat())

        return sorted(list(days), reverse=True)

    def generate_stats(self, business_day_str):
        bday = datetime.date.fromisoformat(business_day_str)
        start_dt = datetime.datetime.combine(bday, datetime.time(6, 0))
        end_dt = start_dt + datetime.timedelta(hours=24) # 06:00 next day

        session = self.Session()
        from main import Order, OrderItem, MenuItem

        # We fetch all orders and filter in Python to handle SQLite datetime nuances cleanly
        all_orders = session.query(Order).all()
        day_orders = []
        for o in all_orders:
            ts = o.timestamp
            if isinstance(ts, str):
                try:
                    ts = datetime.datetime.fromisoformat(ts.split('.')[0])
                except ValueError:
                    continue
            if start_dt <= ts < end_dt:
                day_orders.append((o, ts))

        day_orders.sort(key=lambda x: x[1])

        stats = {
            "business_day": business_day_str,
            "total_orders": len(day_orders),
            "total_revenue": sum(o.total for o, _ in day_orders) if day_orders else 0.0,
            "revenue_by_payment": collections.defaultdict(float),
            "orders_over_time": {}, # 15 min intervals
            "items_sold": collections.defaultdict(int), # Item name -> quantity
            "items_by_category": collections.defaultdict(lambda: collections.defaultdict(int)),
            "burger_stats": {
                "total_burgers": 0,
                "total_menus": 0,
                "burger_types": collections.defaultdict(int)
            }
        }

        if not day_orders:
            session.close()
            return stats

        first_order_ts = day_orders[0][1]
        last_order_ts = day_orders[-1][1]

        # Round first to previous 15 min
        curr_time = first_order_ts.replace(minute=(first_order_ts.minute // 15) * 15, second=0, microsecond=0)
        end_time_rounded = last_order_ts.replace(minute=(last_order_ts.minute // 15) * 15, second=0, microsecond=0) + datetime.timedelta(minutes=15)

        # Initialize intervals
        intervals = []
        while curr_time <= end_time_rounded:
            intervals.append(curr_time)
            stats["orders_over_time"][curr_time.strftime("%H:%M")] = 0
            curr_time += datetime.timedelta(minutes=15)

        # Load menu items for classification
        menu_items_db = session.query(MenuItem).all()
        menu_dict = {m.description: m for m in menu_items_db}

        # Process Orders
        for o, ts in day_orders:
            stats["revenue_by_payment"][o.payment_method] += o.total

            interval_str = ts.replace(minute=(ts.minute // 15) * 15, second=0, microsecond=0).strftime("%H:%M")
            if interval_str in stats["orders_over_time"]:
                stats["orders_over_time"][interval_str] += 1

            for item in o.items:
                mi = menu_dict.get(item.description)
                base_cat = mi.category if mi else "varie"
                qty = getattr(item, "quantity", 1)

                # Count base item
                stats["items_sold"][item.description] += qty
                stats["items_by_category"][base_cat][item.description] += qty

                if mi and mi.category == "menu" and mi.is_combo:
                    stats["burger_stats"]["total_menus"] += qty

                if mi and mi.category == "panini" and not mi.is_combo:
                    stats["burger_stats"]["total_burgers"] += qty
                    stats["burger_stats"]["burger_types"][item.description] += qty

                # Parse combo choices
                if item.combo_choices:
                    choices = [c.strip() for c in item.combo_choices.split(',') if c.strip()]
                    for choice in choices:
                        stats["items_sold"][choice] += qty

                        c_mi = menu_dict.get(choice)
                        c_cat = c_mi.category if c_mi else "varie"
                        stats["items_by_category"][c_cat][choice] += qty

                        if c_mi and c_mi.category == "panini":
                            stats["burger_stats"]["total_burgers"] += qty
                            stats["burger_stats"]["burger_types"][choice] += qty

        session.close()
        return stats

    def export_to_excel(self, stats, filepath):
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Overview
            df_overview = pd.DataFrame([
                {"Metric": "Business Day", "Value": stats["business_day"]},
                {"Metric": "Total Orders", "Value": stats["total_orders"]},
                {"Metric": "Total Revenue", "Value": f"{stats['total_revenue']:.2f}"},
                {"Metric": "Total Menus Sold", "Value": stats["burger_stats"]["total_menus"]},
                {"Metric": "Total Burgers Made", "Value": stats["burger_stats"]["total_burgers"]}
            ])
            df_overview.to_excel(writer, sheet_name="Overview", index=False)

            # Revenue by Payment
            if stats["revenue_by_payment"]:
                df_pay = pd.DataFrame(list(stats["revenue_by_payment"].items()), columns=["Method", "Revenue"])
                df_pay.to_excel(writer, sheet_name="Revenue By Payment", index=False)

            # Orders Over Time
            if stats["orders_over_time"]:
                df_time = pd.DataFrame(list(stats["orders_over_time"].items()), columns=["Time", "Orders"])
                df_time.to_excel(writer, sheet_name="Orders Over Time", index=False)

            # Burger Stats
            if stats["burger_stats"]["burger_types"]:
                df_burgers = pd.DataFrame(list(stats["burger_stats"]["burger_types"].items()), columns=["Burger Type", "Quantity"])
                df_burgers.to_excel(writer, sheet_name="Burgers Detail", index=False)

            # Items by Category
            for cat, items in stats["items_by_category"].items():
                if items:
                    df_cat = pd.DataFrame(list(items.items()), columns=["Item", "Quantity"])
                    # Sheet names must be <= 31 chars
                    sheet_name = f"Cat_{cat}"[:31]
                    df_cat.to_excel(writer, sheet_name=sheet_name, index=False)

    def export_to_pdf(self, stats, filepath):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)

        pdf.cell(0, 10, f"Report for Business Day: {stats['business_day']}", ln=True, align="C")
        pdf.ln(10)

        # Overview Text
        pdf.set_font("Arial", '', 12)
        pdf.cell(0, 8, f"Total Orders: {stats['total_orders']}", ln=True)
        pdf.cell(0, 8, f"Total Revenue: EUR {stats['total_revenue']:.2f}", ln=True)
        pdf.cell(0, 8, f"Total Menus Sold: {stats['burger_stats']['total_menus']}", ln=True)
        pdf.cell(0, 8, f"Total Burgers Realized (inc. menu): {stats['burger_stats']['total_burgers']}", ln=True)
        pdf.ln(10)

        if not stats["total_orders"]:
            pdf.cell(0, 10, "No orders for this day.", ln=True)
            pdf.output(filepath)
            return

        # Generate Graphs
        os.makedirs("static/export", exist_ok=True)

        uid = uuid.uuid4().hex
        time_chart_path = f"static/export/temp_time_chart_{uid}.png"
        pay_chart_path = f"static/export/temp_pay_chart_{uid}.png"
        burger_chart_path = f"static/export/temp_burger_chart_{uid}.png"

        # 1. Orders Over Time Line Chart
        plt.figure(figsize=(10, 4))
        times = list(stats["orders_over_time"].keys())
        orders = list(stats["orders_over_time"].values())

        # Show only every Nth label if too many
        plt.plot(times, orders, marker='o', linestyle='-', color='b')
        plt.title('Orders Over Time (15 min intervals)')
        plt.xlabel('Time')
        plt.ylabel('Orders')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(time_chart_path)
        plt.close()

        pdf.image(time_chart_path, x=10, w=190)
        pdf.add_page()

        # 2. Revenue by Payment Pie Chart
        methods = list(stats["revenue_by_payment"].keys())
        revs = list(stats["revenue_by_payment"].values())
        if revs and sum(revs) > 0:
            plt.figure(figsize=(6, 6))
            plt.pie(revs, labels=methods, autopct='%1.1f%%', startangle=140)
            plt.title('Revenue by Payment Method')
            plt.savefig(pay_chart_path)
            plt.close()
            pdf.image(pay_chart_path, x=10, w=90)

        # 3. Burgers Pie Chart
        b_types = list(stats["burger_stats"]["burger_types"].keys())
        b_counts = list(stats["burger_stats"]["burger_types"].values())
        if b_counts and sum(b_counts) > 0:
            plt.figure(figsize=(6, 6))
            plt.pie(b_counts, labels=b_types, autopct='%1.1f%%', startangle=140)
            plt.title('Burgers Distribution')
            plt.savefig(burger_chart_path)
            plt.close()
            pdf.image(burger_chart_path, x=110, y=pdf.get_y(), w=90)

        pdf.ln(100) # Move past the side-by-side images

        # Category Tables
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "Items Sold by Category", ln=True)
        pdf.ln(5)

        pdf.set_font("Arial", '', 11)
        for cat, items in stats["items_by_category"].items():
            if not items:
                continue
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 8, f"Category: {cat.capitalize()}", ln=True)
            pdf.set_font("Arial", '', 11)
            for item_name, qty in sorted(items.items(), key=lambda x: -x[1]):
                pdf.cell(100, 6, item_name, border=1)
                pdf.cell(40, 6, str(qty), border=1, ln=True, align="R")
            pdf.ln(5)

        pdf.output(filepath)

        # Cleanup temp images
        for f in [time_chart_path, pay_chart_path, burger_chart_path]:
            if os.path.exists(f):
                os.remove(f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export Orders Statistics")
    parser.add_argument("--day", type=str, help="Business day in YYYY-MM-DD format. Defaults to most recent day.")
    args = parser.parse_args()

    exporter = StatsExporter()
    days = exporter.get_available_days()

    if not days:
        print("No orders found in database.")
        exit(0)

    target_day = args.day
    if not target_day:
        target_day = days[0]
        print(f"No day specified. Using most recent day with orders: {target_day}")
    elif target_day not in days:
        print(f"Warning: No orders found for {target_day}. Available days: {days}")

    stats = exporter.generate_stats(target_day)

    os.makedirs("static/export", exist_ok=True)

    excel_path = f"static/export/stats_{target_day}.xlsx"
    pdf_path = f"static/export/stats_{target_day}.pdf"

    exporter.export_to_excel(stats, excel_path)
    exporter.export_to_pdf(stats, pdf_path)

    print(f"Export successful!")
    print(f"Excel: {excel_path}")
    print(f"PDF: {pdf_path}")
