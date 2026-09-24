from django.conf import settings
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
                        padding: 12px 0;
                        color: #999;
                        font-size: 11px;
                        font-weight: 600;
                        letter-spacing: 1.5px;
                        text-transform: uppercase;
                        vertical-align: top;
                        width: 40%;
                    ">
                        {label}
                    </td>

                    <td style="
                        padding: 12px 0;
                        color: #111;
                        font-size: 13px;
                        line-height: 1.6;
                        vertical-align: top;
                    ">
                        {value}
                    </td>
                </tr>
            """

        details_html = f"""
            <div style="
                margin: 30px 0;
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

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="
        margin: 0;
        padding: 0;
        background: #f4f3f0;
        font-family: Arial, Helvetica, sans-serif;
        color: #111;
    ">

        <div style="
            width: 100%;
            padding: 50px 15px;
            box-sizing: border-box;
        ">

            <div style="
                max-width: 580px;
                margin: 0 auto;
                background: #ffffff;
                border: 1px solid #e8e6e1;
                border-radius: 24px;
                overflow: hidden;
            ">

                <!-- HEADER -->

                <div style="
                    padding: 34px 30px;
                    border-bottom: 1px solid #eeeeee;
                    text-align: center;
                ">

                    <div style="
                        font-size: 21px;
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

                <!-- CONTENT -->

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
                        {heading}
                    </h1>

                    <p style="
                        margin: 0;
                        color: #666666;
                        font-size: 15px;
                        line-height: 1.8;
                    ">
                        {message}
                    </p>

                    {details_html}

                    <p style="
                        margin: 28px 0 0;
                        color: #888888;
                        font-size: 12px;
                        line-height: 1.8;
                    ">
                        {footer}
                    </p>

                </div>

                <!-- FOOTER -->

                <div style="
                    padding: 27px 35px;
                    background: #faf9f7;
                    border-top: 1px solid #eeeeee;
                    text-align: center;
                ">

                    <p style="
                        margin: 0;
                        color: #999999;
                        font-size: 11px;
                        line-height: 1.7;
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

    plain_text = (
        "ORENTEMIST\n\n"
        f"{heading}\n\n"
        f"{message}\n\n"
    )

    if details:
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
            "Your order will be prepared for pickup. "
            "We will notify you when it is ready."
        )

        fulfillment_details = (
            "Pickup Location",
            order.pickup_address
            or "Pickup location will be provided by ORENTEMIST.",
        )

    else:

        fulfillment_message = (
            "Your order is being prepared for delivery "
            "to the address below."
        )

        fulfillment_details = (
            "Delivery Address",
            f"{order.address}, {order.city}, {order.state}",
        )

    return send_orentemist_email(
        to_email=order.email,
        subject=subject,
        heading="Thank you for your order.",
        message=(
            f"Hello {order.full_name}, "
            "your order has been successfully received. "
            f"{fulfillment_message}"
        ),
        footer_message=(
            "We will keep you updated as your order moves "
            "through each stage of fulfillment."
        ),
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
                str(order.payment_status).replace(
                    "_",
                    " ",
                ).title(),
            ),
            (
                "Status",
                str(order.status).replace(
                    "_",
                    " ",
                ).title(),
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

    return send_orentemist_email(
        to_email=order.email,
        subject=subject,
        heading="Your fragrance is on its way.",
        message=(
            f"Hello {order.full_name}, "
            "good news — your ORENTEMIST order has "
            "been shipped and is now on its way to you."
        ),
        footer_message=(
            "You can use the tracking information above "
            "with the courier to follow your delivery."
        ),
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
                f"{order.address}, {order.city}, {order.state}",
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

    return send_orentemist_email(
        to_email=order.email,
        subject=subject,
        heading="Your order has arrived.",
        message=(
            f"Hello {order.full_name}, "
            "your ORENTEMIST order has been successfully "
            "delivered."
        ),
        footer_message=(
            "Thank you for choosing ORENTEMIST. "
            "We hope you enjoy your fragrance."
        ),
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
                f"{order.address}, {order.city}, {order.state}",
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

    return send_orentemist_email(
        to_email=order.email,
        subject=subject,
        heading="Your refund has been processed.",
        message=(
            f"Hello {order.full_name}, "
            "your ORENTEMIST order has been cancelled "
            "and a refund has been requested through "
            "our payment provider."
        ),
        footer_message=(
            "The time required for refunded funds to appear "
            "in your account may depend on your bank or "
            "payment provider. If you have any questions, "
            "please contact ORENTEMIST Customer Support."
        ),
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