from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Product, CustomUser

admin.site.register(Product)
admin.site.register(CustomUser, UserAdmin)