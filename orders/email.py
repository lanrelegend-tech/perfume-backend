"use client";

import { useEffect, useState } from "react";
import AdminSidebar from "@/components/AdminSidebar";
import { useParams, useRouter } from "next/navigation";
import {
  Search,
  Bell,
  MessageCircle,
  ArrowLeft,
  Truck,
  MapPin,
  UserRound,
  CreditCard,
  CheckCircle2,
  Clock3,
  PackageCheck,
  Loader2,
  Save,
  AlertTriangle,
} from "lucide-react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "https://perfume-backend-sbvd.onrender.com/api";

export default function OrderDetailsPage() {
  const router = useRouter();
  const params = useParams();
  const orderId = params?.id;

  const [order, setOrder] = useState(null);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);

  const [courier, setCourier] = useState("");
  const [trackingNumber, setTrackingNumber] =
    useState("");

  const [savingShipping, setSavingShipping] =
    useState(false);

  const [error, setError] = useState("");

  const [confirmModal, setConfirmModal] =
    useState({
      open: false,
      status: null,
      title: "",
      message: "",
    });

  useEffect(() => {
    if (!orderId) return;

    const fetchOrder = async () => {
      try {
        setLoading(true);
        setError("");

        const token =
          localStorage.getItem("access_token");

        if (!token) {
          router.push("/admin/login");
          return;
        }

        const response = await fetch(
          `${API_URL}/orders/admin/${orderId}/`,
          {
            method: "GET",
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
            cache: "no-store",
          }
        );

        if (response.status === 401) {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");

          router.push("/admin/login");
          return;
        }

        if (response.status === 403) {
          throw new Error(
            "You do not have permission to view this order."
          );
        }

        if (response.status === 404) {
          throw new Error("Order not found.");
        }

        if (!response.ok) {
          throw new Error(
            "Failed to load order details."
          );
        }

        const data = await response.json();

        console.log(
          "ADMIN ORDER DETAILS:",
          data
        );

        setOrder(data);

        setStatus(
          formatStatus(data.status)
        );

        setCourier(data.courier || "");

        setTrackingNumber(
          data.tracking_number || ""
        );
      } catch (err) {
        console.error(
          "ORDER DETAILS ERROR:",
          err
        );

        setError(
          err.message ||
            "Failed to load order."
        );
      } finally {
        setLoading(false);
      }
    };

    fetchOrder();
  }, [orderId, router]);

  /*
    OPEN CONFIRMATION MODAL
  */

  const updateStatus = async (newStatus) => {
    if (!order) return;

    if (newStatus === order.status) {
      setStatus(formatStatus(newStatus));
      return;
    }

    if (
      order.status === "processing" &&
      newStatus === "shipped"
    ) {
      if (
        !courier.trim() ||
        !trackingNumber.trim()
      ) {
        setError(
          "To mark this order as Shipped, you must enter both the courier and tracking number first."
        );

        return;
      }
    }

    const statusNames = {
      pending: "Pending",
      confirmed: "Confirmed",
      processing: "Processing",
      shipped: "Shipped",
      delivered: "Delivered",
      cancelled: "Cancelled",
    };

    const oldStatusName =
      statusNames[order.status] ||
      order.status;

    const newStatusName =
      statusNames[newStatus] ||
      newStatus;

    let message = `Are you sure you want to change this order from ${oldStatusName} to ${newStatusName}?`;

    if (
      order.status === "processing" &&
      newStatus === "delivered"
    ) {
      message =
        "This order is currently Processing.\n\nAre you sure you want to skip the Shipped stage and mark this order as Delivered?";
    }

    if (newStatus === "cancelled") {
      if (order.payment_status === "paid") {
        message =
          "Are you sure you want to cancel this order?\n\nThis order has been paid. Cancelling it will request a full refund, restore the purchased stock, and reverse the coupon usage if one was used.\n\nPre-order items will not restore inventory because they did not consume current stock.\n\nThis action cannot be undone.";
      } else {
        message =
          "Are you sure you want to cancel this order?\n\nThis order has not been paid, so no refund will be made.\n\nThis action cannot be undone.";
      }
    }

    setConfirmModal({
      open: true,
      status: newStatus,
      title: `Change order to ${newStatusName}?`,
      message,
    });
  };

  /*
    CONFIRM STATUS CHANGE
  */

  const confirmStatusUpdate = async () => {
    const newStatus =
      confirmModal.status;

    if (!newStatus || !order) {
      setConfirmModal({
        open: false,
        status: null,
        title: "",
        message: "",
      });

      return;
    }

    setConfirmModal({
      open: false,
      status: null,
      title: "",
      message: "",
    });

    try {
      setUpdating(true);
      setError("");

      const token =
        localStorage.getItem("access_token");

      if (!token) {
        router.push("/admin/login");
        return;
      }

      const response = await fetch(
        `${API_URL}/orders/admin/${order.id}/`,
        {
          method: "PATCH",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            status: newStatus,
          }),
        }
      );

      if (response.status === 401) {
        localStorage.removeItem(
          "access_token"
        );

        localStorage.removeItem(
          "refresh_token"
        );

        router.push("/admin/login");

        return;
      }

      if (response.status === 403) {
        throw new Error(
          "You do not have permission to update this order."
        );
      }

      if (!response.ok) {
        const errorData =
          await response
            .json()
            .catch(() => null);

        throw new Error(
          errorData?.status?.[0] ||
            errorData?.detail ||
            "Failed to update order status."
        );
      }

      const updatedOrder =
        await response.json();

      console.log(
        "UPDATED ADMIN ORDER:",
        updatedOrder
      );

      setOrder(updatedOrder);

      setCourier(
        updatedOrder.courier || ""
      );

      setTrackingNumber(
        updatedOrder.tracking_number ||
          ""
      );

      setStatus(
        formatStatus(
          updatedOrder.status
        )
      );
    } catch (err) {
      console.error(
        "UPDATE ORDER ERROR:",
        err
      );

      setError(
        err.message ||
          "Failed to update order."
      );

      setStatus(
        formatStatus(order.status)
      );
    } finally {
      setUpdating(false);
    }
  };

  /*
    SAVE SHIPPING DETAILS
  */

  const saveShippingDetails =
    async () => {
      if (!order) return;

      try {
        setSavingShipping(true);
        setError("");

        const token =
          localStorage.getItem(
            "access_token"
          );

        if (!token) {
          router.push("/admin/login");
          return;
        }

        const response = await fetch(
          `${API_URL}/orders/admin/${order.id}/`,
          {
            method: "PATCH",
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify({
              courier:
                courier.trim(),
              tracking_number:
                trackingNumber.trim(),
            }),
          }
        );

        if (response.status === 401) {
          localStorage.removeItem(
            "access_token"
          );

          localStorage.removeItem(
            "refresh_token"
          );

          router.push("/admin/login");

          return;
        }

        if (response.status === 403) {
          throw new Error(
            "You do not have permission to update this order."
          );
        }

        if (!response.ok) {
          const errorData =
            await response
              .json()
              .catch(() => null);

          throw new Error(
            errorData?.courier?.[0] ||
              errorData?.tracking_number?.[0] ||
              errorData?.detail ||
              "Failed to save shipping details."
          );
        }

        const updatedOrder =
          await response.json();

        setOrder(updatedOrder);

        setCourier(
          updatedOrder.courier || ""
        );

        setTrackingNumber(
          updatedOrder.tracking_number ||
            ""
        );
      } catch (err) {
        console.error(
          "SAVE SHIPPING ERROR:",
          err
        );

        setError(
          err.message ||
            "Failed to save shipping details."
        );
      } finally {
        setSavingShipping(false);
      }
    };

  /*
    HELPERS
  */

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat(
      "en-NG",
      {
        style: "currency",
        currency: "NGN",
        maximumFractionDigits: 0,
      }
    ).format(
      Number(amount || 0)
    );
  };

  const getSubtotal = () => {
    if (!order?.items) {
      return 0;
    }

    return order.items.reduce(
      (total, item) => {
        return (
          total +
          Number(
            item.subtotal ||
              Number(
                item.product_price || 0
              ) *
                Number(
                  item.quantity || 0
                )
          )
        );
      },
      0
    );
  };

  const getItemCount = () => {
    if (!order?.items) {
      return 0;
    }

    return order.items.reduce(
      (total, item) =>
        total +
        Number(
          item.quantity || 0
        ),
      0
    );
  };

  const getProductImage = (
    item
  ) => {
    return (
      item.product_image ||
      item.image ||
      item.product?.image ||
      null
    );
  };

  const getProductName = (
    item
  ) => {
    return (
      item.product_name ||
      item.name ||
      `Product #${item.product || ""}`
    );
  };

  const getProductCategory = (
    item
  ) => {
    return (
      item.variant_size ||
      item.product_brand ||
      "ORENTEMIST"
    );
  };

  const getOrderDate = () => {
    if (!order?.created_at) {
      return "Date unavailable";
    }

    return new Intl.DateTimeFormat(
      "en-NG",
      {
        dateStyle: "medium",
        timeStyle: "short",
      }
    ).format(
      new Date(order.created_at)
    );
  };

  const getPaymentMethod = () => {
    if (order?.payment_reference) {
      return "Paystack";
    }

    return "Not available";
  };

  /*
    PRE-ORDER HELPERS
  */

  const isPreorderValue = (value) => {
    return (
      value === true ||
      value === "true" ||
      value === 1 ||
      value === "1"
    );
  };

  const hasPreorderItems =
    Boolean(
      order?.items?.some((item) =>
        isPreorderValue(
          item.is_preorder
        )
      )
    );

  const getPreorderMessage = (
    item
  ) => {
    return (
      item.preorder_message ||
      item.product?.preorder_message ||
      "This item was purchased as a pre-order."
    );
  };

  const getPreorderReleaseDate = (
    item
  ) => {
    const releaseDate =
      item.preorder_release_date ||
      item.product?.preorder_release_date ||
      null;

    if (!releaseDate) {
      return null;
    }

    const date =
      new Date(releaseDate);

    if (
      Number.isNaN(
        date.getTime()
      )
    ) {
      return null;
    }

    return new Intl.DateTimeFormat(
      "en-NG",
      {
        dateStyle: "medium",
      }
    ).format(date);
  };

  /*
    LOADING
    KEEP THIS AS IT WAS
  */

  if (loading) {
    return (
      <div className="min-h-screen bg-[#f7f7f5] text-black">
        <AdminSidebar />

        <main className="lg:ml-[250px]">
          <div className="pt-16 lg:pt-0">
            <header className="flex h-[82px] items-center justify-between border-b border-black/10 bg-white px-5 sm:px-8">
              <div>
                <p className="text-xs text-black/40">
                  ORENTEMIST ADMIN
                </p>

                <h2 className="text-xl font-semibold">
                  Order Details
                </h2>
              </div>
            </header>

            <div className="flex min-h-[70vh] items-center justify-center">
              <div className="flex items-center gap-3 text-sm text-black/50">
                <Loader2
                  size={18}
                  className="animate-spin"
                />

                Loading order...
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }

  /*
    ERROR
  */

  if (error && !order) {
    return (
      <div className="min-h-screen bg-[#f7f7f5] text-black">
        <AdminSidebar />

        <main className="lg:ml-[250px]">
          <div className="pt-16 lg:pt-0">
            <header className="flex h-[82px] items-center justify-between border-b border-black/10 bg-white px-5 sm:px-8">
              <div>
                <p className="text-xs text-black/40">
                  ORENTEMIST ADMIN
                </p>

                <h2 className="text-xl font-semibold">
                  Order Details
                </h2>
              </div>
            </header>

            <div className="p-5 sm:p-8">
              <button
                onClick={() =>
                  router.push(
                    "/admin/orders"
                  )
                }
                className="mb-6 flex items-center gap-2 text-sm text-black/50 transition hover:text-black"
              >
                <ArrowLeft size={16} />
                Back to Orders
              </button>

              <div className="rounded-2xl border border-red-200 bg-red-50 p-6">
                <h2 className="font-semibold text-red-700">
                  Unable to load order
                </h2>

                <p className="mt-2 text-sm text-red-600">
                  {error}
                </p>
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }

  const subtotal = getSubtotal();

  const shippingFee = Number(
    order?.delivery_fee || 0
  );

  const discount = (() => {
    const value = Number(
      order?.coupon_discount_value || 0
    );

    if (!value) {
      return 0;
    }

    if (
      order?.coupon_discount_type ===
      "percentage"
    ) {
      return Math.min(
        subtotal,
        (subtotal * value) / 100
      );
    }

    return Math.min(
      subtotal,
      value
    );
  })();

  const total = Number(
    order?.total_amount || 0
  );

  const paymentStatus =
    formatStatus(
      order?.payment_status
    );

  const canSkipShipping =
    order?.status === "processing";

  return (
    <div className="min-h-screen bg-[#f7f7f5] text-black">
      <AdminSidebar />

      <main className="lg:ml-[250px]">
        <div className="pt-16 lg:pt-0">

          {/* HEADER */}

          <header className="flex h-[82px] items-center justify-between border-b border-black/10 bg-white px-5 sm:px-8">
            <div>
              <p className="text-xs text-black/40">
                ORENTEMIST ADMIN
              </p>

              <h2 className="text-xl font-semibold">
                Order Details
              </h2>
            </div>

            <div className="flex items-center gap-3">
              <button className="hidden rounded-xl border border-black/10 p-3 sm:block">
                <Search size={18} />
              </button>

              <button className="rounded-xl border border-black/10 p-3">
                <Bell size={18} />
              </button>

              <button className="rounded-xl border border-black/10 p-3">
                <MessageCircle size={18} />
              </button>
            </div>
          </header>

          <div className="p-5 sm:p-8">

            {/* ERROR */}

            {error && (
              <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            {/* TOP */}

            <div className="mb-8 flex flex-col justify-between gap-5 md:flex-row md:items-center">

              <div>

                <button
                  onClick={() =>
                    router.push(
                      "/admin/orders"
                    )
                  }
                  className="mb-4 flex items-center gap-2 text-sm text-black/50 transition hover:text-black"
                >
                  <ArrowLeft size={16} />
                  Back to Orders
                </button>

                <div className="flex flex-wrap items-center gap-3">

                  <h1 className="text-3xl font-semibold tracking-tight">
                    {order.order_number ||
                      `#${order.id}`}
                  </h1>

                  <OrderStatus
                    status={status}
                  />

                  {hasPreorderItems && (
                    <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800">
                      Pre-order included
                    </span>
                  )}

                </div>

                <p className="mt-2 text-sm text-black/45">
                  Placed on{" "}
                  {getOrderDate()}
                </p>

              </div>

              {/* STATUS CONTROLS */}

              <div className="flex flex-wrap gap-3">

                {order.status ===
                  "processing" && (
                  <div className="flex flex-wrap gap-3">

                    <button
                      onClick={() => {
                        if (
                          !courier.trim() ||
                          !trackingNumber.trim()
                        ) {
                          setError(
                            "Please enter and save the courier and tracking number before marking this order as Shipped."
                          );

                          return;
                        }

                        updateStatus(
                          "shipped"
                        );
                      }}
                      disabled={updating}
                      className="flex items-center gap-2 rounded-xl bg-black px-5 py-3 text-sm font-medium text-white transition hover:bg-black/90 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {updating ? (
                        <Loader2
                          size={16}
                          className="animate-spin"
                        />
                      ) : (
                        <Truck size={16} />
                      )}

                      Mark as Shipped
                    </button>

                    <button
                      onClick={() =>
                        updateStatus(
                          "delivered"
                        )
                      }
                      disabled={updating}
                      className="flex items-center gap-2 rounded-xl border border-black/10 bg-white px-5 py-3 text-sm font-medium transition hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <CheckCircle2
                        size={16}
                      />

                      Skip Shipping
                    </button>

                    <button
                      onClick={() =>
                        updateStatus(
                          "cancelled"
                        )
                      }
                      disabled={updating}
                      className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-5 py-3 text-sm font-medium text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <AlertTriangle
                        size={16}
                      />

                      Cancel Order
                    </button>

                  </div>
                )}

                {order.status ===
                  "shipped" && (
                  <div className="flex flex-wrap gap-3">

                    <button
                      onClick={() =>
                        updateStatus(
                          "delivered"
                        )
                      }
                      disabled={updating}
                      className="flex items-center gap-2 rounded-xl bg-black px-5 py-3 text-sm font-medium text-white transition hover:bg-black/90 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {updating ? (
                        <Loader2
                          size={16}
                          className="animate-spin"
                        />
                      ) : (
                        <CheckCircle2
                          size={16}
                        />
                      )}

                      Mark as Delivered
                    </button>

                    <button
                      onClick={() =>
                        updateStatus(
                          "cancelled"
                        )
                      }
                      disabled={updating}
                      className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-5 py-3 text-sm font-medium text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <AlertTriangle
                        size={16}
                      />

                      Cancel Order
                    </button>

                  </div>
                )}

                {order.status ===
                  "pending" && (
                  <select
                    value={order.status}
                    disabled={updating}
                    onChange={(e) =>
                      updateStatus(
                        e.target.value
                      )
                    }
                    className="rounded-xl bg-black px-4 py-3 text-sm text-white outline-none disabled:opacity-50"
                  >
                    <option value="pending">
                      Pending
                    </option>

                    <option value="confirmed">
                      Confirmed
                    </option>

                    <option value="cancelled">
                      Cancelled
                    </option>
                  </select>
                )}

                {order.status ===
                  "confirmed" && (
                  <select
                    value={order.status}
                    disabled={updating}
                    onChange={(e) =>
                      updateStatus(
                        e.target.value
                      )
                    }
                    className="rounded-xl bg-black px-4 py-3 text-sm text-white outline-none disabled:opacity-50"
                  >
                    <option value="confirmed">
                      Confirmed
                    </option>

                    <option value="processing">
                      Processing
                    </option>

                    <option value="cancelled">
                      Cancelled
                    </option>
                  </select>
                )}

                {order.status ===
                  "cancelled" && (
                  <div className="rounded-xl bg-red-50 px-5 py-3 text-sm font-medium text-red-700">
                    Order Cancelled
                  </div>
                )}

                {order.status ===
                  "delivered" && (
                  <div className="flex flex-wrap gap-3">

                    <div className="rounded-xl bg-green-50 px-5 py-3 text-sm font-medium text-green-700">
                      Order Delivered
                    </div>

                    <button
                      onClick={() =>
                        updateStatus(
                          "cancelled"
                        )
                      }
                      disabled={updating}
                      className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-5 py-3 text-sm font-medium text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <AlertTriangle
                        size={16}
                      />

                      Cancel Order
                    </button>

                  </div>
                )}

              </div>
            </div>

            {/* CONTENT */}

            <div className="grid gap-6 xl:grid-cols-[1fr_350px]">

              {/* LEFT */}

              <div className="space-y-6">

                {/* PRE-ORDER NOTICE */}

                {hasPreorderItems && (
                  <section className="rounded-2xl border border-amber-200 bg-amber-50 p-5">

                    <div className="flex gap-3">

                      <div className="mt-0.5 shrink-0">
                        <Clock3
                          size={19}
                          className="text-amber-700"
                        />
                      </div>

                      <div className="min-w-0">

                        <h2 className="text-sm font-semibold text-amber-900">
                          Pre-order included
                        </h2>

                        <p className="mt-1 text-xs leading-5 text-amber-800">
                          This order contains one or more pre-order items. The customer has already paid through Paystack. Pre-order items did not consume current inventory.
                        </p>

                        <div className="mt-4 rounded-xl border border-amber-200 bg-white/60 p-3">

                          <p className="text-xs font-semibold text-amber-900">
                            Fulfillment note
                          </p>

                          <p className="mt-1 text-xs leading-5 text-amber-800">
                            Prepare the pre-order item for fulfillment when the fragrance becomes available. Current inventory was not reduced when this order was paid.
                          </p>

                        </div>

                      </div>

                    </div>

                  </section>
                )}

                {/* PRODUCTS */}

                <section className="rounded-2xl border border-black/10 bg-white">

                  <div className="flex items-center justify-between border-b border-black/10 px-5 py-5">

                    <div>
                      <h2 className="font-semibold">
                        Order Items
                      </h2>

                      <p className="mt-1 text-xs text-black/40">
                        {getItemCount()} items
                      </p>
                    </div>

                    {hasPreorderItems && (
                      <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800">
                        Contains Pre-order
                      </span>
                    )}

                  </div>

                  <div className="divide-y divide-black/5">

                    {order.items &&
                    order.items.length >
                      0 ? (
                      order.items.map(
                        (item) => {
                          const image =
                            getProductImage(
                              item
                            );

                          const isPreorder =
                            isPreorderValue(
                              item.is_preorder
                            );

                          const releaseDate =
                            getPreorderReleaseDate(
                              item
                            );

                          return (
                            <div
                              key={
                                item.id
                              }
                              className="flex gap-4 p-5"
                            >

                              <div className="h-20 w-20 shrink-0 overflow-hidden rounded-xl bg-black/5">

                                {image ? (
                                  <img
                                    src={image}
                                    alt={getProductName(
                                      item
                                    )}
                                    className="h-full w-full object-cover"
                                  />
                                ) : (
                                  <div className="flex h-full w-full items-center justify-center text-xs text-black/30">
                                    No image
                                  </div>
                                )}

                              </div>

                              <div className="flex min-w-0 flex-1 flex-col justify-between gap-3 sm:flex-row sm:items-center">

                                <div className="min-w-0">

                                  <div className="flex flex-wrap items-center gap-2">

                                    <h3 className="font-medium">
                                      {getProductName(
                                        item
                                      )}
                                    </h3>

                                    {isPreorder && (
                                      <span className="rounded-full bg-amber-100 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-amber-800">
                                        Pre-order
                                      </span>
                                    )}

                                  </div>

                                  <p className="mt-1 text-xs text-black/40">
                                    {getProductCategory(
                                      item
                                    )}
                                  </p>

                                  <p className="mt-2 text-xs text-black/50">
                                    Quantity:{" "}
                                    {
                                      item.quantity
                                    }
                                  </p>

                                  {isPreorder && (
                                    <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3">

                                      <div className="flex items-center gap-2">

                                        <Clock3
                                          size={14}
                                          className="shrink-0 text-amber-700"
                                        />

                                        <p className="text-xs font-semibold text-amber-900">
                                          Pre-order item
                                        </p>

                                      </div>

                                      <p className="mt-2 text-xs leading-5 text-amber-800">
                                        {getPreorderMessage(
                                          item
                                        )}
                                      </p>

                                      {releaseDate && (
                                        <p className="mt-2 text-xs font-medium text-amber-900">
                                          Expected availability:{" "}
                                          {releaseDate}
                                        </p>
                                      )}

                                      <p className="mt-2 text-[11px] leading-5 text-amber-700">
                                        Payment received. This item did not reduce current inventory.
                                      </p>

                                    </div>
                                  )}

                                </div>

                                <p className="shrink-0 font-medium">
                                  {formatCurrency(
                                    item.subtotal ||
                                      Number(
                                        item.product_price ||
                                          0
                                      ) *
                                        Number(
                                          item.quantity ||
                                            0
                                        )
                                  )}
                                </p>

                              </div>

                            </div>
                          );
                        }
                      )
                    ) : (
                      <div className="p-6 text-center text-sm text-black/40">
                        No order items found.
                      </div>
                    )}

                  </div>

                  <div className="border-t border-black/10 px-5 py-5">

                    <div className="space-y-3 text-sm">

                      <PriceRow
                        label="Subtotal"
                        value={formatCurrency(
                          subtotal
                        )}
                      />

                      <PriceRow
                        label="Shipping"
                        value={formatCurrency(
                          shippingFee
                        )}
                      />

                      <PriceRow
                        label="Discount"
                        value={`-${formatCurrency(
                          discount
                        )}`}
                      />

                      <div className="border-t border-black/10 pt-4">

                        <PriceRow
                          label="Total"
                          value={formatCurrency(
                            total
                          )}
                          bold
                        />

                      </div>

                    </div>

                  </div>

                </section>

                {/* TIMELINE */}

                <section className="rounded-2xl border border-black/10 bg-white p-5 sm:p-6">

                  <h2 className="font-semibold">
                    Order Timeline
                  </h2>

                  <div className="mt-6 space-y-6">

                    {order.status_history &&
                    order.status_history.length >
                      0 ? (
                      order.status_history
                        .slice()
                        .reverse()
                        .map(
                          (history) => (
                            <TimelineItem
                              key={
                                history.id
                              }
                              status={
                                history.status
                              }
                              date={
                                history.created_at
                              }
                              changedBy={
                                history.changed_by
                              }
                              note={
                                history.note
                              }
                            />
                          )
                        )
                    ) : (
                      <>
                        <TimelineItem
                          status={
                            order.status
                          }
                          date={
                            order.created_at
                          }
                          changedBy={null}
                          note="Order status updated."
                        />

                        {order.payment_status ===
                          "paid" && (
                          <TimelineItem
                            status="paid"
                            date={
                              order.created_at
                            }
                            changedBy={
                              null
                            }
                            note="Payment successfully received."
                          />
                        )}

                        {hasPreorderItems && (
                          <TimelineItem
                            status="pre-order"
                            date={
                              order.created_at
                            }
                            changedBy={
                              null
                            }
                            note="This order contains a pre-order item. Current inventory was not consumed."
                          />
                        )}

                        <TimelineItem
                          status="pending"
                          date={
                            order.created_at
                          }
                          changedBy={null}
                          note="Customer created the order."
                        />
                      </>
                    )}

                  </div>

                </section>

              </div>

              {/* RIGHT */}

              <div className="space-y-6">

                {/* CUSTOMER */}

                <section className="rounded-2xl border border-black/10 bg-white p-5">

                  <div className="flex items-center gap-3">

                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-black text-white">
                      <UserRound
                        size={18}
                      />
                    </div>

                    <div>
                      <h2 className="font-semibold">
                        Customer
                      </h2>

                      <p className="text-xs text-black/40">
                        Customer information
                      </p>
                    </div>

                  </div>

                  <div className="mt-5 space-y-4">

                    <InfoRow
                      label="Name"
                      value={
                        order.full_name ||
                        "Guest Customer"
                      }
                    />

                    <InfoRow
                      label="Email"
                      value={
                        order.email ||
                        "Not provided"
                      }
                    />

                    <InfoRow
                      label="Phone"
                      value={
                        order.phone ||
                        "Not provided"
                      }
                    />

                  </div>

                </section>

                {/* DELIVERY */}

                <section className="rounded-2xl border border-black/10 bg-white p-5">

                  <div className="flex items-center gap-3">

                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-black text-white">
                      <MapPin
                        size={18}
                      />
                    </div>

                    <div>
                      <h2 className="font-semibold">
                        Delivery Address
                      </h2>

                      <p className="text-xs text-black/40">
                        Shipping information
                      </p>
                    </div>

                  </div>

                  <div className="mt-5 rounded-xl bg-[#f7f7f5] p-4 text-sm leading-6 text-black/65">

                    {order.delivery_method ===
                    "pickup" ? (
                      <>
                        <p className="font-medium text-black">
                          Pickup Order
                        </p>

                        <p className="mt-1">
                          {order.pickup_address ||
                            "Pickup location will be provided by ORENTEMIST."}
                        </p>
                      </>
                    ) : (
                      <>
                        <p>
                          {order.address ||
                            "Address not provided"}
                        </p>

                        <p>
                          {order.city || ""}
                          {order.city &&
                          order.state
                            ? ", "
                            : ""}
                          {order.state || ""}
                        </p>

                        <p>
                          Nigeria
                        </p>
                      </>
                    )}

                  </div>

                </section>

                {/* PAYMENT */}

                <section className="rounded-2xl border border-black/10 bg-white p-5">

                  <div className="flex items-center gap-3">

                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-black text-white">
                      <CreditCard
                        size={18}
                      />
                    </div>

                    <div>
                      <h2 className="font-semibold">
                        Payment
                      </h2>

                      <p className="text-xs text-black/40">
                        Payment information
                      </p>
                    </div>

                  </div>

                  <div className="mt-5 space-y-4">

                    <InfoRow
                      label="Status"
                      value={
                        paymentStatus
                      }
                      badge
                    />

                    <InfoRow
                      label="Method"
                      value={
                        getPaymentMethod()
                      }
                    />

                    <InfoRow
                      label="Amount"
                      value={formatCurrency(
                        total
                      )}
                    />

                    <InfoRow
                      label="Reference"
                      value={
                        order.payment_reference ||
                        "Not available"
                      }
                    />

                    {hasPreorderItems && (
                      <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">

                        <p className="text-xs font-semibold text-amber-900">
                          Pre-order payment
                        </p>

                        <p className="mt-1 text-xs leading-5 text-amber-800">
                          The customer paid the full order amount through Paystack. No separate payment is required when the pre-order becomes available.
                        </p>

                      </div>
                    )}

                  </div>

                </section>

                {/* SHIPPING / COURIER */}

                <section className="rounded-2xl border border-black/10 bg-white p-5">

                  <div className="flex items-center gap-3">

                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-black text-white">
                      <Truck
                        size={18}
                      />
                    </div>

                    <div>
                      <h2 className="font-semibold">
                        Shipping & Courier
                      </h2>

                      <p className="text-xs text-black/40">
                        Optional delivery information
                      </p>
                    </div>

                  </div>

                  <div className="mt-5 space-y-4">

                    <div>
                      <label className="mb-2 block text-xs font-medium text-black/50">
                        Courier
                      </label>

                      <input
                        type="text"
                        value={courier}
                        onChange={(e) =>
                          setCourier(
                            e.target.value
                          )
                        }
                        placeholder="e.g. GIG Logistics"
                        className="w-full rounded-xl border border-black/10 bg-[#f7f7f5] px-4 py-3 text-sm outline-none transition focus:border-black"
                      />
                    </div>

                    <div>
                      <label className="mb-2 block text-xs font-medium text-black/50">
                        Tracking Number
                      </label>

                      <input
                        type="text"
                        value={
                          trackingNumber
                        }
                        onChange={(e) =>
                          setTrackingNumber(
                            e.target.value
                          )
                        }
                        placeholder="Enter if available"
                        className="w-full rounded-xl border border-black/10 bg-[#f7f7f5] px-4 py-3 text-sm outline-none transition focus:border-black"
                      />
                    </div>

                    <p className="text-xs leading-5 text-black/40">
                      Courier and tracking number are required before this order can be marked as Shipped. If you want to skip shipping and mark the order as Delivered, you can leave these fields empty.
                    </p>

                    <button
                      onClick={
                        saveShippingDetails
                      }
                      disabled={
                        savingShipping
                      }
                      className="flex w-full items-center justify-center gap-2 rounded-xl bg-black px-4 py-3 text-sm font-medium text-white transition hover:bg-black/90 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {savingShipping ? (
                        <>
                          <Loader2
                            size={16}
                            className="animate-spin"
                          />

                          Saving...
                        </>
                      ) : (
                        <>
                          <Save
                            size={16}
                          />

                          Save Shipping Details
                        </>
                      )}
                    </button>

                  </div>

                </section>

                {/* TRACKING */}

                <section className="rounded-2xl border border-black/10 bg-black p-5 text-white">

                  <div className="flex items-center gap-3">

                    <Truck size={19} />

                    <div>
                      <h2 className="font-semibold">
                        Tracking
                      </h2>

                      <p className="text-xs text-white/40">
                        Delivery tracking information
                      </p>
                    </div>

                  </div>

                  <div className="mt-5 space-y-3">

                    <div className="rounded-xl bg-white/10 p-4">

                      <p className="text-xs text-white/40">
                        Courier
                      </p>

                      <p className="mt-1 break-all text-sm font-medium">
                        {order.courier ||
                          "Not assigned"}
                      </p>

                    </div>

                    <div className="rounded-xl bg-white/10 p-4">

                      <p className="text-xs text-white/40">
                        Tracking Number
                      </p>

                      <p className="mt-1 break-all text-sm font-medium">
                        {order.tracking_number ||
                          "Not assigned"}
                      </p>

                    </div>

                  </div>

                  {order.tracking_number && (
                    <button
                      onClick={() => {
                        alert(
                          `Courier: ${
                            order.courier ||
                            "Not specified"
                          }\nTracking Number: ${order.tracking_number}`
                        );
                      }}
                      className="mt-4 w-full rounded-xl bg-white px-4 py-3 text-sm font-medium text-black transition hover:bg-white/90"
                    >
                      Track Shipment
                    </button>
                  )}

                </section>

                {/* PRE-ORDER FULFILLMENT NOTICE */}

                {hasPreorderItems && (
                  <section className="rounded-2xl border border-amber-200 bg-amber-50 p-5">

                    <div className="flex gap-3">

                      <div className="mt-0.5 shrink-0">
                        <Clock3
                          size={18}
                          className="text-amber-600"
                        />
                      </div>

                      <div>

                        <h3 className="text-sm font-semibold text-amber-800">
                          Pre-order Fulfillment
                        </h3>

                        <p className="mt-1 text-xs leading-5 text-amber-700">
                          This order contains a pre-order. The order has already been paid. Do not charge the customer again when the product becomes available.
                        </p>

                        <p className="mt-2 text-xs leading-5 text-amber-700">
                          Once the product is ready, fulfill and ship the order normally using the shipping controls above.
                        </p>

                      </div>

                    </div>

                  </section>
                )}

                {/* SKIP SHIPPING NOTICE */}

                {canSkipShipping && (
                  <section className="rounded-2xl border border-amber-200 bg-amber-50 p-5">

                    <div className="flex gap-3">

                      <div className="mt-0.5 shrink-0">
                        <AlertTriangle
                          size={18}
                          className="text-amber-600"
                        />
                      </div>

                      <div>
                        <h3 className="text-sm font-semibold text-amber-800">
                          Skip Shipping
                        </h3>

                        <p className="mt-1 text-xs leading-5 text-amber-700">
                          You can mark this order as Delivered without entering courier or tracking information if the order is being handled directly or does not require shipping.
                        </p>
                      </div>

                    </div>

                  </section>
                )}

              </div>

            </div>

          </div>
        </div>
      </main>

      {/* CONFIRMATION MODAL */}

      {confirmModal.open && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-5 backdrop-blur-sm"
          onMouseDown={() =>
            setConfirmModal({
              open: false,
              status: null,
              title: "",
              message: "",
            })
          }
        >
          <div
            className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl"
            onMouseDown={(e) =>
              e.stopPropagation()
            }
          >

            <div className="flex items-start gap-4">

              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-amber-50 text-amber-600">
                <AlertTriangle
                  size={21}
                />
              </div>

              <div className="min-w-0">

                <h3 className="text-lg font-semibold text-black">
                  {confirmModal.title}
                </h3>

                <p className="mt-2 whitespace-pre-line text-sm leading-6 text-black/60">
                  {confirmModal.message}
                </p>

              </div>

            </div>

            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">

              <button
                type="button"
                onClick={() =>
                  setConfirmModal({
                    open: false,
                    status: null,
                    title: "",
                    message: "",
                  })
                }
                className="rounded-xl border border-black/10 bg-white px-5 py-3 text-sm font-medium text-black transition hover:bg-black/5"
              >
                No, Go Back
              </button>

              <button
                type="button"
                onClick={
                  confirmStatusUpdate
                }
                className="rounded-xl bg-black px-5 py-3 text-sm font-medium text-white transition hover:bg-black/90"
              >
                Yes, Continue
              </button>

            </div>

          </div>
        </div>
      )}

    </div>
  );
}

/* ===================================================== */
/* STATUS BADGE */
/* ===================================================== */

function OrderStatus({ status }) {
  const normalized =
    String(status || "")
      .toLowerCase();

  const styles = {
    pending:
      "bg-amber-50 text-amber-700",
    confirmed:
      "bg-blue-50 text-blue-700",
    processing:
      "bg-purple-50 text-purple-700",
    shipped:
      "bg-indigo-50 text-indigo-700",
    delivered:
      "bg-green-50 text-green-700",
    cancelled:
      "bg-red-50 text-red-700",
  };

  return (
    <span
      className={`rounded-full px-3 py-1 text-xs font-medium ${
        styles[normalized] ||
        "bg-black/5 text-black/60"
      }`}
    >
      {formatStatus(status)}
    </span>
  );
}

/* ===================================================== */
/* PRICE ROW */
/* ===================================================== */

function PriceRow({
  label,
  value,
  bold = false,
}) {
  return (
    <div
      className={`flex items-center justify-between ${
        bold
          ? "text-base font-semibold"
          : ""
      }`}
    >
      <span
        className={
          bold
            ? "text-black"
            : "text-black/50"
        }
      >
        {label}
      </span>

      <span>{value}</span>
    </div>
  );
}

/* ===================================================== */
/* INFO ROW */
/* ===================================================== */

function InfoRow({
  label,
  value,
  badge = false,
}) {
  return (
    <div className="flex items-start justify-between gap-4">

      <span className="text-xs text-black/40">
        {label}
      </span>

      {badge ? (
        <span className="rounded-full bg-black/5 px-3 py-1 text-xs font-medium">
          {value}
        </span>
      ) : (
        <span className="max-w-[65%] break-words text-right text-sm font-medium">
          {value}
        </span>
      )}

    </div>
  );
}

/* ===================================================== */
/* TIMELINE ITEM */
/* ===================================================== */

function TimelineItem({
  status,
  date,
  changedBy,
  note,
}) {
  const normalized =
    String(status || "")
      .toLowerCase();

  let Icon = Clock3;

  if (
    normalized === "confirmed" ||
    normalized === "processing"
  ) {
    Icon = PackageCheck;
  }

  if (normalized === "shipped") {
    Icon = Truck;
  }

  if (normalized === "delivered") {
    Icon = CheckCircle2;
  }

  if (normalized === "cancelled") {
    Icon = AlertTriangle;
  }

  if (normalized === "paid") {
    Icon = CreditCard;
  }

  if (normalized === "pre-order") {
    Icon = Clock3;
  }

  return (
    <div className="flex gap-4">

      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-black text-white">
        <Icon size={16} />
      </div>

      <div className="min-w-0 flex-1">

        <div className="flex flex-wrap items-center justify-between gap-2">

          <p className="text-sm font-medium">
            {formatStatus(status)}
          </p>

          {date && (
            <p className="text-xs text-black/35">
              {new Intl.DateTimeFormat(
                "en-NG",
                {
                  dateStyle: "medium",
                  timeStyle: "short",
                }
              ).format(
                new Date(date)
              )}
            </p>
          )}

        </div>

        {note && (
          <p className="mt-1 text-xs leading-5 text-black/45">
            {note}
          </p>
        )}

        {changedBy && (
          <p className="mt-1 text-xs text-black/35">
            Changed by {changedBy}
          </p>
        )}

      </div>

    </div>
  );
}

/* ===================================================== */
/* FORMAT STATUS */
/* ===================================================== */

function formatStatus(value) {
  if (!value) {
    return "";
  }

  return String(value)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) =>
      char.toUpperCase()
    );
}