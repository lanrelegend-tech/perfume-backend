from django.db import migrations


def normalize_zero_optional_limits(apps, schema_editor):
    Coupon = apps.get_model("coupons", "Coupon")
    Coupon.objects.filter(usage_limit=0).update(usage_limit=None)
    Coupon.objects.filter(maximum_discount=0).update(maximum_discount=None)


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0002_coupon_used_by"),
    ]

    operations = [
        migrations.RunPython(
            normalize_zero_optional_limits,
            migrations.RunPython.noop,
        ),
    ]
