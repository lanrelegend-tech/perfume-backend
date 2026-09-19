from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate

from products.models import Product
from .models import Order, OrderItem,  Refund


def get_dashboard_stats():

    # -----------------------------
    # BASIC STATISTICS
    # -----------------------------

    total_orders = Order.objects.count()

    total_sales = (
        Order.objects.filter(
            payment_status="paid"
        ).aggregate(
            total=Sum("total_amount")
        )["total"]
        or Decimal("0.00")
    )

    pending_orders = Order.objects.filter(
        status="pending"
    ).count()
    

    confirmed_orders = Order.objects.filter(
        status="confirmed"
    ).count()

    processing_orders = Order.objects.filter(
        status="processing"
    ).count()

    shipped_orders = Order.objects.filter(
        status="shipped"
    ).count()
    product_sales = (
        OrderItem.objects.filter(
            order__payment_status="paid"
        )
        .values(
            "product",
            "product_name",
            "product_brand",
        )
        .annotate(
            units_sold=Sum("quantity"),
            revenue=Sum("subtotal"),
            order_count=Count("order", distinct=True),
        )
        .order_by("-units_sold")[:10]
    )
    refunded_amount = (
        Refund.objects.filter(
        status="processed"
         ).aggregate(
        total=Sum("amount")
        )["total"]
        or Decimal("0.00")
    )

    net_sales = total_sales - refunded_amount
    top_products = []

    for product in product_sales:
        top_products.append({
            "product_id": product["product"],
            "product_name": product["product_name"],
            "brand": product["product_brand"],
            "units_sold": product["units_sold"],
            "revenue": str(
                product["revenue"] or Decimal("0.00")
            ),
            "order_count": product["order_count"],
        })   
    # -----------------------------
    # COUPON ANALYTICS
    # -----------------------------

    total_coupon_usage = Order.objects.filter(
        coupon__isnull=False,
        payment_status="paid"
    ).count()

    total_discounts = (
        Order.objects.filter(
            payment_status="paid"
        ).aggregate(
            total=Sum("discount_amount")
        )["total"]
        or Decimal("0.00")
    )

    # -----------------------------
    # TOP CUSTOMERS
    # -----------------------------

    customer_sales = (
        Order.objects.filter(
            payment_status="paid"
        )
        .values(
            "user",
            "full_name",
            "email",
        )
        .annotate(
            total_spent=Sum("total_amount"),
            order_count=Count("id"),
        )
        .order_by("-total_spent")[:10]
    )

    top_customers = []

    for customer in customer_sales:
        top_customers.append({
            "user_id": customer["user"],
            "name": customer["full_name"],
            "email": customer["email"],
            "total_spent": str(
                customer["total_spent"] or Decimal("0.00")
            ),
            "order_count": customer["order_count"],
        })         

    delivered_orders = Order.objects.filter(
        status="delivered"
    ).count()

    total_customers = User.objects.filter(
        is_staff=False
    ).count()

    total_products = Product.objects.count()

    # -----------------------------
    # RECENT ORDERS
    # -----------------------------

    recent_orders = []

    orders = Order.objects.select_related(
        "user"
    ).order_by(
        "-created_at"
    )[:10]

    for order in orders:
        recent_orders.append({
            "id": order.id,
            "order_number": order.order_number,
            "customer": order.full_name,
            "email": order.email,
            "total_amount": str(order.total_amount),
            "payment_status": order.payment_status,
            "status": order.status,
            "created_at": order.created_at,
        })

    # -----------------------------
    # SALES BY DAY
    # -----------------------------

    sales_by_day = (
        Order.objects.filter(
            payment_status="paid"
        )
        .annotate(
            date=TruncDate("created_at")
        )
        .values("date")
        .annotate(
            total=Sum("total_amount")
        )
        .order_by("date")
    )

    sales_chart = []

    for sale in sales_by_day:
        sales_chart.append({
            "date": sale["date"],
            "total": str(
                sale["total"] or Decimal("0.00")
            ),
        })

    # -----------------------------
    # RETURN DASHBOARD DATA
    # -----------------------------

    return {
        "statistics": {
            "total_orders": total_orders,
            "total_sales": str(total_sales),
            "pending_orders": pending_orders,
            "confirmed_orders": confirmed_orders,
            "processing_orders": processing_orders,
            "shipped_orders": shipped_orders,
            "delivered_orders": delivered_orders,
            "total_customers": total_customers,
            "total_products": total_products,
             "gross_sales": str(total_sales),

             "refunded_amount": str(refunded_amount),

             "net_sales": str(net_sales),
        },

        "recent_orders": recent_orders,

        "sales_chart": sales_chart,
                "top_products": top_products,

        "coupon_analytics": {
            "total_coupon_usage": total_coupon_usage,
            "total_discounts": str(total_discounts),
        },

        "top_customers": top_customers,
    }