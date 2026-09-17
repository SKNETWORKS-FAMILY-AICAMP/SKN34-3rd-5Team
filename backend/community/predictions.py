from datetime import date, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import GamePrediction, PredictionGame, TEAM_CODES
from .prediction_source import LOCKED_STATUSES, PredictionSourceError, sync_prediction_games
from .serializers import PredictionChoiceWriteSerializer, PredictionGameSerializer


KST = ZoneInfo("Asia/Seoul")


def _today(now=None):
    return (now or timezone.now()).astimezone(KST).date()


def _is_stale(game, now=None):
    now = now or timezone.now()
    if game.status in {"final", "cancelled", "postponed"}:
        return False
    if game.status == "unknown" or game.starts_at is None:
        return True
    maximum = timedelta(minutes=7) if game.status in {"live", "suspended"} else timedelta(minutes=75)
    return not game.source_fetched_at or game.source_fetched_at > now + timedelta(minutes=2) or now - game.source_fetched_at > maximum


def _lock_due_games(now=None):
    now = now or timezone.now()
    PredictionGame.objects.filter(locked_at__isnull=True).filter(
        Q(starts_at__isnull=True) | Q(starts_at__lte=now) | Q(status__in=LOCKED_STATUSES)
    ).update(locked_at=now)


def _counts(game):
    values = dict(game.predictions.values_list("choice").annotate(total=Count("id")))
    home, away = values.get("home", 0), values.get("away", 0)
    total = home + away
    return {
        "home": home,
        "away": away,
        "total": total,
        "homePercent": round(home * 100 / total) if total else 0,
        "awayPercent": round(away * 100 / total) if total else 0,
    }


def _serialize(game, user=None, force_stale=False):
    my_choice = None
    if user and user.is_authenticated:
        my_choice = game.predictions.filter(user=user).values_list("choice", flat=True).first()
    return PredictionGameSerializer({
        "gameId": game.source_id,
        "date": game.game_date,
        "startsAt": game.starts_at,
        "stadium": game.stadium,
        "away": {"code": game.away_team_code, "name": game.away_team_name, "score": game.away_score},
        "home": {"code": game.home_team_code, "name": game.home_team_name, "score": game.home_score},
        "status": game.status,
        "result": game.result or None,
        "locked": game.locked_at is not None,
        "voided": game.voided_at is not None,
        "stale": force_stale or _is_stale(game),
        "sourceFetchedAt": game.source_fetched_at,
        "votes": _counts(game),
        "myChoice": my_choice,
    }).data


def _no_store(data, status=200):
    response = Response(data, status=status)
    response["Cache-Control"] = "no-store"
    return response


def _refresh_current(requested_date):
    if requested_date != _today():
        return None
    try:
        sync_prediction_games()
        return None
    except PredictionSourceError as error:
        return str(error)


@extend_schema(
    parameters=[OpenApiParameter("date", OpenApiTypes.DATE), OpenApiParameter("team", OpenApiTypes.STR)],
    responses={200: PredictionGameSerializer(many=True), 400: OpenApiTypes.OBJECT, 503: OpenApiTypes.OBJECT},
)
@api_view(["GET"])
@permission_classes([AllowAny])
def prediction_game_list(request):
    raw_date = request.query_params.get("date")
    try:
        requested_date = date.fromisoformat(raw_date) if raw_date else _today()
    except ValueError:
        return _no_store({"detail": "날짜는 YYYY-MM-DD 형식으로 입력해 주세요."}, 400)
    team = request.query_params.get("team", "").upper()
    if team and team not in TEAM_CODES:
        return _no_store({"detail": "올바른 팀 코드를 입력해 주세요."}, 400)
    source_error = _refresh_current(requested_date)
    _lock_due_games()
    games = PredictionGame.objects.filter(game_date=requested_date).order_by("starts_at", "source_id")
    if team:
        games = games.filter(Q(home_team_code=team) | Q(away_team_code=team))
    if source_error and not games.exists():
        return _no_store({"detail": source_error}, 503)
    return _no_store([_serialize(game, request.user, bool(source_error)) for game in games])


@extend_schema(responses={200: PredictionGameSerializer, 404: OpenApiTypes.OBJECT})
@api_view(["GET"])
@permission_classes([AllowAny])
def prediction_game_detail(request, game_id):
    game = PredictionGame.objects.filter(pk=game_id).first()
    if game is None:
        return _no_store({"detail": "경기를 찾을 수 없습니다."}, 404)
    source_error = _refresh_current(game.game_date)
    _lock_due_games()
    game.refresh_from_db()
    return _no_store(_serialize(game, request.user, bool(source_error)))


@extend_schema(
    request=PredictionChoiceWriteSerializer,
    responses={200: PredictionGameSerializer, 400: OpenApiTypes.OBJECT, 401: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT, 409: OpenApiTypes.OBJECT, 503: OpenApiTypes.OBJECT},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def prediction_game_vote(request, game_id):
    choice = request.data.get("choice") if isinstance(request.data, dict) else object()
    if not isinstance(request.data, dict) or set(request.data) != {"choice"} or choice is not None and choice not in ("home", "away"):
        return _no_store({"detail": "choice는 home, away 또는 null이어야 합니다."}, 400)
    serializer = PredictionChoiceWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    choice = serializer.validated_data["choice"]
    try:
        sync_prediction_games()
    except PredictionSourceError as error:
        return _no_store({"detail": str(error)}, 503)
    with transaction.atomic():
        game = PredictionGame.objects.select_for_update().filter(pk=game_id).first()
        if game is None:
            return _no_store({"detail": "경기를 찾을 수 없습니다."}, 404)
        now = timezone.now()
        due = game.starts_at is None or game.starts_at <= now or game.status in LOCKED_STATUSES
        if due and game.locked_at is None:
            game.locked_at = now
            game.save(update_fields=("locked_at", "updated_at"))
        if game.locked_at or game.voided_at or _is_stale(game, now):
            return _no_store({"detail": "이 경기는 투표가 마감되었습니다."}, 409)
        if choice is None:
            GamePrediction.objects.filter(game=game, user=request.user).delete()
        else:
            prediction, _ = GamePrediction.objects.get_or_create(game=game, user=request.user, defaults={"choice": choice})
            if prediction.choice != choice:
                prediction.choice = choice
                prediction.save(update_fields=("choice", "updated_at"))
    return _no_store(_serialize(game, request.user))
