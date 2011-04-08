keeping the name pypi - means we need to manually drop older pypi app table


should we use the upload-time timestamp on pypi release_urls to determine
a "release date"?


Keeping a relationship of a generic packaginator version to a pypi release

as in the package level, using a one to one field

should hidden and download be moved to pypi release?

downloads would not count github downloads, and so really mean pypi downloads
and so maybe belong on the pypi specific model?

