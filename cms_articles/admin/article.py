import copy
import re
import sys
import warnings
from threading import local
from urllib.parse import unquote

from cms.admin.placeholderadmin import PlaceholderAdminMixin
from cms.constants import PUBLISHER_STATE_PENDING
from cms.models import CMSPlugin, StaticPlaceholder
from cms.utils import get_language_from_request
from cms.utils.conf import get_cms_setting
from cms.utils.i18n import force_language, get_language_list, get_language_object, get_language_tuple
from cms.utils.urlutils import admin_reverse
from django.contrib import admin, messages
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.admin.utils import get_deleted_objects
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import router, transaction
from django.http import Http404, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.template.defaultfilters import escape
from django.template.loader import get_template
from django.urls import path
from django.utils.decorators import method_decorator
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from ..api import add_content
from ..conf import settings
from ..models import Article, Title
from .forms import ArticleCreateForm, ArticleForm

require_POST = method_decorator(require_POST)

_thread_locals = local()


class ArticleAdmin(PlaceholderAdminMixin, admin.ModelAdmin):
    change_list_template = "admin/cms_articles/article_changelist.html"
    search_fields = ("=id", "title_set__slug", "title_set__title", "title_set__description")
    list_display = ("__str__", "order_date", "preview_link") + tuple(
        "lang_{}".format(lang) for lang in get_language_list()
    )
    list_filter = ["tree", "attributes", "categories", "template", "changed_by"]
    date_hierarchy = "order_date"
    filter_horizontal = ["attributes", "categories"]

    preview_template = "admin/cms_articles/article/change_list_preview.html"

    def preview_link(self, obj):
        return get_template(self.preview_template).render(
            {
                "article": obj,
                "lang": _thread_locals.language,
                "request": _thread_locals.request,
            }
        )

    preview_link.short_description = _("Show")
    preview_link.allow_tags = True

    lang_template = "admin/cms_articles/article/change_list_lang.html"

    def __getattr__(self, name):
        if name.startswith("lang_"):
            lang = name[len("lang_") :]

            def lang_dropdown(obj):
                return get_template(self.lang_template).render(
                    {
                        "article": obj,
                        "lang": lang,
                        "language": _thread_locals.language,
                        "has_change_permission": obj.has_change_permission(_thread_locals.request),
                        "has_publish_permission": obj.has_publish_permission(_thread_locals.request),
                        "request": _thread_locals.request,
                    }
                )

            lang_dropdown.short_description = lang
            lang_dropdown.allow_tags = True
            return lang_dropdown
        raise AttributeError(name)

    def get_fieldsets(self, request, obj=None):
        language_dependent = [
            "title",
            "slug",
            "description",
            "content",
            "page_title",
            "menu_title",
            "meta_description",
            "image",
        ]
        if obj:
            language_dependent.remove("content")
        return [
            (None, {"fields": ["tree", "template"]}),
            (_("Language dependent settings"), {"fields": language_dependent}),
            (
                _("Other settings"),
                {"fields": ["attributes", "categories", "publication_date", "publication_end_date", "login_required"]},
            ),
        ]

    def get_urls(self):
        """Get the admin urls"""
        info = "%s_%s" % (self.model._meta.app_label, self.model._meta.model_name)

        def make_path(regex, fn):
            return path(regex, self.admin_site.admin_view(fn), name="%s_%s" % (info, fn.__name__))

        url_patterns = [
            make_path("<int:article_id>/delete-translation/", self.delete_translation),
            make_path("<int:article_id>/<language>/publish/", self.publish_article),
            make_path("<int:article_id>/<language>/unpublish/", self.unpublish),
            make_path("<int:article_id>/<language>/preview/", self.preview_article),
        ]

        url_patterns += super().get_urls()
        return url_patterns

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(
                tree__node__site_id=settings.SITE_ID,
                publisher_is_draft=True,
            )
        )

    def save_model(self, request, obj, form, change):
        new = obj.id is None
        super().save_model(request, obj, form, change)
        Title.objects.set_or_create(request, obj, form, form.cleaned_data["language"])
        if new and form.cleaned_data["content"]:
            add_content(
                obj,
                language=form.cleaned_data["language"],
                slot=settings.CMS_ARTICLES_SLOT,
                content=form.cleaned_data["content"],
            )

    SLUG_REGEXP = re.compile(settings.CMS_ARTICLES_SLUG_REGEXP)

    def get_form(self, request, obj=None, **kwargs):
        """
        Get ArticleForm for the Article model and modify its fields depending on
        the request.
        """
        language = get_language_from_request(request)
        form = super().get_form(request, obj, form=(obj and ArticleForm or ArticleCreateForm), **kwargs)
        # get_form method operates by overriding initial fields value which
        # may persist across invocation. Code below deepcopies fields definition
        # to avoid leaks
        for field in tuple(form.base_fields.keys()):
            form.base_fields[field] = copy.deepcopy(form.base_fields[field])

        if "language" in form.base_fields:
            form.base_fields["language"].initial = language

        if obj:
            title_obj = obj.get_title_obj(language=language, fallback=False, force_reload=True)

            if hasattr(title_obj, "id"):
                for name in ("title", "description", "page_title", "menu_title", "meta_description", "image"):
                    if name in form.base_fields:
                        form.base_fields[name].initial = getattr(title_obj, name)
                try:
                    slug = self.SLUG_REGEXP.search(title_obj.slug).groups()[settings.CMS_ARTICLES_SLUG_GROUP_INDEX]
                except AttributeError:
                    warnings.warn(
                        "Failed to parse slug from CMS_ARTICLES_SLUG_REGEXP. "
                        "It probably doesn't correspond to CMS_ARTICLES_SLUG_FORMAT."
                    )
                    slug = title_obj.slug
                form.base_fields["slug"].initial = slug

        return form

    def get_unihandecode_context(self, language):
        if language[:2] in get_cms_setting("UNIHANDECODE_DECODERS"):
            uhd_lang = language[:2]
        else:
            uhd_lang = get_cms_setting("UNIHANDECODE_DEFAULT_DECODER")
        uhd_host = get_cms_setting("UNIHANDECODE_HOST")
        uhd_version = get_cms_setting("UNIHANDECODE_VERSION")
        if uhd_lang and uhd_host and uhd_version:
            uhd_urls = [
                "%sunihandecode-%s.core.min.js" % (uhd_host, uhd_version),
                "%sunihandecode-%s.%s.min.js" % (uhd_host, uhd_version, uhd_lang),
            ]
        else:
            uhd_urls = []
        return {"unihandecode_lang": uhd_lang, "unihandecode_urls": uhd_urls}

    def changelist_view(self, request, extra_context=None):
        _thread_locals.request = request
        _thread_locals.language = get_language_from_request(request)
        return super().changelist_view(request, extra_context=extra_context)

    def add_view(self, request, form_url="", extra_context=None):
        extra_context = self.update_language_tab_context(request, context=extra_context)
        extra_context.update(self.get_unihandecode_context(extra_context["language"]))
        return super().add_view(request, form_url, extra_context=extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = self.update_language_tab_context(request, context=extra_context)
        language = extra_context["language"]
        extra_context.update(self.get_unihandecode_context(language))
        response = super().change_view(request, object_id, form_url=form_url, extra_context=extra_context)
        if language and response.status_code == 302 and response.headers["location"][1] == request.path_info:
            location = response.headers["location"]
            response.headers["location"] = (location[0], "%s?language=%s" % (location[1], language))
        return response

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        # add context variables
        filled_languages = []
        if obj:
            filled_languages = [t[0] for t in obj.title_set.filter(title__isnull=False).values_list("language")]
        allowed_languages = [lang[0] for lang in get_language_tuple()]
        context.update(
            {
                "filled_languages": [lang for lang in filled_languages if lang in allowed_languages],
            }
        )
        return super().render_change_form(request, context, add, change, form_url, obj)

    def update_language_tab_context(self, request, context=None):
        if not context:
            context = {}
        language = get_language_from_request(request)
        languages = get_language_tuple()
        context.update(
            {
                "language": language,
                "languages": languages,
                "language_tabs": languages,
                "show_language_tabs": len(list(languages)) > 1,
            }
        )
        return context

    @require_POST
    @transaction.atomic
    def publish_article(self, request, article_id, language):
        try:
            article = Article.objects.get(id=article_id, publisher_is_draft=True)
        except Article.DoesNotExist:
            article = None

        # ensure user has permissions to publish this article
        if article:
            if not self.has_change_permission(request):
                return HttpResponseForbidden(_("You do not have permission to publish this article"))
            article.publish(language)
        statics = request.GET.get("statics", "")
        if not statics and not article:
            raise Http404("No article or stack found for publishing.")
        all_published = True
        if statics:
            static_ids = statics.split(",")
            for pk in static_ids:
                static_placeholder = StaticPlaceholder.objects.get(pk=pk)
                published = static_placeholder.publish(request, language)
                if not published:
                    all_published = False
        if article:
            if all_published:
                messages.info(request, _("The content was successfully published."))
                LogEntry.objects.log_action(
                    user_id=request.user.id,
                    content_type_id=ContentType.objects.get_for_model(Article).pk,
                    object_id=article_id,
                    object_repr=article.get_title(language),
                    action_flag=CHANGE,
                )
            else:
                messages.warning(request, _("There was a problem publishing your content"))

        if "redirect" in request.GET:
            return HttpResponseRedirect(request.GET["redirect"])

        referrer = request.META.get("HTTP_REFERER", "")
        path = admin_reverse("cms_articles_article_changelist")
        if request.GET.get("redirect_language"):
            path = "%s?language=%s&article_id=%s" % (
                path,
                request.GET.get("redirect_language"),
                request.GET.get("redirect_article_id"),
            )
        if admin_reverse("index") not in referrer:
            if all_published:
                if article:
                    if article.get_publisher_state(language) == PUBLISHER_STATE_PENDING:
                        path = article.get_absolute_url(language, fallback=True)
                    else:
                        public_article = Article.objects.get(publisher_public=article.pk)
                        path = "%s?%s" % (
                            public_article.get_absolute_url(language, fallback=True),
                            get_cms_setting("CMS_TOOLBAR_URL__EDIT_OFF"),
                        )
                else:
                    path = "%s?%s" % (referrer, get_cms_setting("CMS_TOOLBAR_URL__EDIT_OFF"))
            else:
                path = "/?%s" % get_cms_setting("CMS_TOOLBAR_URL__EDIT_OFF")

        return HttpResponseRedirect(path)

    @require_POST
    @transaction.atomic
    def unpublish(self, request, article_id, language):
        """
        Publish or unpublish a language of a article
        """
        article = get_object_or_404(self.model, pk=article_id)
        if not article.has_publish_permission(request):
            return HttpResponseForbidden(_("You do not have permission to unpublish this article"))
        if not article.publisher_public_id:
            return HttpResponseForbidden(_("This article was never published"))
        try:
            article.unpublish(language)
            message = _('The %(language)s article "%(article)s" was successfully unpublished') % {
                "language": get_language_object(language)["name"],
                "article": article,
            }
            messages.info(request, message)
            LogEntry.objects.log_action(
                user_id=request.user.id,
                content_type_id=ContentType.objects.get_for_model(Article).pk,
                object_id=article_id,
                object_repr=article.get_title(),
                action_flag=CHANGE,
                change_message=message,
            )
        except RuntimeError:
            exc = sys.exc_info()[1]
            messages.error(request, exc.message)
        except ValidationError:
            exc = sys.exc_info()[1]
            messages.error(request, exc.message)
        path = admin_reverse("cms_articles_article_changelist")
        if request.GET.get("redirect_language"):
            path = "%s?language=%s&article_id=%s" % (
                path,
                request.GET.get("redirect_language"),
                request.GET.get("redirect_article_id"),
            )
        return HttpResponseRedirect(path)

    def delete_translation(self, request, object_id, extra_context=None):
        if "language" in request.GET:
            language = request.GET["language"]
        else:
            language = get_language_from_request(request)

        opts = Article._meta
        titleopts = Title._meta
        app_label = titleopts.app_label
        pluginopts = CMSPlugin._meta

        try:
            obj = self.get_queryset(request).get(pk=unquote(object_id))
        except self.model.DoesNotExist:
            # Don't raise Http404 just yet, because we haven't checked
            # permissions yet. We don't want an unauthenticated user to be able
            # to determine whether a given object exists.
            obj = None

        if not self.has_delete_permission(request, obj):
            return HttpResponseForbidden(str(_("You do not have permission to change this article")))

        if obj is None:
            raise Http404(
                _("%(name)s object with primary key %(key)r does not exist.")
                % {"name": force_str(opts.verbose_name), "key": escape(object_id)}
            )

        if not len(list(obj.get_languages())) > 1:
            raise Http404(_("There only exists one translation for this article"))

        titleobj = get_object_or_404(Title, article__id=object_id, language=language)
        saved_plugins = CMSPlugin.objects.filter(placeholder__article__id=object_id, language=language)

        using = router.db_for_read(self.model)
        kwargs = {"admin_site": self.admin_site, "user": request.user, "using": using}

        deleted_objects, __, perms_needed = get_deleted_objects([titleobj], titleopts, **kwargs)[:3]
        to_delete_plugins, __, perms_needed_plugins = get_deleted_objects(saved_plugins, pluginopts, **kwargs)[:3]

        deleted_objects.append(to_delete_plugins)
        perms_needed = set(list(perms_needed) + list(perms_needed_plugins))

        if request.method == "POST":
            if perms_needed:
                raise PermissionDenied

            message = _("Title and plugins with language %(language)s was deleted") % {
                "language": force_str(get_language_object(language)["name"])
            }
            self.log_change(request, titleobj, message)
            messages.info(request, message)

            titleobj.delete()
            for p in saved_plugins:
                p.delete()

            public = obj.publisher_public
            if public:
                public.save()

            if not self.has_change_permission(request, None):
                return HttpResponseRedirect(admin_reverse("index"))
            return HttpResponseRedirect(admin_reverse("cms_articles_article_changelist"))

        context = {
            "title": _("Are you sure?"),
            "object_name": force_str(titleopts.verbose_name),
            "object": titleobj,
            "deleted_objects": deleted_objects,
            "perms_lacking": perms_needed,
            "opts": opts,
            "root_path": admin_reverse("index"),
            "app_label": app_label,
        }
        context.update(extra_context or {})
        request.current_app = self.admin_site.name
        return render(
            request,
            self.delete_confirmation_template
            or [
                "admin/%s/%s/delete_confirmation.html" % (app_label, titleopts.object_name.lower()),
                "admin/%s/delete_confirmation.html" % app_label,
                "admin/delete_confirmation.html",
            ],
            context,
        )

    def preview_article(self, request, article_id, language):
        """Redirecting preview function based on draft_id"""
        article = get_object_or_404(self.model, id=article_id)
        attrs = "?%s" % get_cms_setting("CMS_TOOLBAR_URL__EDIT_ON")
        attrs += "&language=" + language
        with force_language(language):
            url = article.get_absolute_url(language) + attrs
        return HttpResponseRedirect(url)


admin.site.register(Article, ArticleAdmin)
