import jwt
import uuid
import stripe
from contextlib import contextmanager
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from sqlalchemy import create_engine

from backend.config import Config
from backend.db.models import (
    RejectedToken,
    User,
    Subscription
)

conf = Config()
db_host = conf.DB_HOST
db_port = conf.DB_PORT
db_user = conf.DB_USER
db_pass = conf.DB_PASSWORD
db_name = conf.DB_NAME

DATABASE_URI = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
Session = sessionmaker(bind=create_engine(DATABASE_URI))


@contextmanager
def session_scope():
    session = Session()
    session.expire_on_commit = False
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def is_rejected(token):
    with session_scope() as sess:
        token = sess.query(RejectedToken).filter(RejectedToken.token == token).first()
        if token:
            return True
        return False


def find_user_by_email(email):
    with session_scope() as sess:
        return sess.query(User).filter(User.email == email).one_or_none()


def reject_token(token):
    with session_scope() as sess:
        rejected_token = RejectedToken(token=token)
        sess.add(rejected_token)


def generate_token(user, role, is_subscribed) -> str:
    payload = {
        "sub": str(uuid.uuid1()),
        "iat": datetime.timestamp(datetime.now()),
        "exp": int(datetime.timestamp(datetime.now())) + 86400,
        "user": {
            "user-email": user.email,
            "user-name": user.first_name,
            "last_name": user.last_name,
        },
        "role_name": role,
        "is_subscribed": is_subscribed
    }
    token = jwt.encode(payload, conf.JWT_SECRET, "HS256")
    return token


def create_subscription(user_email, price_id, session_id, stripe_customer_id=None):
    with session_scope() as sess:
        user = sess.query(User).filter(User.email == user_email).one_or_none()
        if user:
            subscribe_user = sess.query(Subscription).filter_by(user_id=user.id).one_or_none()
            if not subscribe_user:
                subscription = Subscription(
                    user_id=user.id,
                    price_id=price_id,
                    session_id=session_id,
                    stripe_customer_id=stripe_customer_id,
                    active=True,
                )
                sess.add(subscription)
            else:
                subscribe_user.price_id = price_id,
                subscribe_user.session_id = session_id,
                subscribe_user.stripe_customer_id = stripe_customer_id,
                subscribe_user.active = True
            user.access = True
            sess.commit()


def update_user_subscription(user_email):
    with session_scope() as sess:
        user = sess.query(User).filter(User.email == user_email).one_or_none()
        if user:
            user.is_subscribed = True
            sess.commit()


def add_subscription_detail(user_email):
    with session_scope() as sess:
        user = sess.query(User).filter(User.email == user_email).one_or_none()
        if user:
            subscribe_user = sess.query(Subscription).filter_by(user_id=user.id).one_or_none()
            if subscribe_user:
                if user.is_beta_user == True:  # handle one time product
                    start_date = datetime.utcnow()
                    expire_date = (start_date + timedelta(days=365)).strftime("%d-%m-%Y")
                    subscribe_user.auto_renew_date = expire_date
                    charge = stripe.Charge.retrieve(subscribe_user.stripe_customer_id)
                    if charge and charge.payment_method_details:
                        subscribe_user.last_four_card = charge.payment_method_details["card"]["last4"]
                else:
                    detail = get_payment_details(user)
                    subscribe_user.auto_renew_date = detail["next_renewal_date"]
                    subscribe_user.last_four_card = detail["last4"]
            sess.commit()


def create_or_retrieve_stripe_customer(user_email, user_name):
    try:
        existing_customers = stripe.Customer.list(email=user_email).data
        if existing_customers:
            return existing_customers[0].id
        new_customer = stripe.Customer.create(email=user_email, name=user_name)
        return new_customer.id
    except stripe.error.StripeError as e:
        print(f"Stripe API error: {e}")
        return None


def update_payment_method(user, payment_method_id):
    with session_scope() as sess:
        subscription = (
            sess.query(Subscription)
            .filter(Subscription.user_id == user.id, Subscription.active == True)
            .one_or_none()
        )

        if not subscription:
            raise Exception("Active subscription not found for user")

        customer = stripe.Customer.retrieve(subscription.stripe_customer_id)

        stripe.Customer.modify(
            customer.id, invoice_settings={"default_payment_method": payment_method_id}
        )


def get_payment_details(user):
    try:
        with session_scope() as sess:
            subscription = (
                sess.query(Subscription)
                .filter(Subscription.user_id == user.id)
                .one_or_none()
            )

            if not subscription:
                return {"error": "Subscription not found"}
            if user.is_beta_user == True:
                return {
                    "last4": subscription.last_four_card,
                    "next_renewal_date": subscription.auto_renew_date,
                    "is_paused": False,  # One-time product can't be paused
                    "subscription_cancel": False,  # One-time purchase, no cancellation
                    "active": user.access
                }

            customer = stripe.Customer.retrieve(
                subscription.stripe_customer_id,
                expand=["subscriptions.data.default_payment_method"],
            )

            if not customer.get("subscriptions") or not customer["subscriptions"].get("data"):
                return {"error": "Subscription data not found for the customer"}
            subscription_id = get_subscription_id_from_email(user.email)
            subscription_data = [
                sub for sub in customer["subscriptions"]["data"]
                if sub["id"] == subscription_id
            ]
            if not subscription_data:
                return {"error": "No relevant subscription data found"}

            subscription_info = subscription_data[0]

            default_payment_method = subscription_info.get("default_payment_method")
            if not default_payment_method or not default_payment_method.get("card"):
                return {"error": "Payment method details not found"}

            last4 = default_payment_method["card"].get("last4")
            next_renewal_date_timestamp = subscription_info.get("current_period_end")

            if not last4 or not next_renewal_date_timestamp:
                return {"error": "Incomplete payment details found"}

            # Check if the subscription is paused
            pause_collection = subscription_info.get("pause_collection")
            is_paused = pause_collection is not None and pause_collection.get("behavior") is not None
            subscription_cancel = subscription_info.get("cancel_at_period_end")
            print(f"Pause Collection: {pause_collection}")  # Debugging output
            print(f"Is Paused: {is_paused}")  # Debugging output

            next_renewal_date = datetime.fromtimestamp(
                next_renewal_date_timestamp
            ).strftime("%d-%m-%Y")

            return {
                "last4": last4,
                "next_renewal_date": next_renewal_date,
                "is_paused": is_paused,
                "subscription_cancel": subscription_cancel,
                "active": user.access
            }

    except stripe.error.StripeError as e:
        print(f"Stripe API error: {e}")
        return {"error": "Stripe API error occurred"}
    except Exception as e:
        print(f"Error retrieving payment details: {e}")
        return {"error": "Error retrieving payment details"}


def pause_auto_renewal(user):
    with session_scope() as sess:
        subscription = (
            sess.query(Subscription)
            .filter(Subscription.user_id == user.id, Subscription.active == True)
            .one_or_none()
        )
        if subscription:
            try:
                subscription_id = get_subscription_id_from_email(user.email)
                stripe.Subscription.modify(
                    subscription_id,
                    pause_collection={"behavior": "keep_as_draft"},
                )
                subscription.active = False
                sess.commit()
            except Exception as e:
                print(f"Stripe API Error: {e}")
                raise


def resume_auto_renewal(user):
    with session_scope() as sess:
        subscription = (
            sess.query(Subscription)
            .filter(Subscription.user_id == user.id, Subscription.active == False)
            .one_or_none()
        )
        if subscription:
            try:
                subscription_id = get_subscription_id_from_email(user.email)
                # Use the recommended method from Stripe documentation
                stripe.Subscription.modify(
                    subscription_id,
                    pause_collection='',
                )

                # Retrieve the updated subscription to verify the update
                updated_subscription = stripe.Subscription.retrieve(subscription_id)
                print("HERE", updated_subscription.pause_collection)  # Debugging output

                subscription.active = True
                sess.commit()

                return updated_subscription
            except Exception as e:
                print(f"Stripe API Error: {e}")
                raise


def get_subscription_id_from_email(email):
    try:
        # Step 1: Retrieve the customer object using the email
        customers = stripe.Customer.list(email=email)

        if not customers.data:
            raise Exception(f"No customer found with email: {email}")

        customer = customers.data[
            0
        ]  # Assuming the email is unique and we take the first match

        # Step 2: Retrieve the subscriptions for the customer
        subscriptions = stripe.Subscription.list(customer=customer.id)

        if not subscriptions.data:
            raise Exception(f"No subscriptions found for customer with email: {email}")

        subscription = subscriptions.data[
            0
        ]  # Assuming there's at least one subscription and we take the first match

        return subscription.id

    except stripe.error.StripeError as e:
        # Handle Stripe API errors
        print(f"Stripe error: {e}")
        raise
    except Exception as e:
        # Handle other errors
        print(f"Error: {e}")
        raise


def delete_user_and_associated_records(sess, user_id):
    try:
        # Delete the user and assoiciated tables
        sess.query(User).filter(User.id == user_id).delete()
    except Exception as e:
        print("Error deleting user and associated records:", e)
        raise


def cancel_subscription(user, token):
    with session_scope() as sess:
        subscription = (
            sess.query(Subscription)
            .filter(Subscription.user_id == user.id)
            .one_or_none()
        )

        if subscription:
            try:
                # Retrieve the subscription ID using the email
                subscription_id = get_subscription_id_from_email(user.email)

                # Cancel the subscription
                stripe.Subscription.delete(subscription_id)

                # Update the local subscription record
                subscription.active = False
                sess.add(subscription)
                reject_token(token)
                # Delete user and associated records
                delete_user_and_associated_records(sess, user.id)
            except stripe.error.InvalidRequestError as e:
                print("Stripe error:", e)
                raise Exception("Error unsubscribing: {}".format(e))


def get_payment_method_id_by_email(email):
    try:
        # Retrieve the customer object using the email
        customers = stripe.Customer.list(email=email)

        if not customers.data:
            raise Exception(f"No customer found with email: {email}")

        customer = customers.data[
            0
        ]  # Assuming the email is unique and we take the first match

        # Retrieve the payment methods for the customer
        payment_methods = stripe.PaymentMethod.list(customer=customer.id, type="card")

        if not payment_methods.data:
            raise Exception(
                f"No payment methods found for customer with email: {email}"
            )

        # Select the first payment method (or implement your own logic to choose)
        payment_method = payment_methods.data[0]

        return payment_method.id

    except stripe.error.StripeError as e:
        print(f"Stripe error: {e}")
        raise
    except Exception as e:
        print(f"Error retrieving payment method ID: {e}")
        raise


def handle_payment_failed(invoice, user_email):
    customer_id = invoice['customer']
    subscription_id = invoice['subscription']
    with session_scope() as sess:
        subscription = sess.query(Subscription).filter(Subscription.stripe_customer_id == customer_id).one_or_none()
        if subscription:
            user = sess.query(User).filter_by(email=user_email).first()
            subscription.active = False
            user.access = False
            sess.commit()
