# Stripe Payment Integration

This repository contains the backend and frontend code required to integrate Stripe as a payment method. The backend provides REST API endpoints for handling the payment process, while the frontend includes a basic checkout page for users to enter their payment details.

## Features
- Backend endpoints for Stripe payment processing
- Secure checkout page for user payments
- Integration with Stripe API for seamless transactions

## Technologies Used
- **Backend:** Python (FastAPI)
- **Frontend:** React.js / Vanilla JavaScript
- **Payment Gateway:** Stripe API

## Getting Started
### Prerequisites
- Python installed
- Stripe account and API keys (Publishable & Secret keys)
- Git installed

### Installation
1. **Clone the Repository**
```sh
git clone https://github.com/hamza-shafiq/stripe-sdk.git
cd stripe-sdk
```

2. **Backend Setup**
```sh
cd backend
pip install -r requirements.txt
```

3. **Frontend Setup**
```sh
cd frontend
npm install
```

### Environment Variables
Create a `.env` file with the following & place your credentials:
```env
cp .env.template .env
```

## Backend Endpoints

| Method | Endpoint                   | Description |
|--------|---------------------------|-------------|
| POST   | `/create-checkout-session` | Creates a Stripe session when a user clicks to subscribe. |
| POST   | `/unsubscribe`             | Deletes the user's account upon request. |
| POST   | `/update-payment-method`   | Updates the user's payment method. |
| GET    | `/payment-details`         | Retrieves payment details. |
| POST   | `/toggle-auto-renewal`     | Pauses or resumes future payments for recurring products after subscription expiry. |
| POST   | `/renewtoken`              | Refreshes the token after a user subscribes. |
| POST   | `/webhook`                 | Handles webhook responses from Stripe. |
| GET    | `/customer_portal_session` | Displays the Stripe customer portal, allowing users to view, update, or cancel their subscriptions. |

## Frontend Checkout Page
- Basic UI with a "Pay Now" button
- Calls the `/create-checkout-session` endpoint to initiate the payment process
- Redirects users to the Stripe-hosted payment page

## Running the Application
1. **Start Backend Server**
```sh
cd backend
uvicorn main:app --reload
```

2. **Start Frontend Server**
```sh
npm start
```

3. **Test the Checkout Flow**
- Open the frontend in your browser.
- Click on "Pay Now" to start the checkout process.
- Complete the payment using Stripe test cards.

## Testing with Stripe Test Cards
Use the following test card to simulate a successful payment:
```
Card Number: 4242 4242 4242 4242
Expiry: Any future date
CVC: Any 3 digits
```
For more test cards, visit [Stripe Docs](https://stripe.com/docs/testing)

## Deployment
- Use services like Vercel (for frontend) and Heroku (for backend)
- Configure environment variables in the production environment

## Contact
For questions or issues, feel free to open an issue or contact me at `contacthamzashafique@gmail.com`
