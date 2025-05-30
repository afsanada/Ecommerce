from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from .models import *
from django.urls import reverse_lazy
from django.urls import reverse
from .forms import *
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Count
from django.shortcuts import render
from django.utils.timezone import now
from django.db.models.functions import TruncMonth
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.conf import settings
import json
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Avg
from django.utils.crypto import get_random_string
from decimal import Decimal
from django.utils import timezone
from rest_framework import generics
from .serializers import ProductSerializer
# Create your views here.

User = get_user_model()

def home(request):
    category = request.GET.get('category')
    products = Product.objects.all()

    if category:
        products = products.filter(category=category)

    # Show maximum 8 products on this page
    paginator = Paginator(products, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Pass total count to template for the "View All Products" button logic
    total_products = products.count()

    return render(request, 'store/index.html', {
        'page_obj': page_obj,
        'category': category,
        'total_products': total_products,
    })
    

# views.py
def register_view(request):
    if request.method == 'POST':
        first_name = request.POST.get('firstName')
        last_name = request.POST.get('lastName')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirmPassword')

        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect('register')

        if User.objects.filter(username=email).exists():
            messages.error(request, "User already exists")
            return redirect('register')

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        user.save()
        return redirect('login')

    return render(request, 'page/register.html')

def user_login(request):
    cart_items = [] 
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(request, username=user_obj.username, password=password)
        except User.DoesNotExist:
            user = None

        if user is not None:
            login(request, user)
            request.session['user_id'] = user.id

            messages.success(request, f"Welcome back, {user.username}!")

            # Redirect based on user role
            if user.is_superuser or user.is_staff:
                return redirect('dashboard')
            else:
                return redirect('home')

        else:
            messages.error(request, "Invalid email or password.")

    return render(request, 'registration/login.html')


def user_logout(request):
    logout(request)  # Clears session
    messages.success(request, "You have been logged out.")
    return redirect('login')

def about(request):
    return render(request, 'store/about.html')

@login_required(login_url='login')  # 'login' is your login page URL name
def dashboard_view(request):
    user = request.user

    total_orders = Order.objects.count()
    total_products = Product.objects.count()
    total_categories = Category.objects.count()
    pending_orders = Order.objects.filter(status="Pending").count()

    context = {
        'total_orders': total_orders,
        'total_products': total_products,
        'total_categories': total_categories,
        'pending_orders': pending_orders,
    }

    return render(request, 'admins/dashboard.html', context)

def is_staff_user(user):
    return user.is_staff or user.is_superuser

@login_required
@user_passes_test(is_staff_user)
def add_product(request):
    if not request.user.is_authenticated or not (request.user.is_staff or request.user.is_superuser):
        return render(request, 'unauthorized.html')

    form = ProductForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        form.save()
        return redirect('product_list')

    return render(request, 'products/add_product.html', {
        'form': form,
        'title': 'Add New Product',
        'button_text': 'Add Product'
    })

@login_required
@user_passes_test(is_staff_user)
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if not request.user.is_authenticated or not (request.user.is_staff or request.user.is_superuser):
        return render(request, 'unauthorized.html')

    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if form.is_valid():
        form.save()
        return redirect('product_list')

    return render(request, 'products/add_product.html', {
        'form': form,
        'title': f'Edit Product - {product.name}',
        'button_text': 'Save Changes'
    })

@login_required
@user_passes_test(is_staff_user)
def product_list(request):
    products = Product.objects.filter(is_available=True).order_by('-created_at')
    return render(request, 'products/product_list.html', {'products': products})

@login_required
@user_passes_test(is_staff_user)
def category_list(request):
    categories = Category.objects.filter(parent__isnull=True, is_active=True)
    return render(request, 'categories/category_list.html', {'categories': categories})

@login_required
@user_passes_test(is_staff_user)
def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    children = category.children.filter(is_active=True)
    products = category.products.filter(is_available=True)  # Products in this category only
    return render(request, 'categories/category_detail.html', {
        'category': category,
        'children': children,
        'products': products,
    })

@login_required
@user_passes_test(is_staff_user)
def add_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('category_list')  # redirect to category list page
    else:
        form = CategoryForm()
    return render(request, 'categories/add_category.html', {'form': form})

@login_required
@user_passes_test(is_staff_user)
def order_list(request):
    if not request.user.is_authenticated or not (request.user.is_staff or request.user.is_superuser):
        return render(request, 'unauthorized.html')
    
    orders = Order.objects.select_related('user').order_by('-order_date')
    return render(request, 'orders/order_list.html', {'orders': orders})

@login_required
@user_passes_test(is_staff_user)
def order_detail(request, order_id):
    if not request.user.is_authenticated or not (request.user.is_staff or request.user.is_superuser):
        return render(request, 'unauthorized.html')

    order = get_object_or_404(Order, order_id=order_id)
    status_choices = Order._meta.get_field('status').choices

    if request.method == 'POST':
        new_status = request.POST.get('status')
        tracking_number = request.POST.get('tracking_number')
        order.status = new_status
        order.tracking_number = tracking_number
        order.save()
        return redirect('order_detail', order_id=order.order_id)

    return render(request, 'orders/order_detail.html', {'order': order,'status_choices': status_choices,})

def admin_only(user):
    return user.is_authenticated and user.is_superuser

@login_required
@user_passes_test(is_staff_user)
def reports_dashboard(request):
    total_orders = Order.objects.count()
    total_revenue = Order.objects.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    total_customers = User.objects.filter(is_superuser=False, is_staff=False).count()

    # Orders per month
    monthly_orders = (
        Order.objects.annotate(month=TruncMonth('order_date'))
        .values('month')
        .annotate(order_count=Count('id'), revenue=Sum('total_amount'))
        .order_by('month')
    )

    # Top Selling Products
    top_products = (
        OrderItem.objects.values('product__name')
        .annotate(total_sold=Sum('quantity'))
        .order_by('-total_sold')[:5]
    )

    context = {
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'total_customers': total_customers,
        'monthly_orders': monthly_orders,
        'top_products': top_products,
    }
    return render(request, 'reports/dashboard.html', context)

@login_required
@user_passes_test(admin_only)
def customers_list(request):
    # Get users who are NOT staff and NOT superusers (i.e. customers)
    customers = User.objects.filter(is_staff=False, is_superuser=False).order_by('date_joined')
    
    context = {
        'customers': customers,
    }
    return render(request, 'admins/customers_list.html', context)

@login_required(login_url='login')  # 'login' is your login page URL name
def my_account(request):
    user = request.user
    return render(request, 'store/account.html', {'user': user})

@login_required
def account_orders(request):
    order_list = Order.objects.filter(user=request.user).order_by('-order_date')
    paginator = Paginator(order_list, 5)  # Show 5 orders per page

    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'store/account.html', {'page_obj': page_obj})

@login_required
def brand_list(request):
    brands = Brand.objects.all()
    return render(request, 'brands/brand_list.html', {'brands': brands})

@login_required
def add_brand(request):
    if request.method == 'POST':
        form = BrandForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('brand_list')
    else:
        form = BrandForm()
    return render(request, 'brands/add_brands.html', {'form': form})

@login_required
def edit_brand(request, brand_id):
    brand = get_object_or_404(Brand, id=brand_id)
    if request.method == 'POST':
        form = BrandForm(request.POST, instance=brand)
        if form.is_valid():
            form.save()
            return redirect('brand_list')
    else:
        form = BrandForm(instance=brand)
    return render(request, 'brands/edit_brand.html', {'form': form, 'brand': brand})

@login_required(login_url='login')  # 'login' is your login page URL name
def delete_brand(request, brand_id):
    brand = get_object_or_404(Brand, id=brand_id)
    if request.method == 'POST':
        brand.delete()
        return redirect('brand_list')
    return render(request, 'brands/delete_brand.html', {'brand': brand})

@login_required(login_url='login')  # 'login' is your login page URL name
def account_view(request):
    wishlist_items = Wishlist.objects.filter(user=request.user)
    # Include other context variables if needed

    context = {
        'wishlist_items': wishlist_items,
        # Add other tabs' context if needed
    }
    return render(request, 'store/wishlist.html', context)

@login_required(login_url='login')  # 'login' is your login page URL name
def remove_wishlist(request, product_id):
    if request.method == 'POST':
        Wishlist.objects.filter(user=request.user, product_id=product_id).delete()
    return redirect('wishlist')  # Adjust to your actual account page URL name



@login_required(login_url='login')  # 'login' is your login page URL name
def my_reviews(request):
    reviews = Review.objects.filter(user=request.user).select_related('product')
    return render(request, 'store/account.html', {'reviews': reviews})

@login_required(login_url='login')  # 'login' is your login page URL name
def personal_info_view(request):
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)
    addresses = Address.objects.filter(user=user)
    notification_pref, _ = NotificationPreference.objects.get_or_create(user=user)
    wishlist_items = Wishlist.objects.filter(user=user)

    if request.method == 'POST':
        if 'firstName' in request.POST and 'lastName' in request.POST:
            user.first_name = request.POST.get('firstName')
            user.last_name = request.POST.get('lastName')
            user.email = request.POST.get('email')
            user.save()

            profile.phone_number = request.POST.get('phone')
            profile.birthdate = request.POST.get('birthdate')
            profile.gender = request.POST.get('gender')
            profile.save()

            return redirect('personal_info')  # reload with updated data
        
        elif 'notification_form' in request.POST:
            # Update notification preferences
            notification_pref.order_status = 'orderStatusNotif' in request.POST
            notification_pref.shipping_updates = 'shippingNotif' in request.POST
            notification_pref.security_alerts = 'securityNotif' in request.POST
            notification_pref.password_changes = 'passwordNotif' in request.POST
            notification_pref.promotions = 'promoNotif' in request.POST
            notification_pref.new_products = 'newProductNotif' in request.POST
            notification_pref.recommendations = 'recommendNotif' in request.POST
            notification_pref.save()

            messages.success(request, 'Notification preferences updated successfully.')
            return redirect('personal_info')
    
    context = {
        'user': user,
        'profile': profile,
        'addresses': addresses,
        'notification_pref': notification_pref,
         'wishlist_items': wishlist_items,
    }
    return render(request, 'store/account.html', context)

def returns_view(request):
    return render(request, 'store/returns.html')

def category_user(request):
    parent_categories = Category.objects.filter(parent__isnull=True).prefetch_related('children')
    return render(request, 'store/category.html', {'parent_categories': parent_categories})

def products(request, category_id=None):
    sort_option  = request.GET.get('sort',      'featured')
    price_range  = request.GET.get('price',     '')
    per_page     = int(request.GET.get('per_page', 12))
    query        = request.GET.get('q',         '')
    min_price    = request.GET.get('min_price')
    max_price    = request.GET.get('max_price')

    # Base queryset of available products
    qs = Product.objects.filter(is_available=True)

    # Filter by category if provided
    if category_id:
        qs = qs.filter(category_id=category_id)

    # Search
    if query:
        qs = qs.filter(name__icontains=query)

    # Brand filters
    selected_brands = request.GET.getlist('brand')
    if selected_brands:
        qs = qs.filter(brand__name__in=selected_brands)

    # Price range filters
    if price_range == 'under25':
        qs = qs.filter(price__lt=25)
    elif price_range == '25to50':
        qs = qs.filter(price__gte=25, price__lte=50)
    elif price_range == '50to100':
        qs = qs.filter(price__gte=50, price__lte=100)
    elif price_range == '100to200':
        qs = qs.filter(price__gte=100, price__lte=200)
    elif price_range == 'above200':
        qs = qs.filter(price__gt=200)

    # Explicit min/max price
    if min_price:
        qs = qs.filter(price__gte=min_price)
    if max_price:
        qs = qs.filter(price__lte=max_price)

    # Sorting
    if sort_option == 'price_asc':
        qs = qs.order_by('price')
    elif sort_option == 'price_desc':
        qs = qs.order_by('-price')
    elif sort_option == 'rating_desc':
        qs = qs.annotate(avg_rating=Avg('review__rating')).order_by('-avg_rating')
    elif sort_option == 'newest':
        qs = qs.order_by('-created_at')
    else:  # featured
        qs = qs.order_by('-is_new_arrival', '-created_at')

    # Pagination
    paginator   = Paginator(qs, per_page)
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)

    # Parent categories + their children for the sidebar/menu
    parent_categories = (
        Category.objects
        .filter(parent__isnull=True, is_active=True)
        .prefetch_related('children')
    )

    # Total count of all active subcategories
    subcategory_count = Category.objects.filter(parent__isnull=False, is_active=True).count()
    has_subcategories = subcategory_count > 0

    # Brand list with product counts
    brands = Brand.objects.annotate(product_count=Count('products'))

    # Wishlist count (optional)
    wishlist_count = 0
    if request.user.is_authenticated:
        wishlist_count = Wishlist.objects.filter(user=request.user).count()

    context = {
        'products':        page_obj,
        'page_obj':        page_obj,
        'sort_option':     sort_option,
        'price_range':     price_range,
        'per_page':        per_page,
        'query':           query,
        'parent_categories': parent_categories,
        'subcategory_count': subcategory_count,
        'has_subcategories': has_subcategories,
        'brands':          brands,
        'wishlist_count':  wishlist_count,
    }
    return render(request, 'store/products.html', context)

def product_detail(request, id):
    product = get_object_or_404(Product, id=id)
    discount = None
    if product.original_price and product.original_price > product.price:
        discount = round(((product.original_price - product.price) / product.original_price) * 100)

    context = {
    'product': product,
    'discount': discount,
    }
    return render(request, 'store/product-details.html', context)

def product_list_by_category(request, slug):

    sort_option = request.GET.get('sort', 'featured')
    price_range = request.GET.get('price', '')
    per_page = int(request.GET.get('per_page', 12))
    query = request.GET.get('q', '')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    
    parent_categories = Category.objects.get(slug=slug)
    subcategory_count = parent_categories.children.filter(is_active=True).count()

    products = Product.objects.filter(category=parent_categories)

    brands = Brand.objects.annotate(product_count=Count('products'))

    if query:
        products = products.filter(name__icontains=query)

    selected_brands = request.GET.getlist('brand')
    if selected_brands:
        products = products.filter(brand__name__in=selected_brands)

    # Price filter
    if price_range == 'under25':
        products = products.filter(price__lt=25)
    elif price_range == '25to50':
        products = products.filter(price__gte=25, price__lte=50)
    elif price_range == '50to100':
        products = products.filter(price__gte=50, price__lte=100)
    elif price_range == '100to200':
        products = products.filter(price__gte=100, price__lte=200)
    elif price_range == 'above200':
        products = products.filter(price__gt=200)

    # Sorting
    if sort_option == 'price_asc':
        products = products.order_by('price')
    elif sort_option == 'price_desc':
        products = products.order_by('-price')
    elif sort_option == 'rating_desc':
        products = products.annotate(avg_rating=Avg('review__rating')).order_by('-avg_rating')
    elif sort_option == 'newest':
        products = products.order_by('-created_at')
    else:  # featured
        products = products.order_by('-is_new_arrival', '-created_at')

    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)

    # Pagination (after filtering/sorting)
    paginator = Paginator(products, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'brands': brands,
        'products': page_obj,
        'page_obj': page_obj,
        'sort_option': sort_option,
        'price_range': price_range,
        'per_page': per_page,
        'query': query,
        'parent_categories': parent_categories,
        'subcategory_count': subcategory_count,
    }

    return render(request, 'store/products.html', context)


@login_required(login_url='login')  # 'login' is your login page URL name
def settings_view(request):
    user = request.user

    if request.method == 'POST':
        user.email = request.POST.get('email')
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.save()
        return redirect('settings')  # redirect back to the settings page

    return render(request, 'store/settings.html', {'user': user})

def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        print(name)
        full_message = f"From: {name} <{email}>\n\n{message}"

        try:
            send_mail(
                subject,
                full_message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.CONTACT_EMAIL],
                fail_silently=False,
            )
            messages.success(request, 'Your message has been sent. Thank you!')
        except Exception as e:
            messages.error(request, 'There was an error sending your message. Please try again later.')

    return render(request, 'store/contact.html')

@login_required(login_url='login')  # 'login' is your login page URL name
def apply_coupon(request):
    if request.method == 'POST':
        code = request.POST.get('coupon_code')
        try:
            coupon = Coupon.objects.get(code__iexact=code, active=True)
            order_items = OrderItem.objects.filter(order__user=request.user, order__status='Pending')
            subtotal = sum(item.get_total_price() for item in order_items)

            if subtotal >= coupon.minimum_order_amount:
                request.session['coupon_code'] = coupon.code
                request.session['discount'] = float(coupon.discount_amount)
                return redirect('cart')
            else:
                request.session['coupon_code'] = ''
                request.session['discount'] = 0
                request.session['error_message'] = f"Minimum order amount is ${coupon.minimum_order_amount}"
                return redirect('cart')

        except Coupon.DoesNotExist:
            request.session['coupon_code'] = ''
            request.session['discount'] = 0
            request.session['error_message'] = "Invalid coupon code."
            return redirect('cart')

@login_required(login_url='login')  # 'login' is your login page URL name
def cart_view(request):
    order = Order.objects.filter(user=request.user, status='Pending').first()
    items = order.items.all() if order else []

    # subtotal is Decimal
    subtotal = sum(item.get_total_price() for item in items)

    # Use Decimal for calculations
    tax = (subtotal * Decimal('0.10')).quantize(Decimal('0.01'))  # 10% tax, rounded to 2 decimals
    shipping = Decimal('4.99')

    discount = request.session.get('discount', Decimal('0'))

    coupon_message = ''
    error_message = request.session.pop('error_message', '')

    if discount > 0:
        coupon_code = request.session.get('coupon_code', '')
        coupon_message = f"Coupon applied: {coupon_code} - ₹{discount} off"

    total = subtotal + tax + shipping - discount

    items_with_words = []
    for item in items:
        words = item.product.name.split()
        items_with_words.append({'item': item, 'words': words})

    context = {
        'items_with_words': items_with_words,
        'subtotal': subtotal,
        'tax': tax,
        'shipping': shipping,
        'discount': discount,
        'total': total,
        'coupon_message': coupon_message,
        'error_message': error_message,
    }

    return render(request, 'store/cart.html', context)

@login_required(login_url='login')  # 'login' is your login page URL name
def update_cart(request):
    if request.method == "POST":
        for key, value in request.POST.items():
            if key.startswith("quantity_"):
                try:
                    item_id = int(key.split("_")[1])
                    quantity = int(value)
                    item = OrderItem.objects.get(id=item_id, order__user=request.user)
                    item.quantity = quantity
                    item.save()
                except (OrderItem.DoesNotExist, ValueError):
                    continue
        return redirect('cart')
    else:
        # For non-POST requests, redirect or return some response
        return redirect('cart')

def clear_cart(request):
    if request.user.is_authenticated:
        OrderItem.objects.filter(order__user=request.user).delete()
        messages.success(request, "Your cart has been cleared.")
    else:
        # If using session-based cart for guests
        session_key = request.session.session_key
        OrderItem.objects.filter(session_key=session_key).delete()
        messages.success(request, "Your cart has been cleared.")
    
    return redirect('cart') 

def get_cart_items(user):
    return OrderItem.objects.filter(order__user=user)

def calculate_totals(cart_items):
    subtotal = sum(item.product.price * item.quantity for item in cart_items)
    tax_rate = Decimal('0.10')  # 10%
    shipping_cost = Decimal('5.00') if subtotal > 0 else Decimal('0.00')
    tax = subtotal * tax_rate
    total = subtotal + tax + shipping_cost
    return subtotal, tax, shipping_cost, total

@login_required(login_url='login')  # 'login' is your login page URL name
def checkout(request):
    steps = {
        1: "Information",
        2: "Shipping",
        3: "Payment",
        4: "Review"
    }

    cart_items = get_cart_items(request.user)
    subtotal, tax, shipping_cost, total = calculate_totals(cart_items)

    # Load or initialize session data
    if 'checkout_data' not in request.session:
        request.session['checkout_data'] = {}

    data = request.session['checkout_data']
    current_step = 1

    if request.method == 'POST':
        # Navigation control
        current_step = int(request.POST.get('step', 1))

        # Save form data for each step
        if current_step == 1:
            data.update({
                'first_name': request.POST.get('first_name', '').strip(),
                'last_name': request.POST.get('last_name', '').strip(),
                'email': request.POST.get('email', '').strip(),
                'phone': request.POST.get('phone', '').strip()
            })

        elif current_step == 2:
            data.update({
                'address_line': request.POST.get('address_line', '').strip(),
                'apartment': request.POST.get('apartment', '').strip(),
                'city': request.POST.get('city', '').strip(),
                'state': request.POST.get('state', '').strip(),
                'postal_code': request.POST.get('postal_code', '').strip(),
                'country': request.POST.get('country', '').strip()
            })

        elif current_step == 3:
            data.update({
                'payment_method': request.POST.get('payment_method', '').strip(),
                'card_number': request.POST.get('card_number', '').strip(),
                'expiry': request.POST.get('expiry', '').strip(),
                'cvv': request.POST.get('cvv', '').strip(),
                'card_name': request.POST.get('card_name', '').strip()
            })

        request.session['checkout_data'] = data
        request.session.modified = True

        # If place_order is clicked on step 4
        if 'place_order' in request.POST:
            print("✅ Place order triggered. Checkout data:", data)

            if not cart_items.exists():
                messages.error(request, "Your cart is empty.")
                return redirect('cart')

            # Build full address
            full_name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
            full_address = data.get('address_line', '')
            if data.get('apartment'):
                full_address += f", {data['apartment']}"

            try:
                shipping_address = Address(
                    user=request.user,
                    full_name=full_name,
                    phone=data.get('phone', ''),
                    address_line=full_address,
                    city=data.get('city', ''),
                    state=data.get('state', ''),
                    postal_code=data.get('postal_code', ''),
                    country=data.get('country', ''),
                    is_default=True
                )
                shipping_address.full_clean()
                shipping_address.save()
                print("✅ Address saved:", shipping_address)
            except Exception as e:
                print("❌ Failed to save address:", e)
                messages.error(request, f"Address save failed: {e}")
                return redirect('checkout')

            # Create Order
            order = Order.objects.create(
                user=request.user,
                order_id=get_random_string(12).upper(),
                order_date=timezone.now(),
                status='Processing',
                total_amount=total,
                shipping_address=shipping_address
            )
            print("🛒 Order created:", order)

            # Create Order Items
            for item in cart_items:
                print("🛒 Cart Items Count:", cart_items.count())
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )

            # Clear cart & session
            cart_items.delete()
            del request.session['checkout_data']

            messages.success(request, "✅ Your order has been placed successfully!")
            return redirect('order_success')

        # Navigate steps
        elif 'next' in request.POST:
            current_step += 1
        elif 'prev' in request.POST:
            current_step -= 1

    # Final context
    context = {
        'steps': steps,
        'current_step': current_step,
        'items': cart_items,
        'subtotal': subtotal,
        'tax': tax,
        'shipping': shipping_cost,
        'total': total,
        **data
    }

    return render(request, 'store/checkout.html', context)

def place_order(request):
    if request.method == 'POST':
        # your order logic here
        return redirect('order_success')  # or whatever page you redirect to
    return redirect('checkout')

def order_success(request):
    return render(request, 'store/checkout_success.html')

# Helper function to get or create the user's open cart (Order)
def get_or_create_open_order(user):
    order, created = Order.objects.get_or_create(
        user=user,
        status='Pending',
        defaults={
            'order_id': get_random_string(10).upper(),
            'total_amount': 0,
        }
    )
    return order

# Add to cart
@login_required
def add_to_cart(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        quantity = int(request.POST.get('quantity', 1))

        order = get_or_create_open_order(request.user)

        order_item, created = OrderItem.objects.get_or_create(
            order=order,
            product=product,
            defaults={'quantity': quantity, 'price': product.price}
        )

        if not created:
            order_item.quantity += quantity
            order_item.save()

        # Update order total
        total = sum(item.get_total_price() for item in order.items.all())
        order.total_amount = total
        order.save()

        return JsonResponse({'success': True, 'message': f'{product.name} added to cart!'})
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})

# Remove from cart
@login_required
def remove_from_cart(request, item_id):
    if request.method == 'POST':
        item = get_object_or_404(OrderItem, id=item_id, order__user=request.user, order__status='Pending')
        item.delete()

        # Recalculate total
        order = item.order
        order.total_amount = sum(i.get_total_price() for i in order.items.all())
        order.save()

    return redirect('cart_view')

def add_to_wishlist(request, product_id):
    if request.user.is_authenticated:
        product = get_object_or_404(Product, id=product_id)
        Wishlist.objects.get_or_create(user=request.user, product=product)
    return redirect('products')

def remove_wishlist(request, wishlist_id):
    if request.user.is_authenticated:
        wishlist_item = get_object_or_404(Wishlist, id=wishlist_id, user=request.user)
        wishlist_item.delete()
    return redirect('wishlist')


class ProductListCreateAPIView(generics.ListCreateAPIView):
    queryset = Product.objects.all().order_by('-created_at')
    serializer_class = ProductSerializer

class ProductRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    lookup_field = 'id'  # or use 'slug' if preferred