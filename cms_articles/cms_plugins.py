from __future__ import absolute_import, division, generators, nested_scopes, print_function, unicode_literals, with_statement

from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils.translation import ugettext as _

from .models import ArticlePlugin, ArticlesPlugin, ArticlesCategoryPlugin


class ArticlePlugin(CMSPluginBase):
    module  = _('Articles')
    name    = _('Article')
    model   = ArticlePlugin
    text_enabled = True
    raw_id_fields = ['article']

    def render(self, context, instance, placeholder):
        context.update({
            'plugin': instance,
            'article': instance.get_article(context),
            'placeholder': placeholder,
        })
        return context

    def get_render_template(self, context, instance, placeholder):
        return 'cms_articles/article/%s.html' % instance.template

plugin_pool.register_plugin(ArticlePlugin)



class ArticlesPlugin(CMSPluginBase):
    module  = _('Articles')
    name    = _('Articles')
    model   = ArticlesPlugin
    text_enabled = True

    def render(self, context, instance, placeholder):
        articles    = instance.get_articles(context)
        paginator   = Paginator(articles, instance.number)
        try:
            articles = paginator.page(context['request'].GET.get('page', 1))
        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            articles = paginator.page(1)
        except EmptyPage:
            # If page is out of range (e.g. 9999), deliver last page of results.
            articles = paginator.page(paginator.num_pages)

        context.update({
            'plugin':       instance,
            'articles':     articles,
            'placeholder':  placeholder,
        })
        return context

    def get_render_template(self, context, instance, placeholder):
        return 'cms_articles/articles/%s.html' % instance.template

plugin_pool.register_plugin(ArticlesPlugin)



class ArticlesCategoryPlugin(ArticlesPlugin):
    name    = _('Articles category')
    model   = ArticlesCategoryPlugin

plugin_pool.register_plugin(ArticlesCategoryPlugin)

