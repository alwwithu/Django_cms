from __future__ import absolute_import, division, generators, nested_scopes, print_function, unicode_literals, with_statement

from datetime import datetime
from itertools import chain
from platform import python_version
from copy import copy

from classytags.utils import flatten_context

try:
    from collections import OrderedDict
except ImportError:
    from django.utils.datastructures import SortedDict as OrderedDict

import django
from django import template
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import mail_managers
from django.core.urlresolvers import reverse
from django.db.models import Model
from django.middleware.common import BrokenLinkEmailsMiddleware
from django.template.defaultfilters import safe
from django.template.loader import render_to_string
from django.utils import six
from django.utils.encoding import smart_text, force_text
from django.utils.html import escape
from django.utils.http import urlencode
from django.utils.safestring import mark_safe
from django.utils.six import string_types
from django.utils.translation import ugettext_lazy as _, get_language

from classytags.arguments import (Argument, MultiValueArgument,
                                  MultiKeywordArgument)
from classytags.core import Options, Tag
from classytags.helpers import InclusionTag, AsTag
from classytags.parser import Parser
from classytags.values import StringValue
from sekizai.helpers import Watcher
from sekizai.templatetags.sekizai_tags import SekizaiParser, RenderBlock

from cms import __version__
from cms.cache.page import get_page_url_cache, set_page_url_cache
from cms.cache.placeholder import (get_placeholder_page_cache, set_placeholder_page_cache,
                                   get_placeholder_cache)
from cms.exceptions import PlaceholderNotFound
from cms.models import Page, Placeholder as PlaceholderModel, CMSPlugin, StaticPlaceholder
from cms.plugin_pool import plugin_pool
from cms.plugin_rendering import render_placeholder
from cms.utils.plugins import get_plugins, assign_plugins
from cms.utils import get_language_from_request, get_site_id
from cms.utils.conf import get_cms_setting
from cms.utils.i18n import force_language
from cms.utils.moderator import use_draft
from cms.utils.page_resolver import get_page_queryset
from ..utils.placeholder import validate_placeholder_name, get_toolbar_plugin_struct, restore_sekizai_context
from cms.utils.urlutils import admin_reverse
from menus.templatetags.menu_tags import ShowBreadcrumb
from menus.base import NavigationNode

from ..models import Article

DJANGO_VERSION = django.get_version()
PYTHON_VERSION = python_version()

register = template.Library()


def has_permission(page, request):
    return page.has_change_permission(request)


register.filter(has_permission)



def _get_article_by_untyped_arg(article_lookup, request, site_id):
    """
    The `article_lookup` argument can be of any of the following types:
    - Integer: interpreted as `pk` of the desired article
    - String: interpreted as `reverse_id` of the desired article
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



class ArticleUrl(AsTag):
    name = 'article_url'

    options = Options(
        Argument('article_lookup'),
        Argument('lang', required=False, default=None),
        Argument('site', required=False, default=None),
        'as',
        Argument('varname', required=False, resolve=False),
    )

    def get_value_for_context(self, context, **kwargs):
        #
        # A design decision with several active members of the django-cms
        # community that using this tag with the 'as' breakpoint should never
        # return Exceptions regardless of the setting of settings.DEBUG.
        #
        # We wish to maintain backwards functionality where the non-as-variant
        # of using this tag will raise DNE exceptions only when
        # settings.DEBUG=False.
        #
        try:
            return super(ArticleUrl, self).get_value_for_context(context, **kwargs)
        except Article.DoesNotExist:
            return ''

    def get_value(self, context, article_lookup, lang, site):

        site_id = get_site_id(site)
        request = context.get('request', False)

        if not request:
            return ''

        if lang is None:
            lang = get_language_from_request(request)

        #url = get_article_url_cache(article_lookup, lang, site_id)
        url = None
        if url is None:
            article = _get_article_by_untyped_arg(article_lookup, request, site_id)
            if article:
                url = article.get_absolute_url(language=lang)
                #set_article_url_cache(article_lookup, lang, site_id, url)
        if url:
            return url
        return ''



register.tag(ArticleUrl)
register.tag('article_id_url', ArticleUrl)



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
    if not get_cms_setting('PLACEHOLDER_CACHE') or (hasattr(request, 'toolbar') and request.toolbar.edit_mode):
        fetch_placeholders = placeholders
    else:
        for placeholder in placeholders:
            cached_value = get_placeholder_cache(placeholder, get_language())
            if cached_value is not None:
                restore_sekizai_context(context, cached_value['sekizai'])
                placeholder.content_cache = cached_value['content']
            else:
                fetch_placeholders.append(placeholder)
            placeholder.cache_checked = True
    if fetch_placeholders:
        assign_plugins(context['request'], fetch_placeholders, article.get_template(),  get_language())
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



class PlaceholderParser(Parser):
    def parse_blocks(self):
        for bit in getattr(self.kwargs['extra_bits'], 'value', self.kwargs['extra_bits']):
            if getattr(bit, 'value', bit.var.value) == 'or':
                return super(PlaceholderParser, self).parse_blocks()
        return



class ArticlePlaceholderOptions(Options):
    def get_parser_class(self):
        return PlaceholderParser



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
    options = ArticlePlaceholderOptions(
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
        article = request.current_article
        if not article or article == 'dummy':
            if nodelist:
                return nodelist.render(context)
            return ''
        content = ''
        try:
            content = get_placeholder_content(context, request, article, name, nodelist)
        except PlaceholderNotFound:
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



class RenderPlugin(InclusionTag):
    template = 'cms/content.html'
    name = 'render_plugin'
    options = Options(
        Argument('plugin')
    )

    def get_processors(self, context, plugin, placeholder):
        #
        # Prepend frontedit toolbar output if applicable. Moved to its own
        # method to aide subclassing the whole RenderPlugin if required.
        #
        request = context['request']
        toolbar = getattr(request, 'toolbar', None)
        if (toolbar and getattr(toolbar, "edit_mode", False) and
                getattr(toolbar, "show_toolbar", False) and
                placeholder.has_change_permission(request) and
                getattr(placeholder, 'is_editable', True)):
            from cms.middleware.toolbar import toolbar_plugin_processor
            processors = (toolbar_plugin_processor, )
        else:
            processors = None
        return processors

    def get_context(self, context, plugin):

        # Prepend frontedit toolbar output if applicable
        if not plugin:
            return {'content': ''}

        placeholder = plugin.placeholder

        processors = self.get_processors(context, plugin, placeholder)

        return {
            'content': plugin.render_plugin(
                context,
                placeholder=placeholder,
                processors=processors
            )
        }

register.tag(RenderPlugin)



class RenderPluginBlock(InclusionTag):
    """
    Acts like the CMS's templatetag 'render_model_block' but with a plugin
    instead of a model. This is used to link from a block of markup to a
    plugin's changeform.

    This is useful for UIs that have some plugins hidden from display in
    preview mode, but the CMS author needs to expose a way to edit them
    anyway. It is also useful for just making duplicate or alternate means of
    triggering the change form for a plugin.
    """

    name = 'render_plugin_block'
    template = "cms/toolbar/render_plugin_block.html"
    options = Options(
        Argument('plugin'),
        blocks=[('endrender_plugin_block', 'nodelist')],
    )

    def get_context(self, context, plugin, nodelist):
        context['inner'] = nodelist.render(context)
        context['plugin'] = plugin
        return context

register.tag(RenderPluginBlock)



class PluginChildClasses(InclusionTag):
    """
    Accepts a placeholder or a plugin and renders the allowed plugins for this.
    """

    template = "cms/toolbar/dragitem_menu.html"
    name = "plugin_child_classes"
    options = Options(
        Argument('obj')
    )

    def get_context(self, context, obj):
        # Prepend frontedit toolbar output if applicable
        request = context['request']
        article = request.current_article
        child_plugin_classes = []
        if isinstance(obj, CMSPlugin):
            slot = context['slot']
            plugin = obj
            plugin_class = plugin.get_plugin_class()
            if plugin_class.allow_children:
                instance, plugin = plugin.get_plugin_instance()
                plugin.cms_plugin_instance = instance
                childs = [plugin_pool.get_plugin(cls) for cls in plugin.get_child_classes(slot, article)]
                # Builds the list of dictionaries containing module, name and value for the plugin dropdowns
                child_plugin_classes = get_toolbar_plugin_struct(childs, slot, article, parent=plugin_class)
        elif isinstance(obj, PlaceholderModel):
            placeholder = obj
            article = placeholder.article if placeholder else None
            if not article:
                article = getattr(request, 'current_article', None)
            if placeholder:
                slot = placeholder.slot
            else:
                slot = None
            # Builds the list of dictionaries containing module, name and value for the plugin dropdowns
            child_plugin_classes = get_toolbar_plugin_struct(plugin_pool.get_all_plugins(slot, article), slot, article)
        return {'plugin_classes': child_plugin_classes}

register.tag(PluginChildClasses)



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
         {# Output current article's article_title attribute: #}
         {% article_attribute "article_title" %}
         {# Output article_title attribute of the article with reverse_id "the_article": #}
         {% article_attribute "article_title" "the_article" %}
         {# Output slug attribute of the article with pk 10: #}
         {% article_attribute "slug" 10 %}
         {# Assign article_title attribute to a variable: #}
         {% article_attribute "article_title" as title %}

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
        "meta_description",
        "article_title",
        "menu_title",
        "changed_date",
        "changed_by",
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
            if not isinstance(ret_val, datetime):
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
    except PlaceholderModel.DoesNotExist:
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
        Argument('reverse_id'),
        Argument('lang', required=False, default=None),
        Argument('site', required=False, default=None),
    )

    def get_context(self, *args, **kwargs):
        return _show_placeholder_for_article(**self.get_kwargs(*args, **kwargs))

    def get_kwargs(self, context, placeholder_name, reverse_id, lang, site):
        cache_result = True
        if 'preview' in context['request'].GET:
            cache_result = False
        return {
            'context': context,
            'placeholder_name': placeholder_name,
            'article_lookup': reverse_id,
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
            placeholder = PlaceholderModel.objects.get(slot=placeholder)
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

