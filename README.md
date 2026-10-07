# CloudPOS

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Node Version](https://img.shields.io/badge/node-18%2B-green.svg)
![License](https://img.shields.io/badge/license-Proprietary-red.svg)
![UI](https://img.shields.io/badge/UI-CustomTkinter%20%7C%20React-blueviolet)

A professional desktop Point of Sale (POS) system built with Python and CustomTkinter, accompanied by a modern Web Dashboard built with React. Designed for small and medium businesses, featuring multi-tenant support, robust local-first architecture, license management, and optional real-time cloud synchronization.

## Latest delivery

This release focuses on transaction integrity, cloud-dashboard hardening, and reliable product labels.

- **Safer operations:** strengthened validation around sales, returns, supplier returns, quotations, inventory movements, and open cash sessions.
- **Secure cloud dashboard:** database-enforced tenant isolation, expiring web sessions, login rate limiting, and no embedded cloud database URL in the desktop client.
- **Professional labels:** validated EAN/UPC and Code128 barcodes, persisted internal codes, driver-based printing, five redesigned templates, and a live preview rendered from the exact PDF page sent to the printer.
- **Web administration:** refreshed session handling, authorization behavior, and dashboard/customer-ledger views.
- **Database baseline:** new installations use a versioned, tenant-safe schema with composite foreign keys, constrained document states, per-warehouse sale attribution, and inventory uniqueness by batch/location. SQLite stays local to one installation; it is never opened through a shared network folder.

See [CHANGELOG.md](CHANGELOG.md) for implementation notes and upgrade considerations.

## 📸 Screenshots

> **Note:** Add your screenshots here to showcase the UI.
>
> | Desktop POS (CustomTkinter) | Web Dashboard (React) |
> | :---: | :---: |
> | *(img/desktop-pos.png)* | *(img/web-dashboard.png)* |

## ✨ Features

- **Sales & Checkout** — Fast processing with barcode scanner support, custom combos, and dynamic wholesale pricing.
- **Cash Management** — Shift opening/closing workflows and granular cash drawer tracking.
- **Inventory Control** — Article management, stock movements, Kardex, and automated low-stock alerts.
- **Dynamic Pricing** — Bulk price updates, automatic dollar-rate conversions, and physical label printing.
- **Purchases & Suppliers** — Supplier orders, stock entry logging, and supplier return management.
- **CRM** — Customer accounts, credit lines (fiado), and quotation generation.
- **Analytics & Reports** — End-of-day closing reports, sales/stock history, and Excel exports.
- **Access Control** — Role-based access (Admin / Cashier) with secure employee session management.
- **Hybrid Data Sync** — Local-first SQLite operations with optional synchronization to private PostgreSQL on your VPS.
- **Web Dashboard** — Modern React-based remote administration panel with rich ApexCharts analytics.
- **License System** — Secure trial periods, encrypted activation codes, and license renewals.

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| **Desktop UI** | [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) 5.x |
| **Web UI** | React + Vite + Bootstrap Icons |
| **ORM** | [SQLAlchemy](https://www.sqlalchemy.org/) 2.x |
| **Database** | SQLite (Local) / PostgreSQL privado (VPS) |
| **PDF Generation** | fpdf2 |
| **Data Visualization** | Matplotlib (Desktop) / ApexCharts (Web) |
| **Spreadsheets** | Pandas + openpyxl |
| **Security** | bcrypt |
| **Build & Bundle** | PyInstaller (Desktop) |

## 🚀 Setup & Installation

### Prerequisites
- Python 3.10+
- Node.js 18+ (for Web Dashboard)
- Windows (primary target; easily adaptable to macOS/Linux)

### 1. Desktop App (Local Environment)

```bash
# Clone the repository
git clone https://github.com/br1cabj/POS_master.git
cd POS_master

# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# Install Python dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Open .env and adjust variables (default works for local-only testing)

# Launch the POS App
python main.py
```
*On first launch, a Setup Wizard will guide you through creating the initial tenant, branch, and admin user.*

### 2. Web Dashboard (Remote Admin)

```bash
# Navigate to the web application directory
cd web-dashboard

# Install Node.js dependencies
npm install

# Start the development server
npm run dev
```

## 🧪 Testing & Quality Assurance

This project maintains automated tests to ensure business logic integrity. 

```bash
# Run the test suite using pytest
pytest tests/ -v
```

The label flow is covered by controller tests. The in-app preview is intentionally generated from the same PDF page used for printing, so offers, pricing, logos, barcodes, and the Dual layout cannot drift apart.

For the web dashboard:

```bash
cd web-dashboard
npm run build
npm audit
```

## 📂 Architecture & Project Structure

The project follows a modular, domain-driven design, cleanly separating business logic from UI components.

```
POS_master/
├── controllers/        # Business logic & Database transactions (Domain-driven)
├── views/              # CustomTkinter UI screens (Presentation Layer)
├── database/
│   ├── models.py       # SQLAlchemy ORM schemas
│   └── migrations.py   # Schema migration and initialization
├── core/
│   ├── context.py      # AppContext (Dependency Injection / State)
│   └── base_view.py    # UI base classes and inheritance templates
├── utils/              # Configuration, styling, and shared helpers
├── tests/              # Pytest automated test suite
├── web-dashboard/      # React + Vite web administration frontend
│   ├── src/            # Dashboard components, contexts, and hooks
│   └── package.json    # Node.js configuration
├── main.py             # Application entry point and lifecycle manager
└── .env.example        # Environment variable template
```

## 📦 Deployment (Building the Executable)

To package the desktop application into a standalone Windows executable:

```bash
# Install PyInstaller
pip install pyinstaller

# Build the executable using the provided spec file
pyinstaller CloudPOS.spec --clean

# The generated executable will be located at: dist/CloudPOS/CloudPOS.exe
```

## ⚙️ Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///pos_system.db` | SQLAlchemy database connection string |
| `CLOUDPOS_SYNC_API_URL` | — | URL HTTPS del complemento Cloud opcional |
| `CLOUDPOS_DEVICE_TOKEN` | — | Credencial revocable del equipo principal para sincronizar |
| `CLOUD_SYNC_INTERVAL` | `300` | Intervalo de sincronización en segundos |

> ⚠️ **Security Warning:** Never commit the `.env` file to version control.

El panel web y el escritorio no reciben credenciales PostgreSQL. La PC principal publica una réplica de reportes mediante HTTPS y el panel web es solo de lectura. Consulta la guía de [despliegue en VPS](docs/VPS_DEPLOYMENT.md).

> **Local-first rule:** SQLite is a local single-installation database. Do not put `pos_system.db` on a network share or open it from multiple PCs. For mobile reporting, enable the optional Cloud Sync API; for future multi-terminal operation, use a server API/database rather than a shared SQLite file.

## 🗺 Roadmap

- AFIP Integration for electronic invoicing (See `ROADMAP_AFIP.md`).
- Multi-branch synchronization enhancements.

## 📄 License

Private / Proprietary. All rights reserved.
