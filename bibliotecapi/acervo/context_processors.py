from django.conf import settings


def ambiente(request):
    return {'ambiente_demo': settings.DEMO_MODE}
