from __future__ import absolute_import, division, generators, nested_scopes, print_function, unicode_literals, with_statement

from cms.utils.i18n import get_language_tuple
from cms.models import Page

from django import forms
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.forms.utils import ErrorList
from django.utils import timezone
from django.utils.text import slugify
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _, get_language

from ..conf import settings
from ..models import Article, EmptyTitle
from ..utils import is_valid_article_slug


class ArticleForm(forms.ModelForm):
    language            = forms.ChoiceField(label=_('Language'), choices=get_language_tuple(),
                            help_text=_('The current language of the content fields.'))
    title               = forms.CharField(label=_('Title'), widget=forms.TextInput(),
                            help_text=_('The default title'))
    slug                = forms.CharField(label=_('Slug'), widget=forms.TextInput(),
                            help_text=_('The part of the title that is used in the URL'))
    page_title          = forms.CharField(label=_('Page Title'), widget=forms.TextInput(), required=False,
                            help_text=_('Overwrites what is displayed at the top of your browser or in bookmarks'))
    menu_title          = forms.CharField(label=_('Menu Title'), widget=forms.TextInput(), required=False,
                            help_text=_('Overwrite what is displayed in the menu'))
    meta_description    = forms.CharField(label=_('Description meta tag'), required=False, max_length=155,
                            widget=forms.Textarea(attrs={'maxlength': '155', 'rows': '4'}),
                            help_text=_('A description of the article used by search engines.'))

    class Meta:
        model = Article
        fields = ['category', 'template', 'login_required']

    def __init__(self, *args, **kwargs):
        super(ArticleForm, self).__init__(*args, **kwargs)
        self.fields['language'].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = self.cleaned_data
        slug = cleaned_data.get('slug', '')

        article = self.instance
        lang = cleaned_data.get('language', None)
        # No language, can not go further, but validation failed already
        if not lang:
            return cleaned_data
        category = self.cleaned_data.get('category', None)
        if category and not is_valid_article_slug(article, lang, slug, category):
            self._errors['slug'] = ErrorList([_('Another article with this slug already exists')])
            del cleaned_data['slug']
        return cleaned_data

    def clean_slug(self):
        slug = slugify(self.cleaned_data['slug'])
        if not slug:
            raise ValidationError(_('Slug must not be empty.'))
        return settings.CMS_ARTICLES_SLUG_FORMAT.format(
            now = self.instance.creation_date or now(),
            slug = slug,
        )


class PublicationDatesForm(forms.ModelForm):
    language = forms.ChoiceField(label=_("Language"), choices=get_language_tuple(),
                                 help_text=_('The current language of the content fields.'))

    def __init__(self, *args, **kwargs):
        super(PublicationDatesForm, self).__init__(*args, **kwargs)
        self.fields['language'].widget = forms.HiddenInput()

    class Meta:
        model = Article
        fields = ['publication_date', 'publication_end_date']


