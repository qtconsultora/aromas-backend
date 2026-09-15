# Aromas — Backend / Base de datos

Backend en Django para Aromas (viandas, catering/finger food, café y venta
directa, más atención en el local). Segunda versión del modelo: se
reorganizó tomando como base **GestQuand** (el sistema de gestión que
Pichón ya tiene funcionando para otro comercio), para no resolver dos
veces los mismos problemas — costeo de recetas, unidades de compra vs.
uso, facturación, stock, turnos de caja — y se le sumó lo específico de
Aromas: el menú semanal rotativo y las reservas (de mesa y de eventos).

## Estructura del proyecto

```
config/        configuración del proyecto (settings, urls)
usuarios/      PerfilUsuario (rol: admin/cajero/vendedor) sobre el login de Django
catalogo/      Unidad, Categoria, Marca, Articulo (unificado), Receta, MenuSemanal, OpcionMenuDia
clientes/      Cliente, ClienteAuth, Direccion
pedidos/       Carrito, CarritoItem, Pedido, PedidoItem, ItemPedidoDiaSemana
facturacion/   Turno, Comprobante, ComprobanteItem, Pago, Numeracion, CajaMovimiento
stock/         MovimientoStock
reservas/      ReservaEvento, ReservaMesa
```

## Qué se tomó de GestQuand y por qué cambió todo

La primera versión de este backend tenía un `Producto` separado por línea
de negocio (ProductoVianda/ProductoCatering/ProductoCafe) y no tenía forma
de modelar ingredientes ni costear una receta de verdad. Mirando GestQuand
—que ya resuelve esto en producción para otro comercio— se rehizo el
catálogo sobre esa misma idea:

- **Un solo modelo `Articulo`** para todo (ingredientes, platos elaborados,
  productos de venta directa), diferenciado por el campo `tipo`:
  - `VENTA`: se vende al público, también puede usarse como insumo de otra receta.
  - `INSUMO`: sólo para recetas, no aparece en ventas.
  - `ELABORADO`: tiene receta (composición de insumos), se vende.
- **Unidad de compra vs. unidad de uso**: cada artículo tiene
  `unidad_compra` (ej. bidón, caja), `unidad_uso` (ej. cc, gramo) y
  `relacion_unidades` (cuántas unidades de uso trae la unidad de compra,
  ej. bidón de 5L → 5000). El costo por unidad de uso se calcula en código
  (`Articulo.costo_uso`, nunca se guarda en la base) y es lo que se usa
  para costear recetas — nunca el costo de compra directo.
- **`Receta`**: tabla de composición auto-relacionada sobre `Articulo` (un
  elaborado está hecho de N insumos, cada uno con su cantidad). El costo
  de un elaborado (`Articulo.costo_receta`) es la suma de
  `cantidad × costo_uso` de cada insumo.
- **Precio sugerido** = `costo × (1 + IVA%/100) × (1 + Markup%/100)`. Es
  sólo una referencia — `precio_venta` lo edita Pichón y es lo que se usa
  siempre para vender, igual que en GestQuand.
- **Facturación** (`facturacion/`): `Comprobante` con tipos FA_A/FA_B/FA_C,
  NC/ND, NP (nota de pedido) y TK (ticket no fiscal), numeración propia
  por tipo + punto de venta (`Numeracion.siguiente_numero()`), `Pago` por
  comprobante (soporta pagos mixtos) y `Turno` + `CajaMovimiento` para la
  venta mostrador en el local. El campo `cae` queda vacío y `es_fiscal` en
  `False` hasta que se implemente la integración con ARCA (como en
  GestQuand, esa parte queda pendiente de certificados — ver "Próximos
  pasos").
- **`stock/MovimientoStock`**: cada movimiento de stock queda auditado
  (cuánto había antes, cuánto quedó después) y actualiza
  `Articulo.stock_actual` automáticamente al guardarse.
- **`clientes/`**: `Cliente` separado de `usuarios` (igual que en
  GestQuand: un cliente compra, no opera el sistema). `ClienteAuth` deja
  preparado el login por WhatsApp o email para cuando exista el sitio con
  cuentas — todavía no tiene sesiones JWT (`clientes_sesiones` en
  GestQuand); se agrega cuando haya una API real que las necesite.

### Lo que se simplificó a propósito (por ahora)

- **Listas de precio por cliente/canal**: GestQuand las tiene (con
  descuento % y overrides por artículo) porque atiende mayoristas.
  Aromas no tiene ese caso de uso todavía, así que no se incluyeron —
  se pueden sumar después con el mismo patrón si hace falta.
- **`markup_tipo`** (tabla de aplicación masiva de markup): el campo
  `markup_pct` ya vive directo en `Categoria` y `Marca`, que alcanza para
  "aplicar markup a todo el grupo" sin una tabla aparte.
- **Sesiones JWT de clientes**: se deja para cuando exista el backend de
  API real (FastAPI/DRF) que las va a usar.

### Lo específico de Aromas (no existe en GestQuand)

- **`MenuSemanal` / `OpcionMenuDia`**: el menú rotativo de viandas (3
  opciones × día, lunes a viernes). Tiene un método
  `MenuSemanal.reglas_incumplidas()` que chequea las reglas de
  `reglas_eleccion_menus.md` (opción 3 siempre vegetariana, jueves =
  pastas, viernes = 1 minuta exacta, guisos sólo martes, pescados sólo
  jueves/viernes, no repetir platos en la semana ni contra las 2 semanas
  anteriores/siguiente). Hay una acción **"Validar reglas de negocio"**
  en el admin de `MenuSemanal`.
- **`reservas/`**: `ReservaEvento` (reservar fecha para un catering/evento,
  con seña y estado, antes de armar el pedido en sí — se linkea a un
  `Pedido` cuando se confirma el detalle) y `ReservaMesa` (reservar mesa
  para consumir en el local).

## Carrito y pedidos

`Carrito`/`CarritoItem` son el carrito web (antes de confirmar). Al
confirmar se arma un `Pedido` con sus `PedidoItem` — cada ítem apunta al
`Articulo`, guarda la modalidad de venta (vianda diaria, vianda semanal, a
la carta, catering) y el precio al momento de pedir (si después cambia el
precio del artículo, el pedido viejo no se ve afectado). Cuando la
modalidad es vianda diaria/semanal, `ItemPedidoDiaSemana` guarda qué plato
eligió el cliente para cada día. `Pedido.origen` distingue si se cargó en
el local o vino de la web/WhatsApp, y `Pedido.comprobante` se completa
cuando ese pedido se facturó.

## Instalación (Windows)

Necesitás [Python 3.11+](https://www.python.org/downloads/) instalado (al
instalarlo, tildá "Add python.exe to PATH").

Abrí una terminal (PowerShell) en esta carpeta y ejecutá:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Con el servidor corriendo, entrá a http://127.0.0.1:8000/admin/ y logueate
con el usuario que acabás de crear. Ahí vas a poder ver y editar todo:
catálogo, recetas con costeo, clientes, pedidos, facturación, stock,
turnos y reservas — es un panel administrativo ya funcional mientras se
construye el sitio.

Las próximas veces que quieras trabajar en el proyecto, sólo hace falta
activar el entorno (`.venv\Scripts\activate`) y correr
`python manage.py runserver`.

### Cargar el catálogo real como punto de partida

El proyecto incluye los 47 platos "a la carta", los 15 platos exclusivos
del menú semanal (con la semana publicada hoy en el sitio), las 14
bebidas y los 42 productos de catering, tomados de los archivos que ya
tenías (`data.js` del sitio de viandas y `productos_catering.xlsx`), ahora
como `Articulo` (tipo ELABORADO o VENTA según corresponda). Para
cargarlos:

```powershell
python manage.py cargar_catalogo_real
```

Se puede correr de nuevo en cualquier momento (actualiza en vez de
duplicar). Para empezar de cero: `python manage.py cargar_catalogo_real --borrar-antes`.

> **Importante sobre las recetas**: estos artículos se cargan con el texto
> libre de ingredientes de siempre (visible en `ingredientes_texto`, sólo
> de referencia), pero **sin** ítems de `Receta` — el catálogo viejo nunca
> tuvo cantidades reales por insumo. `costo_receta` va a dar $0 hasta que
> cargues los insumos con cantidad desde el admin, plato por plato (por
> eso conviene no hacerlo con IA: son datos que hay que pesar o medir de
> verdad para que el costeo sirva).
>
> La semana importada como `MenuSemanal` quedó con 2 cosas para revisar
> según `reglas_eleccion_menus.md` (la lasaña del miércoles cuenta como
> pasta y las pastas sólo deberían ir el jueves; el viernes tiene 2
> minutas en vez de 1). Es la semana tal cual está hoy en el sitio, no se
> corrigió nada al importar. La acción "Validar reglas de negocio" del
> admin te lo muestra en cualquier momento.

### Cargar insumos y elaborados reales desde GestQuand

GestQuand ya tiene cargados en producción los ingredientes reales (carnes,
verdulería, pescadería, fiambres, quesos, almacén, etc.) y los platos
elaborados (incluida toda la carta de catering/finger food), con costos y
varias recetas ya armadas. En vez de tipear todo de nuevo, se copian
directo:

1. Corré `exportar_para_aromas.py` (está en `Desktop\gestQuand`, al lado de
   `config.py`) — es de sólo lectura, no toca la base de GestQuand. Te deja
   un `export_aromas.json` en esa misma carpeta.
2. Copiá ese archivo a `catalogo/fixtures_source/gestquand_export.json` en
   este proyecto (o pasale la ruta con `--archivo`).
3. Corré:

   ```powershell
   python manage.py cargar_desde_gestquand
   ```

Esto crea/actualiza todos los `Articulo` tipo INSUMO y ELABORADO **con su
código real de GestQuand**, preservando categorías y marcas con el mismo
nombre que tienen allá (nunca se renombran ni se fusionan). Como GestQuand
no separa por línea de negocio, se asigna automáticamente:

- **INSUMO** → línea "Insumos" (no se venden, sólo se usan en recetas).
- **ELABORADO** → línea "Catering / Finger food" (son los platos reales que
  ya se preparan y venden — incluye la categoría `CATERING` que pediste,
  y algunas otras como `Panificados`, `TABLAS`, `RELLENOS`; si alguna no
  corresponde ahí, se cambia en un click desde el admin, editando la
  categoría, no artículo por artículo).

También copia las recetas que ya existían en GestQuand (queda afuera sólo
la receta de un elaborado si usa como insumo un artículo tipo VENTA de
GestQuand, que no se importa en este paso).

> **Códigos que se liberan automáticamente**: dos códigos de GestQuand
> ("42" y "1005") coincidían por casualidad con los índices internos que
> traían los platos de vianda del sitio viejo. El comando renombra esos
> dos artículos viejos a "V-42"/"V-1005" (sólo el código interno, nada
> visible cambia) para dejarle el código real al artículo de GestQuand.

> **Fotos**: quedan afuera de este paso a propósito — es lo próximo que
> viene, une cada artículo con su imagen real.

## Variables de entorno (`.env`)

Ver `.env.example`. En desarrollo local no hace falta tocar nada (usa
SQLite automáticamente); `DATABASE_URL` sólo se completa cuando se conecte
a Postgres en Render.

## Próximos pasos (según lo charlado)

1. **Este repo**: cargar insumos reales y recetas con cantidad (para que
   el costeo sirva), y revisar el catálogo importado.
2. **Sitio con carrito**: una vez que la base esté firme, construir el
   sitio (API con Django + frontend con carrito) que reemplace las páginas
   estáticas actuales de pedidos.
3. **Hosting**: Render — plan Starter de Web Service (USD 7/mes) + Postgres
   Starter (USD 6/mes), ≈USD 13/mes para arrancar. `DATABASE_URL` la da
   Render directamente. Paso a paso más abajo, en "Desplegar en Render".
4. **Dominio**: ya registrado en NIC.AR — se conecta cuando el sitio esté
   listo para publicarse.
5. **Usuarios**: recién ahí se crean las cuentas de verdad (clientes y,
   si hace falta, usuarios de staff aparte del superusuario) para publicar.
6. **Facturación fiscal (ARCA)**: la estructura de `Comprobante` ya está
   preparada (tipos, códigos ARCA, numeración, CAE), igual que en
   GestQuand. Falta implementar la integración (WSAA → FECAESolicitar →
   CAE) cuando tengas los certificados — se había evaluado afipsdk.com
   como capa de integración en Python.

## Desplegar en Render (paso a paso)

El repo ya está preparado para Render: `requirements.txt` tiene `gunicorn`
y `whitenoise`, hay un `Procfile`, un `build.sh` (instala dependencias,
junta los archivos estáticos y corre las migraciones en cada deploy) y un
`render.yaml` que describe el Web Service + la base Postgres para que
Render los cree juntos con un solo click ("Blueprint").

Render despliega desde un repositorio de Git, así que primero hay que
subir el proyecto a GitHub.

### 1. Subir el proyecto a GitHub (una sola vez)

1. Si no tenés cuenta, creá una en https://github.com (gratis).
2. Creá un repositorio nuevo, vacío y privado (por ejemplo
   "aromas-backend"). No marques "Add README" ni ".gitignore" — el
   proyecto ya los tiene.
3. En tu máquina, abrí una terminal en `Desktop\aromasmarket` y corré:
   ```
   git init
   git add .
   git commit -m "Primera version para desplegar"
   git branch -M main
   git remote add origin https://github.com/TU-USUARIO/aromas-backend.git
   git push -u origin main
   ```
   (La primera vez te va a pedir iniciar sesión en GitHub — seguí las
   instrucciones que te muestre la terminal o el navegador.)

> El `.gitignore` ya excluye `.env`, `db.sqlite3`, `staticfiles/` y
> `__pycache__/` — no se sube nada sensible ni la base local.

### 2. Crear los servicios en Render

**Opción rápida (recomendada): Blueprint**
1. Entrá a https://render.com y creá una cuenta (podés usar la de GitHub).
2. Dashboard → "New" → "Blueprint".
3. Conectá tu cuenta de GitHub y elegí el repositorio "aromas-backend".
4. Render lee `render.yaml` solo y te muestra dos servicios para crear: el
   Web Service ("aromas-backend") y la base ("aromas-db"). Confirmá con
   "Apply".
5. El primer build tarda unos minutos (instala todo, corre
   `collectstatic` y `migrate`).

**Opción manual** (si preferís no usar Blueprint)
1. Dashboard → "New" → "PostgreSQL". Nombre "aromas-db", plan Starter.
2. Dashboard → "New" → "Web Service". Conectá el repo y configurá:
   - Build Command: `bash build.sh`
   - Start Command: `gunicorn config.wsgi --log-file -`
   - Plan: Starter
3. En la pestaña "Environment" del Web Service, cargá las variables de
   abajo a mano.

### 3. Variables de entorno en Render

Con el Blueprint la mayoría ya quedan cargadas solas. Revisá/completá en
la pestaña "Environment" del Web Service:

| Variable | Valor |
|---|---|
| `DJANGO_SECRET_KEY` | dejá que Render la genere sola |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | `.onrender.com` (funciona con cualquier subdominio que asigne Render) |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://*.onrender.com` |
| `DATABASE_URL` | se completa sola con el Blueprint, o conectando la base desde "Add Environment Variable" → "From Database" |

Cuando esté listo el dominio de NIC.AR, sumalo (separado por coma) a
`DJANGO_ALLOWED_HOSTS`, y su versión `https://` a
`DJANGO_CSRF_TRUSTED_ORIGINS`.

### 4. Primer superusuario en producción

La base de Render arranca vacía. Para crear el usuario admin:
1. En el Web Service de Render, pestaña "Shell" (abre una terminal contra
   el servidor ya desplegado).
2. Corré `python manage.py createsuperuser` y seguí las instrucciones.

Si en cambio querés arrancar con el catálogo ya cargado (viandas, menú
semanal, catering) en vez de una base vacía, avisame antes de este paso y
vemos cómo migrar los datos que ya tenés en local.

### 5. Probar

Render da una URL del tipo `https://aromas-backend.onrender.com`. Ahí:
- `/admin/` — panel de administración.
- `/probar-carrito/` — la misma pantalla de prueba del carrito, ahora
  accesible desde cualquier lado, no sólo desde tu máquina.
- `/api/...` — la API que usa esa pantalla.

### Nota sobre las fotos de productos

Las fotos que se suban desde el admin (`MEDIA_ROOT`) se guardan en el
disco del servidor. El plan Starter de Web Service de Render **no tiene
disco persistente**: en cada redeploy se puede perder lo que se subió
después del build anterior. No es un problema para probar ahora, pero
antes de cargar fotos "para quedarse" conviene sumar un disco persistente
(add-on pago de Render) o pasar a guardarlas en un servicio externo (por
ejemplo Cloudinary). Queda pendiente para cuando llegue ese momento.
