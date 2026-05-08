from fastapi import FastAPI, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import text
import datetime
from fpdf import FPDF
from escpos.printer import Network
import socket

DATABASE_URL = "sqlite:///./orders.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Models ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    printer_ip = Column(String)
    active_cart = Column(String, default="[]")
    active_state = Column(String, default="{}")

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)

class MenuItem(Base):
    __tablename__ = "menu_items"
    id = Column(Integer, primary_key=True)
    description = Column(String)
    price = Column(Float)
    image_url = Column(String)
    category = Column(String, default="burgers")
    components = Column(String, default="")
    additions = Column(String, default="")
    is_combo = Column(Boolean, default=False)
    combo_items = Column(String, default="[]")

class SystemSettings(Base):
    __tablename__ = "system_settings"
    id = Column(Integer, primary_key=True)
    bill_printer_ip = Column(String)
    kitchen_printer_ip = Column(String)
    auto_print = Column(Boolean, default=True)
    next_order_number = Column(Integer, default=1)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_number = Column(String, default="")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    total = Column(Float)
    discount = Column(Float)
    payment_method = Column(String)
    takeaway = Column(Boolean)
    table_number = Column(String)
    user_id = Column(Integer, ForeignKey('users.id'))
    notes = Column(String, default="")
    items = relationship("OrderItem", backref="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'))
    description = Column(String)
    quantity = Column(Integer)
    price_at_sale = Column(Float)
    notes = Column(String)
    ingredients = Column(String)
    combo_choices = Column(String, default="")

Base.metadata.create_all(bind=engine)

# Add column 'additions' if missing
from sqlalchemy import inspect
inspector = inspect(engine)
if "menu_items" in inspector.get_table_names():
    columns = [c["name"] for c in inspector.get_columns("menu_items")]
    if "additions" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE menu_items ADD COLUMN additions VARCHAR DEFAULT ''"))

if "users" in inspector.get_table_names():
    user_columns = [c["name"] for c in inspector.get_columns("users")]
    with engine.begin() as conn:
        if "active_cart" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN active_cart VARCHAR DEFAULT '[]'"))
        if "active_state" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN active_state VARCHAR DEFAULT '{}'"))

if "system_settings" in inspector.get_table_names():
    ss_columns = [c["name"] for c in inspector.get_columns("system_settings")]
    with engine.begin() as conn:
        if "next_order_number" not in ss_columns:
            conn.execute(text("ALTER TABLE system_settings ADD COLUMN next_order_number INTEGER DEFAULT 1"))

if "orders" in inspector.get_table_names():
    order_columns = [c["name"] for c in inspector.get_columns("orders")]
    with engine.begin() as conn:
        if "order_number" not in order_columns:
            conn.execute(text("ALTER TABLE orders ADD COLUMN order_number VARCHAR DEFAULT ''"))
            conn.execute(text("UPDATE orders SET order_number = CAST(id AS VARCHAR) WHERE order_number = ''"))



# --- Initial Seeding ---
db = SessionLocal()
if not db.query(User).first():
    db.add_all([User(id=i, name=f"Staff {i}", printer_ip=f"192.168.1.10{i}") for i in range(1, 6)])
    db.add_all([
        Category(name="menu"),
        Category(name="panini"),
        Category(name="contorni"),
        Category(name="bibite"),
        Category(name="dolci")
    ])
    # For local images, replace 'https://placehold.co/...' with '/static/images/your_file.jpg'
    db.add_all([
        MenuItem(description="Panino Classico", price=9.00, image_url="/static/images/burger_classico.png", category="panini", components="Pane,Hamburger,Pomodoro,Insalata"),
        MenuItem(description="Panino Sportivo", price=9.00, image_url="https://placehold.co/400x300?text=Panino+Sportivo", category="panini", components="Pane,Cotoletta,Pomodoro,Insalata"),
        MenuItem(description="Panino Leggero", price=7.00, image_url="https://placehold.co/400x300?text=Panino+Leggero", category="panini", components="Pane,Hamburger Vegetale,Pomodoro,Insalata"),
        MenuItem(description="Menu Classico", price=14.00, image_url="https://placehold.co/400x300?text=Menu+Classico", category="menu", is_combo=True, combo_items='[["Panino Classico"], ["Patatine"], ["Coca Cola", "Birra", "Acqua"]]'),
        MenuItem(description="Menu Sportivo", price=14.00, image_url="https://placehold.co/400x300?text=Menu+Sportivo", category="menu", is_combo=True, combo_items='[["Panino Sportivo"], ["Patatine"], ["Coca Cola", "Birra", "Acqua"]]'),
        MenuItem(description="Menu Leggero", price=12.00, image_url="https://placehold.co/400x300?text=Menu+Supereroe", category="menu", is_combo=True, combo_items='[["Panino Leggero"], ["Patatine"], ["Coca Cola", "Birra", "Acqua"]]'),
        MenuItem(description="Patatine", price=4.00, image_url="https://placehold.co/400x300?text=Patatine", category="contorni", components=""),
        MenuItem(description="Acqua Nat", price=1.00, image_url="/static/images/acqua.png", category="bibite", components=""),
        MenuItem(description="Acqua Gas", price=1.00, image_url="/static/images/acqua.png", category="bibite", components=""),
        MenuItem(description="Coca Cola", price=3.00, image_url="/static/images/cola.png", category="bibite", components=""),
        MenuItem(description="Birra", price=4.00, image_url="/static/images/birra.png", category="bibite", components=""),
        MenuItem(description="Donut", price=5.00, image_url="/static/images/donut.png", category="dolci", components="")
    ])
    settings = SystemSettings(id=1, bill_printer_ip="10.0.0.200", kitchen_printer_ip="10.0.0.200")
    db.add(settings)
    db.commit()
db.close()

def build_header_row(label: str, value: str, width: int = 48) -> str:
    """Return a left/right aligned string padded to `width` characters."""
    spaces = width - len(label) - len(value)
    return label + " " * max(spaces, 1) + value

def print_to_escpos(order_id: int, payload: dict):
    db = SessionLocal()
    settings = db.query(SystemSettings).first()
    db.close()
    
    printer_ip = settings.bill_printer_ip if settings and settings.bill_printer_ip else "10.0.0.200"
    port = 9100
    
    try:
        p = Network(printer_ip, port, profile="KR-306")
        p._raw(b'\x1b\x74\x13') # CP 858
        
        # Logo
        try:
            p.image("rblogo.png", center=True)
        except Exception as e:
            print(f"Logo print error: {e}")
            pass

        # Group header
        p.set(align="center", bold=True, normal_textsize=True)
        p.text("Gruppo Scout\n")
        p.text("VILLAFRANCA DI FORLI' 1\n")
        p.set(align="center", bold=False)
        p.text("Via Lughese 269\n")
        p.text("47122, FORLI' (FC)\n")
        p.text("\n")
        
        # Column header
        p.set(align="left", double_height=True)
        header = build_header_row("DESCRIZIONE", "Prezzo (\xd5)", 48) 
        p.text(header + "\n\n")
        p.set(normal_textsize=True)
        
        # Line items
        p.set(align="left")
        
        gross_total = 0.0
        
        grouped_items = []
        for item in payload.get('items', []):
            desc = item.get('description', '')
            price = float(item.get('price', 0))
            combo_choices = item.get('combo_choices', '')
            notes = item.get('notes', '')
            ingredients = item.get('ingredients', '')
            
            is_groupable = not combo_choices and not notes and not ingredients
            
            if is_groupable:
                found = False
                for g in grouped_items:
                    if g['groupable'] and g['description'] == desc and g['price'] == price:
                        g['qty'] += 1
                        found = True
                        break
                if not found:
                    grouped_items.append({
                        'groupable': True, 'description': desc, 'price': price,
                        'qty': 1, 'combo_choices': '', 'notes': '', 'ingredients': ''
                    })
            else:
                grouped_items.append({
                    'groupable': False, 'description': desc, 'price': price,
                    'qty': 1, 'combo_choices': combo_choices, 'notes': notes, 'ingredients': ingredients
                })
                
        for item in grouped_items:
            desc = item['description']
            price = item['price']
            qty = item['qty']
            item_total = price * qty
            gross_total += item_total
            
            if qty > 1:
                p.text(f"{qty} x {price:.2f}".replace('.', ',') + "\n")
                p.text(build_header_row(desc, f"{item_total:.2f}".replace('.', ','), 48) + "\n")
            else:
                p.text(build_header_row(desc, f"{price:.2f}".replace('.', ','), 48) + "\n")
            
            combo_choices = item['combo_choices']
            if combo_choices:
                for sub in combo_choices.split(','):
                    sub_clean = sub.strip()
                    if sub_clean:
                        p.text(" - " + sub_clean + "\n")
                        
        # Separator
        p.text("-" * 48 + "\n")
        
        # Total
        p.set(align="left", double_height=True)
        total_str = f"{gross_total:.2f}".replace('.', ',')
        p.text(build_header_row("TOTALE", total_str, 48) + "\n")
        p.set(normal_textsize=True)
        
        # Footer
        p.set(align="center")
        now = datetime.datetime.now()
        p.text(f"\n{now.strftime('%d-%m-%Y  %H:%M')}\n")
        p.text(f"DOCUMENTO N. {order_id:03d}\n")
        p.text("\nSCONTRINO NON FISCALE\n\n")
        
        p.cut()
        p.close()
    except Exception as e:
        print(f"Error printing bill: {e}")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

class SettingsUpdate(BaseModel):
    bill_printer_ip: str
    kitchen_printer_ip: str
    auto_print: bool
    next_order_number: int

@app.get("/settings")
def get_settings():
    db = SessionLocal()
    settings = db.query(SystemSettings).first()
    db.close()
    if settings:
        return {"bill_printer_ip": settings.bill_printer_ip, "kitchen_printer_ip": settings.kitchen_printer_ip, "auto_print": settings.auto_print, "next_order_number": settings.next_order_number}
    return {"bill_printer_ip": "", "kitchen_printer_ip": "", "auto_print": True, "next_order_number": 1}

@app.post("/settings")
def update_settings(payload: SettingsUpdate):
    db = SessionLocal()
    try:
        settings = db.query(SystemSettings).first()
        if not settings:
            settings = SystemSettings(id=1)
            db.add(settings)
        settings.bill_printer_ip = payload.bill_printer_ip
        settings.kitchen_printer_ip = payload.kitchen_printer_ip
        settings.auto_print = payload.auto_print
        settings.next_order_number = payload.next_order_number
        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/test-printer")
def test_printer(ip: str, port: int = 9100):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        result = sock.connect_ex((ip, int(port)))
        sock.close()
        
        if result == 0:
            return {"status": "success", "message": f"Stampante raggiungibile su {ip}:{port}"}
        else:
            return {"status": "error", "message": f"Impossibile connettersi a {ip}:{port}"}
    except Exception as e:
        return {"status": "error", "message": f"Errore: {str(e)}"}

@app.get("/users")
def get_users():
    db = SessionLocal()
    users = db.query(User).all()
    db.close()
    return users

class UserStateUpdate(BaseModel):
    active_cart: str
    active_state: str

@app.get("/users/{user_id}/cart")
def get_user_cart(user_id: int):
    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    db.close()
    if user:
        return {"active_cart": user.active_cart or "[]", "active_state": user.active_state or "{}"}
    return {"active_cart": "[]", "active_state": "{}"}

@app.post("/users/{user_id}/cart")
def update_user_cart(user_id: int, payload: UserStateUpdate):
    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.active_cart = payload.active_cart
        user.active_state = payload.active_state
        db.commit()
    db.close()
    return {"status": "success"}

@app.get("/menu")
def get_menu():
    db = SessionLocal()
    items = db.query(MenuItem).all()
    db.close()
    return items

class CategoryCreate(BaseModel):
    name: str

class MenuItemCreate(BaseModel):
    description: str
    price: float
    image_url: str
    category: str
    components: str
    additions: str = ""
    is_combo: bool = False
    combo_items: str = "[]"

@app.get("/categories")
def get_categories():
    db = SessionLocal()
    cats = db.query(Category).all()
    db.close()
    return cats

@app.post("/categories")
def create_category(payload: CategoryCreate):
    db = SessionLocal()
    cat = Category(name=payload.name)
    db.add(cat)
    db.commit()
    db.close()
    return {"status": "success"}

@app.delete("/categories/{cat_id}")
def delete_category(cat_id: int):
    db = SessionLocal()
    db.query(Category).filter(Category.id == cat_id).delete()
    db.commit()
    db.close()
    return {"status": "success"}

@app.post("/menu")
def create_menu_item(payload: MenuItemCreate):
    db = SessionLocal()
    item = MenuItem(**payload.dict())
    db.add(item)
    db.commit()
    db.close()
    return {"status": "success"}

@app.delete("/menu/{item_id}")
def delete_menu_item(item_id: int):
    db = SessionLocal()
    db.query(MenuItem).filter(MenuItem.id == item_id).delete()
    db.commit()
    db.close()
    return {"status": "success"}

@app.put("/menu/{item_id}")
def update_menu_item(item_id: int, payload: MenuItemCreate):
    db = SessionLocal()
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if item:
        item.description = payload.description
        item.price = payload.price
        item.image_url = payload.image_url
        item.category = payload.category
        item.components = payload.components
        item.additions = payload.additions
        item.is_combo = payload.is_combo
        item.combo_items = payload.combo_items
        db.commit()
    db.close()
    return {"status": "success"}

@app.post("/order")
def create_order(payload: dict = Body(...)):
    db = SessionLocal()
    try:
        kwargs = {
            'total': payload['total'],
            'discount': payload['discount'],
            'payment_method': payload['payment_method'],
            'takeaway': payload['takeaway'],
            'table_number': payload['table_number'],
            'user_id': payload['user_id'],
            'notes': payload.get('notes', '')
        }
        
        settings = db.query(SystemSettings).first()
        if not settings:
            settings = SystemSettings(id=1, auto_print=True, next_order_number=1)
            db.add(settings)
            db.flush()

        custom_id = payload.get('order_id')
        if custom_id:
            kwargs['order_number'] = str(custom_id)
        else:
            kwargs['order_number'] = str(settings.next_order_number)
            settings.next_order_number += 1
            
        new_order = Order(**kwargs)
        db.add(new_order)
        db.flush()

        for item in payload['items']:
            order_item = OrderItem(
                order_id=new_order.id,
                description=item['description'],
                quantity=1,
                price_at_sale=item['price'],
                notes=item.get('notes', ''),
                ingredients=item.get('ingredients', ''),
                combo_choices=item.get('combo_choices', '')
            )
            db.add(order_item)
        
        db.commit()
        order_number_str = new_order.order_number
        
        auto_print_enabled = settings.auto_print if settings else True
        if auto_print_enabled:
            print_to_escpos(order_number_str, payload)
        
        return {"status": "success", "order_id": order_number_str, "auto_print": auto_print_enabled}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/orders")
def get_orders():
    db = SessionLocal()
    orders = db.query(Order).order_by(Order.id.desc()).all()
    res = []
    for o in orders:
        items = [{"description": i.description, "price_at_sale": i.price_at_sale, "notes": i.notes, "ingredients": i.ingredients, "combo_choices": i.combo_choices or ""} for i in o.items]
        res.append({"id": o.order_number or str(o.id), "total": o.total, "discount": o.discount, "timestamp": o.timestamp, "items": items, "takeaway": o.takeaway, "table_number": o.table_number, "notes": o.notes})
    db.close()
    return res

@app.get("/export/menu_json")
def export_menu_json():
    db = SessionLocal()
    categories = db.query(Category).all()
    items = db.query(MenuItem).all()
    db.close()
    return {
        "categories": [{"name": c.name} for c in categories],
        "items": [
            {
                "description": i.description,
                "price": i.price,
                "image_url": i.image_url,
                "category": i.category,
                "components": i.components,
                "additions": i.additions,
                "is_combo": i.is_combo,
                "combo_items": i.combo_items
            } for i in items
        ]
    }

class ImportMenuPayload(BaseModel):
    mode: str
    data: dict

@app.post("/import/menu_json")
def import_menu_json(payload: ImportMenuPayload):
    db = SessionLocal()
    try:
        data = payload.data
        if not isinstance(data, dict):
             raise Exception("Invalid JSON format: root is not an object")
             
        cats = data.get("categories", [])
        items = data.get("items", [])
        
        if payload.mode == "replace":
            db.execute(text("DELETE FROM menu_items"))
            db.execute(text("DELETE FROM sqlite_sequence WHERE name='menu_items'"))
            db.execute(text("DELETE FROM categories"))
            db.execute(text("DELETE FROM sqlite_sequence WHERE name='categories'"))
            db.commit()

        existing_names = {name for (name,) in db.query(Category.name).all()}
            
        for c in cats:
            c_name = c.get("name")
            if c_name and c_name not in existing_names:
                db.add(Category(name=c_name))
                existing_names.add(c_name)
                
        for i in items:
            new_item = MenuItem(
                description=i.get("description", ""),
                price=i.get("price", 0.0),
                image_url=i.get("image_url", ""),
                category=i.get("category", ""),
                components=i.get("components", ""),
                additions=i.get("additions", ""),
                is_combo=i.get("is_combo", False),
                combo_items=i.get("combo_items", "[]")
            )
            db.add(new_item)
            
        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@app.delete("/orders")
def delete_all_orders():
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM order_items"))
        db.execute(text("DELETE FROM sqlite_sequence WHERE name='order_items'"))
        db.execute(text("DELETE FROM orders"))
        db.execute(text("DELETE FROM sqlite_sequence WHERE name='orders'"))
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
    return {"status": "success"}

@app.get("/export/orders")
def export_orders():
    db = SessionLocal()
    orders = db.query(Order).order_by(Order.id.asc()).all()
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=16)
    
    pdf.cell(200, 10, txt="Orders Report", ln=True, align='C')
    pdf.ln(5)
    
    for o in orders:
        pdf.set_font("Arial", 'B', 11)
        table_str = f" - Tavolo: {o.table_number}" if o.table_number and o.table_number.lower() != "nessuno" else ""
        pdf.cell(200, 10, txt=f"Order #{o.id} - Date: {o.timestamp} - Total: EUR {o.total:.2f} (Discount: EUR {o.discount:.2f}){table_str}", ln=True)
        pdf.set_font("Arial", '', 10)
        for i in o.items:
            ingr_str = f" [{i.ingredients}]" if i.ingredients else ""
            notes_str = f" (Note: {i.notes})" if i.notes else ""
            pdf.cell(200, 8, txt=f"    - {i.description}{ingr_str}{notes_str} : EUR {i.price_at_sale:.2f}", ln=True)
            if i.combo_choices:
                for choice in i.combo_choices.split(','):
                    pdf.cell(200, 6, txt=f"        > {choice.strip()}", ln=True)
        if hasattr(o, 'notes') and o.notes:
            pdf.set_font("Arial", 'I', 10)
            pdf.cell(200, 8, txt=f"    * Note Ordine: {o.notes}", ln=True)
        pdf.ln(3)
        
    db.close()
    pdf_path = "static/orders_export.pdf"
    pdf.output(pdf_path)
    return FileResponse(pdf_path, filename="orders_export.pdf", media_type='application/pdf')