from django.db import migrations, models


def backfill_preorder_reservations(apps, schema_editor):
    OrderItem = apps.get_model("orders", "OrderItem")
    Product = apps.get_model("products", "Product")
    ProductVariant = apps.get_model("products", "ProductVariant")

    items = (
        OrderItem.objects
        .filter(
            is_preorder=True,
            order__payment_status="paid",
        )
        .exclude(product_id=None)
    )

    for item in items.iterator():
        if item.variant_id:
            ProductVariant.objects.filter(pk=item.variant_id).update(
                preorder_reserved_quantity=(
                    models.F("preorder_reserved_quantity")
                    + item.quantity
                )
            )
        else:
            Product.objects.filter(pk=item.product_id).update(
                preorder_reserved_quantity=(
                    models.F("preorder_reserved_quantity")
                    + item.quantity
                )
            )


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0012_alter_order_payment_reference"),
        ("products", "0010_preorder_reserved_quantity"),
    ]

    operations = [
        migrations.RunPython(
            backfill_preorder_reservations,
            migrations.RunPython.noop,
        ),
    ]
