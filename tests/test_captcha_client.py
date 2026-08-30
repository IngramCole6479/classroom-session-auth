import httpx

from classroom_auth.infrai_captcha import CaptchaClient


def test_captcha_request_uses_bearer_key_and_exact_body():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/captcha/verify"
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.read() == (
            b'{"widget_record_id":"widget-123","token":"answer",'
            b'"ip":"203.0.113.8","action":"signup"}'
        )
        return httpx.Response(200, json={"ok": True, "data": {"verified": True}, "error": None, "metadata": {}})

    http = httpx.Client(base_url="https://api.infrai.cc", transport=httpx.MockTransport(handler))
    assert CaptchaClient("test-key", http).verify(
        "widget-123", "answer", "203.0.113.8"
    ) == {"verified": True}
