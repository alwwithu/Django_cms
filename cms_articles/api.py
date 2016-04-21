from __future__ import absolute_import, division, generators, nested_scopes, print_function, unicode_literals, with_statement

"""
Public Python API to create CMS articles.

WARNING: None of the functions defined in this module checks for permissions.
You must implement the necessary permission checks in your own code before
calling these methods!
"""
import datetime

from django.template.defaultfilters import slugify
from django.template.loader import get_template
from django.utils.timezone import now

from djangocms_text_ckeditor.cms_plugins import TextPlugin

from cms.api import add_plugin
from cms.utils.i18n import get_language_list
from cms.utils.permissions import current_user

from .conf import settings
from .models import Article, Title


def create_article(
        category, template, title, language,
        slug=None, page_title=None, menu_title=None, meta_description=None,
        created_by=None, publication_date=None, publication_end_date=None,
        published=False, login_required=False, creation_date=None,
        contents=[],
    ):
    """
    Create a CMS Article and it's title for the given language
    """

    # validate category
    category = category.get_public_object()
    assert category.application_urls == 'CMSArticlesApp'

    # validate template
    assert template in [tpl[0] for tpl in settings.CMS_ARTICLES_TEMPLATES]
    get_template(template)

    # validate language:
    assert language in get_language_list(category.site_id), settings.CMS_LANGUAGES.get(category.site_id)

    # validate publication date
    if publication_date:
        assert isinstance(publication_date, datetime.date)

    # validate publication end date
    if publication_end_date:
        assert isinstance(publication_end_date, datetime.date)

    # validate publication end date
    if creation_date:
        assert isinstance(creation_date, datetime.date)

    # get username
    if created_by:
        username = created_by.get_username()
    else:
        username = 'script'

    with current_user(username):
        # create article
        article = Article.objects.create(
            template            = template,
            category            = category,
            login_required      = login_required,
            creation_date       = creation_date,
            publication_date    = publication_date,
            publication_end_date= publication_end_date,
            languages           = language,
        )

        # create title
        create_title(
            article             = article,
            language            = language,
            title               = title,
            slug                = slug,
            page_title          = page_title,
            menu_title          = menu_title,
            meta_description    = meta_description,
            creation_date       = creation_date,
        )

        for slot, body in contents.items():
            placeholder = article.placeholders.get(slot=slot)
            add_plugin(placeholder, TextPlugin, language, body=body)

        # publish article
        if published:
            article.publish(language)

    return article.reload()



def create_title(
        article, language, title, slug=None,
        menu_title=None, page_title=None, meta_description=None,
        creation_date=None,
    ):
    """
    Create an article title.
    """
    # validate article
    assert isinstance(article, Article)

    # validate language:
    assert language in get_language_list(article.category.site_id)

    # set default slug:
    if not slug:
        slug = settings.CMS_ARTICLES_SLUG_FORMAT.format(
            now = now(),
            slug = slugify(title),
        )

    # find unused slug:
    base_slug   = slug
    qs          = Title.objects.filter(language=language)
    used_slugs  = list(s for s in qs.values_list('slug', flat=True) if s.startswith(base_slug))
    i = 1
    while slug in used_slugs:
        slug = '%s-%s' % (base_slug, i)
        i += 1

    # create title
    title = Title.objects.create(
        article     = article,
        language    = language,
        title       = title,
        slug        = slug,
        page_title  = page_title,
        menu_title  = menu_title,
        meta_description = meta_description,
    )

    return title



def publish_article(article, language, changed_by=None):
    """
    Publish an article. This sets `article.published` to `True`
    and calls article.publish() which does the actual publishing.
    """
    article = article.reload()

    # get username
    if changed_by:
        username = changed_by.get_username()
    else:
        username = 'script'

    with current_user(username):
        article.publish(language)

    return article.reload()


