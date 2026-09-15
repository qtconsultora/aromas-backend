"""
Serializers de sólo lectura para el catálogo público (lo que va a consumir
la futura web): el menú semanal activo (para armar el selector de
vianda diaria/semanal día por día) y los artículos vendibles en general
(a la carta, catering) y las modalidades de venta (Vianda Diaria/Semanal).
"""

from rest_framework import serializers

from .models import Articulo, MenuSemanal, OpcionMenuDia


class PlatoMinimoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Articulo
        fields = ["id", "codigo", "nombre", "descripcion", "es_vegetariano", "imagen", "requiere_consulta"]


class ArticuloSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source="categoria.nombre", read_only=True)
    linea_negocio = serializers.CharField(source="categoria.linea_negocio", read_only=True)

    class Meta:
        model = Articulo
        fields = [
            "id", "codigo", "nombre", "descripcion", "descripcion_web",
            "categoria_nombre", "linea_negocio", "precio_venta",
            "es_vegetariano", "requiere_consulta", "imagen",
            "unidades_por_presentacion",
        ]


class OpcionMenuDiaSerializer(serializers.ModelSerializer):
    plato = PlatoMinimoSerializer(read_only=True)

    class Meta:
        model = OpcionMenuDia
        fields = ["numero_opcion", "plato"]


class MenuSemanalActivoSerializer(serializers.ModelSerializer):
    dias = serializers.SerializerMethodField()

    class Meta:
        model = MenuSemanal
        fields = ["id", "fecha_inicio", "dias"]

    def get_dias(self, obj):
        from catalogo.models import DIAS_SEMANA_HABILES

        opciones = list(
            obj.opciones.select_related("plato", "plato__categoria").order_by("dia_semana", "numero_opcion")
        )
        por_dia = {codigo: [] for codigo, _ in DIAS_SEMANA_HABILES}
        for op in opciones:
            por_dia[op.dia_semana].append(OpcionMenuDiaSerializer(op).data)
        return por_dia
