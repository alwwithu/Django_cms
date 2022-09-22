from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.utils.translation import gettext_lazy as _

from .archive import Archive
from .conf import settings
from .models import ArticlePlugin, ArticlesCategoryPlugin, ArticlesPlugin


class ArticlePlugin(CMSPluginBase):
    module = _("Articles")
    name = _("Article")
    model = ArticlePlugin
    cache = False
    text_enabled = True
    raw_id_fields = ["article"]

    def render(self, context, instance, placeholder):
        context.update(
            {
                "plugin": instance,
                "article": instance.get_article(context),
                "placeholder": placeholder,
            }
        )
        return context

    def get_render_template(self, context, instance, placeholder):
        return "cms_articles/article/%s.html" % instance.template


plugin_pool.register_plugin(ArticlePlugin)


class ArticlesPlugin(CMSPluginBase):
    module = _("Articles")
    name = _("Articles")
    model = ArticlesPlugin
    cache = False
    text_enabled = True

    def render(self, context, instance, placeholder):
        # get articles based on plugin settings
        articles = instance.get_articles(context)

        # provide archive
        archive = Archive(articles, context["request"])

        # filter articles based on query
        articles = archive.filter_articles()

        # paginate articles
        paginator = Paginator(articles, instance.number)
        try:
            articles = paginator.page(context["request"].GET.get(settings.CMS_ARTICLES_PAGE_FIELD, 1))
        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            articles = paginator.page(1)
        except EmptyPage:
            # If page is out of range (e.g. 9999), deliver last page of results.
            articles = paginator.page(paginator.num_pages)
        articles.page_field = settings.CMS_ARTICLES_PAGE_FIELD

        context.update(
            {
                "plugin": instance,
                "archive": archive,
                "articles": articles,
                "placeholder": placeholder,
            }
        )
        return context

    def get_render_template(self, context, instance, placeholder):
        return "cms_articles/articles/%s.html" % instance.template


plugin_pool.register_plugin(ArticlesPlugin)


class ArticlesCategoryPlugin(ArticlesPlugin):
    name = _("Articles category")
    model = ArticlesCategoryPlugin


plugin_pool.register_plugin(ArticlesCategoryPlugin)
