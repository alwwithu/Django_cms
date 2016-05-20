from __future__ import absolute_import, division, generators, nested_scopes, print_function, unicode_literals, with_statement

from cms.models import Page
from cms.utils.i18n import get_language_tuple
from cms_articles.conf import settings
from django import forms
from django.utils.translation import ugettext_lazy as _

from .utils import import_wordpress
from .models import Item, Options



class XMLImportForm(forms.ModelForm):
    wordpress_xml       = forms.FileField(label=_('WordPress XML file'),
                            help_text=_('Select XML file with posts exported from WP.'))

    class Meta:
        model = Item
        fields = []

    def save(self, *args, **kwargs):
        return import_wordpress(self.cleaned_data['wordpress_xml'])



class CMSImportForm(forms.Form):
    options = forms.ModelChoiceField(
        label       = _('Options'),
        queryset    = Options.objects.order_by('name'),
    )

