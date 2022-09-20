from aldryn_search.helpers import get_plugin_index_data
from aldryn_search.signals import add_to_index, remove_from_index
from aldryn_search.utils import clean_join, get_index_base
from cms.models import CMSPlugin
from django.db.models import Q
from django.dispatch.dispatcher import receiver
from django.utils import timezone

from .conf import settings
from .models import Title
from .signals import post_publish_article, post_unpublish_article


class TitleIndex(get_index_base()):
    index_title = True

    object_actions = ("publish", "unpublish")
    haystack_use_for_indexing = settings.CMS_ARTICLES_USE_HAYSTACK

    def prepare_pub_date(self, obj):
        return obj.article.publication_date

    def prepare_login_required(self, obj):
        return obj.article.login_required

    def prepare_site_id(self, obj):
        return obj.article.tree.node.site_id

    def get_language(self, obj):
        return obj.language

    def get_url(self, obj):
        return obj.article.get_absolute_url()

    def get_title(self, obj):
        return obj.title

    def get_description(self, obj):
        return obj.meta_description or None

    def get_plugin_queryset(self, language):
        queryset = CMSPlugin.objects.filter(language=language)
        return queryset

    def get_article_placeholders(self, article):
        """
        In the project settings set up the variable

        CMS_ARTICLES_PLACEHOLDERS_SEARCH_LIST = {
            'include': [ 'slot1', 'slot2', etc. ],
            'exclude': [ 'slot3', 'slot4', etc. ],
        }

        or leave it empty

        CMS_ARTICLES_PLACEHOLDERS_SEARCH_LIST = {}
        """
        placeholders_search_list = getattr(settings, "CMS_ARTICLES_PLACEHOLDERS_SEARCH_LIST", {})

        included = placeholders_search_list.get("include", [])
        excluded = placeholders_search_list.get("exclude", [])
        diff = set(included) - set(excluded)
        if diff:
            return article.placeholders.filter(slot__in=diff)
        elif excluded:
            return article.placeholders.exclude(slot__in=excluded)
        else:
            return article.placeholders.all()

    def get_search_data(self, obj, language, request):
        current_article = obj.article
        placeholders = self.get_article_placeholders(current_article)
        plugins = self.get_plugin_queryset(language).filter(placeholder__in=placeholders)
        text_bits = []

        for base_plugin in plugins:
            plugin_text_content = self.get_plugin_search_text(base_plugin, request)
            text_bits.append(plugin_text_content)

        article_meta_description = current_article.get_meta_description(fallback=False, language=language)

        if article_meta_description:
            text_bits.append(article_meta_description)

        article_meta_keywords = getattr(current_article, "get_meta_keywords", None)

        if callable(article_meta_keywords):
            text_bits.append(article_meta_keywords())

        return clean_join(" ", text_bits)

    def get_plugin_search_text(self, base_plugin, request):
        plugin_content_bits = get_plugin_index_data(base_plugin, request)
        return clean_join(" ", plugin_content_bits)

    def get_model(self):
        return Title

    def get_index_queryset(self, language):
        queryset = (
            Title.objects.public()
            .filter(
                Q(article__publication_date__lt=timezone.now()) | Q(article__publication_date__isnull=True),
                Q(article__publication_end_date__gte=timezone.now()) | Q(article__publication_end_date__isnull=True),
                language=language,
            )
            .select_related("article")
            .distinct()
        )
        return queryset

    def should_update(self, instance, **kwargs):
        # We use the action flag to prevent
        # updating the cms article on save.
        return kwargs.get("object_action") in self.object_actions


@receiver(post_publish_article, dispatch_uid="publish_cms_article")
def publish_cms_article(sender, instance, language, **kwargs):
    title = instance.publisher_public.get_title_obj(language)
    print("##################### publish_cms_article", title)
    add_to_index.send(sender=Title, instance=title, object_action="publish")


@receiver(post_unpublish_article, dispatch_uid="unpublish_cms_article")
def unpublish_cms_article(sender, instance, language, **kwargs):
    title = instance.publisher_public.get_title_obj(language)
    print("##################### unpublish_cms_article", title)
    remove_from_index.send(sender=Title, instance=title, object_action="unpublish")
