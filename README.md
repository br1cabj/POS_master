# CloudPOS

A desktop Point of Sale system built with Python and CustomTkinter. Designed for small and medium businesses, with multi-tenant support, license management, and optional cloud sync.

## Features

- **Sales** — fast checkout with barcode support, combos, and wholesale pricing
- **Cash management** — opening/closing shifts, cash drawer tracking
- **Inventory** — articles, stock movements, kardex, low-stock alerts
- **Pricing** — bulk price updates, dollar-rate-based pricing, label printing
- **Purchases** — supplier orders, stock entry, supplier returns
- **Customers** — customer accounts, credit (fiado), quotations
- **Reports** — closing reports, sales history, stock history, Excel export
- **Users** — role-based access (admin / cashier), employee management
- **Data sync** — import/export, optional cloud sync via REST API
- **License system** — trial period, activation codes, license renewal

## Tech Stack

| Layer | Technology |
|---|---|
| UI | [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) 5.x |
| ORM | [SQLAlchemy](https://www.sqlalchemy.org/) 2.x |
| Database | SQLite (local) |
| PDF | fpdf2 |
| Charts | Matplotlib |
| Spreadsheets | Pandas + openpyxl |
| Barcodes | python-barcode |
| Auth | bcrypt |
| Build | PyInstaller |

## Requirements

- Python 3.10+
- Windows (primary target; CustomTkinter works on macOS/Linux too)

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/br1cabj/POS_master.git
cd POS_master

# 2. Create a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env if needed (defaults work for local SQLite)

# 5. Run
python main.py
```

On first launch a setup wizard will guide you through creating the initial tenant, branch, and admin user.

## Project Structure

```
POS_master/
├── controllers/        # Business logic (one file per domain)
├── views/              # CustomTkinter UI screens
├── database/
│   ├── models.py       # SQLAlchemy ORM models
│   └── migrations.py   # Schema migration runner
├── core/
│   ├── context.py      # Shared AppContext passed through the app
│   └── base_view.py    # Base class for all views
├── utils/              # Config, styles, label printing, shared helpers
├── main.py             # Entry point and app lifecycle
├── requirements.txt
└── .env.example        # Environment variable template
```

## Building a standalone executable

```bash
pip install pyinstaller
pyinstaller CloudPOS.spec --clean
# Output: dist/CloudPOS/CloudPOS.exe
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///pos_system.db` | SQLAlchemy database URL |
| `CLOUD_ENDPOINT` | — | REST endpoint for cloud sync (optional) |
| `CLOUD_API_KEY` | — | API key for cloud sync (optional) |
| `service_role` | — | Supabase service role key (optional) |

Copy `.env.example` to `.env` and fill in values. Never commit `.env`.

## License

Private / proprietary. All rights reserved.
