import csv
import io
import os
import zipfile

from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.core.files.base import ContentFile
from django.db import transaction

from rest_framework.response import Response
from rest_framework import status

from .models import Category, Product, ProductImage
from .cache_utils import purge_products_cache


MAX_ROWS = 1000
MAX_IMAGES_PER_PRODUCT = 20
MAX_ZIP_SIZE = 100 * 1024 * 1024  # 100 MB

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".webp",
}

REQUIRED_FIELDS = {
    "name",
    "brand",
    "description",
    "price",
}


def parse_bool(value, default=False):
    if value is None:
        return default

    value = str(value).strip().lower()

    if value in {"true", "1", "yes", "y"}:
        return True

    if value in {"false", "0", "no", "n"}:
        return False

    return default


def parse_date(value):
    value = str(value or "").strip()

    if not value:
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(
            "preorder_release_date must use YYYY-MM-DD format."
        )


def find_category(value):
    value = str(value or "").strip()

    if not value:
        return None

    category = Category.objects.filter(
        slug__iexact=value
    ).first()

    if category:
        return category

    category = Category.objects.filter(
        name__iexact=value
    ).first()

    if category:
        return category

    raise ValueError(
        f"Category '{value}' was not found."
    )


def import_products(request):
    csv_file = request.FILES.get("csv_file")
    images_zip = request.FILES.get("images_zip")

    # CSV is required.
    if not csv_file:
        return Response(
            {"error": "csv_file is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ZIP is OPTIONAL.
    # This prevents "images_zip is required" / None errors
    # when importing products without images.
    if images_zip and images_zip.size > MAX_ZIP_SIZE:
        return Response(
            {
                "error": (
                    "ZIP file is too large. "
                    "Maximum size is 100 MB."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ---------------------------------------------------------
    # Read CSV
    # ---------------------------------------------------------

    try:
        csv_content = csv_file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return Response(
            {
                "error": (
                    "CSV file must be UTF-8 encoded."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    reader = csv.DictReader(
        io.StringIO(csv_content)
    )

    if not reader.fieldnames:
        return Response(
            {"error": "CSV file has no header row."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    fieldnames = {
        field.strip()
        for field in reader.fieldnames
        if field
    }

    missing_fields = REQUIRED_FIELDS - fieldnames

    if missing_fields:
        return Response(
            {
                "error": (
                    "CSV is missing required columns: "
                    + ", ".join(
                        sorted(missing_fields)
                    )
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    rows = list(reader)

    if not rows:
        return Response(
            {"error": "CSV contains no products."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(rows) > MAX_ROWS:
        return Response(
            {
                "error": (
                    "CSV can contain a maximum of "
                    "1000 products."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ---------------------------------------------------------
    # Read ZIP safely
    # ---------------------------------------------------------

    zip_file = None
    image_files = {}

    # ZIP is optional.
    if images_zip:
        try:
            zip_file = zipfile.ZipFile(
                images_zip
            )
        except zipfile.BadZipFile:
            return Response(
                {"error": "Invalid ZIP file."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            for zip_info in zip_file.infolist():

                if zip_info.is_dir():
                    continue

                filename = zip_info.filename

                # Prevent path traversal.
                normalized_path = os.path.normpath(
                    filename
                )

                if (
                    normalized_path.startswith("..")
                    or os.path.isabs(normalized_path)
                    or ".." in normalized_path.split(
                        os.sep
                    )
                ):
                    zip_file.close()

                    return Response(
                        {
                            "error": (
                                "ZIP contains an unsafe "
                                f"path: {filename}"
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                extension = os.path.splitext(
                    filename
                )[1].lower()

                if extension not in ALLOWED_IMAGE_EXTENSIONS:
                    continue

                basename = os.path.basename(
                    filename
                ).strip().lower()

                if not basename:
                    continue

                image_files[basename] = zip_info

        except Exception:
            zip_file.close()

            return Response(
                {
                    "error": (
                        "Could not safely read the ZIP file."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    # ---------------------------------------------------------
    # Import products
    # ---------------------------------------------------------

    success_count = 0
    failure_count = 0

    errors = []
    created_products = []

    try:

        for row_number, row in enumerate(
            rows,
            start=2
        ):

            try:

                with transaction.atomic():

                    name = str(
                        row.get("name", "")
                    ).strip()

                    brand = str(
                        row.get("brand", "")
                    ).strip()

                    description = str(
                        row.get("description", "")
                    ).strip()

                    price_value = str(
                        row.get("price", "")
                    ).strip()

                    if not name:
                        raise ValueError(
                            "name is required."
                        )

                    if not brand:
                        raise ValueError(
                            "brand is required."
                        )

                    if not description:
                        raise ValueError(
                            "description is required."
                        )

                    if not price_value:
                        raise ValueError(
                            "price is required."
                        )

                    try:
                        price = Decimal(
                            price_value
                        )

                    except (
                        InvalidOperation,
                        ValueError,
                    ):
                        raise ValueError(
                            "price must be a valid number."
                        )

                    if price < 0:
                        raise ValueError(
                            "price cannot be negative."
                        )

                    category = find_category(
                        row.get("category")
                    )

                    # -------------------------------------------------
                    # Gender
                    # -------------------------------------------------

                    gender = str(
                        row.get(
                            "gender",
                            "unisex"
                        )
                    ).strip().lower()

                    valid_genders = {
                        choice[0]
                        for choice in Product.GENDER_CHOICES
                    }

                    if gender not in valid_genders:
                        raise ValueError(
                            "gender must be one of: "
                            + ", ".join(
                                sorted(valid_genders)
                            )
                        )

                    # -------------------------------------------------
                    # Concentration
                    # -------------------------------------------------

                    concentration = str(
                        row.get(
                            "concentration",
                            ""
                        )
                    ).strip().lower()

                    valid_concentrations = {
                        choice[0]
                        for choice in (
                            Product.CONCENTRATION_CHOICES
                        )
                    }

                    if (
                        concentration
                        and concentration
                        not in valid_concentrations
                    ):
                        raise ValueError(
                            "concentration must be one of: "
                            + ", ".join(
                                sorted(
                                    valid_concentrations
                                )
                            )
                        )

                    # -------------------------------------------------
                    # Stock
                    # -------------------------------------------------

                    try:
                        stock_quantity = int(
                            str(
                                row.get(
                                    "stock_quantity",
                                    "0"
                                )
                            ).strip()
                            or "0"
                        )

                    except ValueError:
                        raise ValueError(
                            "stock_quantity must be a "
                            "whole number."
                        )

                    if stock_quantity < 0:
                        raise ValueError(
                            "stock_quantity cannot "
                            "be negative."
                        )

                    # -------------------------------------------------
                    # Preorder
                    # -------------------------------------------------

                    is_preorder = parse_bool(
                        row.get(
                            "is_preorder"
                        ),
                        False,
                    )

                    preorder_release_date = (
                        parse_date(
                            row.get(
                                "preorder_release_date"
                            )
                        )
                    )

                    # -------------------------------------------------
                    # Create product
                    # -------------------------------------------------

                    product = Product.objects.create(
                        name=name,
                        brand=brand,
                        gender=gender,
                        concentration=concentration,
                        description=description,
                        category=category,
                        price=price,

                        size=str(
                            row.get(
                                "size",
                                ""
                            )
                        ).strip(),

                        fragrance_notes=str(
                            row.get(
                                "fragrance_notes",
                                ""
                            )
                        ).strip(),

                        stock_quantity=stock_quantity,

                        in_stock=parse_bool(
                            row.get(
                                "in_stock"
                            ),
                            stock_quantity > 0,
                        ),

                        featured=parse_bool(
                            row.get(
                                "featured"
                            ),
                            False,
                        ),

                        is_preorder=is_preorder,

                        preorder_release_date=(
                            preorder_release_date
                        ),

                        preorder_message=str(
                            row.get(
                                "preorder_message",
                                ""
                            )
                        ).strip(),
                    )

                    # -------------------------------------------------
                    # Images
                    # -------------------------------------------------

                    image_value = str(
                        row.get(
                            "image_files",
                            ""
                        )
                    ).strip()

                    if not image_value:
                        image_value = str(
                            row.get(
                                "image",
                                ""
                            )
                        ).strip()

                    image_names = [
                        item.strip()
                        for item in image_value.split("|")
                        if item.strip()
                    ]

                    if len(image_names) > MAX_IMAGES_PER_PRODUCT:
                        raise ValueError(
                            "A product can have a maximum "
                            "of 20 images."
                        )

                    image_errors = []

                    for image_index, image_name in enumerate(
                        image_names
                    ):

                        # CSV can contain image names,
                        # but if no ZIP was uploaded,
                        # report the image problem without
                        # crashing the whole import.
                        if not zip_file:
                            image_errors.append(
                                f"Image '{image_name}' "
                                "was listed in CSV but no "
                                "images ZIP was uploaded."
                            )
                            continue

                        lookup_name = (
                            os.path.basename(
                                image_name
                            ).strip().lower()
                        )

                        zip_info = image_files.get(
                            lookup_name
                        )

                        if not zip_info:
                            image_errors.append(
                                f"Image '{image_name}' "
                                "was not found in ZIP."
                            )
                            continue

                        try:

                            image_data = zip_file.read(
                                zip_info
                            )

                            content = ContentFile(
                                image_data
                            )

                            product_image = ProductImage(
                                product=product,
                                is_primary=(
                                    image_index == 0
                                    and not image_errors
                                )
                            )

                            product_image.image.save(
                                os.path.basename(
                                    zip_info.filename
                                ),
                                content,
                                save=True,
                            )

                            # Set first successful image
                            # as the main Product image.
                            if product_image.is_primary:

                                product.image.name = (
                                    product_image.image.name
                                )

                                product.save(
                                    update_fields=[
                                        "image",
                                        "updated_at",
                                    ]
                                )

                        except Exception as exc:

                            image_errors.append(
                                f"Image '{image_name}' "
                                f"failed: {exc}"
                            )

                    # Image problems don't cancel the
                    # entire product import.
                    if image_errors:
                        errors.append(
                            {
                                "row": row_number,
                                "type": "image",
                                "product": product.name,
                                "messages": image_errors,
                            }
                        )

                    success_count += 1

                    created_products.append(
                        {
                            "id": product.id,
                            "name": product.name,
                            "slug": product.slug,
                        }
                    )

            except Exception as exc:

                failure_count += 1

                errors.append(
                    {
                        "row": row_number,
                        "type": "product",
                        "message": str(exc),
                    }
                )

    finally:

        if zip_file:
            zip_file.close()

    # Product API is cached through Cloudflare.
    # Purge once after the entire import instead of
    # purging after every single product/image.
    if success_count:
        purge_products_cache()

    return Response(
        {
            "success_count": success_count,
            "failure_count": failure_count,
            "errors": errors,
            "created_products": created_products,
        },
        status=status.HTTP_201_CREATED,
    )