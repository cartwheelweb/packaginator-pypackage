from django.conf import settings
from django.core.validators import URLValidator
from django import forms
from django.forms import ModelForm
from django.template.defaultfilters import slugify

from package.models import Package, PackageExample
from pypackage.models import PyPackage

pypi_url_help_text = settings.PACKAGINATOR_HELP_TEXT['PYPI_URL']

# TODO figure out how to get the settings.PACKAGINATOR_HELP_TEXT into the form
class PyPackageForm(ModelForm):
    pypi_slug = forms.CharField(max_length=100, required=False,
            help_text=pypi_url_help_text)

    def clean_slug(self):
        return self.cleaned_data['slug'].lower()

    class Meta:
        model = Package
        # TODO mix in pypackage model here in a way to get pypi URL
        fields = ['repo_url', 'title', 'slug', 'pypi_slug', 'category']

    def save(self, force_insert=False, force_update=False, commit=True):
        m = super(PyPackageForm, self).save(commit=False)
        # do custom stuff
        # need to ignore commit param, because we need a valid id
        m.save()
        if self.cleaned_data['pypi_slug']:
            # TODO return an error on the pypi field if pypackage with that slug
            # already exists
            PyPackage.objects.create(
                    packaginator_package = m,
                    name = self.cleaned_data['pypi_slug']
                    )
        return m

