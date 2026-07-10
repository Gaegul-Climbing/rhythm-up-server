from httpx import AsyncClient


async def test_home_renders_booking_frontend(client: AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert '<script type="module" src="/static/app.js"></script>' in response.text
    assert "https://js.tosspayments.com/v2/standard" in response.text


async def test_frontend_static_assets_are_served(client: AsyncClient) -> None:
    css = await client.get("/static/app.css")
    javascript = await client.get("/static/app.js")

    assert css.status_code == 200
    assert "styles/core/variables.css" in css.text
    assert javascript.status_code == 200
    assert 'from "./features/payment.js"' in javascript.text

    payment = await client.get("/static/features/payment.js")
    assert payment.status_code == 200
    assert "mock-payment-provider" in payment.text
    assert "/payments/toss/confirm" in payment.text

    api = await client.get("/static/core/api.js")
    auth = await client.get("/static/features/auth.js")
    assert api.status_code == 200
    assert 'auth:session-expired' in api.text
    assert "SessionExpiredError" in api.text
    assert auth.status_code == 200
    assert 'auth:session-expired' in auth.text

    variables = await client.get("/static/styles/core/variables.css")
    booking_styles = await client.get("/static/styles/features/booking.css")
    assert variables.status_code == 200
    assert "--color-lime" in variables.text
    assert booking_styles.status_code == 200
    assert ".checkout" in booking_styles.text
