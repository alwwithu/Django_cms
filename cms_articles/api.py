# -*- coding: utf-8 -*-
"""
Public Python API to create CMS Articles contents.

WARNING: None of the functions defined in this module checks for permissions.
You must implement the necessary permission checks in your own code before
calling these methods!
"""
import datetime

from cms.api import add_plugin
from cms.utils.i18n import get_language_list
from cms.utils.permissions import current_user
from django.db import transaction
from django.template.defaultfilters import slugify
from django.template.loader import get_template
from django.utils.encoding import force_str
from django.utils.timezone import now
from djangocms_text_ckeditor.cms_plugins import TextPlugin

from .conf import settings
from .models import Article, Title


@transaction.atomic
def create_article(
    tree,
    template,
    title,
    language,
    slug=None,
    description=None,
    page_title=None,
    menu_title=None,
    meta_description=None,
    created_by=None,
    image=None,
    publication_date=None,
    publication_end_date=None,
    published=False,
    login_required=False,
    creation_date=None,
    attributes=[],
    categories=[],
):
    """
    Create a CMS Article and it's title for the given language
    """

    # validate tree
    tree = tree.get_public_object()
    assert tree.application_urls == "CMSArticlesApp"

    # validate template
    assert template in [tpl[0] for tpl in settings.CMS_ARTICLES_TEMPLATES]
    get_template(template)

    # validate language:
    assert language in get_language_list(tree.node.site_id), settings.CMS_LANGUAGES.get(tree.node.site_id)

    # validate publication date
    if publication_date:
        assert isinstance(publication_date, datetime.date)

    # validate publication end date
    if publication_end_date:
        assert isinstance(publication_end_date, datetime.date)

    # validate creation date
    if not creation_date:
        creation_date = publication_date
    if creation_date:
        assert isinstance(creation_date, datetime.date)

    # get username
    if created_by:
        try:
            username = created_by.get_username()
        except Exception:
            username = force_str(created_by)
    else:
        username = "script"

    with current_user(username):
        # create article
        article = Article.objects.create(
            tree=tree,
            template=template,
            login_required=login_required,
            creation_date=creation_date,
            publication_date=publication_date,
            publication_end_date=publication_end_date,
            languages=language,
        )
        article.attributes.set(attributes)
        article.categories.set(categories)

        # create title
        create_title(
            article=article,
            language=language,
            title=title,
            slug=slug,
            description=description,
            page_title=page_title,
            menu_title=menu_title,
            meta_description=meta_description,
            creation_date=creation_date,
            image=image,
        )

        # publish article
        if published:
            article.publish(language)

    return article.reload()


@transaction.atomic
def create_title(
    article,
    language,
    title,
    slug=None,
    description=None,
    page_title=None,
    menu_title=None,
    meta_description=None,
    creation_date=None,
    image=None,
):
    """
    Create an article title.
    """
    # validate article
    assert isinstance(article, Article)

    # validate language:
    assert language in get_language_list(article.tree.node.site_id)

    # validate creation date
    if creation_date:
        assert isinstance(creation_date, datetime.date)

    # set default slug:
    if not slug:
        slug = settings.CMS_ARTICLES_SLUG_FORMAT.format(
            now=creation_date or now(),
            slug=slugify(title),
        )

    # find unused slug:
    base_slug = slug
    qs = Title.objects.filter(language=language)
    used_slugs = list(s for s in qs.values_list("slug", flat=True) if s.startswith(base_slug))
    i = 1
    while slug in used_slugs:
        slug = "%s-%s" % (base_slug, i)
        i += 1

    # create title
    title = Title.objects.create(
        article=article,
        language=language,
        title=title,
        slug=slug,
        description=description or "",
        page_title=page_title,
        menu_title=menu_title,
        meta_description=meta_description,
        image=image,
    )

    return title


@transaction.atomic
def add_content(obj, language, slot, content):
    """
    Adds a TextPlugin with given content to given slot
    """
    placeholder = obj.placeholders.get(slot=slot)
    add_plugin(placeholder, TextPlugin, language, body=content)


def publish_article(article, language, changed_by=None):
    """
    Publish an article. This sets `article.published` to `True` and calls publish()
    which does the actual publishing.
    """
    article = article.reload()

    # get username
    if changed_by:
        username = changed_by.get_username()
    else:
        username = "script"

    with current_user(username):
        article.publish(language)

    return article.reload()
