from django.apps import AppConfig


class ProductConfig(AppConfig):
    name = 'app.product'

    def ready(self):
        print("at ready")
        import app.product.signals