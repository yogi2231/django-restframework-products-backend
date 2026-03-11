import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','mainfolder.settings')
import django
django.setup()

from rest_framework.test import APIClient
from app.models import Product, CustomUser

print('products', list(Product.objects.values('id','product')))
user = CustomUser.objects.get(username='anil')
print('user', user)
client = APIClient()
client.credentials(HTTP_AUTHORIZATION='Token 31379a2ed451b0a5171d8a50a474ef3deb125a01')
resp = client.post('/api/cart/add/', {'product_id':1,'quantity':3}, format='json')
print('status', resp.status_code)
print('data', resp.data)
print('headers', resp._headers)
