from core.models import SiteMaintenance


def get_maintenance_settings():
    settings_obj, _ = SiteMaintenance.objects.get_or_create(pk=1)
    return settings_obj
