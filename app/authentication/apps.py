from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    name = "app.authentication"

    def ready(self):
        print("at ready")
        import app.authentication.signals
