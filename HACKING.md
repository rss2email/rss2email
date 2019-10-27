# Hacking on `rss2email`

This document is still TODO. Please contribute to it and file issues
if you have a question (or something is not described sufficiently).


## Cutting a new release

- `nix-shell`
- `update-copyright.py`
- Prepare `CHANGELOG`
- Fix `__version__` in `rss2email/__init.py`
- `git commit`
- `exit`

- `rm -Rf dist rss2email.egg-info`
- `nix-shell -p python37Packages.{setuptools,wheel,twine}`
- `SOURCE_DATE_EPOCH=315532800 python3 setup.py sdist bdist_wheel`
- `twine upload --repository-url https://test.pypi.org/legacy/ dist/*`
- Check it actually work on test-pypi (NixOS test, run on dev machines…)

- Add git tag, git branch if need be, push it to repository
- `twine upload dist/*`


## Using nix support

`rss2email` has a few nix definitions in order to simplify development.
In order to use them you need to install the [nix package
manager][https://nixos.org/nix] version 2 or later on your system.

### Open a shell with all dependencies

Run `nix-shell` in the top directory. I will open a bash with all
dependencies (python and system) you need for developing `rss2email`.
This uses the `shell.nix` file.

### Test `rss2email` against multiple python versions

`nix/release.nix` contains an expression to build rss2email with
different versions of python and run its tests suite with that
version.

So far, Python 3.5, 3.6 and 3.7 are supported.

You can build each one of them like this:

```
nix-build -A rss2email-python_3_5 nix/release.nix
nix-build -A rss2email-python_3_6 nix/release.nix
nix-build -A rss2email-python_3_7 nix/release.nix
```

and all at once with

```
nix-build nix/release.nix
```
