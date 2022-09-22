import pytest
from cms.api import create_page

from cms_articles.api import create_article


@pytest.mark.django_db
def test_create_article() -> None:
    page = create_page(
        title="News",
        template="default.html",
        language="en",
        apphook="CMSArticlesApp",
        apphook_namespace="news",
        published=True,
    )
    create_article(
        tree=page,
        title="Article",
        template="cms_articles/default.html",
        language="en",
        published=True,
    )
