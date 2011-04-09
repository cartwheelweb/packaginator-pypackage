import locale
import xmlrpclib

from django.contrib.auth.models import User
from django.db import models
from django.utils import simplejson as json
from django.utils.datastructures import MultiValueDict
from django.utils.translation import ugettext_lazy as _

from package.models import Package, Version
from package.signals import signal_fetch_latest_metadata

locale.setlocale(locale.LC_ALL, '')

def handle_fetch_metada_signal(sending_package, **kwargs):
    try:
        pypackage = PyPackage.objects.get(packaginator_package=sending_package)
    except PyPackage.DoesNotExist:
        return False
    pypackage.fetch_releases()

signal_fetch_latest_metadata.connect(handle_fetch_metada_signal)

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
            blank=True, default="http://pypi.python.org/pypi/")

    def __unicode__(self):
        return self.name

    @property
    def latest(self):
        try:
            return self.releases.latest()
        except Release.DoesNotExist:
            return None

# TODO need to update this property pulled of packaginator package model
    # @property
    # def pypi_version(self):
        # string_ver_list = self.version_set.values_list('number', flat=True)
        # if string_ver_list:
            # vers_list = [versioner(v) for v in string_ver_list]
            # latest = sorted(vers_list)[-1]
            # return str(latest)
        # return ''

    def fetch_releases(self, include_hidden=True):


        package_name = self.name
        proxy = xmlrpclib.Server(self.index_api_url)

        for version in proxy.package_releases(package_name, include_hidden):
            try:
                this_release = self.releases.get(version=version)
                # if we have a release already - skip it
                continue
            except Release.DoesNotExist:
                # if we don't have a release, create it now
                pass
            release_data = proxy.release_data(package_name, version)
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

            packaginator_version = Version.objects.get_or_create(
                    package=self.packaginator_package,
                    number=version)
            packaginator_version.downloads = release_data.downloads
            packaginator_version.hidden = release_data.hidden
            packaginator_version.license = release_data.license
            packaginator_version.save()

            self.releases.create(
                version = version,
                packaginator_version = packaginator_version,
                package_info = release_data,
                hidden = release_data.hidden,
                summary = release_data.summary,
                downloads = release_data.downloads)



class Release(models.Model):
    pypackage = models.ForeignKey(PyPackage, related_name="releases", editable=False)
    packaginator_version = models.OneToOneField(Version, related_name = 'pypi')
    version = models.CharField(max_length=128, editable=False)
    metadata_version = models.CharField(max_length=64, default='1.0')
    package_info = PackageInfoField(blank=False)
    hidden = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    summary = models.TextField(blank=True)
    downloads = models.IntegerField(_("downloads"), default=0)
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
        return u"%s-%s" % (self.package.name, self.version)

    @property
    def summary(self):
        return self.package_info.get('summary', u'')

    @property
    def description(self):
        return self.package_info.get('description', u'')

    @property
    def classifiers(self):
        return self.package_info.getlist('classifier')

    @models.permalink
    def get_absolute_url(self):
        return ('djangopypi-release', (), {'package': self.package.name,
                                           'version': self.version})


