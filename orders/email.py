from django.conf import settings
from django.core.mail import send_mail


def send_order_confirmation_email(order):
    subject = f"Order Confirmation - {order.order_number}"

    message = f"""
Hello {order.full_name},

Thank you for your order.

Order Number: {order.order_number}
Total Amount: ₦{order.total_amount:,.2f}
Payment Status: {order.payment_status}
Order Status: {order.status}

Shipping Address:
{order.address}
{order.city}, {order.state}

We will notify you when your order is shipped.

Thank you for shopping with us.
"""

    sent_count = send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [order.email],
        fail_silently=False,
    )

    print("================================")
    print("ORDER EMAIL SENT COUNT:", sent_count)
    print("ORDER EMAIL TO:", order.email)
    print("ORDER EMAIL FROM:", settings.DEFAULT_FROM_EMAIL)
    print("================================")


def send_order_shipped_email(order):
    subject = f"Your Order Has Been Shipped - {order.order_number}"

    tracking_info = order.tracking_number or "Not provided"

    courier_info = order.courier or "Not provided"

    message = f"""
Hello {order.full_name},

Good news! Your order has been shipped.

Order Number: {order.order_number}

Courier:
{courier_info}

Tracking Number:
{tracking_info}

Shipping Address:
{order.address}
{order.city}, {order.state}

You can use the tracking number with the courier to track your package.

Thank you for shopping with us.
"""

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [order.email],
        fail_silently=True,
    )


def send_order_delivered_email(order):
    subject = f"Your Order Has Been Delivered - {order.order_number}"

    message = f"""
Hello {order.full_name},

Your order has been delivered successfully.

Order Number: {order.order_number}
Total Amount: ₦{order.total_amount:,.2f}

Delivery Address:
{order.address}
{order.city}, {order.state}

Thank you for shopping with us.

We hope you enjoy your purchase.
"""

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [order.email],
        fail_silently=True,
    )