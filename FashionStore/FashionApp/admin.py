from django.contrib import admin
from .models import *

# Register your models here.
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(CartItem)
admin.site.register(Wishlist)
admin.site.register(Address)
admin.site.register(Review)
admin.site.register(NotificationPreference)

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'website')  # example
    search_fields = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'category', 'price')
    list_filter = ('brand', 'category')
    search_fields = ('name',)

class BrandInline(admin.TabularInline):
    model = Brand
    extra = 1

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    inlines = [BrandInline]