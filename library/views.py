from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Author, Book, Member, Loan
from .serializers import (
    AuthorSerializer,
    BookSerializer,
    DueDateExtendLoanSerializer,
    MemberSerializer,
    LoanSerializer,
)
from rest_framework.decorators import action
from django.utils import timezone
from .tasks import send_loan_notification
from django.db.models import Q, Count

class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer


class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.select_related('author').all()
    serializer_class = BookSerializer

    @action(detail=True, methods=['post'])
    def loan(self, request, pk=None):
        book = self.get_object()
        if book.available_copies < 1:
            return Response({'error': 'No available copies.'}, status=status.HTTP_400_BAD_REQUEST)
        member_id = request.data.get('member_id')
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            return Response({'error': 'Member does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan = Loan.objects.create(book=book, member=member)
        book.available_copies -= 1
        book.save()
        send_loan_notification.delay(loan.id)
        return Response({'status': 'Book loaned successfully.'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def return_book(self, request, pk=None):
        book = self.get_object()
        member_id = request.data.get('member_id')
        try:
            loan = Loan.objects.get(book=book, member__id=member_id, is_returned=False)
        except Loan.DoesNotExist:
            return Response({'error': 'Active loan does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan.is_returned = True
        loan.return_date = timezone.now().date()
        loan.save()
        book.available_copies += 1
        book.save()
        return Response({'status': 'Book returned successfully.'}, status=status.HTTP_200_OK)

class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer

    @action(detail=False, methods=["get"])
    def top_active(self, request):
        # Get top 5 members with active loans in one query
        active_borrowers = (
            Member.objects
            .annotate(loan_count=Count("loans", filter=Q(loans__is_returned=False)))
            .filter(loan_count__gt=0)
            .select_related("user")
            .order_by("-loan_count")[:5]
        )

        response_data = [
            {
                "id": borrower.id,
                "username": borrower.user.username,
                "email": borrower.user.email,
                "active_loans": borrower.loan_count
            }
            for borrower in active_borrowers
        ]
        
        return Response(response_data, status=status.HTTP_200_OK)


class LoanViewSet(viewsets.ModelViewSet):
    queryset = Loan.objects.all()
    serializer_class = LoanSerializer

    def get_serializer_class(self):
        return DueDateExtendLoanSerializer if self.action == 'extend_loan' else super().get_serializer_class()

    @action(detail=True, methods=['post', 'get'])
    def extend_loan(self, request, pk=None):
        current_loan = self.get_object()
        today = timezone.now().date()

        # Check if loan is overdue
        if current_loan.due_date < today:
            return Response(
                {'error': 'Loan is already overdue.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate extension request
        extension_serializer = self.get_serializer(data=request.data)
        if not extension_serializer.is_valid():
            return Response(extension_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Apply extension
        days_to_extend = extension_serializer.validated_data['additional_days']
        current_loan.due_date += timezone.timedelta(days=days_to_extend)
        current_loan.save()

        # Return updated loan data
        updated_loan_data = LoanSerializer(current_loan).data
        return Response({
            'status': f'Book loan successfully extended by {days_to_extend} days.',
            'data': updated_loan_data
        }, status=status.HTTP_200_OK)


