from __future__ import absolute_import, division, generators, nested_scopes, print_function, unicode_literals, with_statement

from django.db import models
from django.utils.encoding import force_text, python_2_unicode_compatible
from django.utils.translation import get_language, ugettext_lazy as _


@python_2_unicode_compatible
class Attribute(models.Model):
    name    = models.CharField(_('name'), max_length=255)

    class Meta:
        app_label           = 'cms_articles'
        verbose_name        = _('attribute')
        verbose_name_plural = _('attributes')

    def __str__(self):
        return force_text(self.name)


