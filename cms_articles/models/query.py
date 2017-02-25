from cms.publisher.query import PublisherQuerySet
from django.db.models import Q
from django.utils import timezone


class ArticleQuerySet(PublisherQuerySet):
    def published(self, language=None):
        qs = self.filter(
            Q(publication_date__lte=timezone.now()) | Q(publication_date__isnull=True),
            Q(publication_end_date__gt=timezone.now()) | Q(publication_end_date__isnull=True),
            title_set__published=True)
        if language:
            return qs.filter(title_set__language=language)
        else:
            return qs
