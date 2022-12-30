from cms.models import CMSPlugin, Page
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from ..conf import settings
from .article import Article
from .attribute import Attribute
from .category import Category


class ArticlePlugin(CMSPlugin):
    article = models.ForeignKey(
        Article,
        verbose_name=_("article"),
        related_name="+",
        on_delete=models.CASCADE,
        limit_choices_to={"publisher_is_draft": True},
    )
    template = models.CharField(
        _("Template"),
        max_length=100,
        choices=settings.CMS_ARTICLES_PLUGIN_ARTICLE_TEMPLATES,
        default=settings.CMS_ARTICLES_PLUGIN_ARTICLE_TEMPLATES[0][0],
        help_text=_("The template used to render plugin."),
    )

    def __str__(self):
        return self.article.get_title()

    def get_article(self, context):
        try:
            edit_mode = context["request"].toolbar.edit_mode_active
        except (AttributeError, KeyError):
            edit_mode = False

        if edit_mode:
            return self.article
        else:
            return self.article.get_published_object()


class ArticlesPluginBase(CMSPlugin):
    number = models.PositiveSmallIntegerField(
        _("Number of last articles"), default=3, validators=[MinValueValidator(1)]
    )
    template = models.CharField(
        _("Template"),
        max_length=100,
        choices=settings.CMS_ARTICLES_PLUGIN_ARTICLES_TEMPLATES,
        default=settings.CMS_ARTICLES_PLUGIN_ARTICLES_TEMPLATES[0][0],
        help_text=_("The template used to render plugin."),
    )
    attributes = models.ManyToManyField(Attribute, verbose_name=_("attributes"), related_name="+", blank=True)

    class Meta:
        abstract = True

    def copy_relations(self, oldinstance):
        self.attributes.set(oldinstance.attributes.all())

    def get_articles(self, context):
        try:
            edit_mode = context["request"].toolbar.edit_mode_active
        except (AttributeError, KeyError):
            edit_mode = False

        if edit_mode:
            articles = Article.objects.drafts()
        else:
            articles = Article.objects.public().published()

        for attribute in self.attributes.all():
            articles = articles.filter(attributes=attribute)

        return articles


class ArticlesPlugin(ArticlesPluginBase):
    trees = models.ManyToManyField(
        Page,
        verbose_name=_("trees"),
        related_name="+",
        blank=True,
        limit_choices_to={
            "publisher_is_draft": False,
            "application_urls": "CMSArticlesApp",
            "node__site_id": settings.SITE_ID,
        },
    )
    categories = models.ManyToManyField(Category, verbose_name=_("categories"), related_name="+", blank=True)

    def __str__(self):
        return _("last {} articles").format(self.number)

    def get_articles(self, context):
        articles = super().get_articles(context)

        if self.trees.count():
            articles = articles.filter(tree__in=self.trees.all())

        if self.categories.count():
            articles = articles.filter(categories__in=self.categories.all())

        return articles

    def copy_relations(self, oldinstance):
        self.trees.set(oldinstance.trees.all())
        self.categories.set(oldinstance.categories.all())
        super().copy_relations(oldinstance)


class ArticlesCategoryPlugin(ArticlesPluginBase):
    subcategories = models.BooleanField(
        _("include sub-categories"),
        default=False,
        help_text=_("Check, if you want to include articles from sub-categories of this category."),
    )

    def __str__(self):
        return _("last {} articles in this category").format(self.number)

    def get_articles(self, context):
        # no page - no category
        if self.placeholder.page is None:
            return []

        page = self.placeholder.page.get_draft_object()
        try:
            category = page.cms_articles_category
        except Category.DoesNotExist:
            category = Category.objects.create(page=page)

        articles = super().get_articles(context)

        if self.subcategories:
            if not self.placeholder.page.is_home:
                articles = articles.filter(categories__page__node__path__startswith=page.node.path)
            # if self.placeholder.page.is_home, take all
        else:
            articles = articles.filter(categories=category)

        return articles
