from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase


class SignupTest(APITestCase):
    def test_signup_stores_email_and_rejects_invalid_email(self):
        payload = {
            "username": "emailuser",
            "password": "RiverStone742!Q",
            "re_password": "RiverStone742!Q",
            "email": "reader@example.com",
            "first_name": "독자", "birth_date": "2000-01-01", "gender": "F",
        }
        response = self.client.post(reverse("signup"), payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            get_user_model().objects.get(username="emailuser").email,
            "reader@example.com",
        )
        for email in ("not-an-email", "a" * 250 + "@example.com"):
            with self.subTest(email=email):
                payload.update(username="invalidemailuser", email=email)
                response = self.client.post(reverse("signup"), payload, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn("email", response.data)
                self.assertFalse(
                    get_user_model().objects.filter(username="invalidemailuser").exists()
                )

    def signup(self, username, password, confirmation=None):
        return self.client.post(
            reverse("signup"),
            {
                "username": username,
                "password": password,
                "re_password": password if confirmation is None else confirmation,
                "email": f"{username}@example.test", "first_name": "회원",
                "birth_date": "2000-01-01", "gender": "M",
            },
            format="json",
        )

    def test_signup_validates_input_without_authentication(self):
        response = self.client.post(reverse("signup"), {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()), {"username", "email", "password", "re_password", "first_name", "birth_date", "gender"})

    def test_signup_creates_hashed_password_and_can_log_in(self):
        password = "SpacedSafe764!"
        response = self.signup("newuser", password)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(get_user_model().objects.filter(username="newuser").count(), 1)
        user = get_user_model().objects.get(username="newuser")
        self.assertNotEqual(user.password, password)
        self.assertTrue(user.check_password(password))
        login = self.client.post(
            reverse("login"),
            {"username": user.username, "password": password},
            format="json",
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(set(login.data), {"access", "refresh"})

    def test_signup_rejects_password_policy_violations_without_creating_user(self):
        cases = (
            ("shortuser", "Short7!"),
            ("lettersuser", "abcdefgh"),
            ("digitsuser", "12345678"),
            ("commonuser", "password1"),
            ("similaruser9", "similaruser9"),
        )
        for username, password in cases:
            with self.subTest(username=username):
                response = self.signup(username, password)
                self.assertEqual(response.status_code, 400)
                self.assertIn("password", response.data)
                self.assertFalse(get_user_model().objects.filter(username=username).exists())

    def test_signup_rejects_whitespace_without_trimming(self):
        passwords = (
            " SpacedSafe764!",
            "SpacedSafe764! ",
            " SpacedSafe764! ",
            "Spaced Safe764!",
            "\tSpacedSafe764!",
            "SpacedSafe764!\n",
            " SpacedSafe764! ",
        )
        for index, password in enumerate(passwords):
            with self.subTest(password=password):
                username = f"whitespace{index}"
                response = self.signup(username, password)
                self.assertEqual(response.status_code, 400)
                self.assertIn("password", response.data)
                self.assertFalse(get_user_model().objects.filter(username=username).exists())

    def test_signup_rejects_confirmation_mismatch_and_confirmation_whitespace(self):
        for index, confirmation in enumerate(("MismatchSafe9!", " SpacedSafe764! ")):
            with self.subTest(confirmation=confirmation):
                username = f"confirmation{index}"
                response = self.signup(username, "SpacedSafe764!", confirmation)
                self.assertEqual(response.status_code, 400)
                self.assertIn("re_password", response.data)
                self.assertFalse(get_user_model().objects.filter(username=username).exists())
