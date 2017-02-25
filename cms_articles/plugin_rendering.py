# -*- coding: utf-8 -*-
from cms.exceptions import PlaceholderNotFound


class ArticlesContentRenderer(object):

    def __init__(self, content_renderer):
        self.content_renderer = content_renderer
        self._placeholders_by_article_cache = {}

    def render_article_placeholder(self, slot, context, nodelist=None):
        current_article = self.content_renderer.request.current_article

        if not current_article:
            return ''

        content = self._render_article_placeholder(
            context=context,
            slot=slot,
            article=current_article,
            editable=True,
            nodelist=nodelist,
        )

        return content

    def _get_article_placeholder(self, context, article, slot):
        """
        Returns a Placeholder instance attached to article that
        matches the given slot.

        A PlaceholderNotFound is raised if the placeholder is
        not present on the article template.
        """
        placeholder_cache = self._placeholders_by_article_cache

        if article.pk not in placeholder_cache:
            # Instead of loading plugins for this one placeholder
            # try and load them for all placeholders on the article.
            self._preload_placeholders_for_article(article)

        try:
            placeholder = placeholder_cache[article.pk][slot]
        except KeyError:
            message = '"%s" placeholder not found' % slot
            raise PlaceholderNotFound(message)
        return placeholder

    def _render_article_placeholder(self, context, slot, article, editable=True, nodelist=None):
        """
        Renders a placeholder attached to a article.
        """
        try:
            placeholder = self._get_article_placeholder(context, article, slot)
        except PlaceholderNotFound:
            if nodelist:
                return nodelist.render(context)
            return ''

        content = self.content_renderer.render_placeholder(
            placeholder,
            context=context,
            editable=editable,
            use_cache=True,
            nodelist=nodelist,
        )
        return content

    def _preload_placeholders_for_article(self, article):
        """
        Populates the internal plugin cache of each placeholder
        in the given article if the placeholder has not been
        previously cached.
        """
        from cms.utils.plugins import assign_plugins

        site_id = article.tree.site_id
        placeholders = article.rescan_placeholders().values()

        if self.content_renderer.placeholder_cache_is_enabled():
            _cached_content = self.content_renderer._get_cached_placeholder_content
            # Only prefetch placeholder plugins if the placeholder
            # has not been cached.
            placeholders_to_fetch = [
                placeholder for placeholder in placeholders
                if _cached_content(placeholder, site_id, self.content_renderer.request_language) is None]
        else:
            # cache is disabled, prefetch plugins for all
            # placeholders in the article.
            placeholders_to_fetch = placeholders

        if placeholders_to_fetch:
            assign_plugins(
                request=self.content_renderer.request,
                placeholders=placeholders_to_fetch,
                template=article.get_template(),
                lang=self.content_renderer.request_language,
            )

        # Internal cache mapping placeholder slots
        # to placeholder instances.
        article_placeholder_cache = {}

        for placeholder in placeholders:
            # Save a query when the placeholder toolbar is rendered.
            placeholder.article = article
            article_placeholder_cache[placeholder.slot] = placeholder

        self._placeholders_by_article_cache[article.pk] = article_placeholder_cache
