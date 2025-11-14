from django.apps import AppConfig
from . import signals


class LoansConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'loans'
    
    def ready(self):
        import loans.signals  # Import signals