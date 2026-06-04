# Roadmap: Integración Factura Electrónica AFIP en CloudPOS

> Documento de estudio y planificación para implementar facturación electrónica AFIP en el sistema POS CloudPOS (Python + CustomTkinter + SQLAlchemy).

---

## Tabla de Contenidos

1. [Requisitos Legales del Desarrollador](#1-requisitos-legales-del-desarrollador)
2. [Requisitos del Usuario Final (Cliente del POS)](#2-requisitos-del-usuario-final-cliente-del-pos)
3. [Arquitectura de Integración](#3-arquitectura-de-integración)
4. [Modelo de Datos](#4-modelo-de-datos)
5. [Flujo de Emisión de Comprobante](#5-flujo-de-emisión-de-comprobante)
6. [Fase 1: Preparación del Entorno](#6-fase-1-preparación-del-entorno)
7. [Fase 2: Capa de Servicios AFIP](#7-fase-2-capa-de-servicios-afip)
8. [Fase 3: Integración con el POS](#8-fase-3-integración-con-el-pos)
9. [Fase 4: Generación de PDF + QR](#9-fase-4-generación-de-pdf--qr)
10. [Fase 5: Manejo de Errores y Reproceso](#10-fase-5-manejo-de-errores-y-reproceso)
11. [Fase 6: Testing en Homologación](#11-fase-6-testing-en-homologación)
12. [Fase 7: Paso a Producción](#12-fase-7-paso-a-producción)
13. [Fase 8: Funcionalidades Avanzadas](#13-fase-8-funcionalidades-avanzadas)
14. [Checklist de Tareas](#14-checklist-de-tareas)
15. [Comparativa con Líderes del Mercado](#15-comparativa-con-líderes-del-mercado)
16. [Glosario](#16-glosario)
17. [Referencias y Enlaces](#17-referencias-y-enlaces)

---

## 1. Requisitos Legales del Desarrollador

### 1.1. Registro de Responsable del Software Facturador

**Norma:** RG 3749/2015

Si vas a **vender, distribuir o poner en manos de terceros** el POS (incluso gratis), AFIP exige registrarse como **Responsable del Software Facturador**.

**Pasos para registrarse:**

1. Tener **Clave Fiscal nivel 2 o 3** (se obtiene en cualquier oficina de AFIP o por home banking).
2. Ingresar a AFIP con tu CUIT.
3. Ir a **Servicios Web > Registro de Software Facturador**.
4. Completar el formulario:
   - Nombre del software: `CloudPOS`
   - Versión: `1.0.0`
   - Descripción: `Sistema de gestión y punto de venta con facturación electrónica`
   - Tipo de contribuyentes que atiende: Monotributo, Responsable Inscripto, etc.
5. AFIP asigna un **Código de Identificación del Software** (número único).

> **Si el POS es solo para un negocio propio:** No estás obligado a registrarte, pero se recomienda. Si se lo instalás a un familiar, cliente o conocido, **sí estás obligado**.

### 1.2. Obligaciones Técnicas del Software

| Requisito | Norma | Qué implica en código |
|---|---|---|
| **Duplicado digital** | RG 1361/02 | Guardar copia de cada comprobante emitido (XML request/response) por **10 años**. |
| **Código QR** | RG 4291/17, RG 4892/20 | Todos los comprobantes deben incluir QR con datos de AFIP. |
| **Inmutabilidad** | RG 3749/15 | Una vez autorizado el CAE, el comprobante es inmutable. Append-only o versionado. |
| **Resguardo de tickets** | RG 3749/15 | Guardar XML Request/Response de cada comunicación con AFIP. |
| **Controlador fiscal** | Ley 25.506 | Si se usa impresora fiscal, debe generar archivos de control (fuera de scope inicial). |

### 1.3. Licencia del Software

- PyAfipWs tiene licencia **LGPLv3+ con excepción comercial** → podés incluirlo en software propietario.
- PySimpleSOAP: licencia compatible.
- PyFPDF: licencia LGPL.

---

## 2. Requisitos del Usuario Final (Cliente del POS)

Estos requisitos **no dependen de tu código**, pero si el usuario no los cumple, la integración no funciona.

### 2.1. Certificado Digital

- Archivo `.crt` (certificado) y `.key` (clave privada).
- Firmado por una **Autoridad Certificante** reconocida por AFIP (ej: ssl.com, Buypass, etc.).
- Validez: **1 año** (renovable).
- Se obtiene desde AFIP > Clave Fiscal > Administración de Certificados Digitales.
- El certificado está vinculado a un **CUIT específico**.

### 2.2. Punto de Venta Autorizado

- Dado de alta en AFIP por Clave Fiscal.
- Con el servicio **"Facturación Electrónica" (WSFEv1)** habilitado para ese CUIT.
- Cada punto de venta tiene un número (1, 2, 3...) y un tipo de comprobante permitido.

### 2.3. Régimen Fiscal del Usuario

| Régimen | Puede emitir por WSFEv1 | Limitaciones |
|---|---|---|
| **Responsable Inscripto** | ✅ Factura A, B, C, M | Sin restricciones. |
| **Monotributo** | ✅ Factura C, M | NO puede emitir A/B. Solo C (consumidor final) o M (monotributo). |
| **Exento** | ✅ Factura B, C | No cobra IVA. |
| **Consumidor Final** | ❌ | No puede emitir facturas electrónicas. |

> **Importante:** Si tu POS se vende a monotributistas, **WSFEv1 para Factura A/B no les sirve**. Debés implementar Factura C/M o integrar con un facturador externo.

---

## 3. Arquitectura de Integración

### 3.1. Stack Tecnológico

```
┌─────────────────────────────────────────────────────┐
│                    CloudPOS (UI)                     │
│              CustomTkinter + Python                  │
├─────────────────────────────────────────────────────┤
│              controllers/afip_controller.py          │
│         (lógica de negocio AFIP)                     │
├─────────────────────────────────────────────────────┤
│              utils/afip/                             │
│   ├── afip_service.py    (wrapper pyafipws)         │
│   ├── afip_pdf.py        (generación PDF + QR)      │
│   └── afip_config.py     (config por tenant)        │
├─────────────────────────────────────────────────────┤
│              pyafipws + pySimpleSOAP                 │
│         (librería SOAP para AFIP)                    │
├─────────────────────────────────────────────────────┤
│              AFIP Web Services                       │
│   ├── WSAA (Autenticación)                          │
│   ├── WSFEv1 (Mercado Interno)                      │
│   └── WSCDC (Constatación)                          │
└─────────────────────────────────────────────────────┘
```

### 3.2. Principios de Diseño

1. **Desacoplado:** La emisión AFIP es asíncrona. La venta se guarda local primero.
2. **Resiliente:** Si AFIP está caído, la venta no se pierde. Se reintenta después.
3. **Multi-tenant:** Cada tenant tiene su propio certificado y configuración AFIP.
4. **Append-only:** Los comprobantes emitidos no se modifican. Se versionan si hay correcciones.
5. **Trazable:** Se guarda todo (XML request/response, CAE, QR, PDF).

---

## 4. Modelo de Datos

### 4.1. Tablas Nuevas (SQLAlchemy)

Agregar en `database/models.py`:

```python
class AfipConfig(Base):
    """Configuración AFIP por tenant."""
    __tablename__ = 'afip_config'
    id = Column(String(36), primary_key=True, default=uuid4)
    tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
    cuit = Column(String(13), nullable=False)
    cert_path = Column(String(500), nullable=False)
    key_path = Column(String(500), nullable=False)
    is_production = Column(Boolean, default=False)
    punto_venta = Column(Integer, nullable=False)
    last_cbte_nro = Column(Integer, default=0)
    # URLs AFIP
    wsaa_url = Column(String(500))
    wsfev1_url = Column(String(500))
    # Cache de Ticket de Acceso
    ta_token = Column(String(2000))
    ta_sign = Column(String(2000))
    ta_expiration = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ElectronicInvoice(Base):
    """Comprobante electrónico emitido (duplicado digital RG 1361)."""
    __tablename__ = 'electronic_invoices'
    id = Column(String(36), primary_key=True, default=uuid4)
    sale_id = Column(String(36), ForeignKey('sales.id'), nullable=True, index=True)
    tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
    # Datos del comprobante
    cuit = Column(String(13), nullable=False)
    punto_venta = Column(Integer, nullable=False)
    cbte_tipo = Column(Integer, nullable=False)  # 1=A, 6=B, 11=C, etc.
    cbte_nro = Column(Integer, nullable=False)
    # CAE
    cae = Column(String(50), nullable=False)
    cae_fecha_vto = Column(String(8), nullable=False)  # YYYYMMDD
    fecha_emision = Column(DateTime, default=datetime.now)
    # Totales
    imp_total = Column(Numeric(12, 2), nullable=False)
    imp_neto = Column(Numeric(12, 2), default=0)
    imp_iva = Column(Numeric(12, 2), default=0)
    imp_tributos = Column(Numeric(12, 2), default=0)
    # Receptor
    doc_tipo = Column(Integer)  # 80=CUIT, 96=DNI, 99=Consumidor Final
    doc_nro = Column(String(20))
    nombre_receptor = Column(String(200))
    iva_receptor = Column(String(20))  # 1=RI, 4=Exento, 5=Monotributo, 6=CF
    # Moneda
    moneda = Column(String(3), default='PES')
    moneda_ctz = Column(Numeric(12, 4), default=1)
    # Almacenamiento obligatorio
    xml_request = Column(Text, nullable=False)
    xml_response = Column(Text, nullable=False)
    # QR y PDF
    qr_data = Column(Text)
    pdf_path = Column(String(500))
    # Estado
    status = Column(String(20), default='emitida')  # emitida, anulada, rechazada
    # Fecha AFIP
    fch_vto_pago = Column(String(8))  # YYYYMMDD (si aplica FCE)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint('cuit', 'punto_venta', 'cbte_tipo', 'cbte_nro',
                        name='uq_electronic_invoice_number'),
    )


class ElectronicInvoiceItem(Base):
    """Detalle de ítems para WSMTXCA (factura con detalle de productos)."""
    __tablename__ = 'electronic_invoice_items'
    id = Column(String(36), primary_key=True, default=uuid4)
    invoice_id = Column(String(36), ForeignKey('electronic_invoices.id'), nullable=False, index=True)
    codigo = Column(String(50))
    descripcion = Column(String(200), nullable=False)
    cantidad = Column(Numeric(12, 4), nullable=False)
    precio_unit = Column(Numeric(12, 2), nullable=False)
    imp_total = Column(Numeric(12, 2), nullable=False)
    alic_iva = Column(Numeric(5, 2))  # 21.0, 10.5, 0.0, etc.
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class AfipPendingInvoice(Base):
    """Cola de comprobantes pendientes de emisión por fallo de AFIP."""
    __tablename__ = 'afip_pending_invoices'
    id = Column(String(36), primary_key=True, default=uuid4)
    sale_id = Column(String(36), ForeignKey('sales.id'), nullable=False, index=True)
    tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
    # Datos del comprobante a emitir
    cbte_tipo = Column(Integer, nullable=False)
    doc_tipo = Column(Integer)
    doc_nro = Column(String(20))
    imp_total = Column(Numeric(12, 2), nullable=False)
    # Intentos
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=10)
    last_error = Column(String(500))
    next_retry = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
```

### 4.2. Migración

Crear una nueva migración en `database/migrations.py` para agregar estas tablas.

---

## 5. Flujo de Emisión de Comprobante

### 5.1. Flujo Normal (AFIP disponible)

```
1. Usuario finaliza venta → SalesView.process_sale()
2. Se guarda la venta en SQLite (Sale, SaleDetail) → YA EXISTE
3. Si el cliente quiere factura electrónica:
   a. AfipController.emitir_factura(sale_id)
   b. Obtener configuración AFIP del tenant (AfipConfig)
   c. Obtener/renovar Ticket de Acceso (WSAA)
   d. Consultar último comprobante autorizado (CompUltimoAutorizado)
   e. Armar comprobante con datos de la venta
   f. Enviar a AFIP vía WSFEv1.SolicitarCAE
   g. Recibir CAE + fecha de vencimiento
   h. Guardar ElectronicInvoice con XML request/response
   i. Generar PDF con QR
   j. Imprimir o enviar por email
4. Venta completada con factura electrónica emitida
```

### 5.2. Flujo con Error de AFIP (AFIP caído)

```
1. Pasos 1-5 iguales
2. WSFEv1.SolicitarCAE falla (timeout, error interno)
3. Guardar en AfipPendingInvoice
4. Mostrar al usuario: "Venta registrada. Factura pendiente de emisión."
5. Background worker (AfipSyncWorker) reintenta cada 5 minutos
6. Cuando AFIP vuelve, emite y actualiza ElectronicInvoice
7. Notificar al usuario (toast o banner)
```

### 5.3. Flujo de Reproceso (CAE ya otorgado)

```
1. Si AFIP responde "comprobante ya existe" (error 10242)
2. Consultar comprobante en WSFEv1.ConsultarComprobante
3. Recuperar CAE existente
4. Guardar ElectronicInvoice con CAE recuperado
5. Generar PDF con QR
```

---

## 6. Fase 1: Preparación del Entorno

### 6.1. Agregar Dependencias

Editar `requirements.txt`:

```txt
pyafipws==2.7.1874
pySimpleSOAP @ git+https://github.com/pysimplesoap/pysimplesoap.git@stable_py3k
```

### 6.2. Crear Estructura de Directorios

```
POS_master/
├── afip/
│   ├── certs/           # .crt y .key por tenant
│   │   └── .gitignore   # NO commitear certificados
│   ├── cache/           # Tickets de acceso (TA.xml)
│   ├── config/          # .ini por tenant
│   └── templates/       # Plantillas CSV para PyFEPDF
├── controllers/
│   └── afip_controller.py
├── utils/
│   └── afip/
│       ├── __init__.py
│       ├── afip_service.py
│       ├── afip_pdf.py
│       └── afip_config.py
├── views/
│   └── afip_view.py     # UI de configuración AFIP
└── database/
    └── models.py        # + nuevos modelos
```

### 6.3. Crear .gitignore para Certificados

```
# afip/certs/.gitignore
*.crt
*.key
*.pem
*.p12
!*.gitignore
```

### 6.4. URLs de AFIP

| Servicio | Homologación | Producción |
|---|---|---|
| **WSAA** | `https://wsaahomo.afip.gov.ar/ws/services/LoginCms` | `https://wsaa.afip.gov.ar/ws/services/LoginCms` |
| **WSFEv1** | `https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL` | `https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL` |
| **WSCDC** | `https://wswhomo.afip.gov.ar/wscdc/service.asmx?WSDL` | `https://servicios1.afip.gov.ar/wscdc/service.asmx?WSDL` |

### 6.5. CACert de AFIP

Descargar el certificado de la autoridad certificante de AFIP:

```bash
curl -o afip_ca_info.crt https://www.afip.gob.ar/ws/WSAA/afip_ca_info.crt
```

Guardarlo en `afip/config/afip_ca_info.crt`.

---

## 7. Fase 2: Capa de Servicios AFIP

### 7.1. `utils/afip/afip_config.py`

Gestiona la configuración AFIP por tenant:

```python
"""Gestión de configuración AFIP por tenant."""
import os
from pathlib import Path
from typing import Optional

def get_afip_dir() -> Path:
    """Directorio raíz de configuración AFIP."""
    # En desarrollo: raíz del proyecto
    # En producción: directorio del ejecutable
    import sys
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent / 'afip'
    return Path(__file__).parent.parent.parent / 'afip'

def get_cert_path(tenant_id: str) -> Path:
    return get_afip_dir() / 'certs' / f'{tenant_id}.crt'

def get_key_path(tenant_id: str) -> Path:
    return get_afip_dir() / 'certs' / f'{tenant_id}.key'

def get_wsaa_url(is_production: bool) -> str:
    if is_production:
        return 'https://wsaa.afip.gov.ar/ws/services/LoginCms'
    return 'https://wsaahomo.afip.gov.ar/ws/services/LoginCms'

def get_wsfev1_url(is_production: bool) -> str:
    if is_production:
        return 'https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL'
    return 'https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL'
```

### 7.2. `utils/afip/afip_service.py`

Wrapper principal de pyafipws para interactuar con AFIP:

```python
"""Wrapper de pyafipws para servicios AFIP (WSAA + WSFEv1)."""
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class AfipService:
    """Servicio de conexión con AFIP usando pyafipws."""

    def __init__(self, db_engine):
        self.db_engine = db_engine
        self._wsaa = None
        self._wsfev1 = None

    # ── Autenticación (WSAA) ──────────────────────────────────────────────

    def get_ticket_acceso(self, tenant_id: str) -> Tuple[str, str]:
        """
        Obtiene Token y Sign de acceso a AFIP.
        Reutiliza el ticket cacheado si aún es válido.
        """
        from sqlalchemy.orm import sessionmaker
        from database.models import AfipConfig
        Session = sessionmaker(bind=self.db_engine)

        with Session() as s:
            config = s.query(AfipConfig).filter_by(tenant_id=tenant_id).first()
            if not config:
                raise ValueError(f"No hay configuración AFIP para tenant {tenant_id}")

            # Reutilizar TA si es válido
            if (config.ta_token and config.ta_sign and
                config.ta_expiration and config.ta_expiration > datetime.now()):
                return config.ta_token, config.ta_sign

            # Solicitar nuevo TA
            from pyafipws.wsaa import WSAA
            wsaa = WSAA()
            wsaa.LanzarExcepciones = False

            cert_path = str(Path(config.cert_path))
            key_path = str(Path(config.key_path))
            wsaa_url = config.wsaa_url or get_wsaa_url(config.is_production)
            cacert = str(Path(__file__).parent.parent.parent / 'afip' / 'config' / 'afip_ca_info.crt')

            ok = wsaa.Conectar('', wsaa_url, '', '', cacert)
            if not ok:
                raise ConnectionError(f"No se pudo conectar a WSAA: {wsaa.Excepcion}")

            cms = wsaa.SignTRA('wsfe', cert_path, key_path)
            ta = wsaa.LoginCMS(cms)
            if not ta:
                raise ConnectionError(f"Error obteniendo TA: {wsaa.Excepcion}")

            # Guardar en cache
            config.ta_token = wsaa.Token
            config.ta_sign = wsaa.Sign
            config.ta_expiration = datetime.now().replace(hour=23, minute=59, second=59)
            s.commit()

            return wsaa.Token, wsaa.Sign

    # ── Facturación (WSFEv1) ──────────────────────────────────────────────

    def solicitar_cae(self, tenant_id: str, comprobante: dict) -> dict:
        """
        Solicita CAE a AFIP para un comprobante.

        Args:
            comprobante: dict con datos del comprobante (ver estructura abajo)

        Returns:
            dict con CAE, fecha_vto, cbte_nro, xml_request, xml_response
        """
        from pyafipws.wsfev1 import WSFEv1
        from database.models import AfipConfig
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=self.db_engine)

        with Session() as s:
            config = s.query(AfipConfig).filter_by(tenant_id=tenant_id).first()
            token, sign = self.get_ticket_acceso(tenant_id)

            wsfev1 = WSFEv1()
            wsfev1.LanzarExcepciones = False

            wsfev1_url = config.wsfev1_url or get_wsfev1_url(config.is_production)
            ok = wsfev1.Conectar('', wsfev1_url, '', '', '')
            if not ok:
                raise ConnectionError(f"No se pudo conectar a WSFEv1: {wsfev1.Excepcion}")

            wsfev1.Token = token
            wsfev1.Sign = sign
            wsfev1.Cuit = config.cuit

            # ── Armar comprobante ──────────────────────────────────────
            wsfev1.CrearComprobante()
            wsfev1.AgregarCmp(
                Concepto=comprobante['concepto'],       # 1=Productos, 2=Servicios, 3=Ambos
                DocTipo=comprobante['doc_tipo'],        # 80=CUIT, 96=DNI, 99=CF
                DocNro=comprobante['doc_nro'],
                CbteDesde=comprobante['cbte_nro'],
                CbteHasta=comprobante['cbte_nro'],
                ImpTotal=str(comprobante['imp_total']),
                ImpTotConc=str(comprobante.get('imp_neto', 0)),
                ImpNeto=str(comprobante.get('imp_neto', 0)),
                ImpOpEx=str(comprobante.get('imp_exento', 0)),
                ImpTrib=str(comprobante.get('imp_tributos', 0)),
                ImpIVA=str(comprobante.get('imp_iva', 0)),
                MonId=comprobante.get('moneda', 'PES'),
                MonCotiz=str(comprobante.get('moneda_ctz', '1')),
                FchServDesde=comprobante.get('fch_serv_desde'),
                FchServHasta=comprobante.get('fch_serv_hasta'),
                FchVtoPago=comprobante.get('fch_vto_pago'),
            )

            # ── Alicuotas de IVA ───────────────────────────────────────
            for alic in comprobante.get('alicuotas_iva', []):
                wsfev1.AgregarIva(
                    Id=alic['id'],           # 3=21%, 4=10.5%, 5=27%, 6=5%, 8=0%
                    BaseImp=str(alic['base_imp']),
                    Importe=str(alic['importe']),
                )

            # ── Comprobantes asociados (Notas de Crédito/Débito) ───────
            if comprobante.get('cbte_asoc'):
                for asoc in comprobante['cbte_asoc']:
                    wsfev1.AgregarCmpAsoc(
                        Tipo=asoc['tipo'],
                        PtoVta=asoc['pto_vta'],
                        Nro=asoc['nro'],
                        Cuit=asoc.get('cuit'),
                    )

            # ── Solicitar CAE ──────────────────────────────────────────
            ok = wsfev1.SolicitarCAE()
            if not ok:
                # Guardar XML para depuración
                xml_req = wsfev1.XmlRequest
                xml_resp = wsfev1.XmlResponse
                errores = []
                for i in range(wsfev1.ErrorsRep):
                    errores.append({
                        'code': wsfev1.ErrorsRep[i]['Code'],
                        'msg': wsfev1.ErrorsRep[i]['Msg'],
                    })
                raise AfipError(
                    f"Error solicitando CAE: {errores}",
                    code=errores[0]['code'] if errores else None,
                    xml_request=xml_req,
                    xml_response=xml_resp,
                )

            return {
                'cae': wsfev1.CAE,
                'cae_fecha_vto': wsfev1.CAEFchVto,
                'cbte_nro': comprobante['cbte_nro'],
                'xml_request': wsfev1.XmlRequest,
                'xml_response': wsfev1.XmlResponse,
                'resultado': wsfev1.Resultado,  # 'A'=Aprobado, 'R'=Rechazado, 'O'=Observado
                'observaciones': [wsfev1.Obs[i] for i in range(wsfev1.ObsRep)],
            }

    def consultar_ultimo_comprobante(self, tenant_id: str, cbte_tipo: int) -> int:
        """Consulta el último comprobante autorizado para un tipo."""
        from pyafipws.wsfev1 import WSFEv1
        from database.models import AfipConfig
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=self.db_engine)

        with Session() as s:
            config = s.query(AfipConfig).filter_by(tenant_id=tenant_id).first()
            token, sign = self.get_ticket_acceso(tenant_id)

            wsfev1 = WSFEv1()
            wsfev1.LanzarExcepciones = False
            wsfev1_url = config.wsfev1_url or get_wsfev1_url(config.is_production)
            wsfev1.Conectar('', wsfev1_url, '', '', '')
            wsfev1.Token = token
            wsfev1.Sign = sign
            wsfev1.Cuit = config.cuit

            ultimo = wsfev1.CompUltimoAutorizado(cbte_tipo, config.punto_venta)
            return ultimo

    def consultar_comprobante(self, tenant_id: str, cbte_tipo: int, cbte_nro: int) -> dict:
        """Consulta un comprobante existente en AFIP."""
        from pyafipws.wsfev1 import WSFEv1
        from database.models import AfipConfig
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=self.db_engine)

        with Session() as s:
            config = s.query(AfipConfig).filter_by(tenant_id=tenant_id).first()
            token, sign = self.get_ticket_acceso(tenant_id)

            wsfev1 = WSFEv1()
            wsfev1.LanzarExcepciones = False
            wsfev1_url = config.wsfev1_url or get_wsfev1_url(config.is_production)
            wsfev1.Conectar('', wsfev1_url, '', '', '')
            wsfev1.Token = token
            wsfev1.Sign = sign
            wsfev1.Cuit = config.cuit

            ok = wsfev1.ConsultarComprobante(cbte_tipo, config.punto_venta, cbte_nro)
            if not ok:
                return None

            return {
                'cae': wsfev1.CAE,
                'cae_fecha_vto': wsfev1.CAEFchVto,
                'fecha_emision': wsfev1.FchEmis,
                'imp_total': wsfev1.ImpTotal,
                'resultado': wsfev1.Resultado,
            }


class AfipError(Exception):
    """Error retornado por AFIP."""
    def __init__(self, message, code=None, xml_request=None, xml_response=None):
        super().__init__(message)
        self.code = code
        self.xml_request = xml_request
        self.xml_response = xml_response
```

### 7.3. Tipos de Comprobante AFIP

| Código | Descripción | Uso |
|---|---|---|
| **1** | Factura A | Responsable Inscripto → Responsable Inscripto |
| **2** | Nota de Débito A | RI → RI (débito) |
| **3** | Nota de Crédito A | RI → RI (crédito) |
| **6** | Factura B | RI → Consumidor Final / Monotributo |
| **7** | Nota de Débito B | RI → CF/Monotributo (débito) |
| **8** | Nota de Crédito B | RI → CF/Monotributo (crédito) |
| **11** | Factura C | Monotributo → Cualquiera |
| **12** | Nota de Débito C | Monotributo → Cualquiera (débito) |
| **13** | Nota de Crédito C | Monotributo → Cualquiera (crédito) |
| **51** | Factura M | Monotributo Social |
| **52** | Nota de Débito M | Monotributo Social (débito) |
| **53** | Nota de Crédito M | Monotributo Social (crédito) |

### 7.4. Tipos de Documento Receptor

| Código | Descripción |
|---|---|
| **80** | CUIT |
| **96** | DNI |
| **99** | Consumidor Final |
| **89** | LE (Libreta Enrolamiento) |
| **90** | LC (Libreta Cívica) |
| **87** | CDI (Certificado de Identificación) |

### 7.5. Alicuotas de IVA

| Código | Porcentaje | Descripción |
|---|---|---|
| **3** | 21% | Alícuota general |
| **4** | 10.5% | Alícuota reducida |
| **5** | 27% | Alícuota diferencial |
| **6** | 5% | Alícuota especial |
| **8** | 0% | Exento / No gravado |
| **9** | 2.5% | Alícuota especial (regiones) |

---

## 8. Fase 3: Integración con el POS

### 8.1. `controllers/afip_controller.py`

Controller principal que conecta la UI con los servicios AFIP:

```python
"""Controller de Factura Electrónica AFIP."""
import logging
from datetime import datetime
from decimal import Decimal

from controllers.base import BaseController
from database.models import Sale, SaleDetail, AfipConfig, ElectronicInvoice, AfipPendingInvoice
from utils.afip.afip_service import AfipService, AfipError

logger = logging.getLogger(__name__)


class AfipController(BaseController):
    def __init__(self, db_engine=None):
        super().__init__(db_engine)
        self.afip_service = AfipService(db_engine)

    def emitir_factura(self, sale_id: str, tenant_id: str, cbte_tipo: int = 6) -> dict:
        """
        Emite factura electrónica para una venta existente.

        Args:
            sale_id: ID de la venta
            tenant_id: ID del tenant
            cbte_tipo: Tipo de comprobante (1=A, 6=B, 11=C)

        Returns:
            dict con resultado de la emisión
        """
        with self._Session() as session:
            # 1. Obtener venta
            sale = session.query(Sale).filter_by(id=sale_id, tenant_id=tenant_id).first()
            if not sale:
                raise ValueError(f"Venta {sale_id} no encontrada")

            # 2. Verificar si ya tiene factura
            existing = session.query(ElectronicInvoice).filter_by(sale_id=sale_id).first()
            if existing:
                return {
                    'success': True,
                    'message': 'La venta ya tiene factura electrónica emitida.',
                    'cae': existing.cae,
                    'cbte_nro': existing.cbte_nro,
                }

            # 3. Obtener configuración AFIP
            config = session.query(AfipConfig).filter_by(tenant_id=tenant_id).first()
            if not config:
                raise ValueError("No hay configuración AFIP para este tenant")

            # 4. Determinar datos del receptor
            doc_tipo, doc_nro, nombre_receptor, iva_receptor = self._get_receptor_data(sale, session)

            # 5. Calcular próximo número de comprobante
            ultimo = self.afip_service.consultar_ultimo_comprobante(tenant_id, cbte_tipo)
            cbte_nro = ultimo + 1

            # 6. Armar comprobante
            comprobante = self._build_comprobante(sale, sale.items, cbte_tipo, cbte_nro,
                                                   doc_tipo, doc_nro, config)

            # 7. Solicitar CAE
            try:
                resultado = self.afip_service.solicitar_cae(tenant_id, comprobante)
            except AfipError as e:
                # Si es error reprocesable (comprobante ya existe), recuperar
                if e.code == 10242:
                    return self._reprocesar(tenant_id, cbte_tipo, cbte_nro, sale_id, session)
                # Si no, guardar en pendientes
                self._guardar_pendiente(sale_id, tenant_id, cbte_tipo, doc_tipo, doc_nro,
                                        sale.total_amount, str(e), session)
                return {
                    'success': False,
                    'message': 'AFIP no respondió. La factura se emitirá automáticamente.',
                    'pending': True,
                }

            # 8. Guardar factura electrónica
            invoice = ElectronicInvoice(
                sale_id=sale_id,
                tenant_id=tenant_id,
                cuit=config.cuit,
                punto_venta=config.punto_venta,
                cbte_tipo=cbte_tipo,
                cbte_nro=cbte_nro,
                cae=resultado['cae'],
                cae_fecha_vto=resultado['cae_fecha_vto'],
                fecha_emision=datetime.now(),
                imp_total=comprobante['imp_total'],
                imp_neto=comprobante.get('imp_neto', 0),
                imp_iva=comprobante.get('imp_iva', 0),
                doc_tipo=doc_tipo,
                doc_nro=doc_nro,
                nombre_receptor=nombre_receptor,
                iva_receptor=iva_receptor,
                xml_request=resultado['xml_request'],
                xml_response=resultado['xml_response'],
                status='emitida',
            )
            session.add(invoice)

            # 9. Actualizar último número
            config.last_cbte_nro = cbte_nro
            session.commit()

            return {
                'success': True,
                'cae': resultado['cae'],
                'cae_fecha_vto': resultado['cae_fecha_vto'],
                'cbte_nro': cbte_nro,
                'cbte_tipo': cbte_tipo,
                'punto_venta': config.punto_venta,
                'xml_request': resultado['xml_request'],
                'xml_response': resultado['xml_response'],
            }

    def _build_comprobante(self, sale, items, cbte_tipo, cbte_nro,
                           doc_tipo, doc_nro, config) -> dict:
        """Arma el dict de comprobante para WSFEv1."""
        total = Decimal(str(sale.total_amount))

        # Determinar concepto (1=Productos, 2=Servicios, 3=Ambos)
        concepto = 1  # Por defecto productos

        # Calcular IVA
        # Para Factura B/C (consumidor final), no se discrimina IVA
        # Para Factura A, sí se discrimina
        if cbte_tipo == 1:  # Factura A
            # Calcular IVA 21% sobre el neto
            imp_neto = total / Decimal('1.21')
            imp_iva = total - imp_neto
            alicuotas = [{
                'id': 3,  # 21%
                'base_imp': float(imp_neto),
                'importe': float(imp_iva),
            }]
        else:
            # Factura B/C: no discrimina IVA
            imp_neto = total
            imp_iva = Decimal('0')
            alicuotas = []

        return {
            'concepto': concepto,
            'doc_tipo': doc_tipo,
            'doc_nro': doc_nro,
            'cbte_nro': cbte_nro,
            'imp_total': float(total),
            'imp_neto': float(imp_neto),
            'imp_iva': float(imp_iva),
            'imp_exento': 0,
            'imp_tributos': 0,
            'moneda': 'PES',
            'moneda_ctz': 1,
            'alicuotas_iva': alicuotas,
        }

    def _get_receptor_data(self, sale, session):
        """Obtiene datos del receptor de la factura."""
        from database.models import Customer
        if sale.customer_id:
            customer = session.query(Customer).filter_by(id=sale.customer_id).first()
            if customer:
                # Determinar tipo de documento y condición de IVA
                # Esto depende de cómo guardes los datos del cliente
                return 80, customer.phone or '0', customer.name, '5'  # Monotributo por defecto
        # Consumidor Final
        return 99, '0', 'Consumidor Final', '6'

    def _reprocesar(self, tenant_id, cbte_tipo, cbte_nro, sale_id, session):
        """Intenta recuperar un CAE ya otorgado."""
        try:
            data = self.afip_service.consultar_comprobante(tenant_id, cbte_tipo, cbte_nro)
            if data:
                invoice = ElectronicInvoice(
                    sale_id=sale_id,
                    tenant_id=tenant_id,
                    cae=data['cae'],
                    cae_fecha_vto=data['cae_fecha_vto'],
                    cbte_nro=cbte_nro,
                    cbte_tipo=cbte_tipo,
                    status='emitida',
                    xml_request='',
                    xml_response='',
                )
                session.add(invoice)
                session.commit()
                return {'success': True, 'cae': data['cae'], 'reprocesado': True}
        except Exception as e:
            logger.error(f"Error en reproceso: {e}")
        return {'success': False, 'message': 'No se pudo recuperar el CAE'}

    def _guardar_pendiente(self, sale_id, tenant_id, cbte_tipo, doc_tipo, doc_nro,
                           imp_total, error, session):
        """Guarda comprobante en cola de pendientes."""
        from datetime import timedelta
        pending = AfipPendingInvoice(
            sale_id=sale_id,
            tenant_id=tenant_id,
            cbte_tipo=cbte_tipo,
            doc_tipo=doc_tipo,
            doc_nro=doc_nro,
            imp_total=imp_total,
            last_error=error,
            next_retry=datetime.now() + timedelta(minutes=5),
        )
        session.add(pending)
        session.commit()
```

### 8.2. Background Worker para Pendientes

Crear `utils/afip/afip_sync_worker.py` (similar a tu `sync_worker.py`):

```python
"""Background worker para reintentar emisión de facturas pendientes."""
import logging
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

AFIP_SYNC_INTERVAL = 300  # 5 minutos

class AfipSyncWorker:
    def __init__(self, db_engine):
        self.db_engine = db_engine
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name='AfipSyncWorker',
            daemon=True,
        )

    def start(self):
        if not self._thread.is_alive():
            self._stop.clear()
            self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        self._stop.wait(timeout=30)
        while not self._stop.is_set():
            try:
                self._process_pending()
            except Exception as e:
                logger.error(f"Afip sync cycle crashed: {e}", exc_info=True)
            self._stop.wait(timeout=AFIP_SYNC_INTERVAL)

    def _process_pending(self):
        from sqlalchemy.orm import sessionmaker
        from database.models import AfipPendingInvoice
        from controllers.afip_controller import AfipController

        Session = sessionmaker(bind=self.db_engine)
        afip_ctrl = AfipController(self.db_engine)

        with Session() as s:
            pendientes = s.query(AfipPendingInvoice).filter(
                AfipPendingInvoice.next_retry <= datetime.now(),
                AfipPendingInvoice.attempts < AfipPendingInvoice.max_attempts,
            ).all()

            for p in pendientes:
                try:
                    resultado = afip_ctrl.emitir_factura(p.sale_id, p.tenant_id, p.cbte_tipo)
                    if resultado['success']:
                        # Eliminar de pendientes
                        s.delete(p)
                        s.commit()
                        logger.info(f"Factura pendiente emitida: sale {p.sale_id}")
                except Exception as e:
                    p.attempts += 1
                    p.last_error = str(e)
                    p.next_retry = datetime.now() + timedelta(minutes=5 * p.attempts)
                    s.commit()
                    logger.warning(f"Reintento fallido para sale {p.sale_id}: {e}")
```

### 8.3. Integrar en `main.py`

Agregar el worker AFIP al inicio de la app (similar al SyncWorker):

```python
# En main.py, dentro de start_dashboard():
from utils.afip.afip_sync_worker import AfipSyncWorker
self._afip_sync_worker = AfipSyncWorker(engine)
self._afip_sync_worker.start()

# En _on_close():
if hasattr(self, '_afip_sync_worker'):
    self._afip_sync_worker.stop()
```

---

## 9. Fase 4: Generación de PDF + QR

### 9.1. Datos del Código QR (RG 4892/2020)

El QR debe contener un JSON con los siguientes campos:

```json
{
  "ver": 1,
  "fecha": "2024-01-15",
  "cuit": 30712345678,
  "ptoVta": 1,
  "tipoCmp": 6,
  "nroCmp": 1234,
  "importe": 12100.00,
  "moneda": "PES",
  "ctz": 1,
  "tipoDocRec": 99,
  "nroDocRec": "0",
  "tipoCodAut": "E",
  "codAut": "12345678901234"
}
```

Este JSON se codifica en base64 y se genera un QR con la URL:

```
https://www.afip.gob.ar/fe/qr/?p=<base64_del_json>
```

### 9.2. `utils/afip/afip_pdf.py`

```python
"""Generación de PDF de factura electrónica con QR."""
import base64
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fpdf2 import FPDF
import qrcode  # pip install qrcode


def generar_qr_data(invoice: dict) -> str:
    """Genera la URL del QR para AFIP."""
    qr_json = {
        "ver": 1,
        "fecha": invoice['fecha_emision'].strftime('%Y-%m-%d'),
        "cuit": int(invoice['cuit']),
        "ptoVta": invoice['punto_venta'],
        "tipoCmp": invoice['cbte_tipo'],
        "nroCmp": invoice['cbte_nro'],
        "importe": float(invoice['imp_total']),
        "moneda": invoice.get('moneda', 'PES'),
        "ctz": float(invoice.get('moneda_ctz', 1)),
        "tipoDocRec": invoice.get('doc_tipo', 99),
        "nroDocRec": str(invoice.get('doc_nro', '0')),
        "tipoCodAut": "E",
        "codAut": invoice['cae'],
    }
    qr_base64 = base64.b64encode(json.dumps(qr_json).encode()).decode()
    return f"https://www.afip.gob.ar/fe/qr/?p={qr_base64}"


def generar_qr_image(qr_url: str, size: int = 150) -> Path:
    """Genera imagen PNG del código QR."""
    qr_dir = Path(__file__).parent.parent.parent / 'afip' / 'cache'
    qr_dir.mkdir(parents=True, exist_ok=True)

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    qr_path = qr_dir / f"qr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    img.save(str(qr_path))
    return qr_path


def generar_factura_pdf(invoice: dict, items: list, output_path: str) -> str:
    """
    Genera PDF de factura electrónica.

    Args:
        invoice: dict con datos de ElectronicInvoice
        items: lista de dicts con datos de los ítems
        output_path: ruta donde guardar el PDF

    Returns:
        Ruta del PDF generado
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)

    # ── Encabezado ──────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "FACTURA ELECTRÓNICA", ln=True, align="C")

    # Tipo de comprobante
    tipo_map = {1: 'A', 6: 'B', 11: 'C'}
    cbte_tipo = tipo_map.get(invoice['cbte_tipo'], str(invoice['cbte_tipo']))
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Tipo: {cbte_tipo}", ln=True, align="C")

    # CAE
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"CAE: {invoice['cae']}", ln=True, align="C")
    pdf.cell(0, 6, f"Vto. CAE: {invoice['cae_fecha_vto']}", ln=True, align="C")

    # ── Datos del Emisor ────────────────────────────────────────────────
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Datos del Emisor:", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, f"CUIT: {invoice['cuit']}", ln=True)
    pdf.cell(0, 5, f"Punto de Venta: {invoice['punto_venta']}", ln=True)
    pdf.cell(0, 5, f"Nro. Comprobante: {invoice['cbte_nro']:08d}", ln=True)
    pdf.cell(0, 5, f"Fecha de Emisión: {invoice['fecha_emision'].strftime('%d/%m/%Y')}", ln=True)

    # ── Datos del Receptor ──────────────────────────────────────────────
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Datos del Receptor:", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, f"Nombre: {invoice.get('nombre_receptor', 'Consumidor Final')}", ln=True)
    pdf.cell(0, 5, f"CUIT/DNI: {invoice.get('doc_nro', '-')}", ln=True)

    # ── Tabla de Ítems ──────────────────────────────────────────────────
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Detalle:", ln=True)

    # Encabezados
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(80, 6, "Descripción", border=1)
    pdf.cell(25, 6, "Cantidad", border=1, align="C")
    pdf.cell(30, 6, "Precio Unit.", border=1, align="R")
    pdf.cell(30, 6, "Subtotal", border=1, align="R")
    pdf.ln()

    # Ítems
    pdf.set_font("Helvetica", "", 8)
    for item in items:
        pdf.cell(80, 6, str(item.get('descripcion', '')), border=1)
        pdf.cell(25, 6, str(item.get('cantidad', '')), border=1, align="C")
        pdf.cell(30, 6, f"${item.get('precio_unit', 0):.2f}", border=1, align="R")
        pdf.cell(30, 6, f"${item.get('subtotal', 0):.2f}", border=1, align="R")
        pdf.ln()

    # ── Totales ─────────────────────────────────────────────────────────
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"TOTAL: ${float(invoice['imp_total']):.2f}", ln=True, align="R")

    # ── Código QR ───────────────────────────────────────────────────────
    qr_url = generar_qr_data(invoice)
    qr_path = generar_qr_image(qr_url)
    pdf.image(str(qr_path), x=150, y=pdf.get_y() + 5, w=40, h=40)

    # ── Guardar ─────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    pdf.output(output_path)

    return output_path
```

### 9.3. Dependencias Adicionales

Agregar a `requirements.txt`:

```txt
qrcode[pil]>=7.4.2
```

---

## 10. Fase 5: Manejo de Errores y Reproceso

### 10.1. Errores Comunes de AFIP

| Código | Mensaje | Acción |
|---|---|---|
| **10242** | Comprobante ya existe | Reprocesar: consultar y recuperar CAE |
| **600** | Error de token | Renovar TA y reintentar |
| **1000** | Usuario no autorizado | Verificar permisos en AFIP |
| **10015** | CUIT inválida | Verificar configuración |
| **10020** | Punto de venta no habilitado | Dar de alta en AFIP |
| **10024** | Comprobante no alcanzado | Verificar secuencia |
| **Timeout** | Servidor no responde | Guardar en pendientes, reintentar |

### 10.2. Estrategia de Reproceso

```python
# En AfipSyncWorker._process_pending():

# Backoff exponencial: 5min, 10min, 20min, 40min, ...
retry_delay = 5 * (2 ** (p.attempts - 1))  # minutos
p.next_retry = datetime.now() + timedelta(minutes=retry_delay)

# Máximo 10 intentos
if p.attempts >= 10:
    p.status = 'failed'
    # Notificar al usuario
```

### 10.3. Reglas de Oro

1. **NUNCA perder una venta:** La venta se guarda local siempre primero.
2. **NUNCA duplicar un comprobante:** Usar secuencia estricta de números.
3. **NUNCA modificar un CAE emitido:** Append-only. Si hay error, crear nota de crédito.
4. **SIEMPRE guardar XML:** Para auditoría y reproceso.
5. **SIEMPRE verificar QR:** El QR debe apuntar a la URL correcta de AFIP.

---

## 11. Fase 6: Testing en Homologación

### 11.1. Configuración de Homologación

1. **Obtener certificado de homologación:**
   - Ir a AFIP > Clave Fiscal > Administración de Certificados Digitales.
   - Generar un certificado de **prueba** (homologación).
   - Descargar `.crt` y `.key`.

2. **Configurar en la DB:**

```sql
INSERT INTO afip_config (tenant_id, cuit, cert_path, key_path, is_production, punto_venta, wsaa_url, wsfev1_url)
VALUES (
    'tenant-uuid-aqui',
    '30712345678',  -- CUIT de prueba
    '/ruta/afip/certs/tenant.crt',
    '/ruta/afip/certs/tenant.key',
    0,  -- is_production = false
    1,  -- punto de venta
    'https://wsaahomo.afip.gov.ar/ws/services/LoginCms',
    'https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL'
);
```

3. **Verificar conexión:**

```python
from utils.afip.afip_service import AfipService
service = AfipService(engine)
token, sign = service.get_ticket_acceso('tenant-uuid')
print(f"Token: {token[:20]}...")
ultimo = service.consultar_ultimo_comprobante('tenant-uuid', 6)
print(f"Último comprobante tipo 6: {ultimo}")
```

### 11.2. Verificar CAE en Homologación

Ir a: https://wswhomo.afip.gov.ar/sisgen/

> Los CAE de homologación **NO tienen validez fiscal**. Son solo para testing.

### 11.3. Casos de Test

| # | Caso | Resultado Esperado |
|---|---|---|
| 1 | Emitir Factura B a Consumidor Final | CAE otorgado, PDF generado con QR |
| 2 | Emitir Factura A a RI con IVA discriminado | CAE otorgado, IVA 21% calculado |
| 3 | Emitir Nota de Crédito B | CAE otorgado, comprobante asociado |
| 4 | AFIP caído (simular timeout) | Guardado en pendientes, reintento automático |
| 5 | Comprobante ya existe (reproceso) | CAE recuperado sin error |
| 6 | Config AFIP faltante | Error claro al usuario |
| 7 | Certificado expirado | Error claro al usuario |

---

## 12. Fase 7: Paso a Producción

### 12.1. Checklist Pre-Producción

- [ ] Certificado digital de **producción** (.crt + .key) vigente.
- [ ] Punto de venta dado de alta en AFIP con WSFEv1 habilitado.
- [ ] Software registrado como Responsable del Software Facturador.
- [ ] URLs de producción configuradas en `AfipConfig`.
- [ ] `is_production = True` en la configuración.
- [ ] Tests de homologación pasados.
- [ ] Backup de configuración y certificados.
- [ ] Logs de AFIP funcionando.
- [ ] Worker de pendientes activo.

### 12.2. Cambio de URLs

```python
# En AfipConfig para producción:
wsaa_url = 'https://wsaa.afip.gov.ar/ws/services/LoginCms'
wsfev1_url = 'https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL'
is_production = True
```

### 12.3. Verificación Post-Producción

1. Emitir una factura real de monto bajo.
2. Verificar CAE en: https://serviciosweb.afip.gob.ar/genericos/comprobantes/cae.aspx
3. Verificar QR escaneando con celular.
4. Verificar que el PDF se guarda correctamente.
5. Verificar que el XML request/response se almacena.

---

## 13. Fase 8: Funcionalidades Avanzadas

### 13.1. Notas de Crédito y Débito

- **Requiere comprobante asociado:** tipo, punto de venta, número, CUIT.
- **Período de comprobantes asociados:** desde/hasta (RG 4540/19).
- **Método:** `wsfev1.AgregarCmpAsoc()` + `wsfev1.AgregarPeriodoComprobantesAsociados()`.

### 13.2. Factura de Crédito Electrónica MiPyME (FCE)

- **RG 4367/18**
- **Requiere:** CBU del emisor, fecha de vencimiento de pago.
- **Método:** `wsfev1.AgregarOpcional()` con códigos de opción.

### 13.3. WSMTXCA (Factura con Detalle de Productos)

- **RG 2904/10, RG 3536/13**
- Emite factura con codificación de productos y códigos de barras.
- **Método:** `wsmtxca.SolicitarCAE()` con detalle de ítems.
- **Requiere:** Nomenclador de productos de AFIP.

### 13.4. Impresora Fiscal

- Integración con impresoras fiscales (Epson, Hasar, etc.) vía `pyserial`.
- Envía comandos a la impresora para imprimir comprobante fiscal.
- **Fuera de scope inicial.** Se puede agregar como Fase 9.

### 13.5. Email de Factura

- Usar `pyemail` (incluido en pyafipws) o `smtplib` para enviar PDF por email.
- Integrar con la vista de ventas: botón "Enviar factura por email".

### 13.6. Consulta de Padrón AFIP

- **WS-SR-PADRON:** Consulta datos de un CUIT en el padrón de AFIP.
- Útil para autocompletar datos del cliente al ingresar su CUIT.
- **Método:** `ws_sr_padron.AgetPersona()`.

---

## 14. Checklist de Tareas

### Legal / Administrativo

- [ ] Obtener Clave Fiscal nivel 2/3.
- [ ] Registrar software como Responsable del Software Facturador en AFIP.
- [ ] Obtener código de identificación del software.
- [ ] Verificar que los usuarios finales tienen certificado digital vigente.
- [ ] Verificar puntos de venta habilitados en AFIP.

### Infraestructura

- [ ] Crear directorio `afip/` con subdirectorios.
- [ ] Configurar `.gitignore` para certificados.
- [ ] Descargar `afip_ca_info.crt`.
- [ ] Agregar dependencias a `requirements.txt`.

### Base de Datos

- [ ] Crear modelos: `AfipConfig`, `ElectronicInvoice`, `ElectronicInvoiceItem`, `AfipPendingInvoice`.
- [ ] Crear migración para nuevas tablas.
- [ ] Agregar índices y constraints.

### Servicios AFIP

- [ ] Implementar `utils/afip/afip_config.py`.
- [ ] Implementar `utils/afip/afip_service.py` (WSAA + WSFEv1).
- [ ] Implementar manejo de errores (`AfipError`).
- [ ] Implementar cache de Ticket de Acceso.

### Controller

- [ ] Implementar `controllers/afip_controller.py`.
- [ ] Integrar con `SalesView` (botón "Emitir Factura").
- [ ] Implementar reproceso automático.
- [ ] Implementar cola de pendientes.

### Background Worker

- [ ] Implementar `utils/afip/afip_sync_worker.py`.
- [ ] Integrar en `main.py` (start/stop).
- [ ] Configurar intervalo de reintento.

### PDF + QR

- [ ] Implementar `utils/afip/afip_pdf.py`.
- [ ] Generar QR con datos de AFIP.
- [ ] Generar PDF con fpdf2.
- [ ] Agregar QR al PDF.
- [ ] Guardar PDF en disco.

### UI

- [ ] Crear `views/afip_view.py` (configuración AFIP por tenant).
- [ ] Agregar botón "Emitir Factura" en vista de ventas/historial.
- [ ] Mostrar estado de emisión (emitida, pendiente, error).
- [ ] Mostrar CAE, número de comprobante, fecha.
- [ ] Botón "Ver PDF" y "Enviar por Email".
- [ ] Banner de advertencia si AFIP está caído.

### Testing

- [ ] Configurar homologación.
- [ ] Test: Factura B a Consumidor Final.
- [ ] Test: Factura A con IVA discriminado.
- [ ] Test: Nota de Crédito.
- [ ] Test: AFIP caído (simular).
- [ ] Test: Reproceso.
- [ ] Test: QR válido.

### Producción

- [ ] Cambiar URLs a producción.
- [ ] Configurar certificados de producción.
- [ ] Verificar emisión real.
- [ ] Verificar QR escaneado.
- [ ] Verificar almacenamiento de XML.
- [ ] Documentar para el usuario final.

---

## 15. Comparativa con Líderes del Mercado

| Feature | CloudPOS (con AFIP) | Tango Gestión | SAP Business One | Square |
|---|---|---|---|---|
| Factura Electrónica AFIP | ✅ (WSFEv1) | ✅ Nativo | ✅ Nativo | ❌ (no Argentina) |
| Impresora Fiscal | ❌ (Fase 9) | ✅ Nativo | ✅ Nativo | ❌ |
| Notas de Crédito/Débito | ✅ (Fase 8) | ✅ Nativo | ✅ Nativo | ✅ |
| FCE MiPyME | ❌ (Fase 8) | ✅ Nativo | ✅ Nativo | ❌ |
| Consulta Padrón AFIP | ❌ (Fase 8) | ✅ Nativo | ✅ Nativo | ❌ |
| Dashboard Cloud | ✅ (sync) | ✅ Nativo | ✅ Nativo | ✅ Nativo |
| App Móvil | ❌ | ✅ | ✅ | ✅ |
| API REST | ❌ | ✅ (parcial) | ✅ | ✅ |
| Multi-moneda | ❌ | ✅ | ✅ | ✅ |
| Offline | ✅ Parcial | ❌ | ❌ | ✅ Parcial |
| Costo | Gratis (open source) | $$$ | $$$$ | % por transacción |

---

## 16. Glosario

| Término | Significado |
|---|---|
| **AFIP** | Administración Federal de Ingresos Públicos (Argentina). |
| **WSFEv1** | Web Service de Facturación Electrónica versión 1 (Mercado Interno). |
| **WSAA** | Web Service de Autenticación y Autorización. |
| **CAE** | Código de Autorización Electrónico. Número que AFIP asigna a cada comprobante. |
| **CAEA** | Código de Autorización Electrónico Anticipado. |
| **CUIT** | Clave Única de Identificación Tributaria. |
| **TA** | Ticket de Acceso. Credencial temporal para usar los webservices de AFIP. |
| **RG** | Resolución General (norma de AFIP). |
| **RI** | Responsable Inscripto (régimen de IVA). |
| **CF** | Consumidor Final. |
| **Homologación** | Ambiente de testing de AFIP. |
| **Producción** | Ambiente real de AFIP (facturas con validez fiscal). |
| **Reproceso** | Recuperar un CAE ya otorgado cuando la comunicación falla. |
| **Duplicado Digital** | Copia del comprobante emitido que debe guardarse por 10 años. |

---

## 17. Referencias y Enlaces

### AFIP Oficial

- [Facturación Electrónica](https://www.afip.gob.ar/fe/)
- [Web Services de AFIP](https://www.afip.gob.ar/ws/)
- [Consulta de CAE](https://serviciosweb.afip.gob.ar/genericos/comprobantes/cae.aspx)
- [Verificación de Comprobantes](https://serviciosweb.afip.gob.ar/genericos/verificacomprobante/)
- [RG 3749/15 - Facturación Electrónica](https://www.afip.gob.ar/resoluciones/2015/3749/)
- [RG 4291/17 - Código QR](https://www.boletinoficial.gob.ar/detalleAviso/primera/166652/20170627)
- [RG 4892/20 - QR Obligatorio](https://www.boletinoficial.gob.ar/detalleAviso/primera/239173/20201224)

### PyAfipWs

- [GitHub: reingart/pyafipws](https://github.com/reingart/pyafipws)
- [Manual PyAfipWs](https://www.sistemasagiles.com.ar/trac/wiki/ManualPyAfipWs)
- [Proyecto WSFEv1](https://www.sistemasagiles.com.ar/trac/wiki/ProyectoWSFEv1)
- [PyFEPDF (Generador PDF)](https://www.sistemasagiles.com.ar/trac/wiki/ManualPyAfipWs#PyFEPDF:generadordePDFdefacturaselectrónicas)
- [Errores Frecuentes](https://www.sistemasagiles.com.ar/trac/wiki/ManualPyAfipWs#ErroresFrecuentes)
- [Soporte Comercial](https://www.sistemasagiles.com.ar/)

### Normativa

- [RG 1361/02 - Almacenamiento de Duplicados](https://www.afip.gob.ar/resoluciones/2002/1361/)
- [RG 2485/08 - Facturación Electrónica Obligatoria](https://www.afip.gob.ar/resoluciones/2008/2485/)
- [RG 4367/18 - Factura de Crédito Electrónica MiPyME](https://www.boletinoficial.gob.ar/detalleAviso/primera/190854/20180906)
- [RG 4540/19 - Notas de Crédito/Débito](https://www.boletinoficial.gob.ar/detalleAviso/primera/212546/20190801)

### Herramientas

- [OpenSSL](https://www.openssl.org/) - Para generar certificados.
- [PySimpleSOAP](https://github.com/pysimplesoap/pysimplesoap) - Librería SOAP para Python.
- [PyFPDF](https://github.com/reingart/pyfpdf) - Generador de PDF.
- [qrcode](https://pypi.org/project/qrcode/) - Generador de códigos QR.

---

## Notas Finales

- Este documento es una **hoja de ruta**, no una implementación final. Cada fase debe implementarse, testearse y validarse antes de pasar a la siguiente.
- **Siempre empezar en homologación.** Nunca probar directamente en producción.
- **Guardar TODO:** XML request/response, CAE, QR, PDF. AFIP puede auditar y pedir estos archivos.
- **El código de este documento es pseudocódigo de referencia.** Debe adaptarse al estilo y convenciones de CloudPOS.
- **Consultar con un contador** antes de poner en producción. La normativa fiscal cambia frecuentemente en Argentina.

---

*Documento creado: Mayo 2026*
*Versión: 1.0*
*Estado: Planificación*
