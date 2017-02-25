from cms.models import Page
from cms.page_rendering import _handle_no_page
from cms.utils import get_language_code, get_language_from_request
from cms.utils.i18n import (
    force_language, get_fallback_languages, get_language_list,
    get_public_languages, get_redirect_on_fallback,
)
from cms.utils.moderator import use_draft
from cms.views import details as page
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.utils.http import urlquote
from django.utils.translation import get_language


def article(request, slug):

    # Get current CMS Page as article tree
    tree = request.current_page

    # Check whether it really is a tree.
    # It could also be one of its sub-pages.
    if tree.application_urls != 'CMSArticlesApp':
        # In such case show regular CMS Page
        return page(request, slug)

    # Get an Article object from the request
    draft = use_draft(request) and request.user.has_perm('cms_articles.change_article')
    preview = 'preview' in request.GET and request.user.has_perm('cms_articles.change_article')

    if draft:
        articles = tree.cms_articles.drafts()
    elif preview:
        articles = tree.cms_articles.public()
    else:
        articles = tree.cms_articles.public().published()

    try:
        article = articles.filter(title_set__slug=slug).distinct().get()
    except:
        return _handle_no_page(request, slug)

    request.current_article = article

    current_language = request.GET.get('language', None)
    if not current_language:
        current_language = request.POST.get('language', None)
    if current_language:
        current_language = get_language_code(current_language)
        if current_language not in get_language_list():
            current_language = None
    if current_language is None:
        current_language = get_language_code(getattr(request, 'LANGUAGE_CODE', None))
        if current_language:
            current_language = get_language_code(current_language)
            if current_language not in get_language_list():
                current_language = None
    if current_language is None:
        current_language = get_language_code(get_language())

    # Check that the current article is available in the desired (current) language
    available_languages = []

    # this will return all languages in draft mode, and published only in live mode
    article_languages = list(article.get_published_languages())

    if hasattr(request, 'user') and request.user.is_staff:
        user_languages = get_language_list()
    else:
        user_languages = get_public_languages()
    for frontend_lang in user_languages:
        if frontend_lang in article_languages:
            available_languages.append(frontend_lang)

    # Check that the language is in FRONTEND_LANGUAGES:
    own_urls = [
        'http%s://%s%s' % ('s' if request.is_secure() else '', request.get_host(), request.path),
        '/%s' % request.path,
        request.path,
    ]

    if current_language not in user_languages:
        # are we on root?
        if not slug:
            # redirect to supported language
            languages = []
            for language in available_languages:
                languages.append((language, language))
            if languages:
                # get supported language
                new_language = get_language_from_request(request)
                if new_language in get_public_languages():
                    with force_language(new_language):
                        articles_root = reverse('articles-root')
                        if (hasattr(request, 'toolbar') and request.user.is_staff and request.toolbar.edit_mode):
                            request.toolbar.redirect_url = articles_root
                        elif articles_root not in own_urls:
                            return HttpResponseRedirect(articles_root)
            elif not hasattr(request, 'toolbar') or not request.toolbar.redirect_url:
                _handle_no_page(request, slug)
        else:
            return _handle_no_page(request, slug)
    if current_language not in available_languages:
        # If we didn't find the required article in the requested (current)
        # language, let's try to find a fallback
        found = False
        for alt_lang in get_fallback_languages(current_language):
            if alt_lang in available_languages:
                if get_redirect_on_fallback(current_language) or slug == "":
                    with force_language(alt_lang):
                        path = article.get_absolute_url(language=alt_lang, fallback=True)
                        # In the case where the article is not available in the
                    # preferred language, *redirect* to the fallback article. This
                    # is a design decision (instead of rendering in place)).
                    if (hasattr(request, 'toolbar') and request.user.is_staff and request.toolbar.edit_mode):
                        request.toolbar.redirect_url = path
                    elif path not in own_urls:
                        return HttpResponseRedirect(path)
                else:
                    found = True
        if not found and (not hasattr(request, 'toolbar') or not request.toolbar.redirect_url):
            # There is a article object we can't find a proper language to render it
            _handle_no_page(request, slug)

    # permission checks
    if article.login_required and not request.user.is_authenticated():
        return redirect_to_login(urlquote(request.get_full_path()), settings.LOGIN_URL)

    if hasattr(request, 'toolbar'):
        request.toolbar.set_object(article)

    # fill the context
    context = {}
    context['article'] = article
    context['lang'] = current_language
    context['current_article'] = article
    context['has_change_permissions'] = article.has_change_permission(request)

    response = TemplateResponse(request, article.template, context)

    # response.add_post_render_callback(set_article_cache)

    # Add headers for X Frame Options - this really should be changed upon moving to class based views
    xframe_options = article.tree.get_xframe_options()
    # xframe_options can be None if there's no xframe information on the article
    # (eg. a top-level article which has xframe options set to "inherit")
    if xframe_options == Page.X_FRAME_OPTIONS_INHERIT or xframe_options is None:
        # This is when we defer to django's own clickjacking handling
        return response

    # We want to prevent django setting this in their middleware
    response.xframe_options_exempt = True

    if xframe_options == article.tree.X_FRAME_OPTIONS_ALLOW:
        # Do nothing, allowed is no header.
        return response
    elif xframe_options == Page.X_FRAME_OPTIONS_SAMEORIGIN:
        response['X-Frame-Options'] = 'SAMEORIGIN'
    elif xframe_options == Page.X_FRAME_OPTIONS_DENY:
        response['X-Frame-Options'] = 'DENY'
    return response
