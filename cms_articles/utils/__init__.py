from __future__ import absolute_import, division, generators, nested_scopes, print_function, unicode_literals, with_statement

from django.db.models import Q

from ..conf import settings

def is_valid_article_slug(article, lang, slug, category, path=None):
    """Validates given slug depending on settings.
    """
    from ..models import Title

    qs = Title.objects.filter(article__category=category, slug=slug)

    if settings.USE_I18N:
        qs = qs.filter(language=lang)

    if article.pk:
        qs = qs.exclude(Q(language=lang) & Q(article=article))
        qs = qs.exclude(article__publisher_public=article)

    if qs.count():
        return False

    return True


