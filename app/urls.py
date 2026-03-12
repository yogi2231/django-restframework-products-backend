from django.urls import path
from .views import (
    ProductListCreate, ProductDetail, register, login, logout,
    get_cart, add_to_cart, remove_from_cart, update_cart_item, clear_cart,
    orders, create_order_from_cart, ratings, get_wishlist, add_to_wishlist, remove_from_wishlist,
    UserList, ContactListCreate, ContactDetail, AddressListCreate, AddressDetail
)

 

urlpatterns = [
    path('products', ProductListCreate.as_view()),
    path('products/<int:pk>', ProductDetail.as_view()),
    path('auth/register/', register, name='register'),
    path('auth/login/', login, name='login'),
    path('auth/logout/', logout, name='logout'),
    path('cart/', get_cart, name='get_cart'),
    path('cart/add/', add_to_cart, name='add_to_cart'),
    path('cart/remove/', remove_from_cart, name='remove_from_cart'),
    path('cart/update/', update_cart_item, name='update_cart_item'),
    path('cart/clear/', clear_cart, name='clear_cart'),
    path('orders/', orders, name='orders'),
    path('orders/create-from-cart/', create_order_from_cart, name='create_order_from_cart'),
    path('ratings/', ratings, name='ratings'),
    path('wishlist/', get_wishlist, name='get_wishlist'),
    path('wishlist/add/', add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/', remove_from_wishlist, name='remove_from_wishlist'),
    # user management
    path('users/', UserList.as_view(), name='user_list'),
    # contact
    path('contacts/', ContactListCreate.as_view(), name='contact_list_create'),
    path('contacts/<int:pk>', ContactDetail.as_view(), name='contact_detail'),
    # address
    path('addresses/', AddressListCreate.as_view(), name='address_list_create'),
    path('addresses/<int:pk>', AddressDetail.as_view(), name='address_detail'),
]