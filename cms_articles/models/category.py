from __future__ import absolute_import, division, generators, nested_scopes, print_function, unicode_literals, with_statement

from cms.models import Page
from django.db import models
from django.utils.encoding import force_text, python_2_unicode_compatible
from django.utils.translation import get_language, ugettext_lazy as _

from ..conf import settings


@python_2_unicode_compatible
class Category(models.Model):
    page    = models.OneToOneField(Page, verbose_name=_('page'), related_name='cms_articles_category',
                limit_choices_to={'publisher_is_draft': False, 'site_id': settings.SITE_ID})
    class Meta:
        app_label           = 'cms_articles'
        verbose_name        = _('category')
        verbose_name_plural = _('categories')

    def __str__(self):
        return force_text(self.page)


