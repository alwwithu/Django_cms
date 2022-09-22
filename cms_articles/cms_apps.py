from cms.app_base import CMSApp
from cms.apphook_pool import apphook_pool
from django.utils.translation import gettext_lazy as _


class CMSArticlesApp(CMSApp):
    name = _("Articles tree")
    app_name = "cms_articles"

    def get_urls(self, page=None, language=None, **kwargs):
        return ["cms_articles.urls"]


apphook_pool.register(CMSArticlesApp)
