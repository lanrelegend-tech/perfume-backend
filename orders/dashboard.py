from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncDate

from products.models import Product
from .models import Order, OrderItem,  Refund


CACHE_KEY = "admin_dashboard_stats_v1"
CACHE_TIMEOUT_SECONDS = 60


def get_dashboard_stats():
    cached_stats = cache.get(CACHE_KEY)

    if cached_stats is not None:
        return cached_stats

    # -----------------------------
    # BASIC STATISTICS
    # -----------------------------

    order_summary = Order.objects.aggregate(
        total_orders=Count("id"),
        paid_orders=Count(
            "id",
            filter=Q(payment_status="paid"),
        ),
        pending_orders=Count(
            "id",
            filter=Q(status="pending"),
        ),
        confirmed_orders=Count(
            "id",
            filter=Q(status="confirmed"),
        ),
        processing_orders=Count(
            "id",
            filter=Q(status="processing"),
        ),
        shipped_orders=Count(
            "id",
            filter=Q(status="shipped"),
        ),
        delivered_orders=Count(
            "id",
            filter=Q(status="delivered"),
        ),
        cancelled_orders=Count(
            "id",
            filter=Q(status="cancelled"),
        ),
        total_sales=Sum(
            "total_amount",
            filter=Q(payment_status="paid"),
        ),
        delivery_fees=Sum(
            "delivery_fee",
            filter=Q(payment_status="paid"),
        ),
        total_discounts=Sum(
            "discount_amount",
            filter=Q(payment_status="paid"),
        ),
        total_coupon_usage=Count(
            "id",
            filter=Q(
                payment_status="paid",
                coupon__isnull=False,
            ),
        ),
    )

    total_orders = order_summary["total_orders"] or 0
    paid_orders_count = order_summary["paid_orders"] or 0
    pending_orders = order_summary["pending_orders"] or 0
    confirmed_orders = order_summary["confirmed_orders"] or 0
    processing_orders = order_summary["processing_orders"] or 0
    shipped_orders = order_summary["shipped_orders"] or 0
    delivered_orders = order_summary["delivered_orders"] or 0
    cancelled_orders = order_summary["cancelled_orders"] or 0
    total_sales = order_summary["total_sales"] or Decimal("0.00")
    delivery_fees = order_summary["delivery_fees"] or Decimal("0.00")
    total_discounts = order_summary["total_discounts"] or Decimal("0.00")
    total_coupon_usage = order_summary["total_coupon_usage"] or 0

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

    total_items_sold = (
        OrderItem.objects.filter(
            order__payment_status="paid"
        ).aggregate(
            total=Sum("quantity")
        )["total"]
        or 0
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
    average_order_value = (
        total_sales / paid_orders_count
        if paid_orders_count
        else Decimal("0.00")
    )
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

    # -----------------------------
    # CUSTOMER MIX
    # -----------------------------

    customer_order_counts = (
        Order.objects.filter(
            payment_status="paid"
        )
        .values("email")
        .annotate(order_count=Count("id"))
    )

    new_customers = 0
    returning_customers = 0

    for customer in customer_order_counts:
        if customer["order_count"] > 1:
            returning_customers += 1
        else:
            new_customers += 1

    customer_mix_total = new_customers + returning_customers

    customer_mix = [
        {
            "label": "New Customers",
            "value": new_customers,
            "percentage": round(
                (new_customers / customer_mix_total) * 100
            ) if customer_mix_total else 0,
        },
        {
            "label": "Returning Customers",
            "value": returning_customers,
            "percentage": round(
                (returning_customers / customer_mix_total) * 100
            ) if customer_mix_total else 0,
        },
    ]

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

    recent_sales = []

    paid_recent_orders = (
        Order.objects.select_related(
            "user",
            "coupon",
        )
        .prefetch_related("items")
        .filter(payment_status="paid")
        .order_by("-created_at")[:5]
    )

    for order in paid_recent_orders:
        items = list(order.items.all())
        first_item = items[0] if items else None
        discount_amount = order.discount_amount or Decimal("0.00")
        coupon_code = getattr(order.coupon, "code", "") if order.coupon else ""

        recent_sales.append({
            "id": order.order_number or f"#{order.id}",
            "customer": order.full_name or order.email or "Customer",
            "product": first_item.product_name if first_item else "Order",
            "amount": str(order.total_amount),
            "discount": str(discount_amount),
            "discount_label": (
                "None"
                if discount_amount <= Decimal("0.00")
                else str(discount_amount)
            ),
            "coupon": coupon_code,
            "delivery": str(order.delivery_fee or Decimal("0.00")),
            "status": order.status,
            "date": order.created_at,
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
            total=Sum("total_amount"),
            orders=Count("id"),
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
            "orders": sale["orders"],
        })

    # -----------------------------
    # SALES BY CATEGORY
    # -----------------------------

    category_sales = (
        OrderItem.objects.filter(
            order__payment_status="paid"
        )
        .values("product__category__name")
        .annotate(
            revenue=Sum("subtotal"),
            sales=Sum("quantity"),
        )
        .order_by("-revenue")[:6]
    )

    category_total = sum(
        category["revenue"] or Decimal("0.00")
        for category in category_sales
    )

    category_data = []

    for category in category_sales:
        revenue = category["revenue"] or Decimal("0.00")

        category_data.append({
            "name": category["product__category__name"] or "Uncategorized",
            "revenue": str(revenue),
            "sales": category["sales"] or 0,
            "percentage": round(
                (revenue / category_total) * 100
            ) if category_total else 0,
        })

    # -----------------------------
    # RETURN DASHBOARD DATA
    # -----------------------------

    stats = {
        "total_orders": total_orders,
        "total_sales": str(total_sales),
        "pending_orders": pending_orders,
        "confirmed_orders": confirmed_orders,
        "processing_orders": processing_orders,
        "shipped_orders": shipped_orders,
        "cancelled_orders": cancelled_orders,
        "delivered_orders": delivered_orders,
        "total_customers": total_customers,
        "total_products": total_products,
        "paid_orders": paid_orders_count,
        "total_items_sold": total_items_sold,
        "gross_sales": str(total_sales),
        "delivery_fees": str(delivery_fees),
        "refunded_amount": str(refunded_amount),
        "net_sales": str(net_sales),
        "average_order_value": str(average_order_value),

        "statistics": {
            "total_orders": total_orders,
            "total_sales": str(total_sales),
            "pending_orders": pending_orders,
            "confirmed_orders": confirmed_orders,
            "processing_orders": processing_orders,
            "shipped_orders": shipped_orders,
            "cancelled_orders": cancelled_orders,
            "delivered_orders": delivered_orders,
            "total_customers": total_customers,
            "total_products": total_products,
            "paid_orders": paid_orders_count,
            "total_items_sold": total_items_sold,
             "gross_sales": str(total_sales),

             "delivery_fees": str(delivery_fees),

             "refunded_amount": str(refunded_amount),

             "net_sales": str(net_sales),
             "average_order_value": str(average_order_value),
        },

        "recent_orders": recent_orders,
        "recent_sales": recent_sales,

        "sales_chart": sales_chart,
                "top_products": top_products,
        "category_data": category_data,

        "coupon_analytics": {
            "total_coupon_usage": total_coupon_usage,
            "total_discounts": str(total_discounts),
        },

        "top_customers": top_customers,
        "customer_mix": customer_mix,
    }

    cache.set(
        CACHE_KEY,
        stats,
        CACHE_TIMEOUT_SECONDS,
    )

    return stats
