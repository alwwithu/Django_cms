from django.contrib import admin

from ..conf import settings
from ..models import Attribute


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(site_id=settings.SITE_ID)
