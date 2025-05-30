from .models import *  
from django.db.models import Sum, F

def global_context(request):
    categories = Category.objects.filter(parent=None, is_active=True).prefetch_related('children')
    wishlist_items = Wishlist.objects.filter(user=request.user) if request.user.is_authenticated else []
    wishlist_count = wishlist_items.count() if request.user.is_authenticated else 0

    cart_count = 0
    cart_total_price = 0
    cart_items = []
    if request.user.is_authenticated:
        try:
            order = Order.objects.get(user=request.user, status='Pending')  # or your 'open' status
            cart_items = order.items.all()  # assuming related_name='items' on CartItem FK to Order
            cart_count = sum(item.quantity for item in cart_items)
             # Calculate total: quantity × product price
            cart_total_price = cart_items.aggregate(
                total=Sum(F('quantity') * F('product__price'))
            )['total'] or 0
        except Order.DoesNotExist:
            cart_count = 0
            


    return {
        'categories': categories,
        'wishlist_items': wishlist_items,
        'wishlist_count': wishlist_count,
        'cart_count': cart_count,
        'cart_items': cart_items,
        'cart_total_price': cart_total_price,
    }
