# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from cms.utils.page import _page_is_published


def get_article_from_slug(tree, slug, preview=False, draft=False):
    """
    Resolves a slug to a single article object.
    Returns None if article does not exist
    """
    from ..models import Title

    titles = Title.objects.select_related("article").filter(article__tree=tree)
    published_only = not draft and not preview

    if draft:
        titles = titles.filter(publisher_is_draft=True)
    elif preview:
        titles = titles.filter(publisher_is_draft=False)
    else:
        titles = titles.filter(published=True, publisher_is_draft=False)
    titles = titles.filter(slug=slug)

    for title in titles.iterator():
        if published_only and not _page_is_published(title.article):
            continue

        title.article.title_cache = {title.language: title}
        return title.article
    return
