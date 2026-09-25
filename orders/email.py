if is_preorder:
    preorder_html = """
        <div style="
            margin-top: 10px;
            padding: 10px 12px;
            background: #fffbeb;
            border: 1px solid #fde68a;
            border-radius: 10px;
        ">
            <div style="
                color: #92400e;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1px;
                text-transform: uppercase;
            ">
                Pre-order
            </div>

            <div style="
                margin-top: 4px;
                color: #92400e;
                font-size: 11px;
                line-height: 1.6;
            ">
                This item was purchased as a pre-order.
            </div>

            <div style="
                margin-top: 6px;
                color: #92400e;
                font-size: 10px;
                line-height: 1.5;
            ">
                Payment received. This item did not
                reduce current inventory.
            </div>
        </div>
    """