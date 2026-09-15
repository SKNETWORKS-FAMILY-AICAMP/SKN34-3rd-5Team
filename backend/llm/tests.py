from unittest.mock import patch

import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import DatabaseError
from django.test import override_settings
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from openai import OpenAIError
from rest_framework.test import APITestCase

from .chat_service import ChatService
from .models import ChatMessage, ChatSession, ChatTurn, Document, DocumentChunk


class DocumentChatCoexistenceTest(APITestCase):
    def test_chat_deletion_preserves_document_and_embedding(self):
        from django.urls import resolve

        self.assertEqual(resolve("/admin/").url_name, "index")
        self.client.force_authenticate(
            user=get_user_model().objects.create_user(username="coexist")
        )
        document = Document.objects.create(title="문서", source="test")
        chunk = DocumentChunk.objects.create(
            document=document, content="원문", chunk_index=0, embedding=[1.0] * 1536
        )
        session = self.client.post("/chat/sessions/", {"title": "채팅"}, format="json")
        self.assertEqual(session.status_code, 201)
        self.assertEqual(
            self.client.delete(f"/chat/sessions/{session.json()['id']}/").status_code, 204
        )
        chunk.refresh_from_db()
        self.assertEqual(chunk.content, "원문")
        self.assertEqual(len(chunk.embedding), 1536)
        self.assertTrue(Document.objects.filter(pk=document.pk).exists())


class ChatApiTest(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester")
        self.client.force_authenticate(user=self.user)
        self.prompts = []

        def respond(prompt):
            self.prompts.append(prompt.to_messages())
            return AIMessage(content="테스트 답변")

        # 모델만 대체하고 View, ChatService, 히스토리 저장은 실제 실행합니다.
        patcher = patch("llm.chat_service.ChatOpenAI", return_value=RunnableLambda(respond))
        self.model = patcher.start()
        self.addCleanup(patcher.stop)

    def test_session_and_message_crud(self):
        room = self.client.post("/chat/sessions/", {"title": "test"}, format="json")
        self.assertEqual(room.status_code, 201)
        session_id = room.json()["id"]

        updated = self.client.patch(
            f"/chat/sessions/{session_id}/",
            {"title": "updated"},
            format="json",
        )
        self.assertEqual(updated.json()["title"], "updated")

        message = self.client.post(
            f"/chat/sessions/{session_id}/messages/",
            {"content": "hello"},
            format="json",
        )
        self.assertEqual(message.status_code, 201)
        self.assertEqual(message.json()["assistant_message"], "테스트 답변")
        self.assertEqual(
            self.client.get(f"/chat/sessions/{session_id}/messages/").json()[0]["content"],
            "hello",
        )

        second = self.client.post(
            f"/chat/sessions/{session_id}/messages/", {"content": "두 번째 질문"}, format="json"
        )
        self.assertEqual(second.status_code, 201)
        self.assertEqual(
            [(m.type, m.content) for m in self.prompts[1][1:]],
            [("human", "hello"), ("ai", "테스트 답변"), ("human", "두 번째 질문")],
        )
        messages = self.client.get(f"/chat/sessions/{session_id}/messages/").json()
        self.assertEqual([m["role"] for m in messages], ["human", "ai", "human", "ai"])
        self.assertEqual([m["sequence_no"] for m in messages], [1, 2, 3, 4])

        self.assertEqual(self.client.delete(f"/chat/sessions/{session_id}/").status_code, 204)
        self.assertFalse(ChatMessage.objects.exists())

    def test_invalid_input_and_other_users_session_do_not_call_llm(self):
        session = ChatSession.objects.create(user=self.user)
        url = f"/chat/sessions/{session.pk}/messages/"
        self.assertEqual(self.client.post(url, {"content": " "}, format="json").status_code, 400)
        self.client.force_authenticate(user=get_user_model().objects.create_user(username="other"))
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"content": "hello"}, format="json").status_code, 404)
        self.client.force_authenticate(user=None)
        self.assertIn(self.client.post(url, {"content": "hello"}).status_code, (401, 403))
        self.model.assert_not_called()

    def test_llm_failure_returns_502_without_saving_messages(self):
        def fail(prompt):
            raise OpenAIError("upstream private error")

        self.model.return_value = RunnableLambda(fail)
        session = ChatSession.objects.create(user=self.user)
        response = self.client.post(
            f"/chat/sessions/{session.pk}/messages/", {"content": "hello"}, format="json"
        )
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("upstream private error", response.content.decode())
        self.assertFalse(session.messages.exists())

    def test_missing_llm_credentials_returns_sanitized_502_without_saving_messages(self):
        self.model.side_effect = OpenAIError("private missing API key detail")
        session = ChatSession.objects.create(user=self.user)
        response = self.client.post(
            f"/chat/sessions/{session.pk}/messages/", {"content": "hello"}, format="json"
        )
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("private missing API key detail", response.content.decode())
        self.assertFalse(session.messages.exists())

    def test_storage_failure_is_not_reported_as_success(self):
        session = ChatSession.objects.create(user=self.user)
        with patch("llm.chat_message_histories.ChatMessage.objects.bulk_create", side_effect=DatabaseError):
            with self.assertRaises(DatabaseError):
                self.client.post(
                    f"/chat/sessions/{session.pk}/messages/", {"content": "hello"}, format="json"
                )
        self.assertFalse(session.messages.exists())

    @staticmethod
    def events(response):
        body = b"".join(response.streaming_content).decode()
        return [
            (frame.splitlines()[0][7:], json.loads(frame.splitlines()[1][6:]))
            for frame in body.strip().split("\n\n")
        ]

    def stream(self, session, question="hello", chunks=("첫 ", "답변")):
        class Chain:
            def stream(inner_self, values):
                yield from chunks

        with patch("llm.chat_service.ChatService.get_chain", return_value=Chain()):
            response = self.client.post(
                f"/chat/sessions/{session.pk}/messages/",
                {"content": question}, format="json", HTTP_ACCEPT="text/event-stream",
            )
            return self.events(response)

    def finalize(self, event, prefix, final_status):
        return self.client.post(
            f"/chat/turns/{event['turn_id']}/finalize/",
            {"receipt": event["receipt"], "prefix": prefix, "status": final_status},
            format="json",
        )

    @override_settings(CHAT_CHECKPOINT_SIGNING_KEY="test-only-signing-key")
    def test_full_stream_persists_only_after_explicit_finalize_with_ids(self):
        session = ChatSession.objects.create(user=self.user)
        events = self.stream(session)
        self.assertEqual([name for name, _ in events], ["checkpoint", "delta", "delta", "done"])
        self.assertFalse(session.messages.exists())
        result = self.finalize(events[-1][1], "첫 답변", "completed")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["status"], "completed")
        self.assertIsInstance(result.json()["user_message_id"], int)
        self.assertIsInstance(result.json()["assistant_message_id"], int)
        self.assertEqual(
            list(session.messages.values_list("role", "message", "status")),
            [("human", "hello", ""), ("ai", "첫 답변", "completed")],
        )

    @override_settings(CHAT_CHECKPOINT_SIGNING_KEY="test-only-signing-key")
    def test_stop_exact_prefix_wins_completion_race_and_is_idempotent(self):
        session = ChatSession.objects.create(user=self.user)
        events = self.stream(session, chunks=("받은", "뒷부분"))
        partial, completed = events[1][1], events[-1][1]
        first = self.finalize(completed, "받은뒷부분", "completed").json()
        stopped = self.finalize(partial, "받은", "stopped").json()
        repeated = self.finalize(completed, "받은뒷부분", "completed").json()
        self.assertEqual(stopped["status"], "stopped")
        self.assertEqual(stopped["assistant_message"], "받은")
        self.assertEqual(stopped["user_message_id"], first["user_message_id"])
        self.assertEqual(stopped["assistant_message_id"], first["assistant_message_id"])
        self.assertEqual(repeated, stopped)
        self.assertEqual(session.messages.count(), 2)

    @override_settings(CHAT_CHECKPOINT_SIGNING_KEY="test-only-signing-key")
    def test_stop_before_first_token_saves_human_without_empty_assistant(self):
        session = ChatSession.objects.create(user=self.user)
        checkpoint = self.stream(session, chunks=())[0][1]
        result = self.finalize(checkpoint, "", "stopped").json()
        self.assertEqual(result["status"], "stopped")
        self.assertIsNone(result["assistant_message_id"])
        self.assertEqual(list(session.messages.values_list("role", "message")), [("human", "hello")])

    @override_settings(CHAT_CHECKPOINT_SIGNING_KEY="test-only-signing-key")
    def test_abandoned_pending_turn_does_not_block_new_turn_but_cannot_append_stale_history(self):
        session = ChatSession.objects.create(user=self.user)
        abandoned = self.stream(session, question="abandoned", chunks=("old",))[-1][1]
        current = self.stream(session, question="current", chunks=("new",))[-1][1]
        self.assertEqual(self.finalize(current, "new", "completed").status_code, 200)
        self.assertEqual(self.finalize(abandoned, "old", "completed").status_code, 409)
        self.assertEqual(
            list(session.messages.values_list("role", "message")),
            [("human", "current"), ("ai", "new")],
        )

    @override_settings(CHAT_CHECKPOINT_SIGNING_KEY="test-only-signing-key")
    def test_partial_stop_is_used_by_the_next_question(self):
        session = ChatSession.objects.create(user=self.user)
        partial = self.stream(session, question="첫 질문", chunks=("부분", " 나머지"))[1][1]
        self.finalize(partial, "부분", "stopped")
        response = self.client.post(
            f"/chat/sessions/{session.pk}/messages/", {"content": "후속 질문"}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            [(m.type, m.content) for m in self.prompts[-1][1:]],
            [("human", "첫 질문"), ("ai", "부분"), ("human", "후속 질문")],
        )

    @override_settings(CHAT_CHECKPOINT_SIGNING_KEY="test-only-signing-key")
    def test_finalize_rejects_foreign_owner_and_forged_prefix(self):
        session = ChatSession.objects.create(user=self.user)
        checkpoint = self.stream(session, chunks=("서버",))[1][1]
        forged = self.finalize(checkpoint, "클라이언트 위조", "stopped")
        self.assertEqual(forged.status_code, 400)
        invalid = self.client.post(
            f"/chat/turns/{checkpoint['turn_id']}/finalize/",
            {"receipt": "not-a-server-receipt", "prefix": "서버", "status": "stopped"},
            format="json",
        )
        self.assertEqual(invalid.status_code, 400)
        self.client.force_authenticate(user=get_user_model().objects.create_user(username="other"))
        foreign = self.finalize(checkpoint, "서버", "stopped")
        self.assertEqual(foreign.status_code, 404)
        self.assertFalse(session.messages.exists())

    @override_settings(CHAT_CHECKPOINT_SIGNING_KEY="test-only-signing-key")
    def test_completed_turn_cannot_be_rewritten_after_a_later_message(self):
        session = ChatSession.objects.create(user=self.user)
        events = self.stream(session, chunks=("앞", "뒤"))
        self.finalize(events[-1][1], "앞뒤", "completed")
        self.client.post(
            f"/chat/sessions/{session.pk}/messages/", {"content": "later"}, format="json"
        )
        result = self.finalize(events[1][1], "앞", "stopped").json()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["assistant_message"], "앞뒤")

    @override_settings(CHAT_CHECKPOINT_SIGNING_KEY="test-only-signing-key")
    def test_completed_turn_cannot_be_rewritten_after_a_newer_turn_starts(self):
        session = ChatSession.objects.create(user=self.user)
        first = self.stream(session, question="first", chunks=("kept", " tail"))
        self.finalize(first[-1][1], "kept tail", "completed")
        second = self.stream(session, question="second", chunks=("next",))
        late_stop = self.finalize(first[1][1], "kept", "stopped").json()
        self.assertEqual(late_stop["status"], "completed")
        self.assertEqual(late_stop["assistant_message"], "kept tail")
        self.assertEqual(self.finalize(second[-1][1], "next", "completed").status_code, 200)
        self.assertEqual(
            list(session.messages.values_list("role", "message")),
            [("human", "first"), ("ai", "kept tail"), ("human", "second"), ("ai", "next")],
        )

    @override_settings(CHAT_CHECKPOINT_SIGNING_KEY="test-only-signing-key")
    def test_stream_failure_is_sanitized_and_saves_no_messages(self):
        class Chain:
            def stream(inner_self, values):
                yield "부분"
                raise OpenAIError("private provider detail")

        session = ChatSession.objects.create(user=self.user)
        with patch("llm.chat_service.ChatService.get_chain", return_value=Chain()):
            response = self.client.post(
                f"/chat/sessions/{session.pk}/messages/",
                {"content": "hello"}, format="json", HTTP_ACCEPT="text/event-stream",
            )
            body = b"".join(response.streaming_content).decode()
        self.assertIn("event: error", body)
        self.assertNotIn("private provider detail", body)
        self.assertFalse(session.messages.exists())

    @override_settings(CHAT_GUEST_RATE_LIMIT=1, CHAT_GUEST_RATE_WINDOW=60)
    def test_guest_history_has_zero_database_writes_and_is_throttled_before_model(self):
        cache.clear()
        before = (ChatSession.objects.count(), ChatMessage.objects.count(), ChatTurn.objects.count())
        with patch.object(ChatService, "stream_with_history", return_value=iter(("답",))) as model:
            response = self.client.post(
                "/chat/guest/",
                {"messages": [
                    {"role": "user", "content": "첫 질문"},
                    {"role": "assistant", "content": "부분 답"},
                    {"role": "user", "content": "후속 질문"},
                ]},
                format="json", HTTP_ACCEPT="text/event-stream", REMOTE_ADDR="203.0.113.9",
            )
            body = b"".join(response.streaming_content).decode()
            throttled = self.client.post(
                "/chat/guest/", {"messages": [{"role": "user", "content": "또 질문"}]},
                format="json", HTTP_ACCEPT="text/event-stream", REMOTE_ADDR="203.0.113.9",
            )
        self.assertIn('event: done', body)
        history, question = model.call_args.args
        self.assertEqual([(m.type, m.content) for m in history], [("human", "첫 질문"), ("ai", "부분 답")])
        self.assertEqual(question, "후속 질문")
        self.assertEqual(throttled.status_code, 429)
        self.assertEqual(model.call_count, 1)
        self.assertEqual(before, (ChatSession.objects.count(), ChatMessage.objects.count(), ChatTurn.objects.count()))
