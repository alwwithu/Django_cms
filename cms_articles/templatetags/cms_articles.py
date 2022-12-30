# -*- coding: utf-8 -*-

from classytags.arguments import Argument, MultiValueArgument
from classytags.core import Options, Tag
from classytags.helpers import AsTag
from cms.exceptions import PlaceholderNotFound
from cms.templatetags.cms_tags import DeclaredPlaceholder, PlaceholderOptions
from cms.toolbar.utils import get_toolbar_from_request
from cms.utils import get_language_from_request, get_site_id
from cms.utils.moderator import use_draft
from django import template
from django.contrib.sites.models import Site
from django.core.mail import mail_managers
from django.middleware.common import BrokenLinkEmailsMiddleware
from django.utils.encoding import force_str
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _
from menus.base import NavigationNode
from menus.templatetags.menu_tags import ShowBreadcrumb

from ..conf import settings
from ..models import Article
from ..utils.placeholder import validate_placeholder_name

register = template.Library()


def _get_article_by_untyped_arg(article_lookup, request, site_id):
    """
    The `article_lookup` argument can be of any of the following types:
    - Integer: interpreted as `pk` of the desired article
    - `dict`: a dictionary containing keyword arguments to find the desired article
    (for instance: `{'pk': 1}`)
    - `Article`: you can also pass an Article object directly, in which case there will be no database lookup.
    - `None`: the current article will be used
    """
    if article_lookup is None:
        return request.current_article
    if isinstance(article_lookup, Article):
        if hasattr(request, "current_article") and request.current_article.pk == article_lookup.pk:
            return request.current_article
        return article_lookup

    if isinstance(article_lookup, int):
        article_lookup = {"pk": article_lookup}
    elif not isinstance(article_lookup, dict):
        raise TypeError("The article_lookup argument can be either a Dictionary, Integer, or Article.")
    article_lookup.update({"site": site_id})
    try:
        article = Article.objects.all().get(**article_lookup)
        if request and use_draft(request):
            if article.publisher_is_draft:
                return article
            else:
                return article.publisher_draft
        else:
            if article.publisher_is_draft:
                return article.publisher_public
            else:
                return article
    except Article.DoesNotExist:
        site = Site.objects.get_current()
        subject = _("Article not found on %(domain)s") % {"domain": site.domain}
        body = _(
            "A template tag couldn't find the article with lookup arguments `%(article_lookup)s\n`. "
            "The URL of the request was: http://%(host)s%(path)s"
        ) % {"article_lookup": repr(article_lookup), "host": site.domain, "path": request.path_info}
        if settings.DEBUG:
            raise Article.DoesNotExist(body)
        else:
            mw = settings.MIDDLEWARE
            if getattr(settings, "SEND_BROKEN_LINK_EMAILS", False):
                mail_managers(subject, body, fail_silently=True)
            elif "django.middleware.common.BrokenLinkEmailsMiddleware" in mw:
                middle = BrokenLinkEmailsMiddleware()
                domain = request.get_host()
                path = request.get_full_path()
                referer = force_str(request.headers.get("Referer", ""), errors="replace")
                if not middle.is_ignorable_request(request, path, domain, referer):
                    mail_managers(subject, body, fail_silently=True)
            return None


class ArticlePlaceholder(Tag):
    """
    This template node is used to output article content and
    is also used in the admin to dynamically generate input fields.

    eg: {% article_placeholder "placeholder_name" %}

    {% article_placeholder "footer" or %}
        <a href="/about/">About us</a>
    {% endarticle_placeholder %}

    Keyword arguments:
    name -- the name of the placeholder
    or -- optional argument which if given will make the template tag a block
        tag whose content is shown if the placeholder is empty
    """

    name = "article_placeholder"
    options = PlaceholderOptions(
        Argument("name", resolve=False),
        MultiValueArgument("extra_bits", required=False, resolve=False),
        blocks=[
            ("endarticle_placeholder", "nodelist"),
        ],
    )

    def render_tag(self, context, name, extra_bits, nodelist=None):
        request = context.get("request")

        if not request:
            return ""

        validate_placeholder_name(name)

        toolbar = get_toolbar_from_request(request)
        renderer = toolbar.get_content_renderer()
        inherit = False

        try:
            content = renderer.render_page_placeholder(
                slot=name,
                context=context,
                inherit=inherit,
                page=request.current_article,
                nodelist=nodelist,
            )
        except PlaceholderNotFound:
            content = ""

        if not content and nodelist:
            return nodelist.render(context)
        return content

    def get_declaration(self):
        slot = self.kwargs["name"].var.value.strip('"').strip("'")

        return DeclaredPlaceholder(slot=slot, inherit=False)


register.tag("article_placeholder", ArticlePlaceholder)


class ArticleAttribute(AsTag):
    """
    This template node is used to output an attribute from a article such
    as its title or slug.

    Synopsis
         {% article_attribute "field-name" %}
         {% article_attribute "field-name" as varname %}
         {% article_attribute "field-name" article_lookup %}
         {% article_attribute "field-name" article_lookup as varname %}

    Example
         {# Output current article's page_title attribute: #}
         {% article_attribute "page_title" %}
         {# Output slug attribute of the article with pk 10: #}
         {% article_attribute "slug" 10 %}
         {# Assign page_title attribute to a variable: #}
         {% article_attribute "page_title" as title %}

    Keyword arguments:
    field-name -- the name of the field to output. Use one of:
    - title
    - description
    - page_title
    - slug
    - meta_description
    - changed_date
    - changed_by
    - image

    article_lookup -- lookup argument for Article, if omitted field-name of current article is returned.
    See _get_article_by_untyped_arg() for detailed information on the allowed types and their interpretation
    for the article_lookup argument.

    varname -- context variable name. Output will be added to template context as this variable.
    This argument is required to follow the 'as' keyword.
    """

    name = "article_attribute"
    options = Options(
        Argument("name", resolve=False),
        Argument("article_lookup", required=False, default=None),
        "as",
        Argument("varname", required=False, resolve=False),
    )

    valid_attributes = [
        "title",
        "slug",
        "description",
        "page_title",
        "menu_title",
        "meta_description",
        "changed_date",
        "changed_by",
        "image",
    ]

    def get_value(self, context, name, article_lookup):
        if "request" not in context:
            return ""
        name = name.lower()
        request = context["request"]
        lang = get_language_from_request(request)
        article = _get_article_by_untyped_arg(article_lookup, request, get_site_id(None))
        if article and name in self.valid_attributes:
            func = getattr(article, "get_%s" % name)
            ret_val = func(language=lang, fallback=True)
            if name not in ("changed_date", "image"):
                ret_val = escape(ret_val)
            return ret_val
        return ""


register.tag("article_attribute", ArticleAttribute)


class ShowArticleBreadcrumb(ShowBreadcrumb):
    name = "show_article_breadcrumb"

    def get_context(self, context, start_level, template, only_visible):
        context = super().get_context(context, start_level, template, only_visible)
        try:
            current_article = context["request"].current_article
        except (AttributeError, KeyError):
            pass
        else:
            context["ancestors"].append(
                NavigationNode(
                    title=current_article.get_menu_title(),
                    url=current_article.get_absolute_url(),
                    id=current_article.pk,
                    visible=True,
                )
            )
        return context


register.tag("show_article_breadcrumb", ShowArticleBreadcrumb)


@register.simple_tag(takes_context=True)
def url_page(context, page):
    get = context["request"].GET.copy()
    get[settings.CMS_ARTICLES_PAGE_FIELD] = page
    return "{}?{}".format(context["request"].path, get.urlencode())
