from django.db.models import signals

from ..models import Title


def pre_save_title(instance, **kwargs):
    ''' Update article.languages
    '''
    if instance.article.languages:
        languages = instance.article.languages.split(',')
    else:
        languages = []
    if instance.language not in languages:
        languages.append(instance.language)
        instance.article.languages = ','.join(languages)
        instance.article._publisher_keep_state = True
        instance.article.save(no_signals=True)


def pre_delete_title(instance, **kwargs):
    ''' Update article.languages
    '''
    if instance.article.languages:
        languages = instance.article.languages.split(',')
    else:
        languages = []
    if instance.language in languages:
        languages.remove(instance.language)
        instance.article.languages = ','.join(languages)
        instance.article._publisher_keep_state = True
        instance.article.save(no_signals=True)


signals.pre_save.connect(pre_save_title, sender=Title, dispatch_uid='cms_articles_pre_save_article')
signals.pre_delete.connect(pre_delete_title, sender=Title, dispatch_uid='cms_articles_pre_delete_article')
