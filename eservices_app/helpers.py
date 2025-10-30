# eservices_app/helpers.py

from flask import current_app, url_for
from flask_mail import Message
# Import mail object mula sa __init__.py
from . import mail
# Import models kung kailangan (hindi pa dito pero baka sa iba)
# from .models import User, Ticket, Response as TicketResponse

# TANDAAN: Kailangan nating i-access ang app logger dito
import logging
logger = logging.getLogger(__name__) # Pwede ring from flask import current_app at gamitin current_app.logger

# Maaaring kailanganin ding i-import ang models dito kung gagamitin
from .models import User, Ticket, Response as TicketResponse, Service # Idinagdag ang Service


# === EMAIL SENDING FUNCTIONS ===

def send_new_ticket_email(ticket):
    details_text = "\n".join([f"- {key.replace('_', ' ').title()}: {value}" for key, value in ticket.details.items() if value and ('other' not in key or ticket.details.get(key.replace('_other','')) == 'Other')])
    sender_tuple = ('TCSD e-Services', current_app.config['MAIL_USERNAME'])
    msg = Message(f'New Ticket Created: #{ticket.ticket_number}',
                  sender=sender_tuple,
                  recipients=[ticket.requester_email])
    # Gamitin ang f-string para sa body
    msg.body = f"""
Hi {ticket.requester_name},

This is to confirm that we have successfully received your request.

Ticket Number: {ticket.ticket_number}
Department: {ticket.ticket_department.name}
Service Requested: {ticket.service_type.name}

Request Details:
{details_text}

Our team will review your request and get back to you shortly. You can view the status of this ticket in your "My Tickets" dashboard.

Thank you,
TCSD e-Services Team
"""
    try:
        mail.send(msg)
        logger.info(f"New ticket email sent successfully to {ticket.requester_email} for ticket {ticket.ticket_number}")
    except Exception as e:
        logger.error(f"Error sending new ticket email to {ticket.requester_email} for ticket {ticket.ticket_number}: {e}", exc_info=True) # exc_info=True para sa traceback

def send_staff_notification_email(ticket, response):
    # Siguraduhing na-load ang relationships
    # Ito ay posibleng kailangan kung ang 'ticket' object ay galing sa ibang session o detached
    try:
        managers = ticket.service_type.managers.all() # Kunin muna lahat
    except Exception as e:
        logger.error(f"Error accessing managers for service ID {ticket.service_id}: {e}", exc_info=True)
        managers = []

    recipients = {manager.email for manager in managers}
    admins = User.query.filter_by(role='Admin').all()
    for admin in admins:
        recipients.add(admin.email)

    if not recipients:
        logger.warning(f"No recipients found for staff notification for ticket {ticket.ticket_number}")
        return

    sender_tuple = ('TCSD e-Services', current_app.config['MAIL_USERNAME'])
    msg = Message(f'New Response on Ticket #{ticket.ticket_number}',
                  sender=sender_tuple,
                  recipients=list(recipients))
    msg.body = f"""
Hi Team,
A new response has been added to Ticket #{ticket.ticket_number} by the requester.

Ticket Details:
- Service: {ticket.service_type.name}
- Requester: {ticket.requester_name}

New Response:
--------------------------------------------------
{response.body}
--------------------------------------------------

You can view the ticket here:
{url_for('tickets.ticket_detail', ticket_id=ticket.id, _external=True)}

Thank you,
e-Services Notifier
"""
    try:
        mail.send(msg)
        logger.info(f"Staff notification email sent successfully for ticket {ticket.ticket_number}")
    except Exception as e:
        logger.error(f"Error sending staff notification email for ticket {ticket.ticket_number}: {e}", exc_info=True)

def send_reset_email(user):
    token = user.get_reset_token() # Assuming get_reset_token is a method on the User model
    sender_tuple = ('TCSD e-Services', current_app.config['MAIL_USERNAME'])
    msg = Message('Password Reset Request', sender=sender_tuple, recipients=[user.email])
    msg.body = f"""To reset your password, visit the following link:
{url_for('auth.reset_token', token=token, _external=True)}
If you did not make this request then simply ignore this email and no changes will be made.
This link is valid for 30 minutes.
"""
    try:
        mail.send(msg)
        logger.info(f"Password reset email sent successfully to {user.email}")
    except Exception as e:
        logger.error(f"Error sending password reset email to {user.email}: {e}", exc_info=True)

def send_resolution_email(ticket, response_body):
    sender_tuple = ('TCSD e-Services', current_app.config['MAIL_USERNAME'])
    msg = Message(f'Update on your Ticket: #{ticket.ticket_number} - RESOLVED',
                  sender=sender_tuple,
                  recipients=[ticket.requester_email])
    msg.body = f"""
Hi {ticket.requester_name},
Your ticket #{ticket.ticket_number} regarding "{ticket.service_type.name}" has been marked as RESOLVED.

Here is the final response from our team:
--------------------------------------------------
{response_body}
--------------------------------------------------

If you have further questions, please create a new ticket.

Thank you,
TCSD e-Services Team
"""
    try:
        mail.send(msg)
        logger.info(f"Resolution email sent successfully to {ticket.requester_email} for ticket {ticket.ticket_number}")
    except Exception as e:
        logger.error(f"Error sending resolution email to {ticket.requester_email} for ticket {ticket.ticket_number}: {e}", exc_info=True)