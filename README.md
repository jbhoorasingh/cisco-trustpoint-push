# Cisco Trustpoint Pusher

A FastAPI application that helps push trustpoint configurations to Cisco IOS devices.

## Features

- Secure storage of device credentials (encrypted)
- CA certificate management
- Certificate attribute viewing
- Trustpoint configuration pushing to Cisco IOS devices
- Modern web interface using Vue.js

## Setup

1. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
uvicorn main:app --reload
```

4. Open your browser and navigate to `http://localhost:8000`

## Usage

1. First, store your device credentials using the "Store Credentials" form
2. Upload your CA certificate in PEM format
3. View the certificate details to verify the certificate
4. Enter the device IP address and push the configuration

## Security Notes

- Credentials are stored encrypted using Fernet symmetric encryption
- The encryption key is stored in `data/encryption.key`
- The CA certificate is stored in plain text in `data/ca_cert.pem`
- Make sure to secure the `data` directory appropriately

## API Endpoints

- POST `/store-credentials`: Store device credentials
- POST `/store-ca-cert`: Store CA certificate
- GET `/read-ca-cert`: Read and display certificate attributes
- POST `/push-config`: Push trustpoint configuration to device
- GET `/`: Web interface 