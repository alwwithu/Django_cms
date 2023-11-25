from itertools import chain

from cms.models import Page
from django.db import models
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _

from ..conf import settings


class Category(models.Model):
    page = models.OneToOneField(
        Page,
        verbose_name=_("page"),
        related_name="cms_articles_category",
        on_delete=models.CASCADE,
        limit_choices_to={"publisher_is_draft": True, "node__site_id": settings.SITE_ID},
    )

    class Meta:
        app_label = "cms_articles"
        verbose_name = _("category")
        verbose_name_plural = _("categories")

    def __str__(self):
        return " / ".join(
            chain(
                (force_str(p) for p in self.page.get_ancestor_pages()),
                (force_str(self.page),),
            )
        )
