from cms.signals import post_placeholder_operation
from django.db.models import signals

from ..admin.article import ArticleAdmin
from ..models import Article, Title
from .article import post_save_article, pre_delete_article, pre_save_article
from .plugins import post_reorder_plugins, pre_delete_plugins, pre_save_plugins
from .title import pre_delete_title, pre_save_title

# Signals we listen to

post_placeholder_operation.connect(
    post_reorder_plugins, sender=ArticleAdmin, dispatch_uid="cms_articles_post_reorder_plugins"
)

signals.pre_save.connect(pre_save_plugins, dispatch_uid="cms_articles_pre_save_plugin")
signals.pre_delete.connect(pre_delete_plugins, dispatch_uid="cms_articles_pre_delete_plugin")

signals.pre_save.connect(pre_save_article, sender=Article, dispatch_uid="cms_articles_pre_save_article")
signals.post_save.connect(post_save_article, sender=Article, dispatch_uid="cms_articles_post_save_article")
signals.pre_delete.connect(pre_delete_article, sender=Article, dispatch_uid="cms_articles_pre_delete_article")


signals.pre_save.connect(pre_save_title, sender=Title, dispatch_uid="cms_articles_pre_save_article")
signals.pre_delete.connect(pre_delete_title, sender=Title, dispatch_uid="cms_articles_pre_delete_article")
