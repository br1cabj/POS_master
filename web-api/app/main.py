"""Authenticated, tenant-scoped read API for the CloudPOS web dashboard.

The browser is intentionally never connected to PostgreSQL.  This module is
the only public data boundary; all database access stays on the VPS network.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import bcrypt
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, and_, delete, or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from database.migrations import setup_cloud_schema
from database.models import (
    Article,
    ArticleHistory,
    ArticleVariant,
    CashMovement,
    CashSession,
    Category,
    ComboItem,
    Customer,
    Promotion,
    Purchase,
    PurchaseDetail,
    PurchaseReturn,
    PurchaseReturnItem,
    Quotation,
    QuotationItem,
    Sale,
    SaleDetail,
    Stock,
    StockMovement,
    Supplier,
    Tenant,
    User,
    Warehouse,
)


DATABASE_URL = os.getenv('CLOUD_DATABASE_URL', os.getenv('DATABASE_CLOUD_URL', '')).strip()
SESSION_HOURS = max(1, int(os.getenv('CLOUDPOS_WEB_SESSION_HOURS', '8')))
MAX_PAGE_SIZE = 500
MANAGER_ROLES = frozenset({'admin', 'supervisor'})
security = HTTPBearer(auto_error=False)

_metadata = MetaData()
web_sessions = Table(
    'cloudpos_web_sessions', _metadata,
    Column('token_hash', String(64), primary_key=True),
    Column('tenant_id', String(36), nullable=False, index=True),
    Column('user_id', String(36), nullable=False, index=True),
    Column('role', String(50), nullable=False),
    Column('expires_at', DateTime, nullable=False, index=True),
)
web_login_attempts = Table(
    'cloudpos_web_login_attempts', _metadata,
    Column('tenant_id', String(36), primary_key=True),
    Column('username', String(100), primary_key=True),
    Column('attempts', Integer, nullable=False, default=0),
    Column('locked_until', DateTime, nullable=True),
    Column('last_attempt', DateTime, nullable=False),
)
cloud_devices = Table(
    'cloudpos_cloud_devices', _metadata,
    Column('id', String(36), primary_key=True), Column('tenant_id', String(36), nullable=False, index=True),
    Column('token_hash', String(64), nullable=False, unique=True), Column('name', String(120), nullable=False),
    Column('is_active', Integer, nullable=False, default=1), Column('created_at', DateTime, nullable=False),
)

MODELS = {
    'tenants': Tenant, 'users': User, 'categories': Category, 'suppliers': Supplier,
    'articles': Article, 'article_variants': ArticleVariant,
    'article_history': ArticleHistory, 'stocks': Stock, 'stock_movements': StockMovement,
    'customers': Customer, 'sales': Sale, 'sale_details': SaleDetail,
    'cash_sessions': CashSession, 'cash_movements': CashMovement,
    'purchases': Purchase, 'purchase_details': PurchaseDetail,
    'purchase_returns': PurchaseReturn, 'purchase_return_items': PurchaseReturnItem,
    'combo_items': ComboItem, 'quotations': Quotation, 'quotation_items': QuotationItem,
    'promotions': Promotion, 'warehouses': Warehouse,
}
MANAGER_ONLY = frozenset({
    'suppliers', 'article_history', 'cash_sessions', 'cash_movements', 'purchases',
    'purchase_details', 'purchase_returns', 'purchase_return_items', 'promotions',
})
ADMIN_ONLY = frozenset({'users'})
SECRET_COLUMNS = frozenset({'password_hash', 'recovery_pin_hash'})

# (source table, requested target table) -> ORM relationship attribute.  The
# alias from the dashboard is a presentation name, never an SQL identifier.
RELATIONSHIPS = {
    ('article_history', 'users'): 'user', ('cash_sessions', 'users'): 'user',
    ('cash_movements', 'customers'): 'customer', ('article_variants', 'articles'): 'article',
    ('article_variants', 'stocks'): 'stocks', ('article_variants', 'combo_items'): 'ingredients',
    ('stocks', 'article_variants'): 'variant', ('stocks', 'warehouses'): 'warehouse',
    ('stock_movements', 'article_variants'): 'variant', ('stock_movements', 'users'): 'user',
    ('sales', 'customers'): 'customer', ('sales', 'users'): 'user', ('sales', 'sale_details'): 'items',
    ('sale_details', 'article_variants'): 'variant', ('purchases', 'suppliers'): 'supplier',
    ('purchases', 'purchase_details'): 'items', ('purchase_returns', 'purchases'): 'purchase',
    ('purchase_returns', 'purchase_return_items'): 'items',
    ('purchase_details', 'article_variants'): 'variant',
    ('purchase_return_items', 'article_variants'): 'variant',
    ('quotations', 'customers'): 'customer', ('quotations', 'users'): 'user',
    ('quotations', 'quotation_items'): 'items', ('quotation_items', 'article_variants'): 'variant',
    ('promotions', 'article_variants'): 'variant', ('promotions', 'categories'): 'category',
    ('articles', 'categories'): 'category', ('articles', 'suppliers'): 'supplier',
}


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=512)
    tenant_id: str = Field(min_length=1, max_length=36)


class QueryRequest(BaseModel):
    select: str = Field(default='*', max_length=2000)
    filter: list[Any] | None = None
    order: dict[str, Any] | None = None
    limit: int | None = Field(default=None, ge=1, le=MAX_PAGE_SIZE)
    range: list[int] | None = None


class SyncEvent(BaseModel):
    event_id: str = Field(min_length=1, max_length=300)
    table: str = Field(min_length=1, max_length=80)
    payload: dict[str, Any]


class SyncBatch(BaseModel):
    events: list[SyncEvent] = Field(min_length=1, max_length=500)


class DeviceProvisionRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=36)
    name: str = Field(min_length=1, max_length=120)
    cloud_username: str = Field(min_length=3, max_length=100)
    cloud_password: str = Field(min_length=10, max_length=512)


class Selection:
    def __init__(self, columns: set[str] | None = None, relations: list[tuple[str, str, 'Selection']] | None = None):
        self.columns = columns or set()
        self.relations = relations or []


def _split_top_level(value: str) -> list[str]:
    parts, start, depth = [], 0, 0
    for index, char in enumerate(value):
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if depth < 0:
                raise ValueError('Selección inválida')
        elif char == ',' and depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
    if depth != 0:
        raise ValueError('Selección inválida')
    final = value[start:].strip()
    if final:
        parts.append(final)
    return parts


def _top_level_colon(value: str) -> int:
    depth = 0
    for index, char in enumerate(value):
        depth += char == '('
        depth -= char == ')'
        if char == ':' and depth == 0:
            return index
    return -1


def _parse_selection(value: str) -> Selection:
    selection = Selection()
    for item in _split_top_level(value):
        if not item:
            continue
        open_index = item.find('(')
        if open_index < 0:
            selection.columns.add(item)
            continue
        if not item.endswith(')'):
            raise ValueError('Selección inválida')
        head, nested = item[:open_index].strip(), item[open_index + 1:-1]
        colon = _top_level_colon(head)
        alias, target = (head[:colon].strip(), head[colon + 1:].strip()) if colon >= 0 else (head, head)
        target = target.split('!', 1)[0]
        if not alias or not target:
            raise ValueError('Selección inválida')
        selection.relations.append((alias, target, _parse_selection(nested)))
    return selection


def _database_engine() -> Engine:
    if not DATABASE_URL:
        raise RuntimeError('CLOUD_DATABASE_URL no está configurada en el servidor.')
    from sqlalchemy import create_engine
    return create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20, pool_recycle=1800)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _to_json(value: Any) -> Any:
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _columns_for(model: type, requested: set[str]) -> set[str]:
    available = {column.name for column in model.__table__.columns if column.name not in SECRET_COLUMNS}
    if '*' in requested:
        return available
    unknown = requested - available
    if unknown:
        raise HTTPException(status_code=400, detail='La consulta pidió una columna no permitida.')
    return requested


def _serialize(row: Any, table: str, selection: Selection, depth: int = 0) -> dict[str, Any]:
    if depth > 4:
        return {}
    payload = {name: _to_json(getattr(row, name)) for name in _columns_for(type(row), selection.columns)}
    for alias, target, nested in selection.relations:
        relation_name = RELATIONSHIPS.get((table, target))
        if relation_name is None:
            raise HTTPException(status_code=400, detail='La relación solicitada no está permitida.')
        related = getattr(row, relation_name)
        if isinstance(related, list):
            payload[alias] = [_serialize(item, target, nested, depth + 1) for item in related]
        else:
            payload[alias] = _serialize(related, target, nested, depth + 1) if related is not None else None
    return payload


def _scope_statement(model: type, table: str, tenant_id: str):
    if table == 'tenants':
        return model.id == tenant_id
    if table == 'categories':
        return or_(model.tenant_id == tenant_id, model.tenant_id.is_(None))
    if hasattr(model, 'tenant_id'):
        return model.tenant_id == tenant_id
    if table == 'article_variants':
        return model.article.has(Article.tenant_id == tenant_id)
    if table == 'stocks':
        return model.variant.has(ArticleVariant.article.has(Article.tenant_id == tenant_id))
    if table == 'sale_details':
        return model.sale.has(Sale.tenant_id == tenant_id)
    if table == 'purchase_details':
        return model.purchase.has(Purchase.tenant_id == tenant_id)
    if table == 'purchase_return_items':
        return model.purchase_return.has(PurchaseReturn.tenant_id == tenant_id)
    if table == 'quotation_items':
        return model.quotation.has(Quotation.tenant_id == tenant_id)
    if table == 'cash_movements':
        return model.session.has(CashSession.tenant_id == tenant_id)
    if table == 'combo_items':
        return model.combo.has(ArticleVariant.article.has(Article.tenant_id == tenant_id))
    if table == 'warehouses':
        return model.tenant_id == tenant_id
    raise HTTPException(status_code=400, detail='Tabla sin política de aislamiento definida.')


def _apply_filters(statement, model: type, filters: list[Any] | None):
    if not filters:
        return statement
    entries = filters if isinstance(filters[0], list) else [filters]
    for entry in entries:
        if not isinstance(entry, list) or len(entry) != 3:
            raise HTTPException(status_code=400, detail='Filtro inválido.')
        column_name, operator, value = entry
        if not isinstance(column_name, str) or column_name not in model.__table__.columns:
            raise HTTPException(status_code=400, detail='Filtro sobre columna no permitida.')
        column = model.__table__.columns[column_name]
        if operator == 'eq':
            statement = statement.where(column == value)
        elif operator == 'neq':
            statement = statement.where(column != value)
        elif operator == 'gt':
            statement = statement.where(column > value)
        elif operator == 'gte':
            statement = statement.where(column >= value)
        elif operator == 'lt':
            statement = statement.where(column < value)
        elif operator == 'lte':
            statement = statement.where(column <= value)
        elif operator == 'is' and value is None:
            statement = statement.where(column.is_(None))
        elif operator == 'in' and isinstance(value, list) and len(value) <= 500:
            statement = statement.where(column.in_(value))
        else:
            raise HTTPException(status_code=400, detail='Operador de filtro no permitido.')
    return statement


def _user_payload(user: User) -> dict[str, str]:
    return {
        'id': user.id, 'username': user.username, 'display_name': user.display_name or user.username,
        'role': user.role, 'tenant_id': user.tenant_id,
    }


def _attempt_key(data: LoginRequest) -> tuple[str, str]:
    return data.tenant_id, data.username.strip()


def _register_failed_login(db: Session, data: LoginRequest) -> None:
    tenant_id, username = _attempt_key(data)
    now = datetime.now(UTC).replace(tzinfo=None)
    previous = db.execute(select(web_login_attempts).where(
        and_(web_login_attempts.c.tenant_id == tenant_id, web_login_attempts.c.username == username)
    )).mappings().first()
    attempts = 1 if previous is None or previous['last_attempt'] <= now - timedelta(minutes=5) else previous['attempts'] + 1
    locked_until = now + timedelta(minutes=5) if attempts >= 5 else None
    if previous:
        db.execute(
            web_login_attempts.update().where(and_(web_login_attempts.c.tenant_id == tenant_id, web_login_attempts.c.username == username)).values(
                attempts=attempts, locked_until=locked_until, last_attempt=now
            )
        )
    else:
        db.execute(web_login_attempts.insert().values(
            tenant_id=tenant_id, username=username, attempts=attempts, locked_until=locked_until, last_attempt=now
        ))


def _get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    request: Request = None,
) -> User:
    if credentials is None or credentials.scheme.lower() != 'bearer' or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Sesión requerida.')
    engine: Engine = request.app.state.engine
    token_hash = _token_hash(credentials.credentials)
    with Session(engine) as db:
        now = datetime.now(UTC).replace(tzinfo=None)
        row = db.execute(select(web_sessions.c.user_id).where(
            and_(web_sessions.c.token_hash == token_hash, web_sessions.c.expires_at > now)
        )).first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='La sesión expiró.')
        user = db.get(User, row.user_id)
        if user is None or not user.is_active or user.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='La sesión no es válida.')
        db.expunge(user)
        return user


def _get_device(
    credentials: HTTPAuthorizationCredentials | None = Depends(security), request: Request = None,
):
    if credentials is None or credentials.scheme.lower() != 'bearer':
        raise HTTPException(status_code=401, detail='Dispositivo no autenticado.')
    with Session(request.app.state.engine) as db:
        device = db.execute(select(cloud_devices).where(and_(
            cloud_devices.c.token_hash == _token_hash(credentials.credentials), cloud_devices.c.is_active == 1,
        ))).mappings().first()
        if device is None:
            raise HTTPException(status_code=401, detail='Dispositivo no autorizado.')
        return dict(device)


def create_app(database_url: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.engine = _database_engine() if database_url is None else __import__('sqlalchemy').create_engine(database_url)
        setup_cloud_schema(app.state.engine)
        _metadata.create_all(app.state.engine, checkfirst=True)
        yield
        app.state.engine.dispose()

    app = FastAPI(
        title='CloudPOS Web API', version='1.0.0', docs_url=None, redoc_url=None, lifespan=lifespan,
    )
    if database_url:
        os.environ['CLOUD_DATABASE_URL'] = database_url
    origins = [item.strip() for item in os.getenv('CLOUDPOS_WEB_CORS_ORIGINS', '').split(',') if item.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware, allow_origins=origins, allow_credentials=False,
            allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type'], max_age=600,
        )

    @app.get('/api/v1/health', include_in_schema=False)
    def health(request: Request):
        with request.app.state.engine.connect() as connection:
            connection.exec_driver_sql('SELECT 1')
        return {'status': 'ok'}

    @app.post('/api/v1/admin/devices', include_in_schema=False)
    def provision_device(data: DeviceProvisionRequest, request: Request):
        """VPS-admin-only device provisioning; never callable from the desktop."""
        expected = os.getenv('CLOUDPOS_ADMIN_API_KEY', '')
        if not expected or request.headers.get('X-CloudPOS-Admin-Key') != expected:
            raise HTTPException(status_code=404, detail='Recurso no disponible.')
        raw_token, device_id = secrets.token_urlsafe(32), secrets.token_urlsafe(18)
        with Session(request.app.state.engine) as db:
            if db.get(Tenant, data.tenant_id) is None:
                db.add(Tenant(id=data.tenant_id, name='CloudPOS'))
            existing = db.scalar(select(User).where(and_(User.tenant_id == data.tenant_id, User.username == data.cloud_username)))
            if existing is None:
                db.add(User(id=secrets.token_urlsafe(18), tenant_id=data.tenant_id, username=data.cloud_username,
                    display_name=data.cloud_username, role='admin', is_active=True,
                    password_hash=bcrypt.hashpw(data.cloud_password.encode(), bcrypt.gensalt()).decode()))
            else:
                existing.password_hash = bcrypt.hashpw(data.cloud_password.encode(), bcrypt.gensalt()).decode()
                existing.role = 'admin'
            db.execute(cloud_devices.insert().values(
                id=device_id, tenant_id=data.tenant_id, name=data.name, token_hash=_token_hash(raw_token), is_active=1,
                created_at=datetime.now(UTC).replace(tzinfo=None)))
            db.commit()
        return {'device_id': device_id, 'device_token': raw_token}

    @app.post('/api/v1/auth/login', include_in_schema=False)
    def login(data: LoginRequest, request: Request):
        engine: Engine = request.app.state.engine
        username = data.username.strip()
        now = datetime.now(UTC).replace(tzinfo=None)
        with Session(engine) as db:
            attempt = db.execute(select(web_login_attempts).where(and_(
                web_login_attempts.c.tenant_id == data.tenant_id,
                web_login_attempts.c.username == username,
            ))).mappings().first()
            if attempt and attempt['locked_until'] and attempt['locked_until'] > now:
                raise HTTPException(status_code=429, detail='Demasiados intentos. Intente nuevamente en unos minutos.')
            user = db.scalar(select(User).where(and_(
                User.tenant_id == data.tenant_id, User.username == username,
                User.is_active.is_(True), User.deleted_at.is_(None),
            )))
            stored_hash = (user.password_hash if user else '$2b$12$C7/lLXPDFlWDZpTVr7XwZuIzJSfa0FyH96qYOaJuBF5Zm7Zb2Tpo.')
            valid = False
            try:
                valid = bcrypt.checkpw(data.password.encode('utf-8'), stored_hash.encode('utf-8') if isinstance(stored_hash, str) else stored_hash)
            except ValueError:
                valid = False
            if user is None or not valid:
                _register_failed_login(db, data)
                db.commit()
                raise HTTPException(status_code=401, detail='Credenciales o empresa incorrectas.')
            db.execute(delete(web_login_attempts).where(and_(
                web_login_attempts.c.tenant_id == data.tenant_id, web_login_attempts.c.username == username,
            )))
            db.execute(delete(web_sessions).where(web_sessions.c.expires_at <= now))
            token = secrets.token_urlsafe(32)
            db.execute(web_sessions.insert().values(
                token_hash=_token_hash(token), tenant_id=user.tenant_id, user_id=user.id,
                role=user.role,
                expires_at=now + timedelta(hours=SESSION_HOURS),
            ))
            db.commit()
            return {'session_token': token, **_user_payload(user)}

    @app.get('/api/v1/auth/session', include_in_schema=False)
    def session_info(user: User = Depends(_get_current_user)):
        return _user_payload(user)

    @app.post('/api/v1/auth/logout', status_code=status.HTTP_204_NO_CONTENT, include_in_schema=False)
    def logout(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(security)):
        if credentials and credentials.scheme.lower() == 'bearer':
            with request.app.state.engine.begin() as connection:
                connection.execute(delete(web_sessions).where(web_sessions.c.token_hash == _token_hash(credentials.credentials)))

    @app.post('/api/v1/sync/events', include_in_schema=False)
    def sync_events(batch: SyncBatch, request: Request, device=Depends(_get_device)):
        """One-way ingestion endpoint for the offline desktop reporting replica."""
        with Session(request.app.state.engine) as db:
            for event in batch.events:
                model = MODELS.get(event.table)
                if model is None:
                    raise HTTPException(status_code=400, detail='Tipo de dato no sincronizable.')
                payload = dict(event.payload)
                if SECRET_COLUMNS.intersection(payload):
                    raise HTTPException(status_code=400, detail='El evento contiene datos sensibles.')
                if 'tenant_id' in payload and payload['tenant_id'] != device['tenant_id']:
                    raise HTTPException(status_code=403, detail='Evento fuera de la empresa autorizada.')
                if event.table == 'tenants' and payload.get('id') != device['tenant_id']:
                    raise HTTPException(status_code=403, detail='Empresa no autorizada.')
                if event.table == 'users':
                    # Cloud passwords belong to the web account created by the
                    # VPS admin, never to the replicated desktop user record.
                    payload.pop('password_hash', None)
                    payload.pop('recovery_pin_hash', None)
                    existing = db.get(User, payload.get('id'))
                    if existing is None:
                        payload['password_hash'] = bcrypt.hashpw(secrets.token_bytes(32), bcrypt.gensalt()).decode()
                        db.add(User(**payload))
                    else:
                        for key, value in payload.items():
                            if key in {'id', 'password_hash', 'recovery_pin_hash'}:
                                continue
                            setattr(existing, key, value)
                else:
                    db.merge(model(**payload))
            db.commit()
        return {'accepted': [event.event_id for event in batch.events]}

    @app.post('/api/v1/data/{table}', include_in_schema=False)
    def data(table: str, query: QueryRequest, user: User = Depends(_get_current_user), request: Request = None):
        model = MODELS.get(table)
        if model is None:
            raise HTTPException(status_code=404, detail='Recurso no disponible.')
        if table in ADMIN_ONLY and user.role != 'admin':
            raise HTTPException(status_code=403, detail='No tiene permisos para este recurso.')
        if table in MANAGER_ONLY and user.role not in MANAGER_ROLES:
            raise HTTPException(status_code=403, detail='No tiene permisos para este recurso.')
        try:
            selection = _parse_selection(query.select)
            _columns_for(model, selection.columns)
        except ValueError:
            raise HTTPException(status_code=400, detail='Selección inválida.') from None
        statement = select(model).where(_scope_statement(model, table, user.tenant_id))
        statement = _apply_filters(statement, model, query.filter)
        if query.order:
            column_name = query.order.get('column')
            if column_name not in model.__table__.columns:
                raise HTTPException(status_code=400, detail='Orden no permitido.')
            column = model.__table__.columns[column_name]
            statement = statement.order_by(column.asc() if query.order.get('ascending') else column.desc())
        if query.range:
            if len(query.range) != 2 or query.range[0] < 0 or query.range[1] < query.range[0] or query.range[1] - query.range[0] >= MAX_PAGE_SIZE:
                raise HTTPException(status_code=400, detail='Rango inválido.')
            statement = statement.offset(query.range[0]).limit(query.range[1] - query.range[0] + 1)
        else:
            statement = statement.limit(query.limit or MAX_PAGE_SIZE)
        with Session(request.app.state.engine) as db:
            rows = db.scalars(statement).unique().all()
            return [_serialize(row, table, selection) for row in rows]

    return app


app = create_app()
