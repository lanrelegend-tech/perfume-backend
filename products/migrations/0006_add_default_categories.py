from django.db import migrations


def create_default_categories(apps, schema_editor):
    Category = apps.get_model("products", "Category")

    categories = [
        ("Perfume", "perfume"),
        ("Body Spray", "body-spray"),
        ("Perfume Oil", "perfume-oil"),
        ("Gift Set", "gift-set"),
        ("Other", "other"),
    ]

    for name, slug in categories:
        Category.objects.get_or_create(
            name=name,
            defaults={"slug": slug},
        )


def remove_default_categories(apps, schema_editor):
    Category = apps.get_model("products", "Category")

    Category.objects.filter(
        slug__in=[
            "perfume",
            "body-spray",
            "perfume-oil",
            "gift-set",
            "other",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0005_product_concentration"),
    ]

    operations = [
        migrations.RunPython(
            create_default_categories,
            remove_default_categories,
        ),
    ]
