# -*- coding: utf-8 -*-
from cms.toolbar.utils import get_toolbar_from_request

from .plugin_rendering import ArticlesContentRenderer


def cms_articles(request):
    """
    Adds cms-articles-related variables to the context.
    """
    toolbar = get_toolbar_from_request(request)
    return {
        'cms_articles_content_renderer': ArticlesContentRenderer(toolbar.content_renderer),
    }
