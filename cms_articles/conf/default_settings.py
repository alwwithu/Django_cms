from __future__ import absolute_import, division, generators, nested_scopes, print_function, unicode_literals, with_statement

from django.conf import settings
from django.utils.translation import ugettext_lazy as _


# by default, use the same templates as for cms pages
CMS_ARTICLES_TEMPLATES = [
    ('cms_articles/default.html', _('Default'))
]

# default slug format
CMS_ARTICLES_SLUG_FORMAT = '{now:%Y-%m}-{slug}'
CMS_ARTICLES_SLUG_REGEXP = r'[0-9]{4}-[0-9]{2}-([^/]+)'

# templates used to render plugin article
CMS_ARTICLES_PLUGIN_ARTICLE_TEMPLATES = [
    ('default', _('Default')),
]

# templates used to render plugin articles
CMS_ARTICLES_PLUGIN_ARTICLES_TEMPLATES = [
    ('default', _('Default')),
]

