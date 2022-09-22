from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CMSArticlesConfig(AppConfig):
    name = "cms_articles"
    verbose_name = _("django CMS articles")

    def ready(self):
        from . import signals

        signals  # just use it
