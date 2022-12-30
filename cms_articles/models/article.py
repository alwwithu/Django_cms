# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import OrderedDict

from cms import constants
from cms.exceptions import LanguageError, PublicIsUnmodifiable, PublicVersionNeeded
from cms.models import Page
from cms.utils import i18n
from cms.utils.copy_plugins import copy_plugins_to
from django.db import models
from django.utils.encoding import force_str
from django.utils.functional import cached_property
from django.utils.html import strip_tags
from django.utils.timezone import now
from django.utils.translation import get_language, gettext_lazy as _

from ..conf import settings
from .attribute import Attribute
from .category import Category
from .managers import ArticleManager


class Article(models.Model):
    tree = models.ForeignKey(
        Page,
        verbose_name=_("tree"),
        related_name="cms_articles",
        on_delete=models.PROTECT,
        help_text=_("The page the article is accessible at."),
        limit_choices_to={
            "publisher_is_draft": False,
            "application_urls": "CMSArticlesApp",
            "node__site_id": settings.SITE_ID,
        },
    )
    template = models.CharField(
        _("template"),
        max_length=100,
        choices=settings.CMS_ARTICLES_TEMPLATES,
        default=settings.CMS_ARTICLES_TEMPLATES[0][0],
        help_text=_("The template used to render the content."),
    )
    attributes = models.ManyToManyField(
        Attribute,
        verbose_name=_("attributes"),
        related_name="articles",
        blank=True,
        limit_choices_to={"site_id": settings.SITE_ID},
    )
    categories = models.ManyToManyField(Category, verbose_name=_("categories"), related_name="articles", blank=True)
    created_by = models.CharField(_("created by"), max_length=constants.PAGE_USERNAME_MAX_LENGTH, editable=False)
    changed_by = models.CharField(_("changed by"), max_length=constants.PAGE_USERNAME_MAX_LENGTH, editable=False)
    creation_date = models.DateTimeField(auto_now_add=True)
    changed_date = models.DateTimeField(auto_now=True)

    publication_date = models.DateTimeField(
        _("publication date"),
        null=True,
        blank=True,
        help_text=_('When the article should go live. Status must be "Published" for article to go live.'),
        db_index=True,
    )
    publication_end_date = models.DateTimeField(
        _("publication end date"),
        null=True,
        blank=True,
        help_text=_("When to expire the article. Leave empty to never expire."),
        db_index=True,
    )
    order_date = models.DateTimeField(_("publication or creation time"), auto_now_add=True, editable=False)
    login_required = models.BooleanField(_("login required"), default=False)

    # Placeholders (plugins)
    placeholders = models.ManyToManyField("cms.Placeholder", related_name="cms_articles", editable=False)

    # Publisher fields
    publisher_is_draft = models.BooleanField(default=True, editable=False, db_index=True)
    # This is misnamed - the one-to-one relation is populated on both ends
    publisher_public = models.OneToOneField(
        "self",
        on_delete=models.CASCADE,
        related_name="publisher_draft",
        null=True,
        editable=False,
    )
    languages = models.CharField(max_length=255, editable=False, blank=True, null=True)

    # X Frame Options for clickjacking protection
    @cached_property
    def xframe_options(self):
        return self.tree.xframe_options

    # Fake page interface
    parent_page = None

    @cached_property
    def node(self):
        return self.tree.node

    # Managers
    objects = ArticleManager()

    class Meta:
        permissions = (("publish_article", "Can publish article"),)
        ordering = ("-order_date",)
        verbose_name = _("article")
        verbose_name_plural = _("articles")
        app_label = "cms_articles"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title_cache = {}

    def __str__(self):
        try:
            title = self.get_title(fallback=True)
        except LanguageError:
            try:
                title = self.title_set.all()[0]
            except IndexError:
                title = None
        if title is None:
            title = ""
        return str(title)

    def __repr__(self):
        # This is needed to solve the infinite recursion when
        # adding new articles.
        return object.__repr__(self)

    def is_dirty(self, language):
        state = self.get_publisher_state(language)
        return state == constants.PUBLISHER_STATE_DIRTY

    def get_absolute_url(self, language=None, fallback=True):
        if not language:
            language = get_language()

        return "{}{}{}{}".format(
            self.tree.get_absolute_url(language, fallback),
            "" if settings.APPEND_SLASH else "/",
            self.get_slug(language, fallback),
            "/" if settings.APPEND_SLASH else "",
        )

    def get_public_url(self, language=None, fallback=True):
        """
        Returns the URL of the published version of the current article.
        Returns empty string if the article is not published.
        """
        try:
            return self.get_public_object().get_absolute_url(language, fallback)
        except Exception:
            return ""

    def get_draft_url(self, language=None, fallback=True):
        """
        Returns the URL of the draft version of the current article.
        Returns empty string if the draft article is not available.
        """
        try:
            return self.get_draft_object().get_absolute_url(language, fallback)
        except Exception:
            return ""

    def revert_to_live(self, language):
        """Revert the draft version to the same state as the public version"""
        if not self.publisher_is_draft:
            # Revert can only be called on draft articles
            raise PublicIsUnmodifiable("The public instance cannot be reverted. Use draft.")

        if not self.publisher_public:
            raise PublicVersionNeeded("A public version of this article is needed")

        public = self.publisher_public
        public._copy_titles(self, language)
        public._copy_contents(self, language)
        public._copy_attributes(self)

        self.title_set.filter(language=language).update(
            publisher_state=constants.PUBLISHER_STATE_DEFAULT,
            published=True,
        )

        self._publisher_keep_state = True
        self.save()

    def _copy_titles(self, target, language):
        """
        Copy all the titles to a new article (which must have a pk).
        :param target: The article where the new titles should be stored
        """
        from .title import Title

        old_titles = dict(target.title_set.filter(language=language).values_list("language", "pk"))
        for title in self.title_set.filter(language=language):
            old_pk = title.pk
            # If an old title exists, overwrite. Otherwise create new
            title.pk = old_titles.pop(title.language, None)
            title.article = target
            title.publisher_is_draft = target.publisher_is_draft
            title.publisher_public_id = old_pk
            title.publisher_state = constants.PUBLISHER_STATE_DEFAULT
            title.published = True
            title._publisher_keep_state = True
            title.save()

            old_title = Title.objects.get(pk=old_pk)
            old_title.publisher_public = title
            old_title.publisher_state = title.publisher_state
            old_title.published = True
            old_title._publisher_keep_state = True
            old_title.save()
            if hasattr(self, "title_cache"):
                self.title_cache[language] = old_title
        if old_titles:
            Title.objects.filter(id__in=old_titles.values()).delete()

    def _copy_contents(self, target, language):
        """
        Copy all the plugins to a new article.
        :param target: The article where the new content should be stored
        """
        # TODO: Make this into a 'graceful' copy instead of deleting and overwriting
        # copy the placeholders (and plugins on those placeholders!)
        from cms.models.pluginmodel import CMSPlugin

        for plugin in CMSPlugin.objects.filter(placeholder__cms_articles=target, language=language).order_by("-depth"):
            inst, cls = plugin.get_plugin_instance()
            if inst and getattr(inst, "cmsplugin_ptr_id", False):
                inst.cmsplugin_ptr = plugin
                inst.cmsplugin_ptr._no_reorder = True
                inst.delete(no_mp=True)
            else:
                plugin._no_reorder = True
                plugin.delete(no_mp=True)
        new_phs = []
        target_phs = target.placeholders.all()
        for ph in self.get_placeholders():
            plugins = ph.get_plugins_list(language)
            found = False
            for target_ph in target_phs:
                if target_ph.slot == ph.slot:
                    ph = target_ph
                    found = True
                    break
            if not found:
                ph.pk = None  # make a new instance
                ph.save()
                new_phs.append(ph)
                # update the article copy
            if plugins:
                copy_plugins_to(plugins, ph)
        target.placeholders.add(*new_phs)

    def _copy_attributes(self, target):
        target.tree = self.tree
        target.template = self.template
        target.publication_date = self.publication_date
        target.publication_end_date = self.publication_end_date
        target.login_required = self.login_required

    def _copy_relations(self, target):
        target.attributes.set(self.attributes.all())
        target.categories.set(self.categories.all())

    def delete(self, *args, **kwargs):
        articles = [self.pk]
        if self.publisher_public_id:
            articles.append(self.publisher_public_id)
        self.__class__.objects.filter(pk__in=articles).delete()

    def save(self, no_signals=False, commit=True, **kwargs):
        """
        Args:
            commit: True if model should be really saved
        """
        # delete template cache
        if hasattr(self, "_template_cache"):
            delattr(self, "_template_cache")

        created = not bool(self.pk)

        from cms.utils.permissions import get_current_user

        user = get_current_user()

        if user:
            try:
                changed_by = force_str(user)
            except AttributeError:
                # AnonymousUser may not have USERNAME_FIELD
                changed_by = "anonymous"
            else:
                # limit changed_by and created_by to avoid problems with Custom User Model
                if len(changed_by) > constants.PAGE_USERNAME_MAX_LENGTH:
                    changed_by = "{0}... (id={1})".format(
                        changed_by[: constants.PAGE_USERNAME_MAX_LENGTH - 15],
                        user.pk,
                    )

            self.changed_by = changed_by

        else:
            self.changed_by = "script"
        if created:
            self.created_by = self.changed_by

        self.order_date = self.publication_date or self.creation_date

        if commit:
            super().save(**kwargs)

    def save_base(self, *args, **kwargs):
        """Overridden save_base. If an instance is draft, and was changed, mark
        it as dirty.

        Dirty flag is used for changed nodes identification when publish method
        takes place. After current changes are published, state is set back to
        PUBLISHER_STATE_DEFAULT (in publish method).
        """
        keep_state = getattr(self, "_publisher_keep_state", None)
        if self.publisher_is_draft and not keep_state and self.is_new_dirty():
            self.title_set.all().update(publisher_state=constants.PUBLISHER_STATE_DIRTY)
        if keep_state:
            delattr(self, "_publisher_keep_state")
        return super().save_base(*args, **kwargs)

    def is_new_dirty(self):
        if self.pk:
            fields = [
                "publication_date",
                "publication_end_date",
                "tree",
                "template",
                "login_required",
            ]
            try:
                old_article = Article.objects.get(pk=self.pk)
            except Article.DoesNotExist:
                return True
            for field in fields:
                old_val = getattr(old_article, field)
                new_val = getattr(self, field)
                if not old_val == new_val:
                    return True
            if not self.attributes.all() == old_article.attributes.all():
                return True
            if not self.categories.all() == old_article.categories.all():
                return True
            return False
        return True

    def is_published(self, language, force_reload=False):
        return self.get_title_obj(language, False, force_reload=force_reload).published

    def get_publisher_state(self, language, force_reload=False):
        try:
            return self.get_title_obj(language, False, force_reload=force_reload).publisher_state
        except AttributeError:
            return None

    def set_publisher_state(self, language, state, published=None):
        title = self.title_set.get(language=language)
        title.publisher_state = state
        if published is not None:
            title.published = published
        title._publisher_keep_state = True
        title.save()
        if hasattr(self, "title_cache") and language in self.title_cache:
            self.title_cache[language].publisher_state = state
        return title

    def publish(self, language):
        # Publish can only be called on draft articles
        if not self.publisher_is_draft:
            raise PublicIsUnmodifiable("The public instance cannot be published. Use draft.")

        if not self.pk:
            self.save()

        if self.publisher_public_id:
            public_article = self.publisher_public
        else:
            public_article = Article(created_by=self.created_by)

        if not self.publication_date:
            self.publication_date = now()

        self._copy_attributes(public_article)

        # we need to set relate this new public copy to its draft article (self)
        public_article.publisher_public = self
        public_article.publisher_is_draft = False
        public_article.save()

        public_article = public_article.reload()

        # The target article now has a pk, so can be used as a target
        self._copy_titles(public_article, language)
        self._copy_contents(public_article, language)
        self._copy_relations(public_article)

        self.publisher_public = public_article
        self._publisher_keep_state = True
        self.save()

        from cms.signals import post_publish

        post_publish.send(sender=Article, instance=self, language=language)

        return True

    def unpublish(self, language):
        """
        Removes this article from the public site
        :returns: True if this article was successfully unpublished
        """
        # Publish can only be called on draft articles
        if not self.publisher_is_draft:
            raise PublicIsUnmodifiable("The public instance cannot be unpublished. Use draft.")

        # First, make sure we are in the correct state
        title = self.title_set.get(language=language)
        public_title = title.publisher_public
        title.published = False
        title.publisher_state = constants.PUBLISHER_STATE_DIRTY
        title.save()
        if hasattr(self, "title_cache"):
            self.title_cache[language] = title
        public_title.published = False

        public_title.save()
        public_article = self.publisher_public
        public_placeholders = public_article.get_placeholders()
        for pl in public_placeholders:
            pl.cmsplugin_set.filter(language=language).delete()
        public_article.save()
        # trigger update home
        self.save()

        from cms.signals import post_unpublish

        post_unpublish.send(sender=Article, instance=self, language=language)

        return True

    def get_draft_object(self):
        if not self.publisher_is_draft:
            return self.publisher_draft
        return self

    def get_public_object(self):
        if not self.publisher_is_draft:
            return self
        return self.publisher_public

    def get_published_object(self):
        if self.publisher_is_draft:
            public_id = self.publisher_public_id
        else:
            public_id = self.id
        return Article.objects.public().published().filter(id=public_id).first()

    def get_languages(self):
        if self.languages:
            return sorted(self.languages.split(","))
        else:
            return []

    def get_published_languages(self):
        if self.publisher_is_draft:
            return self.get_languages()
        return sorted([language for language in self.get_languages() if self.is_published(language)])

    # Title object access

    def get_title_obj(self, language=None, fallback=True, force_reload=False):
        language = self._get_title_cache(language, fallback, force_reload)
        if language in self.title_cache:
            return self.title_cache[language]

        from .title import Title

        title = Title()
        title.article = self
        title.language = language
        return title

    def get_title_obj_attribute(self, attrname, language=None, fallback=True, force_reload=False):
        """Helper function for getting attribute or None from wanted/current title."""
        try:
            attribute = getattr(self.get_title_obj(language, fallback, force_reload), attrname)
            return attribute
        except AttributeError:
            return None

    def get_slug(self, language=None, fallback=True, force_reload=False):
        """
        get the slug of the article depending on the given language
        """
        return self.get_title_obj_attribute("slug", language, fallback, force_reload)

    def get_title(self, language=None, fallback=True, force_reload=False):
        """
        get the title of the article depending on the given language
        """
        return self.get_title_obj_attribute("title", language, fallback, force_reload)

    def get_image(self, language=None, fallback=True, force_reload=False):
        """
        get the image of the article depending on the given language
        """
        return self.get_title_obj_attribute("image", language, fallback, force_reload)

    def get_description(self, language=None, fallback=True, force_reload=False):
        """
        get description of the article depending on the given language
        """
        return self.get_title_obj_attribute("description", language, fallback, force_reload)

    def get_placeholders(self):
        if not hasattr(self, "_placeholder_cache"):
            self._placeholder_cache = self.placeholders.all()
        return self._placeholder_cache

    def get_changed_date(self, language=None, fallback=True, force_reload=False):
        """
        get when this article was last updated
        """
        return self.changed_date

    def get_changed_by(self, language=None, fallback=True, force_reload=False):
        """
        get user who last changed this article
        """
        return self.changed_by

    def get_page_title(self, language=None, fallback=True, force_reload=False):
        """
        get the page title of the article depending on the given language
        """
        page_title = self.get_title_obj_attribute("page_title", language, fallback, force_reload)
        if not page_title:
            return self.get_title(language, True, force_reload)
        return page_title

    def get_menu_title(self, language=None, fallback=True, force_reload=False):
        """
        get the menu title of the article depending on the given language
        """
        menu_title = self.get_title_obj_attribute("menu_title", language, fallback, force_reload)
        if not menu_title:
            return self.get_title(language, True, force_reload)
        return menu_title

    def get_meta_description(self, language=None, fallback=True, force_reload=False):
        """
        get content for the description meta tag for the article depending on the given language
        """
        return self.get_title_obj_attribute("meta_description", language, fallback, force_reload) or strip_tags(
            self.get_title_obj_attribute("description", language, fallback, force_reload)
        )

    def _get_title_cache(self, language, fallback, force_reload):
        if not language:
            language = get_language()
        load = False
        if not hasattr(self, "title_cache") or force_reload:
            load = True
            self.title_cache = {}
        elif language not in self.title_cache:
            if fallback:
                fallback_langs = i18n.get_fallback_languages(language)
                for lang in fallback_langs:
                    if lang in self.title_cache:
                        return lang
            load = True
        if load:
            from .title import Title

            titles = Title.objects.filter(article=self)
            for title in titles:
                self.title_cache[title.language] = title
            if language in self.title_cache:
                return language
            else:
                if fallback:
                    fallback_langs = i18n.get_fallback_languages(language)
                    for lang in fallback_langs:
                        if lang in self.title_cache:
                            return lang
        return language

    def get_template(self):
        return self.template

    def has_change_permission(self, request, user=None):
        if not user:
            user = request.user
        return user.has_perm("cms_articles.change_article")

    def has_delete_permission(self, request, user=None):
        if not user:
            user = request.user
        return user.has_perm("cms_articles.delete_article")

    def has_publish_permission(self, request, user=None):
        if not user:
            user = request.user
        return user.has_perm("cms_articles.publish_article")

    def has_add_permission(self, request, user=None):
        if not user:
            user = request.user
        return user.has_perm("cms_articles.add_article")

    def reload(self):
        """
        Reload a article from the database
        """
        return Article.objects.get(pk=self.pk)

    def rescan_placeholders(self):
        """
        Rescan and if necessary create placeholders in the current template.
        """
        existing = OrderedDict()
        placeholders = [pl.slot for pl in self.get_declared_placeholders()]

        for placeholder in self.placeholders.all():
            if placeholder.slot in placeholders:
                existing[placeholder.slot] = placeholder

        for placeholder in placeholders:
            if placeholder not in existing:
                existing[placeholder] = self.placeholders.create(slot=placeholder)
        return existing

    def get_declared_placeholders(self):
        # inline import to prevent circular imports
        from ..utils.placeholder import get_placeholders

        return get_placeholders(self.get_template())

    def get_declared_static_placeholders(self, context):
        # inline import to prevent circular imports
        from cms.utils.placeholder import get_static_placeholders

        return get_static_placeholders(self.get_template(), context)

    def get_xframe_options(self):
        return self.tree.get_xframe_options()
