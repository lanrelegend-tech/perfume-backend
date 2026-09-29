from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0009_alter_product_slug"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="preorder_reserved_quantity",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="productvariant",
            name="preorder_reserved_quantity",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
