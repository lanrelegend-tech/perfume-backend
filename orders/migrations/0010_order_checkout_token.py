from django.db import migrations, models
import uuid


def generate_checkout_tokens(apps, schema_editor):
    Order = apps.get_model("orders", "Order")

    for order in Order.objects.all().iterator():
        order.checkout_token = uuid.uuid4()
        order.save(update_fields=["checkout_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0009_order_delivery_method_order_pickup_address_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="checkout_token",
            field=models.UUIDField(
                null=True,
                editable=False,
            ),
        ),

        migrations.RunPython(
            generate_checkout_tokens,
            migrations.RunPython.noop,
        ),

        migrations.AlterField(
            model_name="order",
            name="checkout_token",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                unique=True,
            ),
        ),
    ]