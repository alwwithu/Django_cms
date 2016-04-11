from __future__ import absolute_import, division, generators, nested_scopes, print_function, unicode_literals, with_statement

from django.db.models import Q
from cms.publisher.query import PublisherQuerySet
from django.utils import timezone


class ArticleQuerySet(PublisherQuerySet):
    def published(self, language=None):
        if language:
            return self.filter(
                Q(publication_date__lte=timezone.now()) | Q(publication_date__isnull=True),
                Q(publication_end_date__gt=timezone.now()) | Q(publication_end_date__isnull=True),
                title_set__published=True, title_set__language=language
            )
        else:
            return self.filter(
                Q(publication_date__lte=timezone.now()) | Q(publication_date__isnull=True),
                Q(publication_end_date__gt=timezone.now()) | Q(publication_end_date__isnull=True),
                title_set__published=True
            )
        return pub

