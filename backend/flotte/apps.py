from django.apps import AppConfig


class FlotteConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "flotte"
    verbose_name = "TransitFlow — gestion de flotte"

    def ready(self):
        from . import signals  # noqa: F401