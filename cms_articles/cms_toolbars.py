from cms.cms_toolbars import ADMIN_MENU_IDENTIFIER
from cms.toolbar.items import SubMenu
from cms.toolbar_base import CMSToolbar
from cms.toolbar_pool import toolbar_pool
from cms.utils.i18n import force_language
from cms.utils.urlutils import add_url_parameters, admin_reverse
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


@toolbar_pool.register
class CMSArticlesToolbar(CMSToolbar):
    def populate(self):
        # Articles item in main menu
        admin_menu = self.toolbar.get_or_create_menu(ADMIN_MENU_IDENTIFIER)
        position = admin_menu.get_alphabetical_insert_position(_("Articles"), SubMenu)
        url = reverse("admin:cms_articles_article_changelist")
        admin_menu.add_sideframe_item(_("Articles"), url=url, position=position)

        # Article menu
        article_menu = self.toolbar.get_or_create_menu("cms-articles", _("Article"))
        self.article = getattr(self.request, "current_article", None)
        if self.article:
            if self.toolbar.edit_mode_active:
                url = "{}?language={}".format(
                    admin_reverse("cms_articles_article_change", args=(self.article.pk,)), self.current_lang
                )
                article_menu.add_modal_item(_("Article Settings"), url=url)
            else:
                article_menu.add_link_item(_("Edit this article"), url="?edit")
        url = "{}?language={}".format(admin_reverse("cms_articles_article_add"), self.current_lang)
        if self.request.current_page:
            published_current_page = self.request.current_page.get_public_object()
            if published_current_page and published_current_page.application_urls == "CMSArticlesApp":
                url += "&tree={}".format(published_current_page.id)
        article_menu.add_modal_item(_("New Article"), url=url)

    def post_template_populate(self):
        if (
            self.toolbar.edit_mode_active
            and self.article
            and self.article.has_publish_permission(self.request)
            and self.article.is_dirty(self.current_lang)
        ):
            classes = ["cms-btn-action", "cms-btn-publish", "cms-btn-publish-active", "cms-publish-article"]

            title = _("Publish article now")

            params = {}
            params["redirect"] = self.request.path_info

            with force_language(self.current_lang):
                url = admin_reverse("cms_articles_article_publish_article", args=(self.article.pk, self.current_lang))

            url = add_url_parameters(url, params)

            self.toolbar.add_button(title, url=url, extra_classes=classes, side=self.toolbar.RIGHT, disabled=False)

    def request_hook(self):
        pass
