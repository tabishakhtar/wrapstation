from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views
from .views import customer_register
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [

    # ==========================
    # HOME
    # ==========================
    path('', views.product_list, name='product_list'),

    # ==========================
    # AUTHENTICATION
    # ==========================
    path('register/', views.customer_register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),

    # ==========================
    # CART
    # ==========================
    path('cart/', views.view_cart, name='view_cart'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('increase/<int:cart_id>/', views.increase_quantity, name='increase_quantity'),
    path('decrease/<int:cart_id>/', views.decrease_quantity, name='decrease_quantity'),
    path('remove/<int:cart_id>/', views.remove_from_cart, name='remove_from_cart'),

    # ==========================
    # CHECKOUT
    # ==========================
    path('checkout/', views.checkout, name='checkout'),
    path('order-success/', views.order_success, name='order_success'),

    # ==========================
    # USER ORDERS
    # ==========================
    path('my-orders/', views.my_orders, name='my_orders'),
    path('cancel-order/<int:order_id>/', views.cancel_order, name='cancel_order'),
    path('invoice/<int:order_id>/', views.generate_invoice, name='generate_invoice'),

    # ==========================
    # CUSTOM ADMIN PANEL
    # ==========================
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path(
    'update-status/<int:order_id>/<str:new_status>/',
    views.update_status,
    name='update_status'
    ),
    path(
    'update-status/<int:order_id>/<str:new_status>/',
    views.update_status,
    name='update_status'
    ),
    path('login-select/', views.select_login, name='select_login'),
    path('role-redirect/', views.role_redirect, name='role_redirect'),
    path('staff-dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('create-staff/', views.create_staff, name='create_staff'),
    path('add-product/', views.add_product, name='add_product'),
    path('assign-order/<int:order_id>/', views.assign_order, name='assign_order'),
    path('staff-update/<int:order_id>/', views.staff_update_order, name='staff_update_order'),
    path('delete-staff/<int:staff_id>/', views.delete_staff, name='delete_staff'),
    path('toggle-payment/<int:order_id>/', views.toggle_payment_ajax),
    path('export-orders/', views.export_orders_csv, name='export_orders'),
    path('add-category/', views.add_category, name='add_category'),
    path('delete-category/<int:category_id>/', views.delete_category, name='delete_category'),
    path('profile/', views.profile_dashboard, name='profile_dashboard'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    
]
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('shop.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)