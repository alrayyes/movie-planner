"""Shared fixture data for tests - the real Pathé booking confirmation
shape, with the name and booking number replaced by fictional ones.
"""

PATHE_BOOKING_REF = "N°AB1CD23"

PATHE_EMAIL_PLAIN = f"""\
Booking number

{PATHE_BOOKING_REF}

Hi John,

Thank you for your order! You will find your ticket(s) in this email and in your My Club Pathé account.

Scan the QR code at the cinema. This applies to all types of tickets, including subscriptions.

The Dog Stars
=============

Original Version

Saturday 29/08/26, 12:40 Expected to end at 14:58

Add to calendar



Pathé De Munt

Vijzelstraat 15, 1017HD Amsterdam

Auditorium 1 DOLBY - Row 5 Seat 17



Download your ticket(s)

Unable to attend? Cancel your ticket(s) for free up to 30 minutes before the start of the session

Cancel ticket(s)

Total incl. VAT

3,00€

Tickets:

Unlimited RS



This cinema is pin only.
For films with a viewing rating of 16+ and 18+, admission is only granted from the age of 16. Anyone under 16 will not be admitted in accordance with Dutch law, even if accompanied by an adult. You will be asked for identification. If you cannot identify yourself or do not meet the age requirements, you won't be compensated. For films with the other viewing ratings (6, 9, 12 and 14), children under that age are only admitted when accompanied by an adult.
"""


def _build_pathe_email_mime() -> str:
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = "Pathé Nederland <noreply@pathe.nl>"
    msg["To"] = "john@example.com"
    msg["Subject"] = "Your ticket(s) for The Dog Stars"
    msg.set_content(PATHE_EMAIL_PLAIN)
    msg.add_alternative("<html><body><p>The Dog Stars</p></body></html>", subtype="html")
    return msg.as_string()


PATHE_EMAIL_MIME = _build_pathe_email_mime()
