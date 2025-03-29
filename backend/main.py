import jwt
import stripe
from jwt.exceptions import DecodeError
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import Config
from db import stripe_db

app = FastAPI(
    title="Stripe Payment API",
    description="A FastAPI-based service for integrating Stripe payments, including customer management, payment processing, and subscription handling.",
    version="1.0.0",
    contact={
        "name": "Hamza Shafique",
        "email": "contacthamzashafique@gmail.com",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    }
)

config = Config()
stripe.api_key = config.STRIPE_SECRET_KEY
security = HTTPBearer()

@app.get("/")
def read_root():
    return {"message": "Hello, Welcome to Stripe Integration!"}


def jwt_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        user_identity = jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
        if stripe_db.is_rejected(token):
            raise HTTPException(status_code=403, detail="Token is rejected")
        return user_identity
    except DecodeError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.post("/create-checkout-session")
async def create_checkout_session(user_identity: dict = Depends(jwt_auth)):
    user_email = user_identity.get("user-email")
    user_name = user_identity.get("user-name")
    products = stripe.Product.list()

    stripe_customer_id = stripe_db.create_or_retrieve_stripe_customer(user_email, user_name)
    if not stripe_customer_id:
        raise HTTPException(status_code=500, detail="Error creating or retrieving customer")

    latest_product = next((p for p in products['data'] if p['name'] == config.STRIPE_PRODUCT), None)
    if not latest_product:
        raise HTTPException(status_code=400, detail="No product available!")

    price_id = latest_product.get("default_price")
    line_items = [{"price": price_id, "quantity": 1}]

    payment_mode = 'payment'
    for item in line_items:
        price_data = stripe.Price.retrieve(item['price'])
        if price_data.recurring:
            payment_mode = 'subscription'
            break

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode=payment_mode,
            success_url=f'{config.FE_BASE_URL}/success/{{CHECKOUT_SESSION_ID}}',
            cancel_url=f'{config.FE_BASE_URL}/cancel',
            customer_email=user_email,
            metadata={}
        )
        return {"id": session.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating session: {str(e)}")


@app.post("/unsubscribe")
async def unsubscribe(user_identity: dict = Depends(jwt_auth)):
    user_email = user_identity.get("user-email")
    user = stripe_db.find_user_by_email(user_email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        stripe_db.cancel_subscription(user, user_identity.get("token"))
        return {"status": "unsubscribed and user deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error unsubscribing: {str(e)}")


@app.post("/update-payment-method")
async def update_payment_method(user_identity: dict = Depends(jwt_auth)):
    user_email = user_identity.get("user-email")
    user = stripe_db.find_user_by_email(user_email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        payment_method_id = stripe_db.get_payment_method_id_by_email(user_email)
        stripe_db.update_payment_method(user, payment_method_id)
        return {"status": "payment method updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating payment method: {str(e)}")


@app.get("/payment-details")
async def payment_details(user_identity: dict = Depends(jwt_auth)):
    user_email = user_identity.get("user-email")
    user = stripe_db.find_user_by_email(user_email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        payment_info = stripe_db.get_payment_details(user)
        required_fields = ['last4', 'next_renewal_date']
        missing_fields = [field for field in required_fields if not payment_info.get(field)]
        if missing_fields:
            raise HTTPException(status_code=400, detail=f"Missing payment details: {', '.join(missing_fields)}")
        return payment_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving payment details: {str(e)}")


@app.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    endpoint_secret = config.STRIPE_WEBHOOK_SECRET
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_email = session['customer_email']
        stripe_db.create_subscription(user_email, session['id'], session['customer'])
        return {"status": "success"}
    elif event['type'] == 'invoice.payment_failed':
        session = event['data']['object']
        user_email = session['customer_email']
        # Handle payment failure logic
    return {"status": "received"}
