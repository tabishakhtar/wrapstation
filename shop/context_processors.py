from .models import Cart

def cart_counter(request):   # <-- MUST BE cart_counter
    if request.user.is_authenticated and not request.user.is_staff and not request.user.is_superuser:
        return {
            "cart_count": Cart.objects.filter(customer=request.user).count()
        }
    return {"cart_count": 0}