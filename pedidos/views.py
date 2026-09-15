from decimal import Decimal, InvalidOperation

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Carrito, CarritoItem, EstadoCarrito
from .serializers import (
    CarritoItemReadSerializer,
    CarritoItemWriteSerializer,
    CarritoSerializer,
    ConfirmarPedidoSerializer,
    PedidoReadSerializer,
)


class CarritoCreateView(APIView):
    """POST /api/pedidos/carrito/ -- crea un carrito de invitado nuevo y
    devuelve su token. El frontend lo guarda (localStorage) y lo manda en
    la URL de ahí en adelante para todo lo que haga con este carrito."""

    def post(self, request):
        carrito = Carrito.objects.create()
        return Response(CarritoSerializer(carrito).data, status=201)


class CarritoDetailView(APIView):
    """GET /api/pedidos/carrito/<token>/ -- el carrito completo, con items
    y total. Cualquiera que tenga el token puede verlo (es la identidad del
    carrito de invitado, no hay otro control de acceso todavía)."""

    def get(self, request, token):
        carrito = get_object_or_404(Carrito, token=token)
        return Response(CarritoSerializer(carrito).data)


class CarritoItemListView(APIView):
    """POST /api/pedidos/carrito/<token>/items/ -- agrega un ítem al carrito.

    Body para vianda diaria/semanal (plato_codigo = código del catálogo, ej. "8000"):
        {"modalidad_venta": "VIANDA_DIARIA", "cantidad": 1,
         "selecciones_dias": [{"dia_semana": "LUN", "plato_codigo": "8000"}]}
        {"modalidad_venta": "VIANDA_SEMANAL", "cantidad": 1,
         "selecciones_dias": [{"dia_semana": "LUN", "plato_codigo": "8000"}, ... 5 en total]}

    Body para a la carta / catering (articulo_codigo = código del catálogo):
        {"modalidad_venta": "A_LA_CARTA", "articulo_codigo": "7000", "cantidad": 2}
        {"modalidad_venta": "CATERING", "articulo_codigo": "4000", "cantidad": 12}
    """

    def post(self, request, token):
        carrito = get_object_or_404(Carrito, token=token)
        if carrito.estado != EstadoCarrito.ACTIVO:
            return Response({"detail": "Este carrito ya no está activo."}, status=409)

        serializer = CarritoItemWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save(carrito=carrito)
        carrito.save(update_fields=["updated_at"])  # bump updated_at
        return Response(CarritoItemReadSerializer(item).data, status=201)


class CarritoItemDetailView(APIView):
    """PATCH /api/pedidos/carrito/<token>/items/<item_id>/ -- sólo permite
    cambiar cantidad/observaciones (para cambiar el plato elegido, hay que
    borrar el ítem y agregar uno nuevo).
    DELETE /api/pedidos/carrito/<token>/items/<item_id>/ -- lo saca del carrito.
    """

    def _get_item(self, token, item_id):
        carrito = get_object_or_404(Carrito, token=token)
        item = get_object_or_404(CarritoItem, pk=item_id, carrito=carrito)
        return carrito, item

    def patch(self, request, token, item_id):
        carrito, item = self._get_item(token, item_id)
        if carrito.estado != EstadoCarrito.ACTIVO:
            return Response({"detail": "Este carrito ya no está activo."}, status=409)

        cantidad = request.data.get("cantidad")
        observaciones = request.data.get("observaciones")
        if cantidad is not None:
            try:
                cantidad = Decimal(str(cantidad))
            except (TypeError, ValueError, InvalidOperation):
                return Response({"cantidad": "Tiene que ser un número."}, status=400)
            if cantidad <= 0:
                return Response({"cantidad": "Tiene que ser mayor a 0 (para sacar el ítem, usá DELETE)."}, status=400)
            item.cantidad = cantidad
        if observaciones is not None:
            item.observaciones = observaciones
        item.save()
        carrito.save(update_fields=["updated_at"])
        return Response(CarritoItemReadSerializer(item).data)

    def delete(self, request, token, item_id):
        carrito, item = self._get_item(token, item_id)
        item.delete()
        carrito.save(update_fields=["updated_at"])
        return Response(status=204)


class CarritoConfirmarView(APIView):
    """POST /api/pedidos/carrito/<token>/confirmar/ -- convierte el carrito
    en un Pedido real. A partir de acá el carrito queda CONVERTIDO (ya no
    se puede seguir editando ni volver a confirmar).

    Body:
        {"cliente": {"nombre": "...", "apellido": "...", "telefono": "...",
                     "whatsapp": "...", "email": "..."},
         "tipo_entrega": "RETIRO" | "DELIVERY",
         "direccion": {"direccion": "...", "localidad": "...", ...},  // sólo si DELIVERY
         "fecha_retiro": "2026-09-20", "hora_retiro": "12:30",
         "observaciones": "..."}
    """

    def post(self, request, token):
        carrito = get_object_or_404(Carrito, token=token)
        if carrito.estado != EstadoCarrito.ACTIVO:
            return Response({"detail": "Este carrito ya no está activo (ya se confirmó o se abandonó)."}, status=409)
        if not carrito.items.exists():
            return Response({"detail": "El carrito está vacío."}, status=400)

        serializer = ConfirmarPedidoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pedido = serializer.save(carrito=carrito)
        return Response(PedidoReadSerializer(pedido).data, status=201)
