from django.views.generic import TemplateView


class HubView(TemplateView):
    """Página principal (home): presentación de Aromas y accesos a cada
    línea de negocio (Viandas, Catering, Congelados a futuro, etc.)."""

    template_name = "web/hub.html"


class ViandasView(TemplateView):
    """Sitio público de venta de Viandas (diaria/semanal/a la carta). Todo
    el contenido (menú, catálogo, carrito) lo trae el propio HTML por JS
    consumiendo la API pública (/api/catalogo/..., /api/pedidos/...) --
    esta vista sólo sirve la página."""

    template_name = "web/viandas.html"


class CateringView(TemplateView):
    """Sitio público de catering/finger food para eventos: catálogo,
    calculadora de cantidades por evento y carrito, todo conectado a la
    API pública igual que Viandas."""

    template_name = "web/catering.html"
