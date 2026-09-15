"""
Serializers del carrito de compras (invitado, sin login -- ver el
docstring de pedidos/models.py). La parte más particular es
CarritoItemWriteSerializer: valida distinto según la modalidad de venta
(vianda diaria/semanal necesita selecciones_dias validadas contra el Menú
Semanal activo; a la carta/catering necesita un articulo_id directo), y
resuelve el precio SIEMPRE del lado del servidor (nunca confía en un
precio que mande el cliente).
"""

from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from catalogo.models import Articulo, DIAS_SEMANA_HABILES, MenuSemanal, OpcionMenuDia
from clientes.models import Cliente, Direccion

from .models import (
    Carrito,
    CarritoItem,
    CarritoItemDiaSemana,
    EstadoCarrito,
    ItemPedidoDiaSemana,
    ModalidadVenta,
    OrigenPedido,
    Pedido,
    PedidoItem,
    TipoEntrega,
)

DIAS_HABILES_SET = {codigo for codigo, _ in DIAS_SEMANA_HABILES}

CODIGO_VIANDA_DIARIA = "9000"
CODIGO_VIANDA_SEMANAL = "9002"


class PlatoMinimoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Articulo
        fields = ["id", "codigo", "nombre", "es_vegetariano", "requiere_consulta"]


class ArticuloMinimoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Articulo
        fields = ["id", "codigo", "nombre", "precio_venta", "imagen"]


class CarritoItemDiaSemanaReadSerializer(serializers.ModelSerializer):
    plato = PlatoMinimoSerializer(read_only=True)

    class Meta:
        model = CarritoItemDiaSemana
        fields = ["dia_semana", "plato"]


class SeleccionDiaInputSerializer(serializers.Serializer):
    dia_semana = serializers.ChoiceField(choices=DIAS_SEMANA_HABILES)
    plato_codigo = serializers.CharField()


class CarritoItemReadSerializer(serializers.ModelSerializer):
    articulo = ArticuloMinimoSerializer(read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    selecciones_dias = CarritoItemDiaSemanaReadSerializer(many=True, read_only=True)

    class Meta:
        model = CarritoItem
        fields = [
            "id", "articulo", "modalidad_venta", "descripcion", "cantidad",
            "precio_unit", "subtotal", "requiere_consulta", "observaciones",
            "selecciones_dias", "created_at",
        ]


class CarritoItemWriteSerializer(serializers.Serializer):
    """Serializer de ENTRADA (no ModelSerializer -- los campos que hacen
    falta cambian según la modalidad_venta, más simple validarlo a mano)."""

    modalidad_venta = serializers.ChoiceField(choices=ModalidadVenta.choices)
    cantidad = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"), default=Decimal("1"))
    observaciones = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    articulo_codigo = serializers.CharField(required=False)
    selecciones_dias = SeleccionDiaInputSerializer(many=True, required=False)

    def validate(self, attrs):
        modalidad = attrs["modalidad_venta"]
        es_vianda = modalidad in (ModalidadVenta.VIANDA_DIARIA, ModalidadVenta.VIANDA_SEMANAL)

        if es_vianda:
            self._validar_vianda(modalidad, attrs)
        else:
            self._validar_directo(attrs)

        return attrs

    def _validar_vianda(self, modalidad, attrs):
        selecciones = attrs.get("selecciones_dias") or []
        cantidad_esperada = 1 if modalidad == ModalidadVenta.VIANDA_DIARIA else 5

        if len(selecciones) != cantidad_esperada:
            raise serializers.ValidationError(
                {
                    "selecciones_dias": (
                        f"{modalidad} necesita exactamente {cantidad_esperada} selección(es) de día, "
                        f"se recibieron {len(selecciones)}."
                    )
                }
            )

        dias_pedidos = [s["dia_semana"] for s in selecciones]
        if modalidad == ModalidadVenta.VIANDA_SEMANAL and set(dias_pedidos) != DIAS_HABILES_SET:
            raise serializers.ValidationError(
                {"selecciones_dias": "La vianda semanal necesita un plato para cada día de lunes a viernes, sin repetir ninguno."}
            )
        if len(dias_pedidos) != len(set(dias_pedidos)):
            raise serializers.ValidationError({"selecciones_dias": "No se puede elegir el mismo día dos veces."})

        menu_activo = MenuSemanal.objects.filter(activo=True).first()
        if not menu_activo:
            raise serializers.ValidationError("No hay un Menú Semanal activo -- no se puede vender vianda diaria/semanal ahora mismo.")

        platos_resueltos = []
        for sel in selecciones:
            opcion = OpcionMenuDia.objects.filter(
                menu_semanal=menu_activo, dia_semana=sel["dia_semana"], plato__codigo=sel["plato_codigo"]
            ).select_related("plato").first()
            if not opcion:
                raise serializers.ValidationError(
                    {
                        "selecciones_dias": (
                            f"El plato elegido para {sel['dia_semana']} no es una de las 3 opciones "
                            "del Menú Semanal vigente para ese día."
                        )
                    }
                )
            platos_resueltos.append((sel["dia_semana"], opcion.plato))

        attrs["_platos_resueltos"] = platos_resueltos
        attrs["_codigo_producto"] = CODIGO_VIANDA_DIARIA if modalidad == ModalidadVenta.VIANDA_DIARIA else CODIGO_VIANDA_SEMANAL

    def _validar_directo(self, attrs):
        articulo_codigo = attrs.get("articulo_codigo")
        if not articulo_codigo:
            raise serializers.ValidationError({"articulo_codigo": "Hace falta indicar qué artículo se agrega (a la carta / catering)."})
        articulo = Articulo.objects.filter(codigo=articulo_codigo, activo=True).first()
        if not articulo:
            raise serializers.ValidationError({"articulo_codigo": "No existe ese artículo, o no está activo."})
        if articulo.tipo not in ("VENTA", "ELABORADO"):
            raise serializers.ValidationError({"articulo_codigo": "Ese artículo no se vende directamente (es un insumo)."})
        attrs["_articulo_directo"] = articulo

    @transaction.atomic
    def create(self, validated_data):
        carrito = validated_data["carrito"]
        modalidad = validated_data["modalidad_venta"]
        es_vianda = modalidad in (ModalidadVenta.VIANDA_DIARIA, ModalidadVenta.VIANDA_SEMANAL)

        if es_vianda:
            articulo = Articulo.objects.get(codigo=validated_data["_codigo_producto"])
            platos_resueltos = validated_data["_platos_resueltos"]
            requiere_consulta = any(plato.requiere_consulta for _, plato in platos_resueltos)
        else:
            articulo = validated_data["_articulo_directo"]
            requiere_consulta = articulo.requiere_consulta

        item = CarritoItem.objects.create(
            carrito=carrito,
            articulo=articulo,
            modalidad_venta=modalidad,
            cantidad=validated_data["cantidad"],
            precio_unit=articulo.precio_venta,
            requiere_consulta=requiere_consulta,
            observaciones=validated_data.get("observaciones", ""),
        )

        if es_vianda:
            CarritoItemDiaSemana.objects.bulk_create(
                [
                    CarritoItemDiaSemana(item_carrito=item, dia_semana=dia, plato=plato)
                    for dia, plato in platos_resueltos
                ]
            )

        return item


class CarritoSerializer(serializers.ModelSerializer):
    items = CarritoItemReadSerializer(many=True, read_only=True)
    total_estimado = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Carrito
        fields = ["id", "token", "estado", "items", "total_estimado", "created_at", "updated_at"]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Confirmar carrito -> Pedido
# ---------------------------------------------------------------------------


class ClienteInputSerializer(serializers.Serializer):
    """Datos mínimos para identificar/crear al cliente al confirmar el
    pedido -- es invitado hasta acá, recién ahora hace falta saber quién es.
    Se busca un Cliente ya existente por teléfono/whatsapp (lo que se haya
    mandado) antes de crear uno nuevo, para no duplicar."""

    nombre = serializers.CharField(max_length=100)
    apellido = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    telefono = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    whatsapp = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    email = serializers.EmailField(max_length=150, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if not attrs.get("telefono") and not attrs.get("whatsapp"):
            raise serializers.ValidationError("Hace falta un teléfono o un WhatsApp para poder confirmar el pedido.")
        return attrs


class DireccionInputSerializer(serializers.Serializer):
    direccion = serializers.CharField(max_length=255)
    localidad = serializers.CharField(max_length=100, required=False, allow_blank=True, default="Rosario")
    provincia = serializers.CharField(max_length=100, required=False, allow_blank=True, default="Santa Fe")
    cp = serializers.CharField(max_length=10, required=False, allow_blank=True, default="")
    referencia = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class ItemPedidoDiaSemanaReadSerializer(serializers.ModelSerializer):
    plato = PlatoMinimoSerializer(read_only=True)

    class Meta:
        model = ItemPedidoDiaSemana
        fields = ["dia_semana", "plato"]


class PedidoItemReadSerializer(serializers.ModelSerializer):
    articulo = ArticuloMinimoSerializer(read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    selecciones_dias = ItemPedidoDiaSemanaReadSerializer(many=True, read_only=True)

    class Meta:
        model = PedidoItem
        fields = [
            "id", "articulo", "modalidad_venta", "descripcion", "cantidad",
            "precio_unit", "subtotal", "observaciones", "selecciones_dias",
        ]


class PedidoReadSerializer(serializers.ModelSerializer):
    items = PedidoItemReadSerializer(many=True, read_only=True)
    cliente_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Pedido
        fields = [
            "id", "cliente_nombre", "fecha_pedido", "fecha_retiro", "hora_retiro",
            "estado", "total_estimado", "sena", "origen", "tipo_entrega",
            "pago_estado", "observaciones", "items", "created_at",
        ]

    def get_cliente_nombre(self, obj):
        return str(obj.cliente)


class ConfirmarPedidoSerializer(serializers.Serializer):
    """POST /api/pedidos/carrito/<token>/confirmar/ -- convierte el carrito
    (que tiene que tener al menos 1 ítem) en un Pedido real. A partir de acá
    el carrito deja de poder editarse (queda CONVERTIDO)."""

    cliente = ClienteInputSerializer()
    tipo_entrega = serializers.ChoiceField(choices=TipoEntrega.choices, default=TipoEntrega.RETIRO)
    direccion = DireccionInputSerializer(required=False)
    fecha_retiro = serializers.DateField(required=False, allow_null=True)
    hora_retiro = serializers.TimeField(required=False, allow_null=True)
    observaciones = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs["tipo_entrega"] == TipoEntrega.DELIVERY and "direccion" not in attrs:
            raise serializers.ValidationError({"direccion": "Un pedido con envío necesita una dirección de entrega."})
        return attrs

    def _resolver_cliente(self, datos):
        telefono = datos.get("telefono") or ""
        whatsapp = datos.get("whatsapp") or ""
        cliente = None
        if whatsapp:
            cliente = Cliente.objects.filter(whatsapp=whatsapp).first()
        if not cliente and telefono:
            cliente = Cliente.objects.filter(telefono=telefono).first()

        if cliente:
            # Completa datos que puedan faltar, sin pisar los que ya tenía.
            cambiado = False
            for campo in ("nombre", "apellido", "email"):
                valor_nuevo = datos.get(campo)
                if valor_nuevo and not getattr(cliente, campo):
                    setattr(cliente, campo, valor_nuevo)
                    cambiado = True
            if whatsapp and not cliente.whatsapp:
                cliente.whatsapp = whatsapp
                cambiado = True
            if telefono and not cliente.telefono:
                cliente.telefono = telefono
                cambiado = True
            if cambiado:
                cliente.save()
            return cliente

        return Cliente.objects.create(
            nombre=datos.get("nombre", ""),
            apellido=datos.get("apellido", ""),
            telefono=telefono,
            whatsapp=whatsapp,
            email=datos.get("email", ""),
        )

    def _resolver_direccion(self, cliente, datos):
        if not datos:
            return None
        existente = Direccion.objects.filter(
            cliente=cliente, direccion__iexact=datos["direccion"], activo=True
        ).first()
        if existente:
            return existente
        return Direccion.objects.create(
            cliente=cliente,
            direccion=datos["direccion"],
            localidad=datos.get("localidad") or "Rosario",
            provincia=datos.get("provincia") or "Santa Fe",
            cp=datos.get("cp", ""),
            referencia=datos.get("referencia", ""),
        )

    @transaction.atomic
    def create(self, validated_data):
        carrito = validated_data["carrito"]

        cliente = self._resolver_cliente(validated_data["cliente"])
        direccion = self._resolver_direccion(cliente, validated_data.get("direccion"))

        pedido = Pedido.objects.create(
            cliente=cliente,
            fecha_retiro=validated_data.get("fecha_retiro"),
            hora_retiro=validated_data.get("hora_retiro"),
            total_estimado=carrito.total_estimado,
            origen=OrigenPedido.WEB,
            direccion=direccion,
            tipo_entrega=validated_data["tipo_entrega"],
            observaciones=validated_data.get("observaciones", ""),
        )

        for item in carrito.items.select_related("articulo").prefetch_related("selecciones_dias__plato"):
            pedido_item = PedidoItem.objects.create(
                pedido=pedido,
                articulo=item.articulo,
                modalidad_venta=item.modalidad_venta,
                descripcion=item.descripcion,
                cantidad=item.cantidad,
                precio_unit=item.precio_unit,
                observaciones=item.observaciones,
            )
            if item.selecciones_dias.exists():
                ItemPedidoDiaSemana.objects.bulk_create(
                    [
                        ItemPedidoDiaSemana(item_pedido=pedido_item, dia_semana=sel.dia_semana, plato=sel.plato)
                        for sel in item.selecciones_dias.all()
                    ]
                )

        carrito.cliente = cliente
        carrito.estado = EstadoCarrito.CONVERTIDO
        carrito.save(update_fields=["cliente", "estado", "updated_at"])

        return pedido
