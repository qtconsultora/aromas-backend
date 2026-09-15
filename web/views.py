from django.views.generic import TemplateView


class ViandasView(TemplateView):
    """Sitio público de venta de Viandas (diaria/semanal/a la carta). Todo
    el contenido (menú, catálogo, carrito) lo trae el propio HTML por JS
    consumiendo la API pública (/api/catalogo/..., /api/pedidos/...) --
    esta vista sólo sirve la página."""

    template_name = "web/viandas.html"
