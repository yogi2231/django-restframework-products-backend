from django.shortcuts import render

# Create your views here.
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import FilterSet, NumberFilter
from django.db import transaction
from .models import Product, CustomUser, Cart, CartItem, Order, OrderItem, Rating, Wishlist, WishlistItem, Contact, Address
from .serializers import (
    ProductSerializer, UserRegistrationSerializer, UserLoginSerializer,
    UserSerializer, CartSerializer, CartItemSerializer,
    OrderSerializer, RatingSerializer, WishlistSerializer, WishlistItemSerializer, ContactSerializer, AddressSerializer
)


class IsStoreUser(IsAuthenticated):
    """Permission class to check if user is a store user"""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.user.user_type == 'store'


class UserList(generics.ListAPIView):
    """Endpoint returning all users.  Only accessible by store users."""
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsStoreUser]


class ProductFilter(FilterSet):
    price_min = NumberFilter(field_name='price', lookup_expr='gte')
    price_max = NumberFilter(field_name='price', lookup_expr='lte')
    
    class Meta:
        model = Product
        fields = []


class ProductListCreate(generics.ListCreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['product', 'product_details', 'product_description']
    ordering_fields = ['price', 'product_quantity']
    ordering = ['product']
    
    def get_permissions(self):
        """
        Allow any user to list products
        Only store users can create products
        """
        if self.request.method == 'POST':
            permission_classes = [IsStoreUser]
        else:
            permission_classes = [AllowAny]
        return [permission() for permission in permission_classes]


class ProductDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    
    def get_permissions(self):
        """
        Allow any user to retrieve products
        Only store users can update or delete products
        """
        if self.request.method == 'GET':
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsStoreUser]
        return [permission() for permission in permission_classes]


def _create_order_from_user_cart(user, address_data):
    """Create an order from the authenticated user's cart in a single transaction."""
    try:
        with transaction.atomic():
            cart = Cart.objects.select_for_update().get(user=user)
            cart_items = list(
                cart.items.select_related('product').select_for_update()
            )

            if not cart_items:
                return None, Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)

            # Validate stock before any write so the order is all-or-nothing.
            for item in cart_items:
                if item.product.product_quantity < item.quantity:
                    return None, Response(
                        {
                            'error': (
                                f'Insufficient stock for {item.product.product}. '
                                f'Available: {item.product.product_quantity}, requested: {item.quantity}'
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

            order = Order.objects.create(
                user=user,
                address_line1=address_data['address_line1'],
                address_line2=address_data.get('address_line2'),
                city=address_data['city'],
                state=address_data['state'],
                postal_code=address_data['postal_code'],
                country=address_data['country']
            )
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )
                item.product.product_quantity -= item.quantity
                item.product.save(update_fields=['product_quantity'])

            cart.items.all().delete()
            return order, None
    except Cart.DoesNotExist:
        return None, Response({'error': 'Cart not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """User registration endpoint"""
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        # Create cart and wishlist for new user
        Cart.objects.create(user=user)
        Wishlist.objects.create(user=user)
        return Response({
            'user': UserSerializer(user).data,
            'token': token.key
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """User login endpoint"""
    serializer = UserLoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'user': UserSerializer(user).data,
            'token': token.key
        }, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cart(request):
    """Get user's cart"""
    cart, _ = Cart.objects.get_or_create(user=request.user)
    serializer = CartSerializer(cart)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_to_cart(request):
    """Add product to cart"""
    try:
        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity', 1)

        # Validate product exists
        product = Product.objects.get(id=product_id)

        # Check stock
        if product.product_quantity < quantity:
            return Response(
                {'error': f'Only {product.product_quantity} items available in stock'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get or create user's cart
        cart, _ = Cart.objects.get_or_create(user=request.user)

        # Add or update cart item
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': quantity}
        )

        if not created:
            # If item already exists, update quantity
            cart_item.quantity += quantity
            if cart_item.quantity > product.product_quantity:
                return Response(
                    {'error': f'Only {product.product_quantity} items available in stock'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            cart_item.save()

        cart.save()  # Update modified time
        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    except Product.DoesNotExist:
        return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def remove_from_cart(request):
    """Remove product from cart"""
    try:
        product_id = request.data.get('product_id')
        cart = Cart.objects.get(user=request.user)
        cart_item = CartItem.objects.get(cart=cart, product_id=product_id)
        cart_item.delete()
        serializer = CartSerializer(cart)
        return Response(serializer.data)
    except CartItem.DoesNotExist:
        return Response({'error': 'Item not in cart'}, status=status.HTTP_404_NOT_FOUND)
    except Cart.DoesNotExist:
        return Response({'error': 'Cart not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_cart_item(request):
    """Update quantity of item in cart (0 = remove from cart)"""
    try:
        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity', 1)

        if quantity < 0:
            return Response({'error': 'Quantity cannot be negative'}, status=status.HTTP_400_BAD_REQUEST)

        cart = Cart.objects.get(user=request.user)
        cart_item = CartItem.objects.get(cart=cart, product_id=product_id)

        # If quantity is 0, remove the item from cart
        if quantity == 0:
            cart_item.delete()
            serializer = CartSerializer(cart)
            return Response(serializer.data)

        # Otherwise, check stock and update quantity
        product = Product.objects.get(id=product_id)
        if product.product_quantity < quantity:
            return Response(
                {'error': f'Only {product.product_quantity} items available in stock'},
                status=status.HTTP_400_BAD_REQUEST
            )

        cart_item.quantity = quantity
        cart_item.save()
        cart.save()

        serializer = CartSerializer(cart)
        return Response(serializer.data)
    except CartItem.DoesNotExist:
        return Response({'error': 'Item not in cart'}, status=status.HTTP_404_NOT_FOUND)
    except Cart.DoesNotExist:
        return Response({'error': 'Cart not found'}, status=status.HTTP_404_NOT_FOUND)
    except Product.DoesNotExist:
        return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clear_cart(request):
    """Clear all items from cart"""
    try:
        cart = Cart.objects.get(user=request.user)
        cart.items.all().delete()
        serializer = CartSerializer(cart)
        return Response(serializer.data)
    except Cart.DoesNotExist:
        return Response({'error': 'Cart not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def orders(request):
    """List user orders - most recent first"""
    qs = Order.objects.filter(user=request.user).order_by('-created_at')
    serializer = OrderSerializer(qs, many=True)
    return Response(serializer.data)

   


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_order_from_cart(request):
    """Create an order from the authenticated user's current cart."""
    required_fields = ['address_line1', 'city', 'state', 'postal_code', 'country']
    missing_fields = [field for field in required_fields if not request.data.get(field)]
    if missing_fields:
        return Response(
            {'error': f"Missing required fields: {', '.join(missing_fields)}"},
            status=status.HTTP_400_BAD_REQUEST
        )

    address_data = {
        'address_line1': request.data.get('address_line1'),
        'address_line2': request.data.get('address_line2'),
        'city': request.data.get('city'),
        'state': request.data.get('state'),
        'postal_code': request.data.get('postal_code'),
        'country': request.data.get('country')
    }

    order, error_response = _create_order_from_user_cart(request.user, address_data)
    if error_response:
        return error_response

    serializer = OrderSerializer(order)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def ratings(request):
    """List or create ratings for products by user"""
    if request.method == 'GET':
        qs = Rating.objects.filter(user=request.user).order_by('-created_at')
        serializer = RatingSerializer(qs, many=True)
        return Response(serializer.data)

    # POST: submit a new rating
    data = request.data.copy()
    data['user'] = request.user.id
    serializer = RatingSerializer(data=data)
    if serializer.is_valid():
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_wishlist(request):
    """Get user's wishlist"""
    wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
    serializer = WishlistSerializer(wishlist)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_to_wishlist(request):
    """Add product to wishlist"""
    try:
        product_id = request.data.get('product_id')
        product = Product.objects.get(id=product_id)
        wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
        
        wishlist_item, created = WishlistItem.objects.get_or_create(
            wishlist=wishlist,
            product=product
        )
        
        if not created:
            return Response(
                {'message': 'Product already in wishlist'},
                status=status.HTTP_200_OK
            )
        
        serializer = WishlistSerializer(wishlist)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    except Product.DoesNotExist:
        return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def remove_from_wishlist(request):
    """Remove product from wishlist"""
    try:
        product_id = request.data.get('product_id')
        wishlist = Wishlist.objects.get(user=request.user)
        wishlist_item = WishlistItem.objects.get(wishlist=wishlist, product_id=product_id)
        wishlist_item.delete()
        serializer = WishlistSerializer(wishlist)
        return Response(serializer.data)
    except WishlistItem.DoesNotExist:
        return Response({'error': 'Item not in wishlist'}, status=status.HTTP_404_NOT_FOUND)
    except Wishlist.DoesNotExist:
        return Response({'error': 'Wishlist not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """User logout endpoint - delete token"""
    Token.objects.filter(user=request.user).delete()
    return Response({'detail': 'Logged out successfully'}, status=status.HTTP_200_OK)


class ContactListCreate(generics.ListCreateAPIView):
    """List user's contacts or create a new contact"""
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [OrderingFilter, SearchFilter]
    search_fields = ['subject', 'message', 'name', 'email']
    ordering_fields = ['created_at', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        """Return only contacts for the authenticated user"""
        return Contact.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Create a contact associated with the authenticated user"""
        serializer.save(user=self.request.user)


class ContactDetail(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a contact"""
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return only contacts for the authenticated user"""
        return Contact.objects.filter(user=self.request.user)

    def perform_update(self, serializer):
        """Update only allows status and message fields to be changed"""
        serializer.save()


class AddressListCreate(generics.ListCreateAPIView):
    """List user's addresses or create a new one"""
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [OrderingFilter, SearchFilter]
    search_fields = ['address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country']
    ordering_fields = ['created_at', 'updated_at', 'city', 'state', 'country']
    ordering = ['-created_at']

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AddressDetail(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a user address"""
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)