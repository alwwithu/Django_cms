from django.utils.translation import gettext_lazy as _

# by default, use the same templates as for cms pages
CMS_ARTICLES_TEMPLATES = [("cms_articles/default.html", _("Default"))]

# default slug format
CMS_ARTICLES_SLUG_FORMAT = "{now:%Y-%m}-{slug}"
CMS_ARTICLES_SLUG_REGEXP = r"[0-9]{4}-[0-9]{2}-([^/]+)"
CMS_ARTICLES_SLUG_GROUP_INDEX = 0

# templates used to render plugin article
CMS_ARTICLES_PLUGIN_ARTICLE_TEMPLATES = [
    ("default", _("Default")),
]

# templates used to render plugin articles
CMS_ARTICLES_PLUGIN_ARTICLES_TEMPLATES = [
    ("default", _("Default")),
]

# the main slot for initial content to be stored in
CMS_ARTICLES_SLOT = "content"

CMS_ARTICLES_USE_HAYSTACK = True

CMS_ARTICLES_PAGE_FIELD = "page"
CMS_ARTICLES_YEAR_FIELD = "year"
CMS_ARTICLES_MONTH_FIELD = "month"
CMS_ARTICLES_DAY_FIELD = "day"
