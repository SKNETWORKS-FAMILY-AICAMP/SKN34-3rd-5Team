import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q

import community.models


CREATE_POST_NUMBER_SEQUENCE = """
CREATE SEQUENCE community_post_number_seq MINVALUE 1 MAXVALUE 999999 NO CYCLE;
DO $$
DECLARE highest integer;
BEGIN
    SELECT COALESCE(MAX(post_number::integer), 0)
      INTO highest
      FROM community_communitypost
     WHERE post_number ~ '^[0-9]{6}$';
    IF highest = 0 THEN
        PERFORM setval('community_post_number_seq', 1, false);
    ELSE
        PERFORM setval('community_post_number_seq', LEAST(highest, 999999), true);
    END IF;
END $$;
"""


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("community", "0002_seed_community_posts"),
    ]

    operations = [
        migrations.RunSQL(CREATE_POST_NUMBER_SEQUENCE, "DROP SEQUENCE IF EXISTS community_post_number_seq"),
        migrations.AlterField(
            model_name="communitypost",
            name="source_id",
            field=models.CharField(default=community.models.new_post_source_id, editable=False, max_length=40, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name="communitypost",
            name="post_number",
            field=models.CharField(default=community.models.next_post_number, editable=False, max_length=6, unique=True),
        ),
        migrations.AlterField(
            model_name="communitypost",
            name="created_at",
            field=models.DateTimeField(blank=True, default=django.utils.timezone.now, null=True),
        ),
        migrations.AddField(
            model_name="communitypost",
            name="owner",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="community_posts", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="communitypost",
            name="idempotency_key",
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddConstraint(
            model_name="communitypost",
            constraint=models.CheckConstraint(condition=Q(post_number__gte="000001", post_number__regex=r"^[0-9]{6}$"), name="community_post_number_valid"),
        ),
        migrations.AddConstraint(
            model_name="communitypost",
            constraint=models.UniqueConstraint(condition=Q(idempotency_key__isnull=False, owner__isnull=False), fields=("owner", "idempotency_key"), name="community_post_owner_idempotency_unique"),
        ),
        migrations.CreateModel(
            name="CommunityComment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content", models.TextField(max_length=2000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="community_comments", to=settings.AUTH_USER_MODEL)),
                ("post", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="community.communitypost")),
            ],
            options={"ordering": ("created_at", "pk")},
        ),
        migrations.CreateModel(
            name="CommunityVote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("value", models.CharField(choices=(("up", "up"), ("down", "down")), max_length=4)),
                ("post", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="votes", to="community.communitypost")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="community_votes", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="communityvote",
            constraint=models.UniqueConstraint(fields=("post", "user"), name="community_vote_post_user_unique"),
        ),
        migrations.AddConstraint(
            model_name="communityvote",
            constraint=models.CheckConstraint(condition=Q(value__in=("up", "down")), name="community_vote_value_valid"),
        ),
        migrations.CreateModel(
            name="CommunityReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.CharField(choices=(("spam", "spam"), ("abuse", "abuse"), ("inappropriate", "inappropriate"), ("privacy", "privacy"), ("other", "other")), max_length=13)),
                ("detail", models.CharField(blank=True, max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("post", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reports", to="community.communitypost")),
                ("reporter", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="community_reports", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="communityreport",
            constraint=models.UniqueConstraint(fields=("post", "reporter"), name="community_report_post_reporter_unique"),
        ),
        migrations.AddConstraint(
            model_name="communityreport",
            constraint=models.CheckConstraint(condition=Q(reason__in=("spam", "abuse", "inappropriate", "privacy", "other")), name="community_report_reason_valid"),
        ),
        migrations.CreateModel(
            name="PredictionGame",
            fields=[
                ("source_id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("game_date", models.DateField(db_index=True)),
                ("starts_at", models.DateTimeField(blank=True, null=True)),
                ("stadium", models.CharField(blank=True, max_length=80)),
                ("away_team_code", models.CharField(max_length=2)),
                ("away_team_name", models.CharField(max_length=20)),
                ("home_team_code", models.CharField(max_length=2)),
                ("home_team_name", models.CharField(max_length=20)),
                ("away_score", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("home_score", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("status", models.CharField(choices=(("scheduled", "scheduled"), ("live", "live"), ("final", "final"), ("cancelled", "cancelled"), ("postponed", "postponed"), ("suspended", "suspended"), ("unknown", "unknown")), max_length=10)),
                ("result", models.CharField(blank=True, choices=(("", "pending"), ("home", "home"), ("away", "away"), ("draw", "draw")), default="", max_length=4)),
                ("source_fetched_at", models.DateTimeField()),
                ("locked_at", models.DateTimeField(blank=True, null=True)),
                ("voided_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddConstraint(
            model_name="predictiongame",
            constraint=models.CheckConstraint(condition=Q(home_team_code__in=("LG", "HH", "SK", "SS", "NC", "KT", "LT", "HT", "OB", "WO")), name="community_prediction_home_team_valid"),
        ),
        migrations.AddConstraint(
            model_name="predictiongame",
            constraint=models.CheckConstraint(condition=Q(away_team_code__in=("LG", "HH", "SK", "SS", "NC", "KT", "LT", "HT", "OB", "WO")), name="community_prediction_away_team_valid"),
        ),
        migrations.AddConstraint(
            model_name="predictiongame",
            constraint=models.CheckConstraint(condition=~Q(home_team_code=models.F("away_team_code")), name="community_prediction_teams_distinct"),
        ),
        migrations.AddConstraint(
            model_name="predictiongame",
            constraint=models.CheckConstraint(condition=Q(status__in=("scheduled", "live", "final", "cancelled", "postponed", "suspended", "unknown")), name="community_prediction_status_valid"),
        ),
        migrations.AddConstraint(
            model_name="predictiongame",
            constraint=models.CheckConstraint(condition=Q(result__in=("", "home", "away", "draw")), name="community_prediction_result_valid"),
        ),
        migrations.CreateModel(
            name="GamePrediction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("choice", models.CharField(choices=(("home", "home"), ("away", "away")), max_length=4)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("game", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="predictions", to="community.predictiongame")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="game_predictions", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="gameprediction",
            constraint=models.UniqueConstraint(fields=("user", "game"), name="community_prediction_user_game_unique"),
        ),
        migrations.AddConstraint(
            model_name="gameprediction",
            constraint=models.CheckConstraint(condition=Q(choice__in=("home", "away")), name="community_prediction_choice_valid"),
        ),
    ]
