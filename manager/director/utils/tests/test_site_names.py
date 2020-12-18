import re
import uuid

from ...test.director_test import DirectorTestCase
from ..site_names import is_site_name_allowed


class UtilsSiteNamesTestCase(DirectorTestCase):
    def test_is_site_name_allowed(self):
        unique = str(uuid.uuid4())
        with self.settings(WHITELISTED_SITE_NAMES=unique):
            self.assertTrue(is_site_name_allowed(unique))

        unique = str(uuid.uuid4())
        with self.settings(BLACKLISTED_SITE_NAMES=unique):
            self.assertFalse(is_site_name_allowed(unique))

        with self.settings(BLACKLISTED_SITE_REGEXES=[re.compile(r"\whello\d+")]):
            self.assertFalse(is_site_name_allowed("shello123"))
            self.assertTrue(is_site_name_allowed("shello"))
