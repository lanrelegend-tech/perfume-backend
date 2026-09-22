from django.conf import settings
import resend


def send_order_confirmation_email(order):
    subject = f"Order Confirmation - {order.order_number}"

    if order.delivery_method == "pickup":
        fulfillment_info = f"""
Pickup Order:

Your order will be available for pickup at:

{order.pickup_address or "Pickup location will be provided by ORENTEMIST."}

We will notify you when your order is ready for pickup.
"""
    else:
        fulfillment_info = f"""
Delivery Address:

{order.address}
{order.city}, {order.state}

Your order will be delivered to the address above.
"""

    message = f"""
Hello {order.full_name},

Thank you for your order with ORENTEMIST.

Order Number: {order.order_number}

Total Amount: ₦{order.total_amount:,.2f}
Payment Status: {order.payment_status}
Order Status: {order.status}

{fulfillment_info}

We will keep you updated about your order.

Thank you for shopping with ORENTEMIST.
"""

    resend.api_key = settings.RESEND_API_KEY

    response = resend.Emails.send({
        "from": "ORENTEMIST <onboarding@resend.dev>",
        "to": [order.email],
        "subject": subject,
        "text": message,
    })

    print("RESEND ORDER EMAIL RESPONSE:", response)

    return response
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

    resend.api_key = settings.RESEND_API_KEY

    response = resend.Emails.send({
        "from": "ORENTEMIST <onboarding@resend.dev>",
        "to": [order.email],
        "subject": subject,
        "text": message,
    })

    print("RESEND SHIPPED EMAIL RESPONSE:", response)

    return response


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

    resend.api_key = settings.RESEND_API_KEY

    response = resend.Emails.send({
        "from": "ORENTEMIST <onboarding@resend.dev>",
        "to": [order.email],
        "subject": subject,
        "text": message,
    })

    print("RESEND DELIVERED EMAIL RESPONSE:", response)

    return response

def send_order_refund_email(order, refund):
    subject = f"Order Cancelled & Refund Processed - {order.order_number}"

    message = f"""
Hello {order.full_name},

Your ORENTEMIST order has been cancelled by our team.

Order Number:
{order.order_number}

Refund Amount:
₦{refund.amount:,.2f}

Your refund has been successfully requested through our payment provider and will be returned to your original payment method.

Refund Reference:
{refund.paystack_reference or "N/A"}

Reason:
{refund.reason or "Order cancelled by admin"}

Please note that the time it takes for the refunded funds to appear in your account may depend on your bank or payment provider.

If you have any questions about this refund, please contact our support team.

Thank you for shopping with ORENTEMIST.

ORENTEMIST
"""

    resend.api_key = settings.RESEND_API_KEY

    response = resend.Emails.send({
        "from": "ORENTEMIST <onboarding@resend.dev>",
        "to": [order.email],
        "subject": subject,
        "text": message,
    })

    print("RESEND REFUND EMAIL RESPONSE:", response)

    return response