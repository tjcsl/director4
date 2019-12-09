from django.conf import settings


def is_site_name_allowed(name: str) -> bool:
    if name in settings.WHITELISTED_SITE_NAMES:
        return True

    if name in settings.BLACKLISTED_SITE_NAMES:
        return False

    for pattern in settings.BLACKLISTED_SITE_REGEXES:
        if pattern.search(name) is not None:
            return False

    return True
