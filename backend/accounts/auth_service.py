from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework.exceptions import NotAuthenticated, ValidationError


class AuthService:
    """비밀번호 재설정 메일 발급, 사용자 검증 및 비밀번호 저장을 담당합니다."""

    @staticmethod
    def send_reset_email(email):
        users = get_user_model().objects.filter(email__iexact=email, is_active=True).order_by("pk")
        links = []
        for user in users:
            if not user.has_usable_password():
                continue
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            links.append(f"{user.get_username()}: {settings.AUTH_FRONTEND_ORIGIN}/login#uid={uid}&token={token}")
        if not links:
            return
        send_mail(
            subject="[KBO ROUTE] 비밀번호 재설정",
            message="계정별 비밀번호 재설정 링크입니다.\n\n" + "\n".join(links),
            from_email=None,
            recipient_list=[email],
        )

    @staticmethod
    def get_password_user(actor, uid=None, token=None):
        """호출자의 트랜잭션 안에서 검증부터 비밀번호 저장까지 행 잠금을 유지합니다."""
        User = get_user_model()
        if uid is not None or token is not None:
            if not uid or not token:
                raise ValidationError({'token': 'uid와 token이 모두 필요합니다.'})
            try:
                user_id = force_str(urlsafe_base64_decode(uid))
                user = User.objects.select_for_update().get(pk=user_id, is_active=True)
            except (TypeError, ValueError, OverflowError, User.DoesNotExist, DjangoValidationError):
                raise ValidationError({'token': '유효하지 않은 비밀번호 재설정 링크입니다.'})
            if not user.has_usable_password() or not default_token_generator.check_token(user, token):
                raise ValidationError({'token': '유효하지 않거나 만료된 비밀번호 재설정 링크입니다.'})
        else:
            if not actor.is_authenticated:
                raise NotAuthenticated('로그인하거나 비밀번호 재설정 링크를 이용해 주세요.')
            try:
                user = User.objects.select_for_update().get(pk=actor.pk, is_active=True)
            except User.DoesNotExist:
                raise NotAuthenticated('사용자를 확인할 수 없습니다.')
        return user

    @staticmethod
    def set_password(user, password):
        try:
            validate_password(password, user=user)
        except DjangoValidationError as error:
            raise ValidationError({'password': error.messages})

        # 해시가 바뀌면 기존 비밀번호 재설정 토큰도 무효화됩니다.
        user.set_password(password)
        user.save(update_fields=['password'])
