from django.conf import settings
from django.utils.html import escape
import resend


# =========================================================
# ORENTEMIST EMAIL HELPER
# =========================================================

def send_orentemist_email(
    to_email,
    subject,
    heading,
    message,
    footer_message=None,
    details=None,
    items=None,
):
    footer = footer_message or (
        "If you have any questions, please contact "
        "ORENTEMIST Customer Support."
    )

    details_html = ""

    if details:
        detail_rows = ""

        for label, value in details:
            detail_rows += f"""
                <tr>
                    <td style="
                        padding: 11px 0;
                        color: #999999;
                        font-size: 10px;
                        font-weight: 600;
                        letter-spacing: 1.5px;
                        text-transform: uppercase;
                        vertical-align: top;
                        width: 40%;
                    ">
                        {escape(str(label))}
                    </td>

                    <td style="
                        padding: 11px 0;
                        color: #111111;
                        font-size: 13px;
                        line-height: 1.6;
                        vertical-align: top;
                    ">
                        {escape(str(value))}
                    </td>
                </tr>
            """

        details_html = f"""
            <div style="
                margin: 28px 0;
                padding: 20px 22px;
                background: #f8f7f4;
                border: 1px solid #e5e2dc;
                border-radius: 16px;
            ">
                <table
                    width="100%"
                    cellpadding="0"
                    cellspacing="0"
                    border="0"
                    style="border-collapse: collapse;"
                >
                    {detail_rows}
                </table>
            </div>
        """

    # =====================================================
    # ORDER ITEMS
    # =====================================================

    items_html = ""

    if items:
        item_rows = ""

        for item in items:
            product = getattr(item, "product", None)

            product_name = (
                getattr(product, "name", None)
                or getattr(item, "product_name", None)
                or "ORENTEMIST Fragrance"
            )

            quantity = getattr(item, "quantity", 1)

            price = getattr(
                item,
                "product_price",
                getattr(product, "price", 0),
            )

            subtotal = getattr(
                item,
                "subtotal",
                None,
            )

            if subtotal is None:
                try:
                    subtotal = price * quantity
                except Exception:
                    subtotal = 0

            variant = getattr(item, "variant", None)

            variant_size = ""

            if variant:
                variant_size = (
                    getattr(variant, "size", None)
                    or getattr(variant, "name", None)
                    or ""
                )

            size_html = ""

            if variant_size:
                size_html = f"""
                    <div style="
                        margin-top: 4px;
                        color: #999999;
                        font-size: 11px;
                    ">
                        Size: {escape(str(variant_size))}
                    </div>
                """

            item_rows += f"""
                <tr>
                    <td style="
                        padding: 15px 0;
                        border-bottom: 1px solid #eeeeee;
                    ">
                        <div style="
                            color: #111111;
                            font-size: 14px;
                            font-weight: 600;
                            line-height: 1.5;
                        ">
                            {escape(str(product_name))}
                        </div>

                        {size_html}

                        <div style="
                            margin-top: 5px;
                            color: #999999;
                            font-size: 11px;
                        ">
                            Qty: {escape(str(quantity))}
                        </div>
                    </td>

                    <td style="
                        padding: 15px 0;
                        border-bottom: 1px solid #eeeeee;
                        text-align: right;
                        vertical-align: top;
                        white-space: nowrap;
                    ">
                        <div style="
                            color: #111111;
                            font-size: 13px;
                            font-weight: 600;
                        ">
                            ₦{float(subtotal):,.2f}
                        </div>

                        <div style="
                            margin-top: 5px;
                            color: #999999;
                            font-size: 10px;
                        ">
                            ₦{float(price):,.2f} each
                        </div>
                    </td>
                </tr>
            """

        items_html = f"""
            <div style="
                margin: 30px 0;
            ">

                <div style="
                    margin-bottom: 12px;
                    color: #999999;
                    font-size: 10px;
                    font-weight: 600;
                    letter-spacing: 2px;
                    text-transform: uppercase;
                ">
                    Your Fragrance
                </div>

                <div style="
                    padding: 5px 20px;
                    border: 1px solid #e5e2dc;
                    border-radius: 16px;
                    background: #ffffff;
                ">

                    <table
                        width="100%"
                        cellpadding="0"
                        cellspacing="0"
                        border="0"
                        style="border-collapse: collapse;"
                    >
                        {item_rows}
                    </table>

                </div>

            </div>
        """

    # =====================================================
    # HTML EMAIL
    # =====================================================

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{escape(str(subject))}</title>
    </head>

    <body style="
        margin: 0;
        padding: 0;
        background: #f4f3f0;
        font-family: Arial, Helvetica, sans-serif;
        color: #111111;
    ">

        <div style="
            width: 100%;
            padding: 40px 15px;
            box-sizing: border-box;
        ">

            <div style="
                max-width: 600px;
                margin: 0 auto;
                background: #ffffff;
                border: 1px solid #e8e6e1;
                border-radius: 24px;
                overflow: hidden;
            ">

                <!-- HEADER -->

                <div style="
                    padding: 36px 30px;
                    border-bottom: 1px solid #eeeeee;
                    text-align: center;
                ">

                    <div style="
                        font-size: 22px;
                        font-weight: 700;
                        letter-spacing: 5px;
                        color: #111111;
                    ">
                        ORENTEMIST
                    </div>

                    <div style="
                        margin-top: 9px;
                        color: #999999;
                        font-size: 9px;
                        letter-spacing: 3px;
                        text-transform: uppercase;
                    ">
                        The Art of Fragrance
                    </div>

                </div>

                <!-- MAIN CONTENT -->

                <div style="
                    padding: 42px 35px;
                ">

                    <p style="
                        margin: 0 0 12px;
                        color: #999999;
                        font-size: 10px;
                        font-weight: 600;
                        letter-spacing: 3px;
                        text-transform: uppercase;
                    ">
                        ORENTEMIST
                    </p>

                    <h1 style="
                        margin: 0 0 18px;
                        font-size: 29px;
                        line-height: 1.3;
                        font-weight: 600;
                        color: #111111;
                    ">
                        {escape(str(heading))}
                    </h1>

                    <p style="
                        margin: 0;
                        color: #666666;
                        font-size: 15px;
                        line-height: 1.8;
                    ">
                        {message}
                    </p>

                    {items_html}

                    {details_html}

                    <div style="
                        margin-top: 30px;
                        padding-top: 25px;
                        border-top: 1px solid #eeeeee;
                    ">

                        <p style="
                            margin: 0;
                            color: #888888;
                            font-size: 12px;
                            line-height: 1.8;
                        ">
                            {escape(str(footer))}
                        </p>

                    </div>

                </div>

                <!-- FOOTER -->

                <div style="
                    padding: 28px 35px;
                    background: #faf9f7;
                    border-top: 1px solid #eeeeee;
                    text-align: center;
                ">

                    <p style="
                        margin: 0;
                        color: #999999;
                        font-size: 11px;
                        line-height: 1.8;
                    ">
                        © ORENTEMIST
                        <br>
                        Crafted for those who leave an impression.
                    </p>

                </div>

            </div>

        </div>

    </body>
    </html>
    """

    # =====================================================
    # PLAIN TEXT VERSION
    # =====================================================

    plain_text = (
        "ORENTEMIST\n"
        "The Art of Fragrance\n\n"
        f"{heading}\n\n"
        f"{message}\n\n"
    )

    if items:
        plain_text += "YOUR FRAGRANCE\n"
        plain_text += "------------------------------\n"

        for item in items:
            product = getattr(item, "product", None)

            product_name = (
                getattr(product, "name", None)
                or getattr(item, "product_name", None)
                or "ORENTEMIST Fragrance"
            )

            quantity = getattr(
                item,
                "quantity",
                1,
            )

            price = getattr(
                item,
                "product_price",
                getattr(product, "price", 0),
            )

            subtotal = getattr(
                item,
                "subtotal",
                None,
            )

            if subtotal is None:
                try:
                    subtotal = price * quantity
                except Exception:
                    subtotal = 0

            plain_text += (
                f"{product_name}\n"
                f"Quantity: {quantity}\n"
                f"Price: ₦{float(price):,.2f}\n"
                f"Subtotal: ₦{float(subtotal):,.2f}\n\n"
            )

    if details:
        plain_text += "\nORDER DETAILS\n"
        plain_text += "------------------------------\n"

        for label, value in details:
            plain_text += (
                f"{label}: {value}\n"
            )

        plain_text += "\n"

    plain_text += (
        f"{footer}\n\n"
        "ORENTEMIST Customer Support"
    )

    resend.api_key = settings.RESEND_API_KEY

    response = resend.Emails.send(
        {
            "from": "ORENTEMIST <onboarding@resend.dev>",
            "to": [to_email],
            "subject": subject,
            "html": html,
            "text": plain_text,
        }
    )

    return response


# =========================================================
# ORDER CONFIRMATION
# =========================================================

def send_order_confirmation_email(order):

    subject = (
        f"Your ORENTEMIST Order Is Confirmed — "
        f"{order.order_number}"
    )

    if order.delivery_method == "pickup":

        fulfillment_message = (
            "Your fragrance is now being prepared for "
            "pickup. We will let you know when your order "
            "is ready to collect."
        )

        fulfillment_details = (
            "Pickup Location",
            order.pickup_address
            or "Pickup location will be provided by ORENTEMIST.",
        )

    else:

        fulfillment_message = (
            "Your fragrance is now being prepared for "
            "delivery to the address provided below."
        )

        fulfillment_details = (
            "Delivery Address",
            f"{order.address}, {order.city}, {order.state}",
        )

    first_name = (
        order.full_name.split()[0]
        if order.full_name
        else "there"
    )

    return send_orentemist_email(
        to_email=order.email,
        subject=subject,

        heading="Thank you for your order.",

        message=(
            f"Hello {escape(str(first_name))}, "
            "thank you for choosing ORENTEMIST. "
            "We are delighted to have your order with us. "
            "Your fragrance has been successfully received "
            "and our team is preparing it for you. "
            f"{fulfillment_message} "
            "We truly appreciate your trust in ORENTEMIST."
        ),

        footer_message=(
            "We will keep you updated as your order moves "
            "through each stage of fulfillment. "
            "Thank you for choosing ORENTEMIST — "
            "we hope your fragrance becomes part of "
            "your signature."
        ),

        items=order.items.all(),

        details=[
            (
                "Order Number",
                order.order_number,
            ),
            (
                "Total",
                f"₦{order.total_amount:,.2f}",
            ),
            (
                "Payment",
                str(order.payment_status)
                .replace("_", " ")
                .title(),
            ),
            (
                "Status",
                str(order.status)
                .replace("_", " ")
                .title(),
            ),
            fulfillment_details,
        ],
    )


# =========================================================
# ORDER SHIPPED
# =========================================================

def send_order_shipped_email(order):

    subject = (
        f"Your ORENTEMIST Order Has Shipped — "
        f"{order.order_number}"
    )

    tracking_number = (
        order.tracking_number
        or "Not provided"
    )

    courier = (
        order.courier
        or "Not provided"
    )

    first_name = (
        order.full_name.split()[0]
        if order.full_name
        else "there"
    )

    return send_orentemist_email(
        to_email=order.email,
        subject=subject,

        heading="Your fragrance is on its way.",

        message=(
            f"Hello {escape(str(first_name))}, "
            "good news — your ORENTEMIST fragrance "
            "has left us and is now on its way to you. "
            "We hope you're excited to receive it."
        ),

        footer_message=(
            "You can use the tracking information above "
            "with the courier to follow your delivery. "
            "Thank you for choosing ORENTEMIST."
        ),

        items=order.items.all(),

        details=[
            (
                "Order Number",
                order.order_number,
            ),
            (
                "Courier",
                courier,
            ),
            (
                "Tracking Number",
                tracking_number,
            ),
            (
                "Shipping Address",
                f"{order.address}, "
                f"{order.city}, "
                f"{order.state}",
            ),
        ],
    )


# =========================================================
# ORDER DELIVERED
# =========================================================

def send_order_delivered_email(order):

    subject = (
        f"Your ORENTEMIST Order Has Been Delivered — "
        f"{order.order_number}"
    )

    first_name = (
        order.full_name.split()[0]
        if order.full_name
        else "there"
    )

    return send_orentemist_email(
        to_email=order.email,
        subject=subject,

        heading="Your fragrance has arrived.",

        message=(
            f"Hello {escape(str(first_name))}, "
            "your ORENTEMIST order has been successfully "
            "delivered. Your fragrance is now yours to enjoy. "
            "We hope it becomes a beautiful part of your "
            "everyday moments and leaves an impression "
            "wherever you go."
        ),

        footer_message=(
            "Thank you for choosing ORENTEMIST. "
            "We are grateful to have you as part of "
            "our fragrance journey."
        ),

        items=order.items.all(),

        details=[
            (
                "Order Number",
                order.order_number,
            ),
            (
                "Total Amount",
                f"₦{order.total_amount:,.2f}",
            ),
            (
                "Delivery Address",
                f"{order.address}, "
                f"{order.city}, "
                f"{order.state}",
            ),
        ],
    )


# =========================================================
# ORDER REFUND
# =========================================================

def send_order_refund_email(order, refund):

    subject = (
        f"ORENTEMIST Refund Processed — "
        f"{order.order_number}"
    )

    refund_reference = (
        refund.paystack_reference
        or "N/A"
    )

    refund_reason = (
        refund.reason
        or "Order cancelled by admin"
    )

    first_name = (
        order.full_name.split()[0]
        if order.full_name
        else "there"
    )

    return send_orentemist_email(
        to_email=order.email,
        subject=subject,

        heading="Your refund has been processed.",

        message=(
            f"Hello {escape(str(first_name))}, "
            "your ORENTEMIST order has been cancelled "
            "and your refund has been requested through "
            "our payment provider. "
            "We understand that plans can change, and "
            "we appreciate your patience while the refund "
            "is completed."
        ),

        footer_message=(
            "The time required for refunded funds to appear "
            "in your account may depend on your bank or "
            "payment provider. If you have any questions, "
            "please contact ORENTEMIST Customer Support."
        ),

        items=order.items.all(),

        details=[
            (
                "Order Number",
                order.order_number,
            ),
            (
                "Refund Amount",
                f"₦{refund.amount:,.2f}",
            ),
            (
                "Refund Reference",
                refund_reference,
            ),
            (
                "Reason",
                refund_reason,
            ),
        ],
    )