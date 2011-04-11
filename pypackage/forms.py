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

    def clean_pypi_slug(self):
        if self.cleaned_data['pypi_slug']:
            slug = self.cleaned_data['pypi_slug']
            try:
                PyPackage.objects.get(name=slug)
                # if we already have a pypackage with this slug, its an error
                raise forms.ValidationError("A package with that PyPI name already exists")
            except PyPackage.DoesNotExist:
                # this is the expected case
                return slug

    def save(self, force_insert=False, force_update=False, commit=True):
        m = super(PyPackageForm, self).save(commit=False)
        # need to ignore commit param, because we need a valid id for the package
        m.save()
        if self.cleaned_data['pypi_slug']:
            PyPackage.objects.create(
                    packaginator_package = m,
                    name = self.cleaned_data['pypi_slug']
                    )

        return m

    class Meta:
        model = Package
        fields = ['repo_url', 'title', 'slug', 'pypi_slug', 'category']
