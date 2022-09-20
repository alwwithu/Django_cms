from cms.exceptions import LanguageError
from cms.page_rendering import _handle_no_page, render_object_structure
from cms.utils.conf import get_cms_setting
from cms.utils.i18n import (
    get_default_language_for_site,
    get_fallback_languages,
    get_language_list,
    get_public_languages,
    get_redirect_on_fallback,
)
from cms.utils.moderator import use_draft
from cms.views import details as page
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseRedirect
from django.utils.http import urlquote
from django.utils.translation import get_language_from_request

from .article_rendering import render_article
from .utils.article import get_article_from_slug


def article(request, slug):
    """
    The main view of the Django-CMS Articles! Takes a request and a slug,
    renders the article.
    """
    # Get current CMS Page as article tree
    tree = request.current_page.get_public_object()

    # Check whether it really is a tree.
    # It could also be one of its sub-pages.
    if tree.application_urls != "CMSArticlesApp":
        # In such case show regular CMS Page
        return page(request, slug)

    # Get an Article object from the request
    draft = use_draft(request) and request.user.has_perm("cms_articles.change_article")
    preview = "preview" in request.GET and request.user.has_perm("cms_articles.change_article")

    site = tree.node.site
    article = get_article_from_slug(tree, slug, preview, draft)

    if not article:
        # raise 404
        _handle_no_page(request)

    request.current_article = article

    if hasattr(request, "user") and request.user.is_staff:
        user_languages = get_language_list(site_id=site.pk)
    else:
        user_languages = get_public_languages(site_id=site.pk)

    request_language = get_language_from_request(request, check_path=True)

    # get_published_languages will return all languages in draft mode
    # and published only in live mode.
    # These languages are then filtered out by the user allowed languages
    available_languages = [
        language for language in user_languages if language in list(article.get_published_languages())
    ]

    own_urls = [
        request.build_absolute_uri(request.path),
        "/%s" % request.path,
        request.path,
    ]

    try:
        redirect_on_fallback = get_redirect_on_fallback(request_language, site_id=site.pk)
    except LanguageError:
        redirect_on_fallback = False

    if request_language not in user_languages:
        # Language is not allowed
        # Use the default site language
        default_language = get_default_language_for_site(site.pk)
        fallbacks = get_fallback_languages(default_language, site_id=site.pk)
        fallbacks = [default_language] + fallbacks
    else:
        fallbacks = get_fallback_languages(request_language, site_id=site.pk)

    # Only fallback to languages the user is allowed to see
    fallback_languages = [
        language for language in fallbacks if language != request_language and language in available_languages
    ]
    language_is_unavailable = request_language not in available_languages

    if language_is_unavailable and not fallback_languages:
        # There is no page with the requested language
        # and there's no configured fallbacks
        return _handle_no_page(request)
    elif language_is_unavailable and redirect_on_fallback:
        # There is no page with the requested language and
        # the user has explicitly requested to redirect on fallbacks,
        # so redirect to the first configured / available fallback language
        fallback = fallback_languages[0]
        redirect_url = article.get_absolute_url(fallback, fallback=False)
    else:
        redirect_url = False

    if redirect_url:
        if request.user.is_staff and hasattr(request, "toolbar") and request.toolbar.edit_mode_active:
            request.toolbar.redirect_url = redirect_url
        elif redirect_url not in own_urls:
            # prevent redirect to self
            return HttpResponseRedirect(redirect_url)

    # permission checks
    if article.login_required and not request.user.is_authenticated():
        return redirect_to_login(urlquote(request.get_full_path()), settings.LOGIN_URL)

    if hasattr(request, "toolbar"):
        request.toolbar.obj = article

    structure_requested = get_cms_setting("CMS_TOOLBAR_URL__BUILD") in request.GET

    if article.has_change_permission(request) and structure_requested:
        return render_object_structure(request, article)
    return render_article(request, article, current_language=request_language, slug=slug)
