# -*- coding: utf-8 -*-
from cms.cache.page import set_page_cache
from cms.models import Page
from django.template.response import TemplateResponse


def render_article(request, article, current_language, slug):
    """
    Renders an article
    """
    context = {}
    context["article"] = article
    context["lang"] = current_language
    context["current_article"] = article
    context["has_change_permissions"] = article.has_change_permission(request)

    response = TemplateResponse(request, article.template, context)
    response.add_post_render_callback(set_page_cache)

    # Add headers for X Frame Options - this really should be changed upon moving to class based views
    xframe_options = article.tree.get_xframe_options()
    # xframe_options can be None if there's no xframe information on the page
    # (eg. a top-level page which has xframe options set to "inherit")
    if xframe_options == Page.X_FRAME_OPTIONS_INHERIT or xframe_options is None:
        # This is when we defer to django's own clickjacking handling
        return response

    # We want to prevent django setting this in their middlewear
    response.xframe_options_exempt = True

    if xframe_options == Page.X_FRAME_OPTIONS_ALLOW:
        # Do nothing, allowed is no header.
        return response
    elif xframe_options == Page.X_FRAME_OPTIONS_SAMEORIGIN:
        response["X-Frame-Options"] = "SAMEORIGIN"
    elif xframe_options == Page.X_FRAME_OPTIONS_DENY:
        response["X-Frame-Options"] = "DENY"
    return response
