"""Regression for PR58 GEN-01; ordinary camelCase names remain usable."""
import unittest
from archloop.context_pack import _key_name_is_secret, _looks_like_secret


class AcronymCredentialTests(unittest.TestCase):
    def test_acronym_boundaries_and_regular_names(self):
        for key in ("clientAPIKey", "APIKey", "HTTPAccessToken", "OIDCClientSecret", "clientAPI_KEY"):
            with self.subTest(key=key):
                self.assertTrue(_key_name_is_secret(key))
                self.assertTrue(_looks_like_secret(f'{key} = "abcdefghijklmnop123456"'))
        for key in ("monkey", "turkey", "keynote", "HTTPServiceName", "clientAPIEndpoint"):
            with self.subTest(key=key):
                self.assertFalse(_key_name_is_secret(key))


if __name__ == "__main__": unittest.main()
