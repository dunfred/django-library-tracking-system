import logging
from celery import shared_task
from library_system.celery_utils import backoff
from .models import Loan
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

# Configure logger
logger = logging.getLogger(__name__)

@shared_task
def send_loan_notification(loan_id):
    try:
        loan = Loan.objects.get(id=loan_id)
        member_email = loan.member.user.email
        book_title = loan.book.title
        send_mail(
            subject='Book Loaned Successfully',
            message=f'Hello {loan.member.user.username},\n\nYou have successfully loaned "{book_title}".\nPlease return it by the due date.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member_email],
            fail_silently=False,
        )
    except Loan.DoesNotExist:
        pass

@shared_task(bind=True, max_retries=3)
def check_overdue_loans(self):
    current_date = timezone.now().date()
    overdue_loans = Loan.objects.filter(
        is_returned=False, 
        due_date__lte=current_date
    ).select_related('member__user', 'book')

    if not overdue_loans.exists():
        logger.info("No overdue loans found.")
        return {"msg": "No overdue loans to process."}

    for loan in overdue_loans:
        user = loan.member.user
        member_email = user.email

        try:
            send_mail(
                subject="Your Loaned Book is Overdue",
                message=(
                    f"Hello {user.username},\n\n"
                    f"You have a book '{loan.book.title}' that is overdue. "
                    "Please kindly return it."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[member_email],
                fail_silently=False,
            )
            logger.info(f"Overdue email sent to {user.username} ({member_email}).")

        except Exception as e:
            delay = backoff(self.request.retries)
            logger.error(
                f"Failed to send overdue mail to {user.username} ({member_email}). "
                f"Retry attempt {self.request.retries + 1} in {delay}s. Error: {e}"
            )
            raise self.retry(exc=e, countdown=delay)

    return {"msg": "All overdue loan notifications sent successfully."}
