import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainfolder.settings')
django.setup()

from app.models import Product

Product.objects.create(
    product="iPhone 15",
    price=999.99,
    product_quantity=50,
    product_description="Latest iPhone"
)

Product.objects.create(
    product="Samsung Galaxy",
    price=699.99,
    product_quantity=30,
    product_description="Samsung Phone"
)

Product.objects.create(
    product="MacBook Pro",
    price=1999.99,
    product_quantity=20,
    product_description="Professional laptop"
)

print("✅ Products created successfully!")
print("Product IDs:", [p.id for p in Product.objects.all()])
