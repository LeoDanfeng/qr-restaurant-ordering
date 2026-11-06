# Riverside Kitchen — Local QR Ordering MVP

A single-restaurant QR-code ordering web app. Customers scan a table QR code, browse the menu, build a cart and submit an order. Staff manage incoming orders, menu availability, tables and QR codes from a dashboard.

## Requirements
- Python 3.10+
- A modern browser

## Run locally

```bash
cd qr_restaurant_local
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
# .venv\\Scripts\\Activate.ps1

pip install -r requirements.txt
python app.py
```

Open:
- Customer menu: http://127.0.0.1:5000
- Staff dashboard: http://127.0.0.1:5000/admin

The database (`restaurant.db`) is created automatically and seeded with sample tables, categories and dishes.

## Test on a phone over the same Wi-Fi

1. Find your computer's local LAN IP (for example `192.168.1.20`).
2. Start the server with the public LAN address used by your phone:

```bash
# macOS / Linux
HOST=0.0.0.0 PORT=5000 HOST_URL=http://192.168.1.20:5000 python app.py
```

```powershell
# Windows PowerShell
$env:HOST="0.0.0.0"
$env:PORT="5000"
$env:HOST_URL="http://192.168.1.20:5000"
python app.py
```

3. Allow inbound TCP port 5000 in your computer firewall if prompted.
4. Open the dashboard from your computer at `http://127.0.0.1:5000/admin`.
5. Download each table QR code. The QR codes point to `HOST_URL/?table=<table_id>`.
6. Scan a QR code using a phone connected to the same Wi-Fi.

Replace the example IP with your computer's actual LAN IP. `HOST_URL` must be reachable from customer devices.

## Included functionality
- Mobile-friendly customer menu with category filters
- Cart quantity controls and kitchen notes
- Server-side price lookup and order validation (prices are never trusted from the browser)
- SQLite persistence
- Staff dashboard with automatic order refresh every 8 seconds
- Order status workflow: new → preparing → ready → served (also cancelled)
- Menu item creation and availability toggle
- Table creation, enable/disable, and per-table QR PNG download

## Important MVP limitations
- This is a local-development MVP, not a hardened public production service.
- No payment processing, tax/service-charge rules, printer integration, staff accounts, or customer accounts.
- The admin dashboard has no authentication. Keep it on a trusted local network only.
- Sample currency is displayed as Japanese yen; change the yen formatting and business rules if needed.
- Food images are intentionally represented by neutral placeholders in this first version.
- For public deployment, add HTTPS, authentication/authorization, CSRF protection, rate limiting, audit logs, backups, and a production WSGI server.

## Main project structure

```text
qr_restaurant_local/
├── app.py
├── requirements.txt
├── README.md
├── restaurant.db        # generated on first run
├── templates/
│   ├── index.html
│   └── admin.html
└── static/
    ├── customer.js
    ├── admin.js
    └── style.css
```
