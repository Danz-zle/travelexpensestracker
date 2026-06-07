def normalize_command_text(text):
    if not text:
        return text

    original = text
    stripped = text.strip()

    if not stripped:
        return text

    lower = stripped.lower()

    aliases = {
        # Start / Help / Status
        "hi": "START",
        "hello": "START",
        "guide": "HELP",
        "manual": "HELP",

        # Expense summary
        "exp": "EXPENSE",
        "summary": "EXPENSE",
        "spending": "EXPENSE",

        # Recent expenses
        "last": "RECENT",
        "latest": "RECENT",

        # Delete expense
        "delete expense": "DELETEEXPENSE",
        "delexpense": "DELETEEXPENSE",
        "delexp": "DELETEEXPENSE",
        "deleleexpense": "DELETEEXPENSE",

        # Trips / buckets
        "mytrip": "MYTRIPS",
        "triplist": "MYTRIPS",

        # Daily mode
        "daily": "USEDEFAULT",
        "dailymode": "USEDEFAULT",

        # Shopping DB
        "add": "ADDPRICE",
        "newprice": "ADDPRICE",
        "update": "UPDATEPRICE",
    }

    # Exact alias
    if lower in aliases:
        return aliases[lower]

    # Prefix alias for commands with arguments
    prefix_aliases = {
        "delete expense ": "DELETEEXPENSE ",
        "delexpense ": "DELETEEXPENSE ",
        "delexp ": "DELETEEXPENSE ",
        "deleleexpense ": "DELETEEXPENSE ",

        "add ": "ADDPRICE ",
        "newprice ": "ADDPRICE ",

        "update ": "UPDATEPRICE ",

        "exp ": "EXPENSE ",
        "summary ": "EXPENSE ",

        "last ": "RECENT ",
        "latest ": "RECENT ",
    }

    for alias, command in prefix_aliases.items():
        if lower.startswith(alias):
            return command + stripped[len(alias):]

    return original
