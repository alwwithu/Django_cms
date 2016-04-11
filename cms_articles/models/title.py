from __future__ import absolute_import, division, generators, nested_scopes, print_function, unicode_literals, with_statement

from cms.constants import PUBLISHER_STATE_DIRTY
from cms.models.fields import PlaceholderField
from cms.utils.helpers import reversion_register
from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
from django.utils.functional import cached_property
from django.utils.translation import get_language, ugettext_lazy as _

from ..conf import settings

from .article import Article
from .managers import TitleManager



@python_2_unicode_compatible
class Title(models.Model):
    language            = models.CharField(_('language'), max_length=15, db_index=True)
    title               = models.CharField(_('title'), max_length=255)
    excerpt             = PlaceholderField('excerpt')
    page_title          = models.CharField(_('title'), max_length=255, blank=True, null=True,
                            help_text=_('overwrite the title (html title tag)'))
    menu_title          = models.CharField(_('title'), max_length=255, blank=True, null=True,
                            help_text=_('overwrite the title in the menu'))
    meta_description    = models.TextField(_('description'), max_length=155, blank=True, null=True,
                            help_text=_('The text displayed in search engines.'))
    slug                = models.SlugField(_('slug'), max_length=255, db_index=True, unique=False)
    article             = models.ForeignKey(Article, verbose_name=_('article'), related_name='title_set')
    creation_date       = models.DateTimeField(_('creation date'), editable=False, default=timezone.now)

    # Publisher fields
    published           = models.BooleanField(_('is published'), blank=True, default=False)
    publisher_is_draft  = models.BooleanField(default=True, editable=False, db_index=True)

    # This is misnamed - the one-to-one relation is populated on both ends
    publisher_public    = models.OneToOneField('self', related_name='publisher_draft', null=True, editable=False)
    publisher_state     = models.SmallIntegerField(default=0, editable=False, db_index=True)

    objects = TitleManager()

    class Meta:
        app_label = 'cms_articles'
        unique_together = (('language', 'article'),)

    def __str__(self):
        return u'%s (%s, %s)' % (self.title, self.slug, self.language)

    def is_dirty(self):
        return self.publisher_state == PUBLISHER_STATE_DIRTY

    def save_base(self, *args, **kwargs):
        '''Overridden save_base. If an instance is draft, and was changed, mark
        it as dirty.

        Dirty flag is used for changed nodes identification when publish method
        takes place. After current changes are published, state is set back to
        PUBLISHER_STATE_DEFAULT (in publish method).
        '''
        keep_state = getattr(self, '_publisher_keep_state', None)

        # Published articles should always have a publication date
        # if the article is published we set the publish date if not set yet.
        if self.article.publication_date is None and self.published:
            self.article.publication_date = timezone.now() - timedelta(seconds=5)

        if self.publisher_is_draft and not keep_state and self.is_new_dirty():
            self.publisher_state = PUBLISHER_STATE_DIRTY
        if keep_state:
            delattr(self, '_publisher_keep_state')
        ret = super(Title, self).save_base(*args, **kwargs)
        return ret

    def is_new_dirty(self):
        if self.pk:
            fields = [
                'title', 'page_title', 'menu_title', 'meta_description', 'slug',
            ]
            try:
                old_title = Title.objects.get(pk=self.pk)
            except Title.DoesNotExist:
                return True
            for field in fields:
                old_val = getattr(old_title, field)
                new_val = getattr(self, field)
                if not old_val == new_val:
                    return True
            return False
        return True



class EmptyTitle(object):
    title = ''
    slug = ''
    page_title = ''
    meta_description = ''
    published = False

    def __init__(self, language):
        self.language = language

