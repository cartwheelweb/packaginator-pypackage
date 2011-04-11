import locale
import xmlrpclib

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Sum
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

class PackageInfoField(models.Field):
    """
    a basic jsonfield implementation
    """
    description = u'Python Package Information Field'
    __metaclass__ = models.SubfieldBase

    def __init__(self, *args, **kwargs):
        kwargs['editable'] = False
        super(PackageInfoField,self).__init__(*args, **kwargs)

    def to_python(self, value):
        if isinstance(value, basestring):
            if value:
                return MultiValueDict(json.loads(value))
            else:
                return MultiValueDict()
        if isinstance(value, dict):
            return MultiValueDict(value)
        if isinstance(value,MultiValueDict):
            return value
        raise ValueError('Unexpected value encountered when converting data to python')

    def get_prep_value(self, value):
        if isinstance(value,MultiValueDict):
            return json.dumps(dict(value.iterlists()))
        if isinstance(value, dict):
            return json.dumps(value)
        if isinstance(value, basestring) or value is None:
            return value

        raise ValueError('Unexpected value encountered when preparing for database')

    def get_internal_type(self):
        return 'TextField'

class PyPackage(models.Model):
    """
    A representation of a python package on pypi or similar
    strongly coupled to packaginator project
    """
    packaginator_package = models.OneToOneField(Package, related_name='pypi')
    name = models.CharField(max_length=255, unique=True, editable=False)
    index_api_url = models.URLField(verify_exists=False, max_length=200,
            default="http://pypi.python.org/pypi/")

    def __unicode__(self):
        return self.name

    @property
    def latest(self):
        try:
            return self.releases.latest()
        except PyRelease.DoesNotExist:
            return None

    @property
    def downlaods(self):
        return self.releases.filter(hidden=False).aggregate(Sum('downloads'))['downloads__sum'] or 0

    def save(self, *args, **kwargs):
        if not self.name:
            self.name = self.packaginator_package.title
        super(PyPackage, self).save(*args, **kwargs)

    def fetch_releases(self, include_hidden=True):

        package_name = self.name
        proxy = xmlrpclib.Server(self.index_api_url)

        for version in proxy.package_releases(package_name, include_hidden):
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
    package_info = PackageInfoField(blank=False)
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


