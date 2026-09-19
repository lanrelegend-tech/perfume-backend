from django.urls import path

from .views import (
    ProductListView,
    ProductDetailView,
    CategoryListView,
    AdminProductListCreateView,
    AdminProductDetailView,
    AdminCategoryListCreateView,
    AdminCategoryDetailView,
    AdminInventoryView,
    AdminProductVariantListCreateView,
    AdminProductVariantDetailView,
    AdminProductImageListCreateView,
    AdminProductImageDetailView,
    AdminProductBulkImageUploadView,
    AdminLowStockView,

    )


urlpatterns = [
    # Admin products
    path(
        "admin/",
        AdminProductListCreateView.as_view(),
        name="admin-product-list-create"
    ),

    path(
        "admin/categories/",
        AdminCategoryListCreateView.as_view(),
        name="admin-category-list-create"
    ),
    path(
    "admin/inventory/",
    AdminInventoryView.as_view(),
    name="admin-inventory"
    ),  
    path(
    "admin/variants/",
    AdminProductVariantListCreateView.as_view(),
    name="admin-variant-list-create"
    ),
    path(
    "admin/images/bulk/",
    AdminProductBulkImageUploadView.as_view(),
    name="admin-product-bulk-images"
),

    path(
    "admin/images/",
    AdminProductImageListCreateView.as_view(),
    name="admin-product-images"
),

path(
    "admin/images/<int:pk>/",
    AdminProductImageDetailView.as_view(),
    name="admin-product-image-detail"
),

    path(
    "admin/variants/<int:pk>/",
    AdminProductVariantDetailView.as_view(),
    name="admin-variant-detail"
    ),  
    path(
    "admin/inventory/alerts/",
    AdminLowStockView.as_view(),
    name="admin-inventory-alerts"
    ),

    path(
        "admin/categories/<int:pk>/",
        AdminCategoryDetailView.as_view(),
        name="admin-category-detail"
    ),

    path(
        "admin/<int:pk>/",
        AdminProductDetailView.as_view(),
        name="admin-product-detail"
    ),

    # Public
    path(
        "categories/",
        CategoryListView.as_view(),
        name="category-list"
    ),

    path(
        "<int:pk>/",
        ProductDetailView.as_view(),
        name="product-detail"
    ),

    path(
        "",
        ProductListView.as_view(),
        name="product-list"
    ),
]