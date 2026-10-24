import unittest
from unittest.mock import patch

from pawpos.config import database_url


class ConfigTests(unittest.TestCase):
    def test_credentials_are_preserved_without_url_interpolation(self):
        with patch.dict(
            "os.environ",
            {
                "DB_HOST": "localhost",
                "DB_PORT": "3306",
                "DB_USER": "test@user",
                "DB_PASSWORD": "test:/@?#%",
                "DB_NAME": "pawpos_test",
            },
        ):
            url = database_url()
        self.assertEqual(url.drivername, "mysql+pymysql")
        self.assertEqual(url.username, "test@user")
        self.assertEqual(url.password, "test:/@?#%")
        self.assertEqual(url.database, "pawpos_test")
        self.assertEqual(url.query["charset"], "utf8mb4")
        self.assertNotIn("test:/@?#%", str(url))
