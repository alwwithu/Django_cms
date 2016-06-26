from __future__ import absolute_import, division, generators, nested_scopes, print_function, unicode_literals, with_statement

from copy import copy
from platform import python_version

import django
from django import template
from django.contrib.sites.models import Site
from django.core.mail import mail_managers
from django.middleware.common import BrokenLinkEmailsMiddleware
from django.template.defaultfilters import safe
from django.utils import six
from django.utils.encoding import force_text
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.six import string_types
from django.utils.translation import ugettext_lazy as _, get_language

from classytags.arguments import Argument, MultiValueArgument
from classytags.core import Options, Tag
from classytags.helpers import InclusionTag, AsTag

from cms.cache.placeholder import get_placeholder_cache
from cms.models import Placeholder
from cms.plugin_rendering import render_placeholder
from cms.templatetags.cms_tags import PlaceholderOptions
from cms.utils.plugins import get_plugins, assign_plugins
from cms.utils import get_language_from_request, get_site_id
from cms.utils.conf import get_cms_setting
from cms.utils.moderator import use_draft
from ..utils.placeholder import validate_placeholder_name, restore_sekizai_context
from menus.templatetags.menu_tags import ShowBreadcrumb
from menus.base import NavigationNode

from sekizai.helpers import Watcher

from ..conf import settings
from ..models import Article

DJANGO_VERSION = django.get_version()
PYTHON_VERSION = python_version()

register = template.Library()



def _get_article_by_untyped_arg(article_lookup, request, site_id):
    """
    The `article_lookup` argument can be of any of the following types:
    - Integer: interpreted as `pk` of the desired article
    - `dict`: a dictionary containing keyword arguments to find the desired article
    (for instance: `{'pk': 1}`)
    - `Article`: you can also pass a Article object directly, in which case there will be no database lookup.
    - `None`: the current article will be used
    """
    if article_lookup is None:
        return request.current_article
    if isinstance(article_lookup, Article):
        if hasattr(request, 'current_article') and request.current_article.pk == article_lookup.pk:
            return request.current_article
        return article_lookup
    elif isinstance(article_lookup, six.integer_types):
        article_lookup = {'pk': article_lookup}
    elif not isinstance(article_lookup, dict):
        raise TypeError('The article_lookup argument can be either a Dictionary, Integer, or Article.')
    article_lookup.update({'site': site_id})
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
        subject = _('Article not found on %(domain)s') % {'domain': site.domain}
        body = _("A template tag couldn't find the article with lookup arguments `%(article_lookup)s\n`. "
                 "The URL of the request was: http://%(host)s%(path)s") \
               % {'article_lookup': repr(article_lookup), 'host': site.domain, 'path': request.path_info}
        if settings.DEBUG:
            raise Article.DoesNotExist(body)
        else:
            if getattr(settings, 'SEND_BROKEN_LINK_EMAILS', False):
                mail_managers(subject, body, fail_silently=True)
            elif 'django.middleware.common.BrokenLinkEmailsMiddleware' in settings.MIDDLEWARE_CLASSES:
                middle = BrokenLinkEmailsMiddleware()
                domain = request.get_host()
                path = request.get_full_path()
                referer = force_text(request.META.get('HTTP_REFERER', ''), errors='replace')
                if not middle.is_ignorable_request(request, path, domain, referer):
                    mail_managers(subject, body, fail_silently=True)
            return None



def _get_placeholder(article, context, name):
    placeholder_cache = getattr(article, '_tmp_placeholders_cache', {})
    if article.pk in placeholder_cache:
        placeholder = placeholder_cache[article.pk].get(name, None)
        if placeholder:
            return placeholder
    placeholder_cache[article.pk] = {}
    placeholders = article.rescan_placeholders().values()
    fetch_placeholders = []
    request = context['request']
    site_id = article.tree.site_id
    if not get_cms_setting('PLACEHOLDER_CACHE') or (hasattr(request, 'toolbar') and request.toolbar.edit_mode):
        fetch_placeholders = placeholders
    else:
        for placeholder in placeholders:
            cached_value = get_placeholder_cache(placeholder, get_language(), site_id, request)
            if cached_value is not None:
                restore_sekizai_context(context, cached_value['sekizai'])
                placeholder.content_cache = cached_value['content']
            else:
                fetch_placeholders.append(placeholder)
            placeholder.cache_checked = True
    if fetch_placeholders:
        assign_plugins(context['request'], fetch_placeholders, article.get_template(), get_language())
    for placeholder in placeholders:
        placeholder_cache[article.pk][placeholder.slot] = placeholder
        placeholder.article = article
    article._tmp_placeholders_cache = placeholder_cache
    placeholder = placeholder_cache[article.pk].get(name, None)
    return placeholder



def get_placeholder_content(context, request, article, name, default):
    edit_mode = getattr(request, 'toolbar', None) and getattr(request.toolbar, 'edit_mode')
    placeholder = _get_placeholder(article, context, name)
    if placeholder:
        if not edit_mode and get_cms_setting('PLACEHOLDER_CACHE'):
            if hasattr(placeholder, 'content_cache'):
                return mark_safe(placeholder.content_cache)
            if not hasattr(placeholder, 'cache_checked'):
                cached_value = get_placeholder_cache(placeholder, get_language())
                if cached_value is not None:
                    restore_sekizai_context(context, cached_value['sekizai'])
                    return mark_safe(cached_value['content'])
        get_plugins(request, placeholder, article.get_template())
    return render_placeholder(placeholder, context, name, default=default)



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
    name = 'article_placeholder'
    options = PlaceholderOptions(
        Argument('name', resolve=False),
        MultiValueArgument('extra_bits', required=False, resolve=False),
        blocks=[
            ('endarticle_placeholder', 'nodelist'),
        ]
    )

    def render_tag(self, context, name, extra_bits, nodelist=None):
        validate_placeholder_name(name)
        if not 'request' in context:
            return ''
        request = context['request']
        article = getattr(request, 'current_article', None)
        if not article:
            if nodelist:
                return nodelist.render(context)
            return ''
        content = ''
        try:
            content = get_placeholder_content(context, request, article, name, nodelist)
        except Placeholder.DoesNotExist:
            if nodelist:
                return nodelist.render(context)
        if not content:
            if nodelist:
                return nodelist.render(context)
            return ''
        return content

    def get_name(self):
        return self.kwargs['name'].var.value.strip('"').strip("'")

register.tag(ArticlePlaceholder)



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
    - page_title
    - slug
    - meta_description
    - changed_date
    - changed_by

    article_lookup -- lookup argument for Article, if omitted field-name of current article is returned.
    See _get_article_by_untyped_arg() for detailed information on the allowed types and their interpretation
    for the article_lookup argument.

    varname -- context variable name. Output will be added to template context as this variable.
    This argument is required to follow the 'as' keyword.
    """
    name = 'article_attribute'
    options = Options(
        Argument('name', resolve=False),
        Argument('article_lookup', required=False, default=None),
        'as',
        Argument('varname', required=False, resolve=False)
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
        if not 'request' in context:
            return ''
        name = name.lower()
        request = context['request']
        lang = get_language_from_request(request)
        article = _get_article_by_untyped_arg(article_lookup, request, get_site_id(None))
        if article == "dummy":
            return ''
        if article and name in self.valid_attributes:
            func = getattr(article, "get_%s" % name)
            ret_val = func(language=lang, fallback=True)
            if not name in ("changed_date", "image"):
                ret_val = escape(ret_val)
            return ret_val
        return ''

register.tag(ArticleAttribute)



def _show_placeholder_for_article(context, placeholder_name, article_lookup, lang=None,
                               site=None, cache_result=True):
    """
    Shows the content of a article with a placeholder name and given lookup
    arguments in the given language.
    This is useful if you want to have some more or less static content that is
    shared among many articles, such as a footer.

    See _get_article_by_untyped_arg() for detailed information on the allowed types
    and their interpretation for the article_lookup argument.
    """
    validate_placeholder_name(placeholder_name)

    request = context.get('request', False)

    site_id = get_site_id(site)

    if not request:
        return {'content': ''}
    if lang is None:
        lang = get_language_from_request(request)

    if cache_result:
        cached_value = get_placeholder_page_cache(article_lookup, lang, site_id, placeholder_name)
        if cached_value:
            restore_sekizai_context(context, cached_value['sekizai'])
            return {'content': mark_safe(cached_value['content'])}
    article = _get_article_by_untyped_arg(article_lookup, request, site_id)
    if not article:
        return {'content': ''}
    try:
        placeholder = article.placeholders.get(slot=placeholder_name)
    except Placeholder.DoesNotExist:
        if settings.DEBUG:
            raise
        return {'content': ''}
    watcher = Watcher(context)
    content = render_placeholder(placeholder, context, placeholder_name, lang=lang,
                                 use_cache=cache_result)
    changes = watcher.get_changes()
    if cache_result:
        set_placeholder_page_cache(article_lookup, lang, site_id, placeholder_name,
                                   {'content': content, 'sekizai': changes})

    if content:
        return {'content': mark_safe(content)}
    return {'content': ''}



class ShowArticlePlaceholderById(InclusionTag):
    template = 'cms/content.html'
    name = 'show_article_placeholder_by_id'

    options = Options(
        Argument('placeholder_name'),
        Argument('article_id'),
        Argument('lang', required=False, default=None),
        Argument('site', required=False, default=None),
    )

    def get_context(self, *args, **kwargs):
        return _show_placeholder_for_article(**self.get_kwargs(*args, **kwargs))

    def get_kwargs(self, context, placeholder_name, article_id, lang, site):
        cache_result = True
        if 'preview' in context['request'].GET:
            cache_result = False
        return {
            'context': context,
            'placeholder_name': placeholder_name,
            'article_lookup': article_id,
            'lang': lang,
            'site': site,
            'cache_result': cache_result
        }

register.tag(ShowArticlePlaceholderById)
register.tag('show_article_placeholder', ShowArticlePlaceholderById)



class ShowUncachedArticlePlaceholderById(ShowArticlePlaceholderById):
    name = 'show_uncached_article_placeholder_by_id'

    def get_kwargs(self, *args, **kwargs):
        kwargs = super(ShowUncachedArticlePlaceholderById, self).get_kwargs(*args, **kwargs)
        kwargs['cache_result'] = False
        return kwargs

register.tag(ShowUncachedArticlePlaceholderById)
register.tag('show_uncached_article_placeholder', ShowUncachedArticlePlaceholderById)



class RenderArticlePlaceholder(AsTag):
    """
    Render the content of the plugins contained in a placeholder.
    The result can be assigned to a variable within the template's context by using the `as` keyword.
    It behaves in the same way as the `ArticleAttribute` class, check its docstring for more details.
    """
    name = 'render_article_placeholder'
    options = Options(
        Argument('placeholder'),
        Argument('width', default=None, required=False),
        'language',
        Argument('language', default=None, required=False),
        'as',
        Argument('varname', required=False, resolve=False)
    )

    def _get_value(self, context, editable=True, **kwargs):
        request = context.get('request', None)
        placeholder = kwargs.get('placeholder')
        width = kwargs.get('width')
        nocache = kwargs.get('nocache', False)
        language = kwargs.get('language')
        if not request:
            return ''
        if not placeholder:
            return ''

        if isinstance(placeholder, string_types):
            placeholder = Placeholder.objects.get(slot=placeholder)
        if not hasattr(request, 'placeholders'):
            request.placeholders = []
        if placeholder.has_change_permission(request):
            request.placeholders.append(placeholder)
        context = copy(context)
        return safe(placeholder.render(context, width, lang=language,
                                       editable=editable, use_cache=not nocache))

    def get_value_for_context(self, context, **kwargs):
        return self._get_value(context, editable=False, **kwargs)

    def get_value(self, context, **kwargs):
        return self._get_value(context, **kwargs)

register.tag(RenderArticlePlaceholder)


class RenderUncachedArticlePlaceholder(RenderArticlePlaceholder):
    """
    Uncached version of RenderArticlePlaceholder
    This templatetag will neither get the result from cache, nor will update
    the cache value for the given placeholder
    """
    name = 'render_uncached_placeholder'

    def _get_value(self, context, editable=True, **kwargs):
        kwargs['nocache'] = True
        return super(RenderUncachedArticlePlaceholder, self)._get_value(context, editable, **kwargs)

register.tag(RenderUncachedArticlePlaceholder)



class ShowArticleBreadcrumb(ShowBreadcrumb):
    name = 'show_article_breadcrumb'

    def get_context(self, context, start_level, template, only_visible):
        context = super(ShowArticleBreadcrumb, self).get_context(context, start_level, template, only_visible)
        try:
            current_article = context['request'].current_article
        except:
            pass
        else:
            context['ancestors'].append(NavigationNode(
                title   = current_article.get_menu_title(),
                url     = current_article.get_absolute_url(),
                id      = current_article.pk,
                visible = True,
            ))
        return context

register.tag(ShowArticleBreadcrumb)



@register.simple_tag(takes_context = True)
def url_page(context, page):
    get = context['request'].GET.copy()
    get[settings.CMS_ARTICLES_PAGE_FIELD] = page
    return '{}?{}'.format(context['request'].path, get.urlencode())


