import locale
import xmlrpclib

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Sum
from django.template.defaultfilters import slugify
from django.utils import simplejson as json
from django.utils.datastructures import MultiValueDict
from django.utils.translation import ugettext_lazy as _

from package.models import Package, Version
from package.signals import signal_fetch_latest_metadata
from package.utils import get_version

locale.setlocale(locale.LC_ALL, '')

def handle_fetch_metada_signal(**kwargs):
    sending_package = kwargs.get('sender')
    try:
        pypackage = PyPackage.objects.get(packaginator_package=sending_package)
    except PyPackage.DoesNotExist:
        return False
    pypackage.fetch_releases()

signal_fetch_latest_metadata.connect(handle_fetch_metada_signal)

class PypiVersion(object):
    def __init__(self, release_data):
        self.__dict__.update(release_data)

class PyPackageManager(models.Manager):
    def create_with_package(self, *args, **kwargs):
        package, created = Package.objects.get_or_create(
                title=kwargs['name'],
                slug=slugify(kwargs['name']))
        kwargs['packaginator_package'] = package
        # TODO do we fetch releases and try to scrape repo URLs?
        return super(PyPackageManager, self).create(*args, **kwargs)

class PyPackage(models.Model):
    """
    A representation of a python package on pypi or similar.
    Strongly coupled to packaginator project.

    PyPI interface (see http://wiki.python.org/moin/PyPiXmlRpc)
    """
    packaginator_package = models.OneToOneField(Package, related_name='pypi')
    name = models.CharField(max_length=255, unique=True, editable=False)
    index_api_url = models.URLField(verify_exists=False, max_length=200,
            default="http://pypi.python.org/pypi/")

    objects = PyPackageManager()
    def __unicode__(self):
        return self.name

    @property
    def latest(self):
        try:
            return self.releases.latest()
        except PyRelease.DoesNotExist:
            return None

    @property
    def downloads(self):
        return self.releases.filter(hidden=False).aggregate(Sum('downloads'))['downloads__sum'] or 0

    def save(self, *args, **kwargs):
        if not self.name:
            self.name = self.packaginator_package.title
        if not self.id:
            # first save, make sure we have releases
            proxy = xmlrpclib.Server(self.index_api_url)
            releases = proxy.package_releases(self.name)
            if not releases:
                raise ValueError(
                        "No package named %s could be found indexed at %s" %
                        (self.name, self.index_api_url))

        # TODO do we fetch releases on save?
        return super(PyPackage, self).save(*args, **kwargs)

    def fetch_releases(self, include_hidden=True):

        package_name = self.name
        proxy = xmlrpclib.Server(self.index_api_url)
        releases = proxy.package_releases(package_name, include_hidden)

        if not releases:
            # TODO is this an error?
            pass

        for version in releases:
            try:
                this_release = self.releases.get(version=version)
                # if we have a release already - skip it
                continue
            except PyRelease.DoesNotExist:
                # if we don't have a release, create it now
                pass
            release_data = PypiVersion(proxy.release_data
                    (package_name, version))
            release_data.hidden = release_data._pypi_hidden
            release_data.downloads = 0
            for download in proxy.release_urls(package_name, version):
                release_data.downloads +=  download["downloads"]
            if release_data.license == None or 'UNKNOWN' == release_data.license.upper():
                for classifier in release_data.classifiers:
                    if classifier.startswith('License'):
                        # Do it this way to cover people not quite following the spec
                        # at http://docs.python.org/distutils/setupscript.html#additional-meta-data
                        release_data.license = classifier.replace('License ::', '')
                        release_data.license = release_data.license.replace('OSI Approved :: ', '')
                        break

            if release_data.license and len(release_data.license) > 100:
                release_data.license = "Other (see http://pypi.python.org/pypi/%s)" % package_name

            packaginator_version, created = Version.objects.get_or_create(
                    package=self.packaginator_package,
                    number=version)
            # TODO hidden and downloads will probably come off this model
            # packaginator_version.downloads = release_data.downloads
            # packaginator_version.hidden = release_data.hidden
            packaginator_version.license = release_data.license
            packaginator_version.save()


            this_release = self.releases.create(
                packaginator_version = packaginator_version,
                hidden = release_data.hidden,
                )
            for attr in release_data.__dict__:
                if attr == 'classifiers':
                    this_release.pypi_classifiers ='\n'.join(getattr(release_data, attr))
                    continue

                if hasattr(this_release, attr):
                    val = getattr(release_data, attr)
                    if val:
                        setattr(this_release, attr, val)
            this_release.save()

class ReleaseManager(models.Manager):

    def by_version(self):
        qs = self.get_query_set()
        return sorted(qs,key=lambda r: get_version(r.version))

    def latest(self):
        by_version = self.by_version()
        if by_version:
            return by_version[-1]
        else:
            return None

class PyRelease(models.Model):
    author = models.CharField(max_length=128, blank=True)
    author_email = models.EmailField(max_length=75, blank=True)
    # classifiers is reserved word
    pypi_classifiers = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    description = models.TextField(blank=True)
    download_url = models.URLField(verify_exists=False, max_length=200, blank=True)
    downloads = models.IntegerField(_("downloads"), default=0)
    hidden = models.BooleanField(default=False)
    home_page = models.URLField(verify_exists=False, max_length=200, blank=True)
    keywords = models.TextField(blank=True)
    license = models.CharField(max_length=128, blank=True)
    maintainer = models.CharField(max_length=128)
    maintainer_email = models.EmailField(max_length=75, blank=True)
    metadata_version = models.CharField(max_length=64, default='1.0')
    # TODO is name for a release ever different then on package?
    # name = models.CharField(max_length=255, blank=True)
    packaginator_version = models.OneToOneField(Version, related_name = 'pypi')
    platform = models.CharField(max_length=128, blank=True)
    pypackage = models.ForeignKey(PyPackage, related_name="releases", editable=False)
    release_url = models.URLField(verify_exists=False, max_length=200, blank=True)
    requires_python = models.CharField(max_length=20, blank=True)
    stable_version = models.CharField(max_length=128, blank=True)
    summary = models.TextField(blank=True)
    version = models.CharField(max_length=128, editable=False)

    objects = ReleaseManager()

    # TODO publish date from release_urls upload time?

    class Meta:
        verbose_name = _(u"release")
        verbose_name_plural = _(u"releases")
        unique_together = ("pypackage", "version")
        get_latest_by = 'created'
        ordering = ['-created']

    def __unicode__(self):
        return self.release_name

    @property
    def release_name(self):
        return u"%s-%s" % (self.pypackage.name, self.version)

    # @property
    # def summary(self):
        # return self.package_info.get('summary', u'')

    # @property
    # def description(self):
        # return self.package_info.get('description', u'')

    @property
    def classifiers(self):
        return self.package_info.getlist('classifier')

    # @models.permalink
    # def get_absolute_url(self):
        # return ('djangopypi-release', (), {'package': self.package.name,
                                           # 'version': self.version})


