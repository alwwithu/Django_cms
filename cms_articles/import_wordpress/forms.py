from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Item, Options
from .utils import import_wordpress


class XMLImportForm(forms.ModelForm):
    wordpress_xml = forms.FileField(
        label=_("WordPress XML file"), help_text=_("Select XML file with posts exported from WP.")
    )

    class Meta:
        model = Item
        fields = []

    def save(self, *args, **kwargs):
        return import_wordpress(self.cleaned_data["wordpress_xml"])


class CMSImportForm(forms.Form):
    options = forms.ModelChoiceField(
        label=_("Options"),
        queryset=Options.objects.order_by("name"),
    )
