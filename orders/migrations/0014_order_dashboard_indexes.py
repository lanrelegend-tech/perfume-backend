from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0013_backfill_preorder_reservations"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="order",
            index=models.Index(
                fields=["created_at"],
                name="orders_orde_created_6cf3b9_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(
                fields=["status"],
                name="orders_orde_status_fdebb8_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(
                fields=["payment_status"],
                name="orders_orde_payment_43ab57_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(
                fields=["payment_status", "created_at"],
                name="orders_orde_payment_f66a45_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(
                fields=["status", "created_at"],
                name="orders_orde_status_22441f_idx",
            ),
        ),
    ]
