from flask import Flask, render_template, request, jsonify, abort, send_file
from pathlib import Path
from io import BytesIO
import sqlite3, os
from datetime import datetime
import qrcode

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "restaurant.db"
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS tables (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, sort_order INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS menu_items (id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', price_cents INTEGER NOT NULL CHECK(price_cents >= 0), image_url TEXT NOT NULL DEFAULT '', available INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, table_id INTEGER REFERENCES tables(id), status TEXT NOT NULL DEFAULT 'new', note TEXT NOT NULL DEFAULT '', total_cents INTEGER NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS order_items (id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE, menu_item_id INTEGER, item_name TEXT NOT NULL, unit_price_cents INTEGER NOT NULL, quantity INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '');
        """)
        if conn.execute("SELECT COUNT(*) FROM tables").fetchone()[0] == 0:
            conn.executemany("INSERT INTO tables(name) VALUES (?)", [(f"Table {i}",) for i in range(1, 9)])
        if conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
            conn.executemany("INSERT INTO categories(name,sort_order) VALUES (?,?)", [("Main dishes",1),("Drinks",2),("Desserts",3)])
        if conn.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0] == 0:
            cats = {r["name"]:r["id"] for r in conn.execute("SELECT * FROM categories")}
            samples = [
                (cats["Main dishes"],"Classic cheeseburger","Beef patty, cheddar, lettuce and house sauce.",1290),
                (cats["Main dishes"],"Grilled chicken bowl","Grilled chicken, rice and seasonal vegetables.",1450),
                (cats["Main dishes"],"Margherita pizza","Tomato, mozzarella and fresh basil.",1390),
                (cats["Drinks"],"Iced tea","Freshly brewed tea served over ice.",390),
                (cats["Drinks"],"Sparkling water","Chilled sparkling mineral water.",300),
                (cats["Desserts"],"Chocolate brownie","Warm brownie with a soft chocolate center.",590)]
            conn.executemany("INSERT INTO menu_items(category_id,name,description,price_cents) VALUES (?,?,?,?)", samples)

@app.get("/")
def home(): return render_template("index.html")

@app.get("/api/menu")
def menu():
    with db() as conn:
        tables=[dict(r) for r in conn.execute("SELECT * FROM tables WHERE active=1 ORDER BY id")]
        categories=[dict(r) for r in conn.execute("SELECT * FROM categories ORDER BY sort_order,id")]
        items=[dict(r) for r in conn.execute("""SELECT m.*,c.name AS category_name FROM menu_items m LEFT JOIN categories c ON c.id=m.category_id WHERE m.available=1 ORDER BY c.sort_order,c.id,m.id""")]
    return jsonify(tables=tables,categories=categories,items=items)

@app.post("/api/orders")
def create_order():
    p=request.get_json(silent=True) or {}; table_id=p.get("table_id"); items=p.get("items") or []; note=str(p.get("note",""))[:500]
    if not table_id or not isinstance(items,list) or not items: return jsonify(error="Choose a table and add at least one item."),400
    with db() as conn:
        table=conn.execute("SELECT * FROM tables WHERE id=? AND active=1",(table_id,)).fetchone()
        if not table: return jsonify(error="That table is unavailable. Please scan its QR code again."),400
        normalized=[]; total=0
        for entry in items:
            try: item_id,qty=int(entry["item_id"]),int(entry["quantity"])
            except (KeyError,TypeError,ValueError): return jsonify(error="Invalid item in your order."),400
            if qty<1 or qty>30: return jsonify(error="Quantity must be between 1 and 30."),400
            item=conn.execute("SELECT * FROM menu_items WHERE id=? AND available=1",(item_id,)).fetchone()
            if not item: return jsonify(error="One of your selected dishes is no longer available."),409
            item_note=str(entry.get("note",""))[:250]; total+=item["price_cents"]*qty
            normalized.append((item["id"],item["name"],item["price_cents"],qty,item_note))
        cur=conn.execute("INSERT INTO orders(table_id,status,note,total_cents,created_at) VALUES (?,'new',?,?,?)",(table_id,note,total,datetime.now().isoformat(timespec="seconds")))
        order_id=cur.lastrowid
        conn.executemany("INSERT INTO order_items(order_id,menu_item_id,item_name,unit_price_cents,quantity,note) VALUES (?,?,?,?,?,?)",[(order_id,*row) for row in normalized])
    return jsonify(order_id=order_id,message="Your order has been sent to the restaurant."),201

@app.get("/api/orders")
def list_orders():
    with db() as conn:
        orders=[dict(r) for r in conn.execute("""SELECT o.*,t.name AS table_name FROM orders o LEFT JOIN tables t ON t.id=o.table_id ORDER BY CASE o.status WHEN 'new' THEN 0 WHEN 'preparing' THEN 1 ELSE 2 END,o.id DESC""")]
        for order in orders: order["items"]=[dict(r) for r in conn.execute("SELECT * FROM order_items WHERE order_id=? ORDER BY id",(order["id"],))]
    return jsonify(orders=orders)

@app.patch("/api/orders/<int:order_id>")
def update_order(order_id):
    status=(request.get_json(silent=True) or {}).get("status")
    if status not in ("new","preparing","ready","served","cancelled"): return jsonify(error="Unsupported order status."),400
    with db() as conn:
        cur=conn.execute("UPDATE orders SET status=? WHERE id=?",(status,order_id))
        if cur.rowcount==0: return jsonify(error="Order not found."),404
    return jsonify(ok=True)

@app.get("/admin")
def admin(): return render_template("admin.html")

@app.get("/api/admin/menu")
def admin_menu():
    with db() as conn:
        items=[dict(r) for r in conn.execute("SELECT m.*,c.name AS category_name FROM menu_items m LEFT JOIN categories c ON c.id=m.category_id ORDER BY m.id DESC")]
        categories=[dict(r) for r in conn.execute("SELECT * FROM categories ORDER BY sort_order,id")]
    return jsonify(items=items,categories=categories)

@app.post("/api/admin/menu")
def add_menu_item():
    p=request.get_json(silent=True) or {}
    try: name=str(p["name"]).strip(); price=int(round(float(p["price"])*100)); category_id=int(p["category_id"]) if p.get("category_id") else None
    except (KeyError,TypeError,ValueError): return jsonify(error="Enter a name and a valid price."),400
    if not name or price<0: return jsonify(error="Name and non-negative price are required."),400
    with db() as conn:
        cur=conn.execute("INSERT INTO menu_items(category_id,name,description,price_cents,image_url,available) VALUES (?,?,?,?,?,1)",(category_id,name,str(p.get("description",""))[:500],price,str(p.get("image_url",""))[:1000]))
    return jsonify(id=cur.lastrowid),201

@app.patch("/api/admin/menu/<int:item_id>")
def edit_menu_item(item_id):
    p=request.get_json(silent=True) or {}; fields={}
    if "available" in p: fields["available"]=1 if p["available"] else 0
    if "name" in p: fields["name"]=str(p["name"]).strip()[:120]
    if "description" in p: fields["description"]=str(p["description"])[:500]
    if "price" in p:
        try: fields["price_cents"]=int(round(float(p["price"])*100))
        except (ValueError,TypeError): return jsonify(error="Invalid price."),400
    if not fields: return jsonify(error="No changes supplied."),400
    assignments=",".join(f"{k}=?" for k in fields)
    with db() as conn: cur=conn.execute(f"UPDATE menu_items SET {assignments} WHERE id=?",(*fields.values(),item_id))
    if cur.rowcount==0: return jsonify(error="Menu item not found."),404
    return jsonify(ok=True)

@app.get("/api/tables")
def get_tables():
    with db() as conn: rows=[dict(r) for r in conn.execute("SELECT * FROM tables ORDER BY id")]
    return jsonify(tables=rows)

@app.post("/api/tables")
def add_table():
    name=str((request.get_json(silent=True) or {}).get("name","")).strip()[:80]
    if not name: return jsonify(error="Enter a table name."),400
    try:
        with db() as conn: cur=conn.execute("INSERT INTO tables(name) VALUES (?)",(name,))
        return jsonify(id=cur.lastrowid),201
    except sqlite3.IntegrityError: return jsonify(error="That table name already exists."),409

@app.patch("/api/tables/<int:table_id>")
def toggle_table(table_id):
    p=request.get_json(silent=True) or {}
    with db() as conn: cur=conn.execute("UPDATE tables SET active=? WHERE id=?",(1 if p.get("active") else 0,table_id))
    if cur.rowcount==0: return jsonify(error="Table not found."),404
    return jsonify(ok=True)

@app.get("/qr/<int:table_id>.png")
def table_qr(table_id):
    with db() as conn: table=conn.execute("SELECT * FROM tables WHERE id=?",(table_id,)).fetchone()
    if not table: abort(404)
    base=os.environ.get("HOST_URL",request.host_url.rstrip("/")); url=f"{base}/?table={table_id}"
    qr=qrcode.QRCode(box_size=10,border=3); qr.add_data(url); qr.make(fit=True)
    image=qr.make_image(fill_color="black",back_color="white"); buf=BytesIO(); image.save(buf,format="PNG"); buf.seek(0)
    return send_file(buf,mimetype="image/png",download_name=f"{table['name'].replace(' ','-')}-qr.png")

@app.get("/health")
def health(): return jsonify(status="ok")

if __name__=="__main__":
    init_db(); host=os.environ.get("HOST","0.0.0.0"); port=int(os.environ.get("PORT","5000"))
    print(f"Restaurant ordering app running at http://127.0.0.1:{port}")
    app.run(host=host,port=port,debug=False)
