import warnings

from django.template import TemplateDoesNotExist

from ..models import Article


def pre_save_article(instance, **kwargs):
    instance.old_article = None
    try:
        instance.old_article = Article.objects.get(pk=instance.pk)
    except Article.DoesNotExist:
        pass


def post_save_article(instance, raw, **kwargs):
    if not raw:
        try:
            instance.rescan_placeholders()
        except TemplateDoesNotExist as e:
            warnings.warn("Exception occurred: %s template does not exists" % e)


def pre_delete_article(instance, **kwargs):
    for placeholder in instance.get_placeholders():
        for plugin in placeholder.cmsplugin_set.all().order_by("-depth"):
            plugin._no_reorder = True
            plugin.delete(no_mp=True)
        placeholder.delete()
