"""
Crea los 2 "productos" que representan las modalidades de venta de Viandas
que NO son un plato específico, sino un paquete (15/09/2026, para poder
armar el carrito de compras):

- Vianda Diaria: 1 porción, 1 día (el cliente elige día + plato de las 3
  opciones de ese día en el Menú Semanal activo).
- Vianda Semanal: 5 porciones, lunes a viernes (el cliente elige 1 plato
  por cada día de la semana activa).

Los platos en sí (códigos 8000+) siguen con precio_venta=0 -- no se venden
sueltos, el precio está acá. Precios confirmados por Pichón: $9500 la
diaria (salvo el plato elegido tenga requiere_consulta=True, en cuyo caso
el precio final se confirma aparte), $38000 la semanal (precio de paquete,
no es 5 × diaria).

Se usa un código propio (9000/9001), fuera de cualquier rango ya usado
(4000+/7000+/8000+ Viandas y Catering, y los códigos originales de
GestQuand), para que quede clarísimo que esto es "modalidad de venta", no
un plato. Idempotente: se puede volver a correr sin duplicar nada ni pisar
un precio que Pichón ya haya cambiado a mano desde el admin (sólo crea si
no existe; si ya existe, no le toca el precio).

Uso:
    python manage.py cargar_modalidades_venta_viandas
"""

from decimal import Decimal

from django.core.management.base import BaseCommand

from catalogo.models import Articulo, Categoria, LineaNegocio, TipoArticulo, Unidad

PRODUCTOS = [
    {
        # Ojo: "9001" NO se usa -- ya lo tenía tomado un artículo importado
        # de GestQuand ("TABLA DE MADERA P/2", puro código de origen suyo,
        # nada que ver con Viandas). Mismo tipo de colisión que se encontró
        # y reparó en 7041/8005 -- ver reparar_colision_gestquand_viandas.
        "codigo": "9000",
        "nombre": "Vianda Diaria",
        "descripcion": "1 porción para 1 día, a elección entre las 3 opciones del día en el Menú Semanal vigente.",
        "precio_venta": Decimal("9500"),
    },
    {
        "codigo": "9002",
        "nombre": "Vianda Semanal",
        "descripcion": "5 porciones, lunes a viernes, a elección entre las 3 opciones de cada día en el Menú Semanal vigente.",
        "precio_venta": Decimal("38000"),
    },
]


class Command(BaseCommand):
    help = "Crea los productos 'Vianda Diaria' (9000) y 'Vianda Semanal' (9001) usados por el carrito de compras"

    def handle(self, *args, **options):
        unidad_default, _ = Unidad.objects.get_or_create(
            nombre="Unidad", defaults={"abreviatura": "u"}
        )
        categoria, created = Categoria.objects.get_or_create(
            linea_negocio=LineaNegocio.VIANDAS,
            nombre="Modalidad de Venta",
            defaults={"orden": 0},
        )
        if created:
            self.stdout.write(f"Categoría creada: {categoria}")

        for prod in PRODUCTOS:
            existente = Articulo.objects.filter(codigo=prod["codigo"]).first()
            if existente and existente.nombre.strip().lower() != prod["nombre"].strip().lower():
                # Mismo tipo de colisión que 7041/8005: el código ya lo tiene
                # OTRO artículo (típicamente importado de GestQuand con su
                # propio código de origen). No pisar nada -- avisar y frenar.
                self.stderr.write(
                    self.style.ERROR(
                        f"  El código '{prod['codigo']}' ya lo tiene «{existente.nombre}» "
                        f"(id={existente.pk}, {existente.categoria.linea_negocio}) -- NO es "
                        f"'{prod['nombre']}'. No se tocó nada; hay que elegir otro código."
                    )
                )
                continue

            obj, was_created = Articulo.objects.get_or_create(
                codigo=prod["codigo"],
                defaults=dict(
                    nombre=prod["nombre"],
                    descripcion=prod["descripcion"],
                    categoria=categoria,
                    unidad_compra=unidad_default,
                    unidad_uso=unidad_default,
                    relacion_unidades=1,
                    tipo=TipoArticulo.VENTA,
                    precio_costo=0,
                    precio_venta=prod["precio_venta"],
                    alicuota_iva=21,
                    visible_web=True,
                    requiere_consulta=False,
                    activo=True,
                ),
            )
            if was_created:
                self.stdout.write(f"  Creado: {obj.codigo} {obj.nombre} — ${obj.precio_venta}")
            else:
                self.stdout.write(f"  Ya existía: {obj.codigo} {obj.nombre} — ${obj.precio_venta} (no se tocó)")

        self.stdout.write(self.style.SUCCESS("Modalidades de venta listas."))
