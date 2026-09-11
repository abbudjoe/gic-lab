"""Explicit CI launcher bootstrap, before pytest imports or fixture construction."""

import os

if "GICLAB_CI_GUARD_JOURNAL" in os.environ:
    try:
        from offline_guard import install

        install()
    except BaseException:
        # Python normally only prints sitecustomize errors and continues.
        os._exit(92)
