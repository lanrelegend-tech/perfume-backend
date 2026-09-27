from django.db import migrations, models
from django.utils.text import slugify


def populate_product_slugs(apps, schema_editor):
    Product = apps.get_model("products", "Product")

    for product in Product.objects.all():
        base_slug = slugify(product.name)

        if not base_slug:
            base_slug = f"product-{product.pk}"

        slug = base_slug
        counter = 2

        while Product.objects.filter(slug=slug).exclude(pk=product.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        product.slug = slug
        product.save(update_fields=["slug"])


class Migration(migrations.Migration):

    dependencies = [
        (
            "products",
            "0007_product_is_preorder_product_preorder_message_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="slug",
            field=models.SlugField(
                max_length=200,
                blank=True,
                null=True,
            ),
        ),

        migrations.RunPython(
            populate_product_slugs,
            migrations.RunPython.noop,
        ),
    ]