from cms.app_base import CMSApp
from cms.apphook_pool import apphook_pool
from django.utils.translation import ugettext_lazy as _

from .urls import urlpatterns


class CMSArticlesApp(CMSApp):
    name = _('Articles tree')
    urls = [urlpatterns]
    app_name = 'cms_articles'


apphook_pool.register(CMSArticlesApp)
