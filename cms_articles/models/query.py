from cms.models.query import PageQuerySet


class ArticleQuerySet(PageQuerySet):
    def on_site(self, site=None):
        from cms.utils import get_current_site

        if site is None:
            site = get_current_site()
        return self.filter(tree__node__site=site)
