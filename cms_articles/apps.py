from __future__ import absolute_import, division, generators, nested_scopes, print_function, unicode_literals, with_statement

from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class CMSArticlesConfig(AppConfig):
    name            = 'cms_articles'
    verbose_name    = _('django CMS articles')

    def ready(self):
        from . import signals
