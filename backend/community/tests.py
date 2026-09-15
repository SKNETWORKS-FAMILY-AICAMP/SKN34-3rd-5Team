import importlib
import json
from pathlib import Path

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from rest_framework.test import APITestCase

from .models import CommunityPost, TEAM_CODES


SEED_FILE = Path(__file__).parent / "migrations/data/community_posts_v1.json"


class CommunityPostApiTests(APITestCase):
    def test_public_list_and_filters_return_seeded_dto(self):
        response = self.client.get("/community/posts/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 350)
        self.assertEqual(response.data[0], {
            "id": "lg-sample-1", "sourceId": "lg-sample-1", "postNumber": "001001", "board": "teams",
            "teamCode": "LG", "author": "예시 작성자", "title": "잠실 외야에서 보면 타구 판단 좀 되나요?",
            "content": "늘 내야에서만 보다가 이번엔 외야로 가볼까 합니다.\n\n공이 뜨면 홈런인지 평범한 플라이인지 구분이 잘 되는지 궁금해요. 중계로 볼 때랑 느낌이 많이 다를 것 같아서요. LG 응원하면서 수비 위치도 같이 보고 싶습니다.",
            "category": "좌석·예매", "createdAt": None, "views": 0, "recommendations": 0,
            "commentCount": 0, "isSample": True,
        })
        self.assertEqual(len(self.client.get("/community/posts/?board=free").data), 50)
        self.assertEqual(len(self.client.get("/community/posts/?board=teams&team=lt").data), 30)

    def test_invalid_filters_and_writes_are_rejected(self):
        for query in ("?board=other", "?team=XX", "?board=free&team=LG"):
            self.assertEqual(self.client.get(f"/community/posts/{query}").status_code, 400)
        for method in (self.client.post, self.client.patch, self.client.delete):
            self.assertEqual(method("/community/posts/", {}, format="json").status_code, 405)


class CommunitySeedMigrationTests(TransactionTestCase):
    reset_sequences = True

    def test_seed_is_complete_insert_only_and_historical(self):
        executor = MigrationExecutor(connection)
        executor.migrate([("community", "0001_initial")])
        historical_apps = executor.loader.project_state([("community", "0001_initial")]).apps
        HistoricalPost = historical_apps.get_model("community", "CommunityPost")
        HistoricalPost.objects.all().delete()
        HistoricalPost.objects.create(
            source_id="custom-post", post_number="999999", board="free", team_code="", author="사용자",
            title="보존할 글", content="사용자 본문", category="잡담",
        )

        migration = importlib.import_module("community.migrations.0002_seed_community_posts")
        with connection.schema_editor() as schema_editor:
            migration.seed_community_posts(historical_apps, schema_editor)
        HistoricalPost.objects.filter(source_id="free-sample-1").update(title="수정된 샘플")
        with connection.schema_editor() as schema_editor:
            migration.seed_community_posts(historical_apps, schema_editor)

        self.assertEqual(HistoricalPost.objects.count(), 351)
        self.assertEqual(HistoricalPost.objects.filter(board="free", is_sample=True).count(), 50)
        self.assertEqual(HistoricalPost.objects.filter(board="teams", is_sample=True).count(), 300)
        self.assertEqual(set(HistoricalPost.objects.filter(board="teams").values_list("team_code", flat=True)), set(TEAM_CODES))
        self.assertEqual(HistoricalPost.objects.get(source_id="free-sample-1").title, "수정된 샘플")
        self.assertEqual(HistoricalPost.objects.get(source_id="custom-post").content, "사용자 본문")

        executor = MigrationExecutor(connection)
        executor.migrate([("community", "0002_seed_community_posts")])
        self.assertEqual(CommunityPost.objects.count(), 351)
        executor.migrate([("community", "0001_initial")])
        self.assertEqual(CommunityPost.objects.count(), 351)
        executor.migrate([("community", "0002_seed_community_posts")])
        self.assertEqual(CommunityPost.objects.count(), 351)

    def test_versioned_json_matches_all_exported_objects(self):
        records = json.loads(SEED_FILE.read_text())
        self.assertEqual((len(records), sum(post["board"] == "free" for post in records)), (350, 50))
        self.assertEqual(len({post["sourceId"] for post in records}), 350)
        self.assertEqual(len({post["postNumber"] for post in records}), 350)
        self.assertEqual(len({(post["title"], post["content"]) for post in records}), 350)
        self.assertEqual(set(records[0]), {"sourceId", "board", "postNumber", "author", "createdAt", "views", "recommendations", "commentCount", "teamCode", "category", "title", "content", "isSample"})
        self.assertEqual({post["teamCode"] for post in records if post["board"] == "teams"}, set(TEAM_CODES))
        self.assertTrue(all(post["createdAt"] is None and post["views"] == post["recommendations"] == post["commentCount"] == 0 and post["isSample"] for post in records))
