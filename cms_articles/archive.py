import calendar
from datetime import date

from django.utils.functional import cached_property

from .conf import settings


class Archive:
    def __init__(self, articles, request):
        self.articles = articles
        self.request = request
        self.year = self.month = self.day = None
        try:
            self.year = int(request.GET[settings.CMS_ARTICLES_YEAR_FIELD])
            self.month = int(request.GET[settings.CMS_ARTICLES_MONTH_FIELD])
            self.day = int(request.GET[settings.CMS_ARTICLES_DAY_FIELD])
        except (KeyError, ValueError):
            pass

    def filter_articles(self):
        articles = self.articles
        if self.year:
            articles = articles.filter(order_date__year=self.year)
            if self.month:
                articles = articles.filter(order_date__month=self.month)
                if self.day:
                    articles = articles.filter(order_date__day=self.day)
        return articles

    @cached_property
    def last(self):
        try:
            return self.articles.last().order_date
        except AttributeError:
            return date.today()

    def years(self):
        for year in range(date.today().year, self.last.year - 1, -1):
            yield YearArchive(year, self)

    @cached_property
    def date(self):
        if self.year:
            return date(self.year, self.month or 1, self.day or 1)
        else:
            return None


class YearArchive:
    def __init__(self, year, archive):
        self.year = year
        self.archive = archive
        self.articles = archive.articles.filter(order_date__year=year)
        self.active = archive.year == year

    def months(self):
        if self.year == date.today().year:
            first = date.today().month
        else:
            first = 12
        if self.year == self.archive.last.year:
            last = self.archive.last.month
        else:
            last = 1
        for month in range(first, last, -1):
            yield MonthArchive(month, self)

    @cached_property
    def date(self):
        return date(self.year, 1, 1)

    @cached_property
    def url(self):
        return "{path}?{y}={year}".format(
            path=self.archive.request.path,
            y=settings.CMS_ARTICLES_YEAR_FIELD,
            year=self.year,
        )


class MonthArchive:
    def __init__(self, month, year_archive):
        self.month = month
        self.year_archive = year_archive
        self.articles = year_archive.articles.filter(order_date__month=month)
        self.active = year_archive.archive.month == month

    def days(self):
        if self.year == date.today().year and self.month == date.today().month:
            first = date.today().day
        else:
            first = calendar.monthrange(self.year_archive.year, self.month)[1]
        if self.year == self.year_archive.archive.last.year and self.month == self.year_archive.archive.last.month:
            last = self.year_archive.archive.last.day
        else:
            last = 1
        for day in range(first, last, -1):
            yield DayArchive(day, self)

    @cached_property
    def date(self):
        return date(self.year_archive.year, self.month, 1)

    @cached_property
    def url(self):
        return "{path}?{y}={year}&{m}={month}".format(
            path=self.year_archive.archive.request.path,
            y=settings.CMS_ARTICLES_YEAR_FIELD,
            m=settings.CMS_ARTICLES_MONTH_FIELD,
            year=self.year_archive.year,
            month=self.month,
        )


class DayArchive:
    def __init__(self, day, month_archive):
        self.day = day
        self.month_archive = month_archive
        self.articles = month_archive.articles.filter(order_date__day=day)
        self.active = month_archive.year_archive.archive.day == day

    @cached_property
    def date(self):
        return date(self.month_archive.year_archive.year, self.month_archive.month, self.day)

    @cached_property
    def url(self):
        return "{path}?{y}={year}&{m}={month}&{d}={day}".format(
            path=self.month_archive.year_archive.archive.request.path,
            y=settings.CMS_ARTICLES_YEAR_FIELD,
            m=settings.CMS_ARTICLES_MONTH_FIELD,
            d=settings.CMS_ARTICLES_DAY_FIELD,
            year=self.month_archive.year_archive.year,
            month=self.month_archive.month,
            day=self.day,
        )
