from django.core.mail import send_mail
from django.conf import settings

def send_order_email(order):
    subject = f"Wrap Station - Order Confirmation #{order.id}"

    message = f"""
Thank you for your order!

Order ID: {order.id}
Total Amount: Rs {order.total_amount}
Payment Method: {order.payment_method}

Your food is being prepared.
"""

    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [order.user.email],
        fail_silently=False,
    )