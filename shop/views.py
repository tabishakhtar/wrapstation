from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.db.models import Sum
from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse
from reportlab.pdfgen import canvas
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import csv

from .models import (
    Product,
    Order,
    OrderItem,
    Cart,
    DeliveryAddress,
    Category,
    OrderTimeline,
    StaffCommission,
    Profile,
)
from .forms import DeliveryAddressForm, EmailLoginForm


# =================================================
# ROLE CHECK FUNCTIONS
# =================================================

def is_superuser(user):
    return user.is_superuser


def is_manager(user):
    return user.groups.filter(name='Manager').exists()


def is_staff_user(user):
    return user.is_staff and not user.is_superuser


# =================================================
# ROLE BASED REDIRECT
# =================================================

def role_redirect(request):
    if request.user.is_superuser:
        return redirect('admin_dashboard')
    elif is_manager(request.user):
        return redirect('manager_dashboard')
    elif request.user.is_staff:
        return redirect('staff_dashboard')
    else:
        return redirect('product_list')


# =================================================
# LOGIN SELECT
# =================================================

def select_login(request):
    return render(request, 'shop/select_login.html')


# =================================================
# PRODUCT LIST
# =================================================

def product_list(request):
    category_id = request.GET.get('category')
    categories = Category.objects.all()

    if category_id:
        products = Product.objects.filter(category_id=category_id, available=True)
    else:
        products = Product.objects.filter(available=True)

    return render(request, 'shop/product_list.html', {
        'products': products,
        'categories': categories
    })


# =================================================
# REGISTER
# =================================================
from django.shortcuts import render, redirect
from django.contrib.auth import login
from .forms import CustomerRegisterForm

def customer_register(request):
    if request.method == 'POST':
        form = CustomerRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')   # Automatically log user in
            return redirect('product_list')  # Make sure your home URL name is 'home'
    else:
        form = CustomerRegisterForm()

    return render(request, 'shop/register.html', {'form': form})
# =================================================
# CUSTOM LOGIN
# =================================================


from django.contrib.auth import authenticate, login

def login_view(request):
    role = request.GET.get("role")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        role = request.POST.get("role")

        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, "Invalid username or password.")
            return redirect(f"/login/?role={role}")

        # 🔒 STRICT ROLE CONTROL

        # ADMIN LOGIN
        if role == "admin":
            if not user.is_superuser:
                messages.error(request, "Only Admin can login here.")
                return redirect("/login/?role=admin")

        # STAFF LOGIN
        elif role == "staff":
            if not user.is_staff or user.is_superuser:
                messages.error(request, "Only Staff can login here.")
                return redirect("/login/?role=staff")

        # CUSTOMER LOGIN
        elif role == "customer":
            if user.is_staff or user.is_superuser:
                messages.error(request, "Admin/Staff cannot login as Customer.")
                return redirect("/login/?role=customer")

        else:
            messages.error(request, "Invalid login type.")
            return redirect("/login-select/")

        # ✅ If passed all checks
        login(request, user)
        return redirect("role_redirect")

    return render(request, "shop/login.html", {"role": role})

# =================================================
# ADMIN DASHBOARD
# =================================================

@user_passes_test(is_superuser)
def admin_dashboard(request):

    orders = Order.objects.all().order_by('-created_at')
    products = Product.objects.all()
    staff_members = User.objects.filter(is_staff=True, is_superuser=False)
    categories = Category.objects.all()

    total_orders = orders.count()
    pending_orders = orders.filter(status='Pending').count()
    delivered_orders = orders.filter(status='Delivered').count()

    total_revenue = orders.filter(
        payment_status='Paid'
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    return render(request, 'shop/admin_dashboard.html', {
        'orders': orders,
        'products': products,
        'staff_members': staff_members,
        'categories': categories,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'delivered_orders': delivered_orders,
        'total_revenue': total_revenue,
    })


# =================================================
# ADD CATEGORY (NEW - SAFE)
# =================================================

@user_passes_test(is_superuser)
def add_category(request):

    if request.method == "POST":
        name = request.POST.get("name")

        if name:
            Category.objects.create(name=name)
            messages.success(request, "Category added successfully")
            return redirect("add_category")

    categories = Category.objects.all()
    return render(request, "shop/add_category.html", {
        "categories": categories
    })


# =================================================
# DELETE CATEGORY (NEW - SAFE)
# =================================================

@user_passes_test(is_superuser)
def delete_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    category.delete()
    return redirect("add_category")


# =================================================
# CREATE STAFF
# =================================================

@user_passes_test(is_superuser)
def create_staff(request):

    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
        else:
            staff = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            staff.is_staff = True
            staff.save()

            staff_group, _ = Group.objects.get_or_create(name="Staff")
            staff.groups.add(staff_group)

            messages.success(request, "Staff created successfully")
            return redirect('admin_dashboard')

    return render(request, 'shop/create_staff.html')
# =================================================
# DELETE STAFF
# =================================================

@user_passes_test(is_superuser)
def delete_staff(request, staff_id):
    staff = get_object_or_404(User, id=staff_id, is_staff=True)
    staff.delete()
    messages.success(request, "Staff deleted successfully")
    return redirect('admin_dashboard')


# =================================================
# ADD / EDIT / DELETE PRODUCT (ALL IN ONE)
# =================================================

@user_passes_test(is_superuser)
def add_product(request):

    edit_id = request.GET.get("edit")
    delete_id = request.GET.get("delete")

    # DELETE PRODUCT
    if delete_id:
        product = get_object_or_404(Product, id=delete_id)
        product.delete()
        messages.success(request, "Product deleted successfully")
        return redirect("add_product")

    # EDIT PRODUCT
    if edit_id:
        product = get_object_or_404(Product, id=edit_id)
    else:
        product = None

    # SAVE (ADD OR UPDATE)
    if request.method == "POST":

        name = request.POST.get("name")
        description = request.POST.get("description")
        price = request.POST.get("price")
        stock = request.POST.get("stock")
        category_id = request.POST.get("category")
        image = request.FILES.get("image")

        if product:  # UPDATE
            product.name = name
            product.slug = name.replace(" ", "-").lower()
            product.description = description
            product.price = price
            product.stock = stock
            product.category_id = category_id
            if image:
                product.image = image
            product.save()
            messages.success(request, "Product updated successfully")
        else:  # CREATE
            Product.objects.create(
                name=name,
                slug=name.replace(" ", "-").lower(),
                description=description,
                price=price,
                stock=stock,
                category_id=category_id,
                image=image
            )
            messages.success(request, "Product added successfully")

        return redirect("add_product")

    products = Product.objects.all()
    categories = Category.objects.all()

    return render(request, "shop/add_product.html", {
        "products": products,
        "categories": categories,
        "edit_product": product
    })
# =================================================
# ALL YOUR OTHER FUNCTIONS REMAIN UNCHANGED
# (assign_order, update_status, cart, checkout, invoice, etc.)
# =================================================
# =================================================
# ASSIGN ORDER
# =================================================

@user_passes_test(is_superuser)
def assign_order(request, order_id):

    order = get_object_or_404(Order, id=order_id)
    staff_id = request.POST.get("staff")

    staff = User.objects.get(id=staff_id)
    order.assigned_to = staff
    order.status = "Out for Delivery"
    order.save()

    OrderTimeline.objects.create(order=order, status="Out for Delivery")

    return redirect('admin_dashboard')


# =================================================
# UPDATE STATUS (ADMIN)
# =================================================

# =================================================
# UPDATE STATUS (ADMIN - DROPDOWN SAFE VERSION)
# =================================================

@user_passes_test(is_superuser)
def update_status(request, order_id, new_status=None):

    order = get_object_or_404(Order, id=order_id)

    # If status comes from dropdown POST
    if request.method == "POST":
        new_status = request.POST.get("status")

    # Validate status safely
    if new_status and new_status in dict(Order.STATUS_CHOICES):

        order.status = new_status

        # Auto mark payment paid if delivered
        if new_status == "Delivered":
            order.payment_status = "Paid"

        order.save()

        OrderTimeline.objects.create(
            order=order,
            status=new_status
        )

        # WebSocket live update
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "orders",
            {
                "type": "send_update",
                "message": "Order Updated"
            }
        )

    return redirect('admin_dashboard')

# =================================================
# AJAX PAYMENT TOGGLE
# =================================================

@user_passes_test(is_superuser)
def toggle_payment_ajax(request, order_id):

    order = get_object_or_404(Order, id=order_id)

    if order.payment_status == "Paid":
        order.payment_status = "Unpaid"
    else:
        order.payment_status = "Paid"

    order.save()

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "orders",
        {
            "type": "send_update",
            "message": "Payment Updated"
        }
    )

    return JsonResponse({"status": order.payment_status})


# =================================================
# STAFF DASHBOARD
# =================================================
from decimal import Decimal
@user_passes_test(is_staff_user)
def staff_dashboard(request):
    orders = Order.objects.filter(assigned_to=request.user)
    return render(request, 'shop/staff_dashboard.html', {'orders': orders})


@user_passes_test(is_staff_user)
def staff_update_order(request, order_id):

    order = get_object_or_404(Order, id=order_id, assigned_to=request.user)
    order.status = "Delivered"
    order.payment_status = "Paid"
    order.save()

    # Commission 5%
    commission_amount = order.total_amount * Decimal("0.05")
    StaffCommission.objects.create(
        staff=request.user,
        order=order,
        commission_amount=commission_amount
    )

    OrderTimeline.objects.create(order=order, status="Delivered")

    return redirect('staff_dashboard')


# =================================================
# EXPORT CSV
# =================================================

@user_passes_test(is_superuser)
def export_orders_csv(request):

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="orders.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'User', 'Status', 'Payment', 'Total'])

    orders = Order.objects.all()

    for order in orders:
        writer.writerow([
            order.id,
            order.user.username,
            order.status,
            order.payment_status,
            order.total_amount
        ])

    return response


# =================================================
# CART & CHECKOUT
# =================================================

@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id, available=True)
    cart_item, created = Cart.objects.get_or_create(
        customer=request.user,
        product=product
    )
    if not created:
        cart_item.quantity += 1
    cart_item.save()
    return redirect('view_cart')


@login_required
def view_cart(request):
    cart_items = Cart.objects.filter(customer=request.user)
    total = sum(item.total_price() for item in cart_items)
    return render(request, 'shop/cart.html', {
        'cart_items': cart_items,
        'total': total
    })


@login_required
def checkout(request):

    cart_items = Cart.objects.filter(customer=request.user)

    if not cart_items.exists():
        return redirect('view_cart')

    total = sum(item.total_price() for item in cart_items)

    if request.method == "POST":
        form = DeliveryAddressForm(request.POST)
        payment_method = request.POST.get("payment_method")

        if form.is_valid():

            address = form.save(commit=False)
            address.user = request.user
            address.save()

            order = Order.objects.create(
                user=request.user,
                delivery_address=address,
                payment_method=payment_method,
                payment_status="Unpaid",
                total_amount=total,
                status="Pending"
            )

            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )

            OrderTimeline.objects.create(order=order, status="Pending")

            cart_items.delete()
            send_order_email(order)

            return redirect("order_success")

    else:
        form = DeliveryAddressForm()

    return render(request, "shop/checkout.html", {
        "form": form,
        "cart_items": cart_items,
        "total": total
    })
# =================================================
# ORDER SUCCESS
# =================================================

@login_required
def order_success(request):
    return render(request, "shop/order_success.html")


# =================================================
# MY ORDERS
# =================================================

@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user)
    return render(request, "shop/my_orders.html", {"orders": orders})


# =================================================
# CANCEL ORDER
# =================================================

@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.status == "Pending":
        order.status = "Cancelled"
        order.save()

    return redirect("my_orders")


# =================================================
# INCREASE CART QUANTITY
# =================================================

@login_required
def increase_quantity(request, cart_id):
    cart_item = get_object_or_404(
        Cart,
        id=cart_id,
        customer=request.user
    )
    cart_item.quantity += 1
    cart_item.save()
    return redirect("view_cart")


# =================================================
# DECREASE CART QUANTITY
# =================================================

@login_required
def decrease_quantity(request, cart_id):
    cart_item = get_object_or_404(
        Cart,
        id=cart_id,
        customer=request.user
    )

    if cart_item.quantity > 1:
        cart_item.quantity -= 1
        cart_item.save()
    else:
        cart_item.delete()

    return redirect("view_cart")


# =================================================
# REMOVE FROM CART
# =================================================

@login_required
def remove_from_cart(request, cart_id):
    cart_item = get_object_or_404(
        Cart,
        id=cart_id,
        customer=request.user
    )
    cart_item.delete()
    return redirect("view_cart")
# =================================================
# GENERATE PDF INVOICE
# =================================================

@login_required
def generate_invoice(request, order_id):

    order = get_object_or_404(
        Order,
        id=order_id,
        user=request.user
    )

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{order.id}.pdf"'

    p = canvas.Canvas(response)

    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 820, "Wrap Station")

    p.setFont("Helvetica", 12)
    p.drawString(100, 800, f"Invoice for Order #{order.id}")
    p.drawString(100, 780, f"Customer: {order.user.username}")
    p.drawString(100, 760, f"Total Amount: Rs {order.total_amount}")
    p.drawString(100, 740, f"Payment Method: {order.payment_method}")
    p.drawString(100, 720, f"Status: {order.status}")

    y = 680
    p.drawString(100, y, "Items:")
    y -= 20

    for item in order.items.all():
        product_name = item.product.name if item.product else "Deleted Product"
        p.drawString(
            120,
            y,
            f"{product_name} x{item.quantity} = Rs {item.quantity * item.price}"
        )
        y -= 20

    p.showPage()
    p.save()

    return response


# =================================================
# EMAIL
# =================================================

def send_order_email(order):
    subject = f"Wrap Station - Order Confirmation #{order.id}"
    message = f"""
Thank you for your order!

Order ID: {order.id}
Total Amount: Rs {order.total_amount}
Payment Method: {order.payment_method}

We will deliver your food soon!
"""
    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [order.user.email],
        fail_silently=True
    )
from django.contrib.auth.decorators import login_required

@login_required
def profile_dashboard(request):
    return render(request, 'shop/profile_dashboard.html')
@login_required
def edit_profile(request):
    if request.method == 'POST':
        request.user.email = request.POST.get('email')
        if request.FILES.get('profile_image'):
            request.user.profile.profile_image = request.FILES.get('profile_image')
        request.user.save()
        request.user.profile.save()
        return redirect('profile_dashboard')

    return render(request, 'shop/edit_profile.html') 