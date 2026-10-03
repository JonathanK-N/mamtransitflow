import pytest
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from whitenoise.middleware import WhiteNoiseMiddleware


@pytest.mark.parametrize('filename,content_type', [
    ('sw.js', 'text/javascript'),
    ('manifest.webmanifest', 'application/manifest+json'),
    ('index.html', 'text/html'),
])
def test_pwa_entrypoints_revalidate(tmp_path, filename, content_type):
    (tmp_path / filename).write_text('{}', encoding='utf-8')
    with override_settings(WHITENOISE_ROOT=tmp_path, STATIC_ROOT=None,
                           WHITENOISE_AUTOREFRESH=False, WHITENOISE_USE_FINDERS=False):
        middleware = WhiteNoiseMiddleware(lambda request: HttpResponse(status=404))
        response = middleware(RequestFactory().get('/' + filename))
    assert response.status_code == 200
    assert response['Content-Type'].split(';')[0] == content_type
    assert response['Cache-Control'] == 'no-cache'


def test_static_images_keep_public_cache(tmp_path):
    (tmp_path / 'icon.png').write_bytes(b'image')
    with override_settings(WHITENOISE_ROOT=tmp_path, STATIC_ROOT=None,
                           WHITENOISE_AUTOREFRESH=False, WHITENOISE_USE_FINDERS=False):
        middleware = WhiteNoiseMiddleware(lambda request: HttpResponse(status=404))
        response = middleware(RequestFactory().get('/icon.png'))
    assert response.status_code == 200
    assert 'public' in response['Cache-Control']
