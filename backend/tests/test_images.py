import io

from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from test_api import login


def picture():
    output = io.BytesIO()
    Image.new('RGB', (1200, 800), 'red').save(output, 'PNG')
    return output.getvalue()


def test_catalog_image_upload_and_tenant_bound_references():
    with TestClient(app) as c:
        owner, cashier = login(c, '1111'), login(c, '2222')
        assert c.post('/api/images', content=picture()).status_code == 401
        assert c.post('/api/images', headers=cashier, content=picture()).status_code == 403
        assert c.post('/api/images', headers=owner, content=b'<svg onload="alert(1)"/>').status_code == 422
        assert c.post('/api/images', headers=owner, content=b'x' * (3 * 1024 * 1024 + 1)).status_code == 413
        r = c.post('/api/images', headers=owner, content=picture())
        assert r.status_code == 201, r.text
        url = r.json()['url']
        loaded = c.get(url)
        assert loaded.status_code == 200 and loaded.headers['content-type'] == 'image/webp'
        normalized = Image.open(io.BytesIO(loaded.content))
        assert normalized.width == 1024
        assert loaded.headers['x-content-type-options'] == 'nosniff'
        category = c.post('/api/categories', headers=owner, json={'name': 'Image test', 'imageUrl': url})
        assert category.status_code == 200, category.text
        key = category.json()['id']
        assert category.json()['imageUrl'] == url
        assert c.put('/api/categories/' + key, headers=owner, json={'name': 'Renamed image test'}).json()['imageUrl'] == url
        product = {'cat': key, 'name': 'Picture product', 'imageUrl': url, 'sizes': [{'code': '-', 'label': '', 'price': 1000, 'recipe': []}]}
        assert c.post('/api/products', headers=owner, json=product).status_code == 200
        menu = c.get('/api/menu', headers=owner).json()
        assert next(x for x in menu['categories'] if x['id'] == key)['imageUrl'] == url
        assert c.post('/api/products', headers=owner, json={**product, 'imageUrl': 'https://share.google/abc'}).status_code == 422
        # A different authenticated tenant must not attach another tenant's stored image.
        from app.db import SessionLocal
        from app.main import create_company
        import secrets
        slug = 'image-' + secrets.token_hex(4)
        with SessionLocal() as db:
            create_company(db, slug, 'Image tenant', 'Owner', '1234')
            db.commit()
        other = login(c, '1234', slug)
        assert c.post('/api/categories', headers=other, json={'name': 'Other', 'imageUrl': url}).status_code == 422
        assert c.get('/api/images/not-a-key').status_code == 404
        assert c.put('/api/categories/' + key, headers=owner, json={'name': 'Renamed image test', 'imageUrl': ''}).json()['imageUrl'] == ''
