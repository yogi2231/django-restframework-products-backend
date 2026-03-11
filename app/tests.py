from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from .models import CustomUser


class UserAPITestCase(TestCase):
    def setUp(self):
        # create a store user and a regular customer
        self.store_user = CustomUser.objects.create_user(
            username='store', password='password', user_type='store'
        )
        self.customer = CustomUser.objects.create_user(
            username='customer', password='password', user_type='customer'
        )
        self.client = APIClient()

    def get_token(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        return token.key

    def test_store_user_can_list_users(self):
        token = self.get_token(self.store_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, 200)
        # should include at least the two created users
        usernames = [u['username'] for u in response.json()]
        self.assertIn('store', usernames)
        self.assertIn('customer', usernames)

    def test_non_store_user_cannot_list_users(self):
        token = self.get_token(self.customer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, 403)
