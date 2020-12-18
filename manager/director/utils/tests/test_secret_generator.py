from ...test.director_test import DirectorTestCase
from ..secret_generator import gen_database_password


class UtilsSecretGenTestCase(DirectorTestCase):
    def test_gen_database_password(self):
        with self.settings(DIRECTOR_DATABASE_PASSWORD_LENGTH=50):
            self.assertEqual(50, len(gen_database_password()))
