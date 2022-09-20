import logging
from json import dumps
from xml.etree.ElementTree import ElementTree

from cms.utils.compat.dj import is_installed
from dateutil.parser import parse
from django.utils.timezone import make_aware

from ..conf import settings

if is_installed("django.contrib.redirects"):
    from django.contrib.redirects.models import Redirect

    try:
        from urllib.parse import urlparse
    except ImportError:
        from urlparse import urlparse

    def create_redirect(old_url, new_url):
        old_path = urlparse(old_url).path
        new_path = urlparse(new_url).path
        if old_path != "/" and new_path != old_path:
            redirect = Redirect.objects.get_or_create(
                site_id=settings.SITE_ID,
                old_path=urlparse(old_path).path,
            )[0]
            redirect.new_path = new_path
            redirect.save()
            return redirect

else:

    def create_redirect(old_url, new_url):
        pass


def import_wordpress(xmlfile):
    from .models import Author, Category, Item

    try:
        rss = ElementTree(file=xmlfile).getroot()
        assert rss.tag == "rss"
    except Exception as e:
        raise Exception("Failed to parse file {}: {}".format(xmlfile, e))

    imported_items = 0
    errors = []

    # import authors
    authors = {}
    for author in rss.findall("*/{http://wordpress.org/export/1.2/}author"):
        author_id = "unknown"
        try:
            # first of all try to parse author_id for use in potential error messages
            author_id = int(author.find("{http://wordpress.org/export/1.2/}author_id").text)
            login = author.find("{http://wordpress.org/export/1.2/}author_login").text
            email = author.find("{http://wordpress.org/export/1.2/}author_email").text
            first_name = author.find("{http://wordpress.org/export/1.2/}author_first_name").text
            last_name = author.find("{http://wordpress.org/export/1.2/}author_last_name").text
        except Exception as e:
            error = "Failed to parse author with author_id {}: {}".format(author_id, e)
            logging.warning(error)
            errors.append(error)
            continue
        try:
            author = Author.objects.get_or_create(
                author_id=author_id,
                login=login,
                email=email,
                first_name=first_name,
                last_name=last_name,
            )[0]
        except Exception as e:
            error = "Failed to save author with author_id {}: {}".format(author_id, e)
            logging.warning(error)
            errors.append(error)
            continue
        authors[login] = author

    # import categories
    categories = {}
    for category in rss.findall("*/{http://wordpress.org/export/1.2/}category"):
        term_id = "unknown"
        try:
            # first of all try to parse term_id for use in potential error messages
            term_id = int(category.find("{http://wordpress.org/export/1.2/}term_id").text)
            name = category.find("{http://wordpress.org/export/1.2/}cat_name").text
            slug = category.find("{http://wordpress.org/export/1.2/}category_nicename").text
            parent = category.find("{http://wordpress.org/export/1.2/}category_parent").text
        except Exception as e:
            error = "Failed to parse category with term_id {}: {}".format(term_id, e)
            logging.warning(error)
            errors.append(error)
            raise
            continue
        try:
            category = Category.objects.get_or_create(
                term_id=term_id,
                name=name,
                slug=slug,
                parent=parent,
            )[0]
        except Exception as e:
            error = "Failed to save category with term_id {}: {}".format(term_id, e)
            logging.warning(error)
            errors.append(error)
            continue
        categories[slug] = category

    # import items
    for item in rss.findall("*/item"):
        post_id = "unknown"
        try:
            # first of all try to parse post_id for use in potential error messages
            post_id = int(item.find("{http://wordpress.org/export/1.2/}post_id").text)
            title = item.find("title").text or ""
            link = item.find("link").text or ""
            pub_date = parse(item.find("pubDate").text)
            created_by = item.find("{http://purl.org/dc/elements/1.1/}creator").text
            guid = item.find("guid").text
            description = item.find("description").text or ""
            content = item.find("{http://purl.org/rss/1.0/modules/content/}encoded").text or ""
            excerpt = item.find("{http://wordpress.org/export/1.2/excerpt/}encoded").text or ""
            post_date = make_aware(parse(item.find("{http://wordpress.org/export/1.2/}post_date").text))
            post_name = item.find("{http://wordpress.org/export/1.2/}post_name").text or ""
            status = item.find("{http://wordpress.org/export/1.2/}status").text
            post_parent = int(item.find("{http://wordpress.org/export/1.2/}post_parent").text)
            post_type = item.find("{http://wordpress.org/export/1.2/}post_type").text
            postmeta = dumps(
                dict(
                    (
                        pm.find("{http://wordpress.org/export/1.2/}meta_key").text,
                        pm.find("{http://wordpress.org/export/1.2/}meta_value").text,
                    )
                    for pm in item.findall("{http://wordpress.org/export/1.2/}postmeta")
                )
            )
            cats = [
                categories[cat.attrib["nicename"]]
                for cat in item.findall("category")
                if cat.attrib["nicename"] in categories
            ]
        except Exception as e:
            error = "Failed to parse item with post_id {}: {}".format(post_id, e)
            logging.warning(error)
            errors.append(error)
            continue
        try:
            item = Item.objects.create(
                title=title,
                link=link,
                pub_date=pub_date,
                created_by=authors[created_by],
                guid=guid,
                description=description,
                content=content,
                excerpt=excerpt,
                post_id=post_id,
                post_date=post_date,
                post_name=post_name,
                status=status,
                post_parent=post_parent,
                post_type=post_type,
                postmeta=postmeta,
            )
            item.categories = cats
        except Exception as e:
            error = "Failed to save item with post_id {}: {}".format(post_id, e)
            logging.warning(error)
            errors.append(error)
            continue
        imported_items += 1
    return {
        "authors": len(authors),
        "categories": len(categories),
        "items": imported_items,
        "errors": errors,
    }
