from django.contrib import admin
from reversion.admin import VersionAdmin

from package.models import Category, Package, PackageExample, Commit, Version

class PackageExampleInline(admin.TabularInline):
    model = PackageExample

class PyPackageAdmin(VersionAdmin):

    save_on_top = True
    search_fields = ("title",)
    list_filter = ("category",)
    list_display = ("title", "created", )
    date_hierarchy = "created"
    inlines = [
        PackageExampleInline,
    ]
    fieldsets = (
        (None, {
            "fields": ("title", "slug", "category", "repo_url", "usage", "created_by", "last_modified_by",)
        }),
        ("Pulled data", {
            "classes": ("collapse",),
            "fields": ("repo_description", "repo_watchers", "repo_forks", "repo_commits", "participants")
        }),
    )

# admin.site.register(Package, PyPackageAdmin)
