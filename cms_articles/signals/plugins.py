from cms.constants import PUBLISHER_STATE_DIRTY
from cms.models import CMSPlugin, Placeholder


def _set_dirty_placeholder(placeholder, language):
    for article in placeholder.cms_articles.all():
        article.title_set.filter(language=language).update(publisher_state=PUBLISHER_STATE_DIRTY)


def _set_dirty_plugin(plugin):
    if plugin.placeholder_id:
        try:
            placeholder = plugin.placeholder
        except Placeholder.DoesNotExist:
            placeholder = None
    else:
        placeholder = plugin.placeholder

    if placeholder:
        _set_dirty_placeholder(placeholder, plugin.language)


def post_reorder_plugins(**kwargs):
    for prefix in ("source", "target"):
        placeholder = kwargs.get(prefix + "_placeholder")
        language = kwargs.get(prefix + "_language")
        if placeholder and language:
            _set_dirty_placeholder(placeholder, language)

    placeholder = kwargs.get("placeholder")
    if placeholder:
        for arg_name in ("plugin", "old_plugin", "new_plugin"):
            plugin = kwargs.get("plugin")
            if plugin:
                _set_dirty_placeholder(placeholder, plugin.language)
                break


def pre_save_plugins(**kwargs):
    plugin = kwargs["instance"]

    if not isinstance(plugin, CMSPlugin) or hasattr(plugin, "_no_reorder"):
        return

    _set_dirty_plugin(plugin)

    if not plugin.pk:
        return

    try:
        old_plugin = (
            CMSPlugin.objects.select_related("placeholder")
            .only("language", "placeholder")
            .exclude(placeholder=plugin.placeholder_id)
            .get(pk=plugin.pk)
        )
    except CMSPlugin.DoesNotExist:
        pass
    else:
        _set_dirty_plugin(old_plugin)


def pre_delete_plugins(**kwargs):
    plugin = kwargs["instance"]

    if not isinstance(plugin, CMSPlugin) or hasattr(plugin, "_no_reorder"):
        return

    _set_dirty_plugin(plugin)
