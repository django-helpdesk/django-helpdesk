"""Static content used by the demo_data command: people, queues, issues, replies."""

# (username, first name, last name, queues this person usually works on)
STAFF = [
    ("alice", "Alice", "Martin", ["IT", "DH"]),
    ("bruno", "Bruno", "Costa", ["SP", "BIL"]),
    ("chloe", "Chloé", "Dubois", ["WEB", "DH", "SP"]),
    ("kenji", "Kenji", "Sato", ["IT", "WEB"]),
]

# A customer with a login, who submits tickets through the public form.
CUSTOMER = ("sam", "Sam", "Rivera", "sam.rivera@example.com")

# Submitters without an account, writing in by e-mail or through the public form.
SUBMITTERS = [
    "maria.gonzalez@example.com",
    "li.wei@example.org",
    "olivia.brown@example.net",
    "ahmed.hassan@example.com",
    "emma.schmidt@example.org",
    "noah.johnson@example.com",
    "fatima.diallo@example.net",
    "lucas.moreau@example.com",
    "priya.sharma@example.org",
    "tom.wilson@example.com",
]

# (title, slug, e-mail address). DH and SP come from the demo.json fixture.
NEW_QUEUES = [
    ("IT Support", "IT", "it-support@example.com"),
    ("Billing", "BIL", "billing@example.com"),
    ("Website", "WEB", "web@example.com"),
]
QUEUE_WEIGHTS = {"IT": 34, "DH": 18, "SP": 20, "BIL": 16, "WEB": 12}

# (title, description, resolution) per queue slug.
ISSUES = {
    "IT": [
        (
            "Laptop will not connect to the office Wi-Fi",
            (
                "Since this morning my laptop sees the office network but fails to "
                "connect. Other devices work fine."
            ),
            (
                "Removed the stale Wi-Fi profile and re-enrolled the laptop "
                "certificate. Connection is stable again."
            ),
        ),
        (
            "VPN disconnects every few minutes",
            (
                "When working from home the VPN drops roughly every five minutes, "
                "which cuts my calls."
            ),
            (
                "Updated the VPN client to the latest version and switched the "
                "profile to TCP. No more drops reported."
            ),
        ),
        (
            "Printer on 2nd floor shows paper jam",
            (
                "The printer next to the meeting rooms keeps reporting a paper jam "
                "even though the trays are empty."
            ),
            "A torn label was stuck in the fuser. Removed it and ran a cleaning cycle.",
        ),
        (
            "Request access to the shared finance drive",
            (
                "I joined the finance team this week and need read/write access to "
                "the shared finance drive."
            ),
            "Added the user to the finance-rw group after manager approval.",
        ),
        (
            "Outlook keeps asking for my password",
            (
                "Outlook prompts for my password every time I open it, even after "
                "ticking 'remember me'."
            ),
            (
                "Cleared the cached credentials and re-registered the device. The "
                "prompt is gone."
            ),
        ),
        (
            "Monitor flickering when docked",
            (
                "My external monitor flickers as soon as I plug the laptop into the "
                "docking station."
            ),
            (
                "Replaced the USB-C cable with a certified one and updated the dock "
                "firmware."
            ),
        ),
        (
            "Install Python 3.13 on build machine",
            "We need Python 3.13 on the CI build machine to test the next release.",
            (
                "Installed Python 3.13 side by side with the existing versions and "
                "updated the CI image."
            ),
        ),
        (
            "Phishing e-mail reported",
            (
                "I received an e-mail asking me to reset my password through a "
                "strange link. Forwarding it as an attachment."
            ),
            (
                "Blocked the sender domain, purged the message from all mailboxes "
                "and reminded the team about the phishing guide."
            ),
        ),
        (
            "Laptop battery drains very fast",
            "My laptop goes from full to empty in about an hour, even with light use.",
            "Battery health was at 41%. Replaced the battery under warranty.",
        ),
        (
            "Cannot share screen in video calls",
            "Screen sharing shows a black window for the other participants.",
            (
                "Granted the screen recording permission to the video call app in "
                "the OS privacy settings."
            ),
        ),
    ],
    "DH": [
        (
            "E-mail replies are not attached to the ticket",
            (
                "When a customer replies to a notification, a new ticket is created "
                "instead of a follow-up on the existing one."
            ),
            (
                "The mail client stripped the ticket ID from the subject. Enabled "
                "Message-ID threading on the queue."
            ),
        ),
        (
            "Add a custom field for the contract number",
            (
                "We would like agents to record the customer's contract number on "
                "each ticket."
            ),
            (
                "Created a 'Customer reference' custom field, visible to staff and "
                "submitters."
            ),
        ),
        (
            "Escalation does not run on weekends",
            "Tickets that should be escalated on Saturday wait until Monday.",
            (
                "Weekend days were listed as escalation exclusions. Removed them "
                "for the critical queue."
            ),
        ),
        (
            "Kanban board is slow with many tickets",
            "Loading the kanban view takes more than ten seconds on our main queue.",
            "Limited closed tickets shown on the board to the last six weeks.",
        ),
        (
            "Translate notification e-mails to Spanish",
            "Our Madrid office needs the notification e-mails in Spanish.",
            "Set the queue locale to 'es'. The Spanish templates are now used.",
        ),
        (
            "Public form should ask for a phone number",
            (
                "Customers often forget to leave a phone number. Can we add a "
                "field to the public submission form?"
            ),
            "Added an optional custom field and enabled it on the public form.",
        ),
        (
            "Agent cannot see tickets of the Website queue",
            "Our new agent only sees one queue in the dashboard.",
            "Granted the missing queue permission to the agent.",
        ),
        (
            "Upgrade to the latest django-helpdesk release",
            "Plan the upgrade of our helpdesk to the latest release.",
            (
                "Upgraded on staging, ran migrations, checked e-mail import, then "
                "upgraded production."
            ),
        ),
    ],
    "SP": [
        (
            "App crashes when exporting a report to PDF",
            (
                "Exporting the monthly report to PDF closes the application "
                "without any error message."
            ),
            "Fixed in 4.2.1: the PDF exporter ran out of memory on large tables.",
        ),
        (
            "Sync between mobile and desktop is delayed",
            "Changes made on my phone take hours to appear on the desktop version.",
            (
                "The background sync was disabled by the phone's battery saver. "
                "Added the app to the allow list."
            ),
        ),
        (
            "Feature request: dark mode",
            "It would be great to have a dark theme for late evening work.",
            "Dark mode shipped in version 4.2.",
        ),
        (
            "Cannot import CSV with semicolons",
            (
                "Our CSV files use semicolons as separators and the import wizard "
                "rejects them."
            ),
            (
                "Explained how to pick the separator in the import wizard. "
                "Auto-detection is planned."
            ),
        ),
        (
            "License key rejected after reinstall",
            "I reinstalled my computer and the license key is now refused.",
            "Released the previous activation from the license portal.",
        ),
        (
            "Search does not find accented words",
            "Searching for 'cafe' does not return records containing 'café'.",
            "Enabled accent-insensitive search in the index settings.",
        ),
        (
            "Slow startup after update",
            "Since the last update the application takes almost a minute to start.",
            "The local cache was rebuilt at every start. Fixed in 4.2.2.",
        ),
        (
            "Charts are blank on Windows 11",
            "All the dashboard charts are empty on Windows 11 machines.",
            (
                "Hardware acceleration bug in the graphics driver. Updated driver "
                "fixes it."
            ),
        ),
    ],
    "BIL": [
        (
            "Charged twice for the same invoice",
            "My card was charged twice for invoice INV-2291.",
            (
                "Refunded the duplicate charge. It will appear on the statement in "
                "3 to 5 business days."
            ),
        ),
        (
            "Update the company address on invoices",
            "We moved offices. Please update the billing address on future invoices.",
            "Billing address updated. Next invoices will use the new address.",
        ),
        (
            "Request a refund for unused seats",
            "We reduced our team from 25 to 18 users and would like a prorated refund.",
            "Prorated refund issued for 7 seats.",
        ),
        (
            "VAT number missing on invoice",
            (
                "Our VAT number does not appear on the last invoice, so our "
                "accounting cannot book it."
            ),
            "Added the VAT number to the account and re-issued the invoice.",
        ),
        (
            "Switch from monthly to yearly plan",
            "We would like to move to yearly billing to get the discount.",
            "Plan switched to yearly billing with the remaining month credited.",
        ),
        (
            "Payment failed with expired card",
            (
                "We got an e-mail saying the payment failed. The card was renewed "
                "last month."
            ),
            "Customer updated the card in the portal and the payment went through.",
        ),
    ],
    "WEB": [
        (
            "Contact form returns an error 500",
            "Submitting the contact form on the website shows a server error.",
            (
                "The SMTP password had expired. Rotated it and added monitoring on "
                "the form."
            ),
        ),
        (
            "Broken images on the blog",
            "Several blog posts show broken image icons since the migration.",
            "Fixed the media URLs left over from the old domain.",
        ),
        (
            "Page load is slow on mobile",
            "The home page takes more than 6 seconds to load on a phone.",
            "Compressed the hero images and enabled lazy loading.",
        ),
        (
            "Update the team page",
            "Please add the three new team members to the 'About us' page.",
            "Team page updated with the new photos and bios.",
        ),
        (
            "Cookie banner shows up on every page",
            "The cookie consent banner appears again after each click.",
            "The consent cookie was set on the wrong domain. Fixed.",
        ),
        (
            "Typo in the pricing page",
            "The pricing page says 'anual' instead of 'annual'.",
            "Typo fixed.",
        ),
    ],
}

STAFF_REPLIES = [
    "Thanks for reporting this. I am looking into it and will get back to you shortly.",
    "Could you send us a screenshot of the error and tell us when it started?",
    "I have been able to reproduce the problem on our side. Working on a fix.",
    "We have applied a change. Can you check whether it works better now?",
    "This needs a quick call. Are you available tomorrow morning?",
    "Thanks for your patience, we are still waiting on our supplier.",
]

CUSTOMER_REPLIES = [
    "Here is the screenshot you asked for.",
    "It started on Monday, right after the update.",
    "I tried again this morning and it is still happening.",
    "Thanks, it seems to be working now. I will let you know if it comes back.",
    "Tomorrow at 10:00 works for me.",
    "Any news on this? It is starting to block my work.",
]

PRIVATE_NOTES = [
    "Checked the logs, nothing obvious. Escalating to the second level.",
    "Same issue as last month, see the KB article.",
    "Waiting for the vendor to confirm the fix date.",
    "Customer is on the premium plan, keep the response time short.",
    "Probably a configuration problem on their side, asked for details.",
    "Linked to the release planned for next week.",
]

REOPEN_REPLIES = [
    "Sorry, the problem is back since yesterday.",
    "It worked for a day but now it fails again.",
]

# Tickets submitted by the customer with a login
# (queue slug, title, description, resolution or None while open).
CUSTOMER_TICKETS = [
    (
        "SP",
        "How do I share a report with my team?",
        (
            "I created a report and would like my colleagues to see it without "
            "exporting it each time."
        ),
        "Explained the sharing options. A KB article covers it as well.",
    ),
    (
        "BIL",
        "Invoice for October not received",
        "I did not receive the invoice for October by e-mail. Could you send it again?",
        "Re-sent the invoice and fixed the billing contact address.",
    ),
    (
        "SP",
        "Reports export cuts off long names",
        "When I export a report, names longer than 30 characters are cut.",
        None,
    ),
]

KB_CATEGORIES = [
    (
        "Getting started",
        "getting-started",
        "Everything you need for your first days with our products.",
        "SP",
        [
            (
                "Installing the desktop application",
                "How do I install the desktop application?",
                (
                    "Download the installer from your account page, run it and sign "
                    "in with your usual credentials. The application updates itself "
                    "automatically."
                ),
            ),
            (
                "Sharing reports with your team",
                "How can my colleagues see the reports I create?",
                (
                    "Open the report, click **Share** and pick the people or the "
                    "team who should see it. They will find it under *Shared with "
                    "me*."
                ),
            ),
            (
                "Importing data from a CSV file",
                "Which CSV formats can I import?",
                (
                    "Comma and semicolon separators are supported. Choose the "
                    "separator on the first step of the import wizard."
                ),
            ),
        ],
    ),
    (
        "Billing & payments",
        "billing",
        "Invoices, payment methods and plan changes.",
        "BIL",
        [
            (
                "Changing your payment method",
                "How do I update the card used for payments?",
                (
                    "Go to **Account > Billing**, click *Payment method* and enter "
                    "the new card. The next invoice will use it."
                ),
            ),
            (
                "Getting a refund",
                "Can I get a refund for unused seats?",
                (
                    "Yes. Seats removed during a billing period are refunded "
                    "prorata on the next invoice. Open a ticket in the Billing queue "
                    "if you need it sooner."
                ),
            ),
        ],
    ),
    (
        "IT how-tos",
        "it-howto",
        "Self-service guides from the IT team.",
        "IT",
        [
            (
                "Connecting to the VPN",
                "How do I connect to the company VPN from home?",
                (
                    "Install the VPN client from the software center, then sign in "
                    "with your company account. Use the *TCP* profile if your "
                    "connection keeps dropping."
                ),
            ),
            (
                "Recognizing a phishing e-mail",
                "How can I tell if an e-mail is a phishing attempt?",
                (
                    "Check the sender address, hover links before clicking them and "
                    "never type your password on a page opened from an e-mail. "
                    "Forward anything suspicious to the IT Support queue."
                ),
            ),
        ],
    ),
]

CHECKLIST_TEMPLATES = {
    "onboarding": (
        "New employee onboarding",
        [
            "Order laptop",
            "Create company account",
            "Add to mailing lists",
            "Grant access to shared drives",
            "Schedule security training",
        ],
    ),
    "refund": (
        "Refund procedure",
        [
            "Check the original payment",
            "Get approval from finance",
            "Issue the refund",
            "Send confirmation to the customer",
        ],
    ),
}
