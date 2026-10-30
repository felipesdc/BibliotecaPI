from django.apps import AppConfig


class AcervoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'acervo'

    def ready(self):
        from . import signals  # noqa: F401
