from django.apps import AppConfig


class OrderConfig(AppConfig):
    name = 'app.order'

    def ready(self):
        print("at ready")
        import app.order.signals
