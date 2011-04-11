from django.conf.urls.defaults import *

from pypackage.forms import PyPackageForm
from package.views import (
        package_list,
        add_package
        )

from grid.views import (
        grid_detail,
        )

overridden_urlpatterns = patterns('',
    # url(
        # regex   = r"^$",
        # view    = package_list,
        # name    = "packages",
        # kwargs  = {}
    # ),
    url(
        regex   = r"^packages/add/$",
        view    = add_package,
        name    = "add_package",
        kwargs  = {'form_class': PyPackageForm}
    ),

    url(
    regex = '^grids/g/(?P<slug>[-\w]+)/$',
    view    = grid_detail,
    name    = 'grid',
    kwargs  = {'additional_attributes':
                (
                    ('pypi.latest.downloads', 'Downloads'),
                    ('pypi.latest.version', 'Version'),
                )
                },
    ),
)
