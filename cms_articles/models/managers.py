from cms.publisher import PublisherManager
from cms.utils.i18n import get_fallback_languages
from django.contrib.sites.models import Site
from django.db.models import Q

from .query import ArticleQuerySet


class ArticleManager(PublisherManager):
    """Use draft() and public() methods for accessing the corresponding
    instances.
    """

    def get_queryset(self):
        """Change standard model queryset to our own."""
        return ArticleQuerySet(self.model)

    def search(self, q, language=None, current_site_only=True):
        """Simple search function

        Plugins can define a 'search_fields' tuple similar to ModelAdmin classes
        """
        from cms.plugin_pool import plugin_pool

        qs = self.get_queryset()
        qs = qs.public()

        if current_site_only:
            site = Site.objects.get_current()
            qs = qs.filter(tree__site=site)

        qt = Q(title_set__title__icontains=q)

        # find 'searchable' plugins and build query
        qp = Q()
        plugins = plugin_pool.get_all_plugins()
        for plugin in plugins:
            cmsplugin = plugin.model
            if not (hasattr(cmsplugin, "search_fields") and hasattr(cmsplugin, "cmsplugin_ptr")):
                continue
            field = cmsplugin.cmsplugin_ptr.field
            related_query_name = field.related_query_name()
            if related_query_name and not related_query_name.startswith("+"):
                for field in cmsplugin.search_fields:
                    qp |= Q(
                        **{
                            "placeholders__cmsplugin__{0}__{1}__icontains".format(
                                related_query_name,
                                field,
                            ): q
                        }
                    )
        if language:
            qt &= Q(title_set__language=language)
            qp &= Q(cmsplugin__language=language)

        qs = qs.filter(qt | qp)

        return qs.distinct()


class TitleManager(PublisherManager):
    def get_title(self, article, language, language_fallback=False):
        """
        Gets the latest content for a particular article and language. Falls back
        to another language if wanted.
        """
        try:
            title = self.get(language=language, article=article)
            return title
        except self.model.DoesNotExist:
            if language_fallback:
                try:
                    titles = self.filter(article=article)
                    fallbacks = get_fallback_languages(language)
                    for lang in fallbacks:
                        for title in titles:
                            if lang == title.language:
                                return title
                    return None
                except self.model.DoesNotExist:
                    pass
            else:
                raise
        return None

    # created new public method to meet test case requirement and to get a list of titles for published articles
    def public(self):
        return self.get_queryset().filter(publisher_is_draft=False, published=True)

    def drafts(self):
        return self.get_queryset().filter(publisher_is_draft=True)

    def set_or_create(self, request, article, form, language):
        """
        set or create a title for a particular article and language
        """
        base_fields = [
            "slug",
            "title",
            "description",
            "meta_description",
            "page_title",
            "menu_title",
            "image",
        ]
        cleaned_data = form.cleaned_data
        try:
            obj = self.get(article=article, language=language)
        except self.model.DoesNotExist:
            data = {}
            for name in base_fields:
                if name in cleaned_data:
                    data[name] = cleaned_data[name]
            data["article"] = article
            data["language"] = language
            return self.create(**data)
        for name in base_fields:
            if name in form.base_fields:
                value = cleaned_data.get(name, None)
                setattr(obj, name, value)
        obj.save()
        return obj
