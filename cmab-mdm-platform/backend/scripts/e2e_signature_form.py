"""Official Casdoor application fields only; no scripts or upstream source patch."""
CLIENTS = {'mdm-signing-login', 'mdm-signing-proof', 'mdm-signing-pm', 'mdm-signing-portal', 'mdm-signing-pm-delegation'}


def configure_identity_fixture(init, _configuration):
    applications = init.get('applications', [])
    if (len(applications) != len(CLIENTS) or {app.get('name') for app in applications} != CLIENTS
            or any(app.get('organization') != 'mdm-signing-synthetic' for app in applications)):
        raise ValueError('Only the known new synthetic five-client fixture is permitted')
    app = next(value for value in applications if value['name'] == 'mdm-signing-proof')
    if app.get('grantTypes') != ['authorization_code'] or app.get('tags') != ['dcr']:
        raise ValueError('Signature client audience/grant category must remain restricted')
    app.update(
        displayName='签名密码验证', enableAutoSignin=False,
        signinMethods=[{'name': 'Password', 'displayName': '密码', 'rule': 'All'}],
        logo='', formBackgroundUrl='', formBackgroundUrlMobile='', headerHtml='',
        footerHtml='<span>统一身份验证</span>', formSideHtml='',
        formCss='.login-panel{max-width:440px;padding:16px;background:#fff;box-shadow:none;border:0}'
                '.login-forget-password{display:none !important}'
                'button[aria-label="主题"],button[aria-label="Theme"]{display:none !important}',
        signinItems=[
            {'name': 'Logo', 'visible': False},
            {'name': 'Languages', 'visible': False},
            {'name': 'Username', 'visible': False},
            {'name': 'Password', 'visible': True, 'label': '密码', 'placeholder': '请输入统一身份登录密码',
             'customCss': '/* official-v4 label: preserve explicit label during legacy CSS migration */'},
            # Keep this item: removing it makes v4 default remember-login to true.
            {'name': 'Forgot password?', 'visible': False, 'rule': 'Auto sign in - False',
             'customCss': '.login-forget-password{display:none !important}'},
            {'name': 'Login button', 'visible': True, 'label': '验证并签名',
             'customCss': '/* official-v4 label: preserve explicit label during legacy CSS migration */'},
        ])
