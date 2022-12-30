# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from datetime import timedelta

from cms.constants import PUBLISHER_STATE_DIRTY
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from filer.fields.image import FilerImageField

from .article import Article
from .managers import TitleManager


class Title(models.Model):
    # These are the fields whose values are compared when saving
    # a Title object to know if it has changed.
    editable_fields = [
        "title",
        "slug",
        "page_title",
        "menu_title",
        "meta_description",
    ]

    article = models.ForeignKey(Article, verbose_name=_("article"), related_name="title_set", on_delete=models.CASCADE)
    language = models.CharField(_("language"), max_length=15, db_index=True)
    title = models.CharField(_("title"), max_length=255)
    description = HTMLField(
        _("description"), blank=True, default="", help_text=_("The text displayed in an articles overview.")
    )
    page_title = models.CharField(
        _("page title"), max_length=255, blank=True, null=True, help_text=_("overwrite the title (html title tag)")
    )
    menu_title = models.CharField(
        _("menu title"),
        max_length=255,
        blank=True,
        null=True,
        help_text=_("overwrite the title in the articles overview"),
    )
    meta_description = models.TextField(
        _("meta description"),
        max_length=155,
        blank=True,
        null=True,
        help_text=_("The text displayed in search engines."),
    )
    slug = models.SlugField(_("slug"), max_length=255, db_index=True, unique=False)
    creation_date = models.DateTimeField(_("creation date"), editable=False, default=timezone.now)
    image = FilerImageField(verbose_name=_("image"), related_name="+", on_delete=models.PROTECT, blank=True, null=True)

    # Publisher fields
    published = models.BooleanField(_("is published"), blank=True, default=False)
    publisher_is_draft = models.BooleanField(default=True, editable=False, db_index=True)
    # This is misnamed - the one-to-one relation is populated on both ends
    publisher_public = models.OneToOneField(
        "self", related_name="publisher_draft", on_delete=models.CASCADE, null=True, editable=False
    )
    publisher_state = models.SmallIntegerField(default=0, editable=False, db_index=True)

    objects = TitleManager()

    class Meta:
        unique_together = (("language", "article"),)
        app_label = "cms_articles"

    def __str__(self):
        return "%s (%s, %s)" % (self.title, self.slug, self.language)

    def is_dirty(self):
        return self.publisher_state == PUBLISHER_STATE_DIRTY

    def save_base(self, *args, **kwargs):
        """Overridden save_base. If an instance is draft, and was changed, mark
        it as dirty.

        Dirty flag is used for changed nodes identification when publish method
        takes place. After current changes are published, state is set back to
        PUBLISHER_STATE_DEFAULT (in publish method).
        """
        keep_state = getattr(self, "_publisher_keep_state", None)

        # Published articles should always have a publication date
        # if the article is published we set the publish date if not set yet.
        if self.article.publication_date is None and self.published:
            self.article.publication_date = timezone.now() - timedelta(seconds=5)

        if self.publisher_is_draft and not keep_state and self.is_new_dirty():
            self.publisher_state = PUBLISHER_STATE_DIRTY

        if keep_state:
            delattr(self, "_publisher_keep_state")
        return super().save_base(*args, **kwargs)

    def is_new_dirty(self):
        if not self.pk:
            return True

        try:
            old_title = Title.objects.get(pk=self.pk)
        except Title.DoesNotExist:
            return True

        for field in self.editable_fields:
            old_val = getattr(old_title, field)
            new_val = getattr(self, field)
            if not old_val == new_val:
                return True
        return False
