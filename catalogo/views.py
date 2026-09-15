from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Articulo, MenuSemanal
from .serializers import ArticuloSerializer, MenuSemanalActivoSerializer


class MenuSemanalActivoView(APIView):
    """GET /api/catalogo/menu-semanal/activo/ -- la semana publicada ahora
    mismo, con las 3 opciones de cada día (lunes a viernes). Es lo que
    necesita el frontend para armar el selector de vianda diaria/semanal."""

    def get(self, request):
        menu = MenuSemanal.objects.filter(activo=True).prefetch_related(
            "opciones__plato__categoria"
        ).first()
        if not menu:
            return Response({"detail": "No hay un Menú Semanal activo cargado todavía."}, status=404)
        return Response(MenuSemanalActivoSerializer(menu).data)


class ModalidadesVentaView(ListAPIView):
    """GET /api/catalogo/modalidades-venta/ -- los productos 'Vianda Diaria'
    (9000) y 'Vianda Semanal' (9002), con su precio actual. El frontend los
    usa para mostrar el precio sin tenerlo hardcodeado."""

    serializer_class = ArticuloSerializer

    def get_queryset(self):
        return Articulo.objects.filter(codigo__in=["9000", "9002"], activo=True)


class ArticuloListView(ListAPIView):
    """GET /api/catalogo/articulos/?linea_negocio=CATERING -- catálogo
    vendible (a la carta, catering), visible en la web. No incluye los
    platos de vianda sueltos (esos se listan vía menu-semanal/activo,
    porque su venta depende del día/semana, no se compran sueltos)."""

    serializer_class = ArticuloSerializer

    def get_queryset(self):
        qs = Articulo.objects.filter(activo=True, visible_web=True).select_related("categoria")
        linea = self.request.query_params.get("linea_negocio")
        if linea:
            qs = qs.filter(categoria__linea_negocio=linea.upper())
        categoria = self.request.query_params.get("categoria")
        if categoria:
            qs = qs.filter(categoria__nombre__iexact=categoria)
        return qs
