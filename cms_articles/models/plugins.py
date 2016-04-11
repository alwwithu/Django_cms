from __future__ import absolute_import, division, generators, nested_scopes, print_function, unicode_literals, with_statement

from cms.models import Page, CMSPlugin
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.functional import cached_property
from django.utils.translation import get_language, ugettext_lazy as _

from ..conf import settings

from .article import Article



@python_2_unicode_compatible
class ArticlePlugin(CMSPlugin):
    article     = models.ForeignKey(Article, verbose_name=_('article'), related_name='+',
                    limit_choices_to={'publisher_is_draft': False})
    template    = models.CharField(_('Template'), max_length = 100,
        choices     = settings.CMS_ARTICLES_PLUGIN_ARTICLE_TEMPLATES,
        default     = settings.CMS_ARTICLES_PLUGIN_ARTICLE_TEMPLATES[0][0],
        help_text   = _('The template used to render plugin.'),
    )

    def __str__(self):
        return self.article.get_title()

    def get_article(self, context):
        try:
            edit_mode = context['request'].toolbar.edit_mode
        except:
            edit_mode = False

        if edit_mode:
            return self.article.get_draft_object()
        else:
            return self.article

    @cached_property
    def render_template(self):
        return 'cms_articles/article/%s.html' % self.template



@python_2_unicode_compatible
class ArticlesPlugin(CMSPlugin):
    number      = models.IntegerField(_('Number of last articles'), default = 3)
    template    = models.CharField(_('Template'), max_length = 100,
        choices     = settings.CMS_ARTICLES_PLUGIN_ARTICLES_TEMPLATES,
        default     = settings.CMS_ARTICLES_PLUGIN_ARTICLES_TEMPLATES[0][0],
        help_text=_('The template used to render plugin.'),
    )
    category    = models.ForeignKey(Page, verbose_name=_('category'), related_name='+', blank=True, null=True,
                    help_text=_('Keep empty to show articles from current page, if current page is a category.'), limit_choices_to={
                        'publisher_is_draft': False,
                        'application_urls': 'CMSArticlesApp',
                        'site_id':  settings.SITE_ID,
                    })

    def __str__(self):
        return _('last {} articles').format(self.number)

    def get_articles(self, context):
        category = self.category or self.placeholder.page

        try:
            edit_mode = context['request'].toolbar.edit_mode
        except:
            edit_mode = False

        if edit_mode:
            articles = Article.objects.drafts().filter(category=category.get_public_object())
        else:
            articles = Article.objects.public().published().filter(category=category)

        return articles.order_by('-publication_date')[:self.number]

    @cached_property
    def render_template(self):
        return 'cms_articles/articles/%s.html' % self.template


