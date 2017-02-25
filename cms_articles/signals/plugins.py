from cms.constants import PUBLISHER_STATE_DIRTY
from cms.models import CMSPlugin
from cms.signals.plugins import get_placeholder
from django.db.models import signals


def set_dirty(plugin):
    placeholder = get_placeholder(plugin)

    if placeholder:
        for article in placeholder.cms_articles.all():
            article.title_set.filter(language=plugin.language).update(publisher_state=PUBLISHER_STATE_DIRTY)


def pre_save_plugins(**kwargs):
    plugin = kwargs['instance']

    if hasattr(plugin, '_no_reorder'):
        return

    set_dirty(plugin)

    if not plugin.pk:
        return

    try:
        old_plugin = (
            CMSPlugin
            .objects
            .select_related('placeholder')
            .only('language', 'placeholder')
            .exclude(placeholder=plugin.placeholder_id)
            .get(pk=plugin.pk)
        )
    except CMSPlugin.DoesNotExist:
        pass
    else:
        set_dirty(old_plugin)


def pre_delete_plugins(**kwargs):
    plugin = kwargs['instance']
    if hasattr(plugin, '_no_reorder'):
        return

    set_dirty(plugin)


signals.pre_save.connect(pre_save_plugins, sender=CMSPlugin, dispatch_uid='cms_pre_save_plugin')
signals.pre_delete.connect(pre_delete_plugins, sender=CMSPlugin, dispatch_uid='cms_pre_delete_plugin')
