from json import loads

from cms.api import create_page
from cms.models import Page
from cms.models.fields import PageField
from django.core.files import File as DjangoFile
from django.core.files.temp import NamedTemporaryFile
from django.db import models
from django.utils.encoding import force_bytes
from django.utils.functional import cached_property
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from filer.fields.folder import FilerFolderField
from filer.models import File, Folder

from cms_articles.api import add_content, create_article, publish_article
from cms_articles.conf import settings

from .utils import create_redirect

try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen


class Author(models.Model):
    author_id = models.IntegerField(_("author id"), unique=True)
    login = models.CharField(_("login name"), max_length=255)
    email = models.EmailField(_("email"), blank=True, null=True)
    first_name = models.CharField(_("first name"), max_length=255, blank=True, null=True)
    last_name = models.CharField(_("last name"), max_length=255, blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("user"),
        related_name="+",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    def __str__(self):
        return "{}".format(self.login)

    class Meta:
        verbose_name = _("author")
        verbose_name_plural = _("authors")


class Category(models.Model):
    term_id = models.IntegerField(_("term id"), unique=True)
    name = models.CharField(_("name"), max_length=255)
    slug = models.SlugField(_("slug"))
    parent = models.CharField(_("parent slug"), max_length=255, blank=True, null=True)
    cached_name = models.CharField(_("name"), max_length=512, blank=True, null=True)
    category = models.ForeignKey(
        "cms_articles.Category",
        verbose_name=_("articles category"),
        related_name="+",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    def __str__(self):
        try:
            parent = Category.objects.get(slug=self.parent)
        except Category.DoesNotExist:
            parent = None
        if parent:
            name = "{} / {}".format(parent.name, self.name)
        else:
            name = "{}".format(self.name)
        if name != self.cached_name:
            self.cached_name = name
            self.save()
        return name

    class Meta:
        verbose_name = _("category")
        verbose_name_plural = _("categories")


class Item(models.Model):
    title = models.TextField(_("title"), default="")
    link = models.CharField(_("link"), max_length=255)
    pub_date = models.DateTimeField(_("publication date"))
    created_by = models.ForeignKey(Author, verbose_name=_("created by"))
    guid = models.CharField(_("url"), max_length=255)
    description = models.TextField(_("description"))
    content = models.TextField(_("content"))
    excerpt = models.TextField(_("excerpt"))
    post_id = models.IntegerField(_("post id"), unique=True)
    post_date = models.DateTimeField(_("post date"))
    post_name = models.CharField(_("post name"), max_length=255)
    status = models.CharField(_("status"), max_length=20)
    post_parent = models.IntegerField(_("parent post id"))
    post_type = models.CharField(_("type"), max_length=20)
    categories = models.ManyToManyField(Category, _("categories"), blank=True)
    postmeta = models.TextField(_("metadata"))
    article = models.OneToOneField(
        "cms_articles.Article",
        verbose_name=_("imported article"),
        related_name="+",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    page = models.OneToOneField(
        "cms.Page", verbose_name=_("imported page"), related_name="+", on_delete=models.SET_NULL, blank=True, null=True
    )
    file = models.OneToOneField(
        File, verbose_name=_("imported file"), related_name="+", on_delete=models.SET_NULL, blank=True, null=True
    )
    folder = models.ForeignKey(
        Folder, verbose_name=_("attachments folder"), related_name="+", on_delete=models.SET_NULL, blank=True, null=True
    )

    def __str__(self):
        return "{}".format(self.title)

    class Meta:
        verbose_name = _("item")
        verbose_name_plural = _("items")

    @property
    def children(self):
        return Item.objects.filter(post_parent=self.post_id)

    @cached_property
    def parent(self):
        if self.post_parent:
            try:
                return Item.objects.get(post_id=self.post_parent)
            except Item.DoesNotExist:
                pass
        return None

    @cached_property
    def meta(self):
        return loads(self.postmeta)

    def cms_import(self, options):
        obj = None
        if self.post_type == "post":
            obj = self.get_or_import_article(options)
        elif self.post_type == "page":
            obj = self.get_or_import_page(options)
        elif self.post_type == "attachment":
            obj = self.get_or_import_file(options)
        # also import children
        for child in self.children.all():
            child.cms_import(options)
        return obj

    def get_or_import_article(self, options):
        assert self.post_type == "post"
        if self.article:
            return self.article
        # import thumbnail
        image = None
        if "_thumbnail_id" in self.meta:
            image_item = Item.objects.get(post_id=int(self.meta["_thumbnail_id"]))
            image = image_item.get_or_import_file(options)
        self.article = create_article(
            tree=options.article_tree,
            template=options.article_template,
            title=self.title,
            language=options.language,
            description=self.excerpt,
            created_by=self.created_by.user or self.created_by.login,
            image=image,
            publicationdate=self.pub_date,
            categories=[c.category for c in self.categories.exclude(category=None)],
        )
        self.article.creation_date = self.post_date
        self.article.save()
        content = "\n".join("<p>{}</p>".format(p) for p in self.content.split("\n\n"))
        add_content(self.article, language=options.language, slot=options.article_slot, content=content)
        if options.article_publish:
            self.article = publish_article(
                article=self.article,
                language=options.language,
                changed_by=self.created_by.user or self.created_by.login,
            )
            public = self.article.get_public_object()
            public.creation_date = self.pub_date
            public.save()
        if options.article_redirects:
            create_redirect(self.link, self.article.get_absolute_url())
        self.save()
        return self.article

    def get_or_import_page(self, options):
        assert self.post_type == "page"
        if self.page:
            return self.page
        # import parent page first
        if self.parent:
            parent = self.parent.get_or_import_page(options)
        else:
            parent = options.page_root
        # get valid slug
        slug = self.post_name or slugify(self.title)
        assert slug
        # handle existing page
        self.page = Page.objects.filter(parent=parent, title_set__slug=slug).first()
        if self.page:
            self.save()
            return self.page
        # create new page
        self.page = create_page(
            template=options.page_template,
            language=options.language,
            title=self.title,
            slug=slug,
            meta_description=None,
            created_by=self.created_by.user or self.created_by.login,
            parent=parent,
            publication_date=self.pub_date,
        )
        self.page.creation_date = self.post_date
        self.page.save()
        content = "\n".join("<p>{}</p>".format(p) for p in self.content.split("\n\n"))
        add_content(self.page, language=options.language, slot=options.page_slot, content=content)
        if options.page_publish:
            self.page.publish(options.language)
            public = self.page.get_public_object()
            public.creation_date = self.pub_date
            public.save()
        if options.page_redirects:
            create_redirect(self.link, self.page.get_absolute_url())
        self.save()
        return self.page

    def get_or_import_file(self, options):
        from filer.management.commands.import_files import FileImporter

        assert self.post_type == "attachment"
        if self.file:
            return self.file
        # download content into deleted temp_file
        temp_file = NamedTemporaryFile(delete=True)
        temp_file.write(urlopen(force_bytes(self.guid)).read())
        temp_file.flush()
        # create DjangoFile object
        django_file = DjangoFile(temp_file, name=self.guid.split("/")[-1])
        # choose folder
        if self.parent:
            folder = self.parent.get_or_create_folder(options)
        else:
            folder = options.file_folder
        # import file
        self.file = FileImporter().import_file(file_obj=django_file, folder=folder)
        # set date and owner
        self.file.created_at = self.pub_date
        self.file.owner = self.created_by.user
        self.file.save()
        # return imported file
        self.save()
        return self.file

    def get_or_create_folder(self, options):
        assert self.children.count() > 0
        if self.folder:
            return self.folder
        # do not create sub-folders for slides
        if self.post_type == "slide":
            self.folder = options.slide_folder
            self.save()
            return self.folder
        parent = options.get_folder(self.post_type)
        self.folder, new = Folder.objects.get_or_create(parent=parent, name=self.title)
        if new:
            self.folder.created_at = self.post_date
            self.folder.owner = self.created_by.user
            self.folder.save()
        self.save()
        return self.folder


class Options(models.Model):
    name = models.CharField(_("name"), max_length=255, unique=True)

    # global options
    language = models.CharField(_("language"), max_length=15, help_text=_("The language of the content fields."))

    # article specific options
    article_tree = models.ForeignKey(
        Page,
        verbose_name=_("tree"),
        related_name="+",
        help_text=_("All posts will be imported as articles in this tree."),
        limit_choices_to={
            "publisher_is_draft": False,
            "application_urls": "CMSArticlesApp",
            "node__site_id": settings.SITE_ID,
        },
    )
    article_template = models.CharField(
        _("template"),
        max_length=100,
        choices=settings.CMS_ARTICLES_TEMPLATES,
        default=settings.CMS_ARTICLES_TEMPLATES[0][0],
    )
    article_slot = models.CharField(
        _("slot"),
        max_length=255,
        default=settings.CMS_ARTICLES_SLOT,
        help_text=_("The name of placeholder used to create content plugins in."),
    )
    article_folder = FilerFolderField(
        verbose_name=_("attachments folder"),
        related_name="+",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text=_("Select folder for articles. Subfolder will be created for each article with attachments."),
    )
    article_redirects = models.BooleanField(
        _("create redirects"),
        default=True,
        help_text=_("Create django redirects for each article from the old path to the new imported path"),
    )
    article_publish = models.BooleanField(_("publish"), default=False, help_text=_("Publish imported articles."))

    # page specific options
    page_root = PageField(
        verbose_name=_("root"),
        related_name="+",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text=_("All pages will be imported as sub-pages of this page."),
    )
    page_template = models.CharField(
        _("template"), max_length=100, choices=Page.template_choices, default=Page.TEMPLATE_DEFAULT
    )
    page_slot = models.CharField(
        _("slot"),
        max_length=255,
        default="content",
        help_text=_("The name of placeholder used to create content plugins in."),
    )
    page_folder = FilerFolderField(
        verbose_name=_("attachments folder"),
        related_name="+",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text=_("Select folder for pages. Subfolder will be created for each page with attachments."),
    )
    page_redirects = models.BooleanField(
        _("create redirects"),
        default=True,
        help_text=_("Create django redirects for each page from the old path to the new imported path"),
    )
    page_publish = models.BooleanField(_("publish"), default=False, help_text=_("Publish imported pages."))

    # file specific options
    gallery_folder = FilerFolderField(
        verbose_name=_("folder"),
        related_name="+",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text=_("Select folder for galleries. Subfolder will be created for each gallery."),
    )

    # file specific options
    slide_folder = FilerFolderField(
        verbose_name=_("folder"),
        related_name="+",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text=_("Select folder for slides."),
    )

    # file specific options
    file_folder = FilerFolderField(
        verbose_name=_("folder"),
        related_name="+",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text=_("Select folder for other attachments."),
    )

    def __str__(self):
        return "{}".format(self.name)

    class Meta:
        verbose_name = _("options")
        verbose_name_plural = _("options")

    @cached_property
    def folders(self):
        return {
            "post": self.article_folder,
            "page": self.page_folder,
            "gallery": self.gallery_folder,
            "slide": self.slide_folder,
        }

    def get_folder(self, post_type):
        return self.folders.get(post_type, self.file_folder)
