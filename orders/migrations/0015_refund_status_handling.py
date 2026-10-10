from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0014_order_dashboard_indexes"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="payment_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("paid", "Paid"),
                    ("failed", "Failed"),
                    ("refund_pending", "Refund Pending"),
                    ("refund_processing", "Refund Processing"),
                    ("refund_failed", "Refund Failed"),
                    ("refunded", "Refunded"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="refund",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("processing", "Processing"),
                    ("needs_attention", "Needs Attention"),
                    ("processed", "Processed"),
                    ("failed", "Failed"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
