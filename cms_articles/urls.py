from __future__ import absolute_import, division, generators, nested_scopes, print_function, unicode_literals, with_statement

from django.conf.urls import url

from . import views
from .conf import settings

if settings.APPEND_SLASH:
    regexp = r'^(?P<slug>{})/$'.format(settings.CMS_ARTICLES_SLUG_REGEXP)
else:
    regexp = r'^(?P<slug>{})$'.format(settings.CMS_ARTICLES_SLUG_REGEXP)

urlpatterns = [
    url(regexp, views.article, name='article'),
]

