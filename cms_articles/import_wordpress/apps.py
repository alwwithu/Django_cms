from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class CmsArticlesImportWordpressConfig(AppConfig):
    name = 'cms_articles.import_wordpress'
    verbose_name = _('django CMS articles - import from WordPress')
