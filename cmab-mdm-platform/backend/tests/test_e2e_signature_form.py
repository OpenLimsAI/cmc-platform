import copy
import unittest

from scripts.e2e_signature_form import configure_identity_fixture


def fixture():
    names = ['mdm-signing-login', 'mdm-signing-proof', 'mdm-signing-pm', 'mdm-signing-portal', 'mdm-signing-pm-delegation']
    return {'organizations': [{'name': 'mdm-signing-synthetic', 'languages': ['en']}], 'applications': [{'owner': 'admin', 'name': name, 'organization': 'mdm-signing-synthetic', 'tags': ['dcr'], 'grantTypes': ['authorization_code'], 'clientSecret': 'unit-placeholder-only', 'expireInHours': 1, 'redirectUris': ['http://localhost:19190/mdm/signature-callback']} for name in names], 'users': []}

class ConfigurationTests(unittest.TestCase):

    def test_only_signature_client_presentation_changes(self):
        value = fixture()
        before = copy.deepcopy(value)
        conf = {'forceLanguage': '"en"', 'defaultLanguage': '"en"'}
        configure_identity_fixture(value, conf)
        self.assertEqual(value['organizations'], before['organizations'])
        self.assertEqual(conf, {'forceLanguage': '"en"', 'defaultLanguage': '"en"'})
        for old, new in zip(before['applications'], value['applications'], strict=True):
            if old['name'] != 'mdm-signing-proof':
                self.assertEqual(old, new)
            for key in ('clientSecret', 'redirectUris', 'tags', 'grantTypes', 'expireInHours'):
                self.assertEqual(old[key], new[key])

    def test_password_is_the_only_visible_input_and_default_remember_is_false(self):
        value = fixture()
        configure_identity_fixture(value, {})
        app = next(a for a in value['applications'] if a['name'] == 'mdm-signing-proof')
        items = {item['name']: item for item in app['signinItems']}
        self.assertFalse(items['Username']['visible'])
        self.assertFalse(items['Logo']['visible'])
        self.assertFalse(items['Languages']['visible'])
        self.assertTrue(items['Password']['visible'])
        self.assertEqual(items['Password']['label'], '密码')
        self.assertEqual(items['Login button']['label'], '验证并签名')
        self.assertFalse(items['Forgot password?']['visible'])
        self.assertEqual(items['Forgot password?']['rule'], 'Auto sign in - False')
        self.assertIn('display:none', items['Forgot password?']['customCss'])
        self.assertFalse(app['enableAutoSignin'])
        self.assertEqual(app['signinMethods'], [{'name': 'Password', 'displayName': '密码', 'rule': 'All'}])
        self.assertNotIn('<script', str(app))

    def test_unknown_organization_or_client_set_is_refused(self):
        value = fixture()
        value['applications'][0]['organization'] = 'not-the-isolated-organization'
        with self.assertRaises(ValueError):
            configure_identity_fixture(value, {})
