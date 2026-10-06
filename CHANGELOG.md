# Changelog

All notable changes are documented here. This repository follows an unreleased-development workflow; validate against a staging database before updating a production deployment.

## Unreleased

### Security

- Removed the embedded, obfuscated cloud database URL from the desktop client. Cloud sync is enabled only when `DATABASE_CLOUD_URL` is supplied through the environment.
- Added cloud-dashboard session functions with hashed, expiring tokens, tenant-scoped row-level security policies, and temporary login lockouts after repeated failed attempts.
- Restricted web-dashboard data access according to tenant and user role.

### Data integrity

- Added migration support for one open cash session per user and tenant.
- Hardened sales, inventory, quotation, purchase, and return paths against duplicate or inconsistent operations.
- Made cashier offline fallback read-only, preventing writes that cannot be merged safely later.

### Labels and printing

- Redesigned Supermercado, Producto, Mini, Precio, and Dual labels to reserve distinct title, pricing, and barcode zones.
- Validated EAN-8, EAN-13, UPC-A, and Code128 values before printing; internal labels receive a persisted, scannable code.
- Added Windows-driver label delivery with an explicit preview-versus-print setting; generic printers no longer receive raw ZPL.
- Replaced the approximate widget preview with an image rendered from the exact generated PDF page.
- Added `pypdfium2` for PDF preview rendering and `pywin32` for Windows printer delivery.

### Verification

- Added label-controller tests covering barcode checks, persistence of generated codes, duplicate prevention, PDF preflight, and PDF-page preview rendering.
- The current suite is run with `pytest -q -p no:cacheprovider`; the web dashboard is validated with `npm run build` and `npm audit`.

## Upgrade notes

1. Install dependencies with `python -m pip install -r requirements.txt`.
2. Apply database migrations at application startup before allowing web-dashboard access.
3. Set cloud variables in the deployment environment instead of committing them. Review `.env.example` for the expected names.
4. In **Configuración > Periféricos**, select the label printer and choose whether to open a PDF preview or send it to the selected Windows printer driver. Configure paper dimensions in that driver to match the chosen template.
