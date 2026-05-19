from App.services.maintenance_mode import is_maintenance_mode_enabled


def maintenance_mode_status(request):
    return {
        "maintenance_mode_enabled_global": is_maintenance_mode_enabled(),
    }
