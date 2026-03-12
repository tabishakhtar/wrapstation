from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver


# =================================================
# RESTAURANT (SaaS Multi-Tenant Support)
# =================================================
class Restaurant(models.Model):
    name = models.CharField(max_length=200)
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="owned_restaurants"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# =================================================
# CATEGORY
# =================================================
class Category(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="categories",
        null=True,
        blank=True
    )

    name = models.CharField(max_length=100)
    slug = models.SlugField()

    class Meta:
        ordering = ['name']
        unique_together = ('restaurant', 'slug')

    def __str__(self):
        return self.name


# =================================================
# PRODUCT
# =================================================
from cloudinary.models import CloudinaryField
class Product(models.Model):

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="products",
        null=True,
        blank=True
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    name = models.CharField(max_length=200)
    slug = models.SlugField()
    description = models.TextField()

    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = CloudinaryField('image')
    stock = models.PositiveIntegerField(default=0)
    available = models.BooleanField(default=True)

    order_position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order_position', '-created_at']
        unique_together = ('restaurant', 'slug')

    def __str__(self):
        return self.name

    def is_in_stock(self):
        return self.stock > 0


# =================================================
# DELIVERY ADDRESS
# =================================================
class DeliveryAddress(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="addresses"
    )

    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    address_line = models.TextField()
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} - {self.city}"


# =================================================
# ORDER
# =================================================
class Order(models.Model):

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Preparing', 'Preparing'),
        ('Out for Delivery', 'Out for Delivery'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
    ]

    PAYMENT_METHODS = [
        ('COD', 'Cash on Delivery'),
        ('JazzCash', 'JazzCash'),
    ]

    PAYMENT_STATUS = [
        ('Unpaid', 'Unpaid'),
        ('Paid', 'Paid'),
        ('Failed', 'Failed'),
    ]

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="orders"
    )

    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_orders"
    )

    delivery_address = models.ForeignKey(
        DeliveryAddress,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='Pending'
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS,
        default='Unpaid'
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    transaction_id = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    delivery_lat = models.FloatField(null=True, blank=True)
    delivery_lng = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.id} - {self.user.username}"

    def calculate_total(self):
        total = sum(item.get_total() for item in self.items.all())
        self.total_amount = total
        self.save()
        return total


# =================================================
# ORDER TIMELINE
# =================================================
class OrderTimeline(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="timeline"
    )
    status = models.CharField(max_length=50)
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.order.id} - {self.status}"


# =================================================
# ORDER ITEM
# =================================================
class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    def save(self, *args, **kwargs):
        if self.product and not self.pk:
            if self.product.stock >= self.quantity:
                self.product.stock -= self.quantity
                self.product.save()
            else:
                raise ValueError("Not enough stock")

        super().save(*args, **kwargs)

    def get_total(self):
        return self.quantity * self.price

    def __str__(self):
        product_name = self.product.name if self.product else "Deleted Product"
        return f"{product_name} (x{self.quantity})"


# =================================================
# STAFF COMMISSION
# =================================================
class StaffCommission(models.Model):
    staff = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="commissions"
    )

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE
    )

    commission_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.staff.username} - Rs {self.commission_amount}"


# =================================================
# CART
# =================================================
class Cart(models.Model):
    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="cart_items"
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE
    )

    quantity = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('customer', 'product')

    def total_price(self):
        return self.quantity * self.product.price

    def __str__(self):
        return f"{self.product.name} ({self.quantity})"


# =================================================
# PROFILE (FIXED SAFE VERSION)
# =================================================
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_image = models.ImageField(
        upload_to='profiles/',
        default='profiles/default.png'
    )

    def __str__(self):
        return self.user.username


# =================================================
# PROFILE SIGNALS (SAFE VERSION)
# =================================================
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()