from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny

from .models import CommunityPost, TEAM_CODES
from .serializers import CommunityPostSerializer


class CommunityPostListView(generics.ListAPIView):
    serializer_class = CommunityPostSerializer
    permission_classes = (AllowAny,)
    http_method_names = ("get", "head", "options")

    def get_queryset(self):
        queryset = CommunityPost.objects.all()
        board = self.request.query_params.get("board")
        team = self.request.query_params.get("team")
        if board is not None and board not in {"free", "teams"}:
            raise ValidationError({"board": "free 또는 teams를 입력해 주세요."})
        if team is not None:
            team = team.upper()
            if team not in TEAM_CODES:
                raise ValidationError({"team": "올바른 팀 코드를 입력해 주세요."})
            if board == "free":
                raise ValidationError({"team": "팀 필터는 teams 게시판에서만 사용할 수 있습니다."})
            queryset = queryset.filter(team_code=team)
        if board is not None:
            queryset = queryset.filter(board=board)
        return queryset
