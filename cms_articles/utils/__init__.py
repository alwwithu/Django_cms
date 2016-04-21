from __future__ import absolute_import, division, generators, nested_scopes, print_function, unicode_literals, with_statement

from django.db.models import Q

from ..conf import settings

def is_valid_article_slug(article, language, slug):
    """Validates given slug depending on settings.
    """
    from ..models import Title

    qs = Title.objects.filter(slug=slug, language=language)

    if article.pk:
        qs = qs.exclude(Q(language=language) & Q(article=article))
        qs = qs.exclude(article__publisher_public=article)

    if qs.count():
        return False

    return True


