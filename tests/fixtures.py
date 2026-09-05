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

# The real shape movie-planner#158 found: Pathé's actual booking
# confirmations are multipart/mixed with only a text/html part (plus a
# PDF ticket attachment) - no text/plain part anywhere. Trimmed of the
# real email's decorative CSS/marketing boilerplate, but every tag,
# class, and phrase the parser matches against is kept verbatim from a
# real (redacted) confirmation - see movie-planner#158's own comments
# for the untrimmed original.
PATHE_HTML_BOOKING_REF = "AB1CD23"

_PATHE_HTML_BODY = f"""\
<html>
<body>
<h1>Order successful!</h1>
<p>Thank you for your purchase with reservation no.{PATHE_HTML_BOOKING_REF}.<br>Your tickets can be found in this email and in your My Club Pathé account.</p>
<h2>Sunday 9 August 2026 at &nbsp;13:45 <span>Expected end time:&nbsp;16:30</span></h2>
<h2 class="movie-title">Spider-Man: Brand New Day</h2>
<p><a href="https://www.pathe.nl/" style="color: #606369;">Pathé De Munt</a>
- Vijzelstraat 15 1017HD Amsterdam</p>
<p>Original Version
– <b>Auditorium 1 dolby</b>
– <b>1 Seat</b>: Row&nbsp;4&nbsp;Seat&nbsp;1<br>
<b>Number of tickets:</b> 1 Unlimited RS<br>
<b>Price incl. VAT:</b> &euro; 0,00</p>
<p>The screening is scheduled for <b>Sunday 9 August 2026 at 13:45</b> at <br> <b>Pathé De Munt</b></p>
</body>
</html>
"""


def _build_pathe_html_only_email() -> str:
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = "Pathé <no-reply@service.pathe.nl>"
    msg["To"] = "moviewatcher@example.com"
    msg["Subject"] = "🎫 Ticketconfirmation Pathé"
    msg["Date"] = "Sun, 09 Aug 2026 11:27:15 +0000"
    msg.set_content(_PATHE_HTML_BODY, subtype="html")
    msg.add_attachment(
        b"%PDF-1.1 fake ticket pdf, not a real PDF",
        maintype="application",
        subtype="pdf",
        filename="Ticket.pdf",
    )
    return msg.as_string()


PATHE_EMAIL_HTML_ONLY = _build_pathe_html_only_email()
