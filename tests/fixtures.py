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

# The real shape movie-planner#171 found: a *third* Pathé confirmation
# template, structurally closer to the old plain-text template
# (PATHE_EMAIL_PLAIN above) than #158's HTML template - it says
# "Booking number"/"N°..." and puts the title before the date/time -
# but as multipart/alternative with a non-informative "view this in
# HTML" text/plain part (movie-planner#171's other half: envelope.py
# handing that stub to a translation script instead of falling back to
# the real HTML). Trimmed of the real email's decorative CSS/marketing
# boilerplate; the source's own soft line-wrapping inside a paragraph
# (no real HTML tag or entity involved) is kept exactly where the real
# email has it - that literal newline between "27/08/26," and "13:40"
# is what movie-planner#171 is actually about. See movie-planner#171's
# own first comment for the untrimmed original.
PATHE_LEGACY_HTML_BOOKING_REF = "N°AB1CD23"

_PATHE_LEGACY_HTML_BODY = f"""\
<html>
<body>
<style>.some-marketing-css {{ color: #1f2326; }}</style>
<p>Booking number</p>
<p>{PATHE_LEGACY_HTML_BOOKING_REF}</p>
<p>Hi User,</p>
<p>Thank you for your order! You will find your ticket(s) in this email and in your My Club Pathé account.</p>
<p>Scan the QR code at the cinema. This applies to all types of tickets, including subscriptions.</p>
<p>Insidious: Out of the Further</p>
<p>Original Version</p>
<p>Thursday 27/08/26,
                      13:40 Expected to end at  15:46</p>
<p>Pathé City</p>
<p>Kleine-Gartmanplantsoen 15-19,
1017RP Amsterdam</p>
<p><span>Auditorium 4</span> -

                        Row&nbsp;2&nbsp;Seat&nbsp;4

</p>
</body>
</html>
"""


def _build_pathe_legacy_html_email() -> str:
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = "Pathé <no-reply@service.pathe.nl>"
    msg["To"] = "moviewatcher@example.com"
    msg["Subject"] = "🎫 Your filmticket(s) for Pathé"
    msg["Date"] = "Thu, 27 Aug 2026 10:42:07 +0000"
    # A real Pathé confirmation of this template carries a generated,
    # non-informative text/plain alternative alongside the real HTML -
    # exactly the "view this in an HTML-capable client" filler
    # envelope.py's extraction needs to see through (movie-planner#171).
    msg.set_content("This is a multipart/mixed message with an HTML part and a PDF attachment.\n")
    msg.add_alternative(_PATHE_LEGACY_HTML_BODY, subtype="html")
    msg.add_attachment(
        b"%PDF-1.1 fake ticket pdf, not a real PDF",
        maintype="application",
        subtype="pdf",
        filename="Ticket.pdf",
    )
    return msg.as_string()


PATHE_EMAIL_LEGACY_HTML = _build_pathe_legacy_html_email()

# The real shape movie-planner#191 found: a real Pathé confirmation
# whose PDF ticket attachment is mislabeled Content-Type: text/plain
# by Pathé's own mail template - Content-Disposition: attachment is
# still correct, and is the signal that should exclude it from ever
# being picked as the message body. Reuses #158's real HTML booking
# body (same template, already handled once the real body is reached).
PATHE_MISLABELED_ATTACHMENT_BOOKING_REF = PATHE_HTML_BOOKING_REF


def _build_pathe_mislabeled_attachment_email() -> str:
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = "Pathé <no-reply@service.pathe.nl>"
    msg["To"] = "moviewatcher@example.com"
    msg["Subject"] = "🎫 Ticketconfirmation Pathé"
    msg["Date"] = "Sun, 09 Aug 2026 11:27:15 +0000"
    msg.set_content(_PATHE_HTML_BODY, subtype="html")
    msg.add_attachment(
        b"fake ticket attachment content 0123456789, not a real PDF",
        maintype="text",
        subtype="plain",
        filename="E-billet.pdf",
    )
    return msg.as_string()


PATHE_EMAIL_MISLABELED_ATTACHMENT = _build_pathe_mislabeled_attachment_email()

# The real shapes movie-planner#200 found: three more templates from
# Ryan's historical (2009-2019) Pathé archive, each a real, redacted
# .eml - trimmed of decorative CSS/marketing boilerplate the same way
# PATHE_EMAIL_LEGACY_HTML above is, keeping every phrase and tag the
# parser actually matches against verbatim. See movie-planner#200's own
# comments for the untrimmed originals. All three are Dutch and, unlike
# every template above, print no year in their own date text - the
# email's own Date header (received_date) is what supplies one.

# "Pathé Mobiel" (~2013, e.pathe.nl) - also has no end time at all.
PATHE_MOBIEL_BOOKING_REF = "XXXXXXXXX"
PATHE_MOBIEL_DATE_HEADER = "Fri, 28 Jun 2013 19:28:07 +0200"

_PATHE_MOBIEL_HTML_BODY = f"""\
<html>
<body>
<td style="font-weight: bold;" valign="middle">
<span style="font-size: 14px;">World War Z 3D O3D</span><br /> <br />
Vrijdag 28 juni, 20:30<br /> Pathe Arena<br /> <br /> Unlimited x 1<br /> <br />
Zaal  4<br /> Row 1 Seat 1<br /> Totaal: &euro; 0.00</td>
<td>Path&eacute; Unlimited reservering bevestigd</td>
<td>Gebruik bij communicatie met de klantenservice de referentiecode
<strong>{PATHE_MOBIEL_BOOKING_REF}</strong>.</td>
<td>Referentie: {PATHE_MOBIEL_BOOKING_REF}<br /> </td>
</body>
</html>
"""


def _build_pathe_mobiel_email() -> str:
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = "Pathé <aankoop@e.pathe.nl>"
    msg["To"] = "user@example.com"
    msg["Subject"] = "Bestelling via Pathé Mobiel (XXXXXXXXX)"
    msg["Date"] = PATHE_MOBIEL_DATE_HEADER
    # Same "view this in an HTML-capable client" placeholder shape as
    # PATHE_EMAIL_LEGACY_HTML - its own tracking link contains a digit,
    # which is the second half of movie-planner#200 (the #171
    # digit-heuristic false-positiving on it).
    msg.set_content(
        "Dit is een bevestiging van uw aankoop. Waarschijnlijk ondersteunt uw "
        "e-mail programma geen HTML.\nBezoek de volgende pagina om dit bericht "
        "in uw internet-browser te lezen:\n\n"
        "http://e.pathe.nl/x/?S7Y1NPqfa2tsbvy.yNbM3NzcxPx.gW1xclFmQUl8cWkSiJWUCgAA12\n"
    )
    msg.add_alternative(_PATHE_MOBIEL_HTML_BODY, subtype="html")
    return msg.as_string()


PATHE_EMAIL_MOBIEL = _build_pathe_mobiel_email()

# "Ticketbevestiging" (~2014, pathe.emsecure.net) - also has no end time.
PATHE_TICKETBEVESTIGING_BOOKING_REF = "000000000000000"
PATHE_TICKETBEVESTIGING_DATE_HEADER = "Fri, 26 Dec 2014 11:27:09 +0100"

_PATHE_TICKETBEVESTIGING_HTML_BODY = f"""\
<html>
<body>
<td colspan="2" style="font-weight: bold;">The Imitation Game</td>
<td>&nbsp;</td></tr><tr><td>
<span class="datetime">Vrijdag 26 december om 21:05</span><br /><span class="locationhall">Path&eacute; Tuschinski, Amsterdam: <span>Zaal 1</span></span><br /><span class="seats">Rij: 1 Stoel: 1</span>
<td>Gebruik bij contact de referentiecode {PATHE_TICKETBEVESTIGING_BOOKING_REF}.</td>
<td>Klantenservice | Referentie: {PATHE_TICKETBEVESTIGING_BOOKING_REF}</td>
</body>
</html>
"""


def _build_pathe_ticketbevestiging_email() -> str:
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = "Pathé <aankoop@pathe.emsecure.net>"
    msg["To"] = "user@example.com"
    msg["Subject"] = "Pathé Ticketbevestiging"
    msg["Date"] = PATHE_TICKETBEVESTIGING_DATE_HEADER
    msg.set_content(
        "Waarschijnlijk ondersteunt je e-mail programma geen HTML.\n"
        "Bezoek de volgende pagina om dit bericht in je internet-browser te "
        "lezen:\n"
        "http://pathe.emsecure.net/optiext/optiextension.dll?ID=3D%2BxC%2BAuZN_yqmEY1O\n"
    )
    msg.add_alternative(_PATHE_TICKETBEVESTIGING_HTML_BODY, subtype="html")
    return msg.as_string()


PATHE_EMAIL_TICKETBEVESTIGING = _build_pathe_ticketbevestiging_email()

# "Reservering <title> - Referentie: ..." (2019, info.pathe.nl) - the
# only one of the three that does carry an end time, and the only one
# with an "(OV)"/language-tag line between the title and the date.
PATHE_RESERVERING_BOOKING_REF = "000000000000000"
PATHE_RESERVERING_DATE_HEADER = "Thu, 13 Jun 2019 14:53:15 +0200"

_PATHE_RESERVERING_HTML_BODY = f"""\
<html>
<body>
<td colspan="2" style="font-weight: bold;">Long Shot
<span style="color:#6d6e71;">(OV)</span></td><td>&nbsp;</td></tr><tr><td>
<span class="datetime">Donderdag 13 juni om 15:20 tot 17:39</span><br /><span class="locationhall">Path&eacute; De Munt, Amsterdam</span><br /><span class="seats">Zaal  1
 </span><br /><span class="seats">Rij: 1 stoel: 1</span>
<td>Gebruik bij contact de referentiecode {PATHE_RESERVERING_BOOKING_REF}.</td>
<td>Klantenservice | Referentie: {PATHE_RESERVERING_BOOKING_REF}</td>
</body>
</html>
"""


def _build_pathe_reservering_email() -> str:
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = "Pathé De Munt, Amsterdam <info@info.pathe.nl>"
    msg["To"] = "user@example.com"
    msg["Subject"] = f"Reservering Long Shot - Referentie: {PATHE_RESERVERING_BOOKING_REF}"
    msg["Date"] = PATHE_RESERVERING_DATE_HEADER
    msg.set_content(
        "Waarschijnlijk ondersteunt je e-mail programma geen HTML.\n"
        "Bezoek de volgende pagina om dit bericht in je internet-browser te "
        "lezen:\n"
        "http://info.pathe.nl/optiext/optiextension.dll?ID=3D5VZMySfjxxTr_PYbXybZYMMTx\n"
    )
    msg.add_alternative(_PATHE_RESERVERING_HTML_BODY, subtype="html")
    return msg.as_string()


PATHE_EMAIL_RESERVERING = _build_pathe_reservering_email()
