from __future__ import absolute_import, division, generators, nested_scopes, print_function, unicode_literals, with_statement

from django.utils.translation import ugettext_lazy as _

from cms.app_base import CMSApp
from cms.apphook_pool import apphook_pool

from .urls import urlpatterns


class CMSArticlesApp(CMSApp):
    name = _('Articles category')
    urls = [urlpatterns]
    app_name = 'cms_articles'

apphook_pool.register(CMSArticlesApp)

