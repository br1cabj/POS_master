# Despliegue de CloudPOS en VPS

Esta configuración sustituye Supabase por tres servicios propios: PostgreSQL,
la API privada de CloudPOS y el panel web. El navegador solo llega a HTTPS y
la API; **PostgreSQL no se publica en Internet**.

## Requisitos

- Un VPS Linux con Docker Engine y el complemento Docker Compose.
- Un dominio o subdominio (por ejemplo, `pos.tudominio.com`) con un registro A
  hacia la IP del VPS.
- Puertos TCP 80 y 443 abiertos. Caddy gestiona el certificado TLS.
- Para el escritorio, una red privada hacia el VPS: WireGuard, Tailscale o una
  VPN equivalente. Como alternativa temporal, se puede permitir el puerto
  5432 solo desde IPs fijas y con TLS, pero no es la opción recomendada.

## Primera instalación

En el VPS, clone el repositorio y cree el archivo de secretos:

```bash
cd POS_master
cp deploy/.env.example deploy/.env
chmod 600 deploy/.env
```

Edite `deploy/.env`: indique el dominio real y genere una contraseña larga,
única y URL-segura para `POSTGRES_PASSWORD`. No use comillas ni caracteres que
rompan una URL; letras, números, `-` y `_` son una elección segura.

Construya e inicie los servicios:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --build
docker compose --env-file deploy/.env -f deploy/docker-compose.yml ps
```

Abra `https://pos.tudominio.com`. El primer inicio de la API crea el esquema
PostgreSQL y las tablas de sesión. Compruebe también la salud desde el VPS:

```bash
curl -fsS https://pos.tudominio.com/api/v1/health
```

Debe responder `{"status":"ok"}`. Los logs se consultan con
`docker compose --env-file deploy/.env -f deploy/docker-compose.yml logs -f api`.

Antes de vincular una PC principal, defina `CLOUDPOS_ADMIN_API_KEY` en
`deploy/.env` y agréguelo al servicio `api`. Desde el VPS, emita una credencial
por dispositivo con `POST /api/v1/admin/devices`, enviando ese secreto en el
header `X-CloudPOS-Admin-Key`. Guarde el `device_token` resultante únicamente
en el `.env` de esa PC. Revocar o reemplazar ese token no detiene las ventas
locales: solo pausa la actualización de reportes móviles.

## Configuración del escritorio

Cada instalación de escritorio conserva SQLite local y solo la PC principal
publica una réplica de reportes mediante la API HTTPS. Nunca se entrega una
contraseña PostgreSQL al cliente. En el archivo `.env` situado junto al
ejecutable configure:

```dotenv
CLOUDPOS_SYNC_API_URL=https://pos.tudominio.com/api/v1
CLOUDPOS_DEVICE_TOKEN=token-revocable-emitido-por-el-vps
CLOUD_SYNC_INTERVAL=300
```

El token se emite en el VPS para una PC principal y puede revocarse sin afectar
el POS local. Reinicie la aplicación y confirme en Configuración que la
sincronización está activa. PostgreSQL permanece en la red privada Docker;
no abra el puerto 5432 para los escritorios.

## Migración desde Supabase

1. Detenga temporalmente las sincronizaciones de escritorio para evitar datos
   que cambien durante la copia.
2. Exporte la base de Supabase con `pg_dump` desde una estación segura.
3. Restaure el dump en la base PostgreSQL del VPS antes de iniciar la API.
   Use `pg_restore` para dumps de formato custom o `psql` para SQL plano.
4. Inicie la pila. La API añade las columnas/tablas de CloudPOS que falten.
5. Cambie el `.env` de cada escritorio a `CLOUD_DATABASE_URL`, valide ventas,
   stock y usuarios, y recién entonces retire las credenciales de Supabase.

Haga una copia de seguridad antes de cada paso. Si solo existe información en
los SQLite locales, conecte un escritorio a la nueva URL y deje que complete
una sincronización inicial, verificando el resultado antes de conectar los
demás.

## Operación y copias de seguridad

Ejecute un backup lógico periódico desde el VPS y guárdelo cifrado fuera de
esa máquina:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml exec -T db \
  pg_dump -U cloudpos_app -d cloudpos > cloudpos-$(date +%F).sql
```

Pruebe la restauración de una copia antes de depender de ella. Mantenga
actualizado Docker, el sistema operativo y las imágenes; para actualizar la
aplicación, obtenga el nuevo código y vuelva a ejecutar el comando `up -d
--build`.

## Límites de seguridad aplicados

- No hay clave de PostgreSQL ni clave de servicio en el bundle web.
- La API usa tokens aleatorios almacenados como hash, vencimiento y bloqueo de
  inicio de sesión tras intentos fallidos.
- Toda lectura se filtra por `tenant_id` en el servidor y se limita a tablas,
  columnas, relaciones y operadores permitidos.
- Las pantallas sensibles requieren rol `admin` o `supervisor`.
- Caddy entrega HTTPS y PostgreSQL vive únicamente en la red privada Docker.
