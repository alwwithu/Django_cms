# -*- coding: utf-8 -*-
from django.conf.urls import url
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.utils.translation import gettext_lazy as _

from .forms import CMSImportForm, XMLImportForm
from .models import Author, Category, Item, Options

User = get_user_model()


class AuthorAdmin(admin.ModelAdmin):
    search_fields = ["login", "email", "first_name", "last_name"]
    list_display = ["login", "email", "first_name", "last_name", "user"]
    list_editable = ["user"]
    actions = ["create_users", "find_users"]

    def has_add_permission(self, request):
        return False

    def create_users(self, request, queryset):
        for author in queryset.all():
            if author.user:
                continue
            try:
                author.user = User.objects.create(
                    username=author.login,
                    email=author.email,
                    first_name=author.first_name or "",
                    last_name=author.last_name or "",
                )
                author.save()
            except Exception as e:
                self.message_user(request, _("Failed to create user {}: {}").format(author.login, e), messages.ERROR)
            else:
                self.message_user(request, _("Successfully created user {}").format(author.login), messages.SUCCESS)

    create_users.short_description = _("Create users for selected authors")

    def find_users(self, request, queryset):
        for author in queryset.all():
            if author.user:
                continue

            try:
                author.user = User.objects.get(username=author.login)
            except User.DoesNotExist:
                pass

            if not author.user:
                author.user = User.objects.filter(email=author.email).first()

            if not author.user:
                author.user = User.objects.filter(first_name=author.first_name, last_name=author.last_name).first()

            if author.user:
                author.save()
                self.message_user(
                    request, _("Successfully found user {} for author").format(author.user, author), messages.SUCCESS
                )
            else:
                self.message_user(request, _("Failed to find user for author {}").format(author), messages.ERROR)

    find_users.short_description = _("Find users for selected authors")


admin.site.register(Author, AuthorAdmin)


class CategoryAdmin(admin.ModelAdmin):
    search_fields = ["=term_id", "name", "slug"]
    list_display = ["slug", "cached_name", "category"]
    list_editable = ["category"]
    ordering = ["cached_name"]

    def has_add_permission(self, request):
        return False


admin.site.register(Category, CategoryAdmin)


class ItemAdmin(admin.ModelAdmin):
    search_fields = ["=post_id", "=post_parent", "categories__name", "title"]
    list_filter = ["post_type", "status", "categories"]
    list_display = [
        "post_id",
        "parent_link",
        "children_link",
        "title_link",
        "post_type",
        "post_date",
        "status",
        "imported_link",
    ]
    actions = ["cms_import"]

    def get_urls(self):
        return [
            url(
                r"^import/$",
                self.import_item,
                name="{}_{}_import_item".format(
                    self.model._meta.app_label,
                    self.model._meta.model_name,
                ),
            ),
        ] + super().get_urls()

    def save_model(self, request, obj, form, change):
        pass

    def save_related(self, request, form, formsets, change):
        pass

    def log_addition(self, request, object, message):
        pass

    def response_add(self, request, obj, post_url_continue=None):
        for error in obj["errors"]:
            self.message_user(request, error, messages.ERROR)
        for msg in (
            _("Successfullty imported {} authors").format(obj["authors"]),
            _("Successfullty imported {} categories").format(obj["categories"]),
            _("Successfullty imported {} items").format(obj["items"]),
        ):
            self.message_user(request, msg, messages.SUCCESS)
        return self.response_post_save_add(request, obj)

    def get_form(self, request, obj=None, **kwargs):
        if not obj:
            kwargs["form"] = XMLImportForm
        return super().get_form(request, obj, **kwargs)

    def parent_link(self, obj):
        if obj.post_parent:
            return '<a href="{url}">{label}</a>'.format(
                url=reverse(
                    "admin:{}_{}_changelist".format(
                        Item._meta.app_label,
                        Item._meta.model_name,
                    )
                )
                + "?post_id__exact={}".format(obj.post_parent),
                label=obj.post_parent,
            )
        else:
            return ""

    parent_link.short_description = _("post parent")
    parent_link.admin_order_field = "post_parent"
    parent_link.allow_tags = True

    def children_link(self, obj):
        count = obj.children.count()
        if count:
            return '<a href="{url}">{label}</a>'.format(
                url=reverse(
                    "admin:{}_{}_changelist".format(
                        Item._meta.app_label,
                        Item._meta.model_name,
                    )
                )
                + "?post_parent__exact={}".format(obj.post_id),
                label=count,
            )
        else:
            return ""

    children_link.short_description = _("post children")
    children_link.allow_tags = True

    def title_link(self, obj):
        return '<a href="{url}" title="{url}" target="_blank">{title}</a>'.format(
            url=obj.guid,
            title=obj.title,
        )

    title_link.short_description = _("title")
    title_link.admin_order_field = "title"
    title_link.allow_tags = True

    def imported_link(self, obj):
        url = None
        if obj.article or obj.page:
            url = (obj.article or obj.page).get_absolute_url()
        elif obj.file:
            url = obj.file.file.url
        elif obj.folder:
            url = obj.folder.get_admin_directory_listing_url_path()
        if url:
            return '<a href="{url}" target="_blank">{obj}</a>'.format(
                obj=obj.article or obj.page or obj.file or obj.folder,
                url=url,
            )
        else:
            return ""

    imported_link.short_description = _("imported as")
    imported_link.allow_tags = True

    def cms_import(self, request, queryset):
        if request.POST.get("post", "no") == "yes":
            form = CMSImportForm(request.POST)
            if form.is_valid():
                return render_to_response(
                    "cms_articles/import_wordpress/cms_import.html",
                    {
                        "title": _("Running import"),
                        "items": queryset,
                        "options": form.cleaned_data["options"],
                        "media": self.media,
                        "opts": self.model._meta,
                    },
                    context_instance=RequestContext(request),
                )
        else:
            form = CMSImportForm()
        return render_to_response(
            "cms_articles/import_wordpress/form.html",
            {
                "title": _("Select predefined import options"),
                "queryset": queryset,
                "opts": self.model._meta,
                "form": form,
                "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            },
            context_instance=RequestContext(request),
        )

    cms_import.short_description = _("Import selected items into CMS")

    @transaction.atomic
    def import_item(self, request):
        try:
            item_id = int(request.GET["item_id"])
            options_id = int(request.GET["options_id"])
        except (KeyError, ValueError):
            return HttpResponseBadRequest()
        item = get_object_or_404(Item, id=item_id)
        options = get_object_or_404(Options, id=options_id)
        item.cms_import(options)
        return HttpResponse("0", content_type="text/json")


admin.site.register(Item, ItemAdmin)


class OptionsAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    save_as = True

    fieldsets = [
        (None, {"fields": ["name"]}),
        (_("Global options"), {"fields": ["language"]}),
        (
            _("Article specific options"),
            {
                "fields": [
                    "article_tree",
                    "article_template",
                    "article_slot",
                    "article_folder",
                    "article_redirects",
                    "article_publish",
                ]
            },
        ),
        (
            _("Page specific options"),
            {"fields": ["page_root", "page_template", "page_slot", "page_folder", "page_redirects", "page_publish"]},
        ),
        (_("File specific options"), {"fields": ["file_folder"]}),
        (_("Gallery specific options"), {"fields": ["gallery_folder"]}),
        (_("Slide specific options"), {"fields": ["slide_folder"]}),
    ]


admin.site.register(Options, OptionsAdmin)
