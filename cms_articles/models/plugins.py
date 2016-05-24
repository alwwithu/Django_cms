from __future__ import absolute_import, division, generators, nested_scopes, print_function, unicode_literals, with_statement

from cms.models import Page, CMSPlugin
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.functional import cached_property
from django.utils.translation import get_language, ugettext_lazy as _

from ..conf import settings

from .category import Category
from .article import Article


@python_2_unicode_compatible
class ArticlePlugin(CMSPlugin):
    article     = models.ForeignKey(Article, verbose_name=_('article'), related_name='+',
                    limit_choices_to={'publisher_is_draft': True})
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
            return self.article
        else:
            return self.article.get_published_object()



class ArticlesPluginBase(CMSPlugin):
    number      = models.IntegerField(_('Number of last articles'), default = 3)
    template    = models.CharField(_('Template'), max_length = 100,
        choices     = settings.CMS_ARTICLES_PLUGIN_ARTICLES_TEMPLATES,
        default     = settings.CMS_ARTICLES_PLUGIN_ARTICLES_TEMPLATES[0][0],
        help_text=_('The template used to render plugin.'),
    )

    class Meta:
        abstract = True



@python_2_unicode_compatible
class ArticlesPlugin(ArticlesPluginBase):
    tree        = models.ForeignKey(Page, verbose_name=_('tree'), related_name='+', blank=True, null=True,
                    help_text=_('Keep empty to show articles from current page, if current page is a tree.'), limit_choices_to={
                        'publisher_is_draft': False,
                        'application_urls': 'CMSArticlesApp',
                        'site_id':  settings.SITE_ID,
                    })
    categories  = models.ManyToManyField(Category, verbose_name=_('categories'), related_name='+', blank=True)

    def __str__(self):
        return _('last {} articles').format(self.number)

    def get_articles(self, context):
        tree = self.tree or self.placeholder.page

        try:
            edit_mode = context['request'].toolbar.edit_mode
        except:
            edit_mode = False

        if edit_mode:
            articles = Article.objects.drafts().filter(tree=tree.get_public_object())
        else:
            articles = Article.objects.public().published().filter(tree=tree)

        if self.categories.count():
            articles = articles.filter(categories=self.categories.all())

        return articles.order_by('-publication_date')

    def copy_relations(self, oldinstance):
        self.categories = oldinstance.categories.all()



@python_2_unicode_compatible
class ArticlesCategoryPlugin(ArticlesPluginBase):
    subcategories   = models.BooleanField(_('include sub-categories'), default=False,
                        help_text=_('Check, if you want to include articles from sub-categories of this category.'))

    def __str__(self):
        return _('last {} articles in this category').format(self.number)

    def get_articles(self, context):
        # no page - no category
        if self.placeholder.page is None:
            return []

        page = self.placeholder.page.get_draft_object()
        try:
            category = page.cms_articles_category
        except:
            category = Category.objects.create(page=page)

        if self.placeholder.page.publisher_is_draft:
            articles = Article.objects.drafts()
        else:
            articles = Article.objects.public().published()

        if self.subcategories:
            if not self.placeholder.page.is_home:
                articles = articles.filter(categories__page__in=self.placeholder.page.get_descendants(True))
            # if self.placeholder.page.is_home, take all
        else:
            articles = articles.filter(categories=category)

        return articles.order_by('-publication_date')

