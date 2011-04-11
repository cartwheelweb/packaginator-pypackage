from django.test import TestCase
from django import forms

from package.models import Package, Category
from pypackage.models import PyPackage
from pypackage.forms import PyPackageForm

class PyPackageFormTests(TestCase):

    def setUp(self):
        dj = Package.objects.create(title='Django', slug='django')
        djpypi = PyPackage.objects.create(packaginator_package=dj,
                name='django')
        Category.objects.create(title='foo', slug='foo')

    def test_new_save(self):
        category = Category.objects.all()[0].id
        data = {'title':'django-uni-form',
                'slug':'django-uni-form',
                'repo_url':'https://github.com/pydanny/django-uni-form',
                'pypi_slug':'django-uni-form',
                'category':category}
        form = PyPackageForm(data)
        self.assertTrue(form.is_valid())
        package_model = form.save()
        self.assertTrue(isinstance(package_model, Package))
        self.assertTrue(isinstance(package_model.pypi, PyPackage))
        self.assertEquals(package_model.pypi.name, data['pypi_slug'])
        self.assertEquals(package_model.pypi.packaginator_package, package_model)

    def test_fail_on_dupe_pypi(self):
        category = Category.objects.all()[0].id
        data = {'title':'Django',
                'slug':'Django',
                'repo_url':'',
                'pypi_slug':'django',
                'category':category}
        form = PyPackageForm(data)
        self.assertFalse(form.is_valid())
        self.assertTrue('pypi_slug' in form.errors)



