from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from cryptography.fernet import Fernet
import json
import os
from pathlib import Path
import base64
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import netmiko
from netmiko import ConnectHandler
import time

app = FastAPI()

# Create necessary directories
Path("static").mkdir(exist_ok=True)
Path("data").mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Generate encryption key if not exists
def get_encryption_key():
    key_file = "data/encryption.key"
    if not os.path.exists(key_file):
        key = Fernet.generate_key()
        with open(key_file, "wb") as f:
            f.write(key)
    else:
        with open(key_file, "rb") as f:
            key = f.read()
    return key

@app.post("/store-credentials")
async def store_credentials(username: str = Form(...), password: str = Form(...)):
    key = get_encryption_key()
    f = Fernet(key)
    
    credentials = {
        "username": username,
        "password": password
    }
    
    encrypted_data = f.encrypt(json.dumps(credentials).encode())
    
    with open("data/credentials.enc", "wb") as f:
        f.write(encrypted_data)
    
    return {"message": "Credentials stored successfully"}

@app.post("/store-ca-cert")
async def store_ca_cert(certificate: str = Form(...)):
    with open("data/ca_cert.pem", "w") as f:
        f.write(certificate)
    return {"message": "CA certificate stored successfully"}

@app.get("/read-ca-cert")
async def read_ca_cert():
    try:
        with open("data/ca_cert.pem", "r") as f:
            cert_data = f.read()
        
        # Split the certificate data into individual certificates
        certs = cert_data.split("-----BEGIN CERTIFICATE-----")
        certs = ["-----BEGIN CERTIFICATE-----" + cert for cert in certs if cert.strip()]
        
        cert_details = []
        for cert in certs:
            cert_obj = x509.load_pem_x509_certificate(cert.encode(), default_backend())
            cert_details.append({
                "subject": str(cert_obj.subject),
                "issuer": str(cert_obj.issuer),
                "not_valid_before": cert_obj.not_valid_before.isoformat(),
                "not_valid_after": cert_obj.not_valid_after.isoformat(),
                "serial_number": str(cert_obj.serial_number)
            })
        
        return cert_details
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/push-config")
async def push_config(device_ip: str = Form(...)):
    try:
        # Read encrypted credentials
        key = get_encryption_key()
        f = Fernet(key)
        with open("data/credentials.enc", "rb") as cred_file:
            encrypted_data = cred_file.read()
        credentials = json.loads(f.decrypt(encrypted_data))
        
        # Read CA certificate
        with open("data/ca_cert.pem", "r") as cert_file:
            ca_cert = cert_file.read()
        
        # Split certificate into lines and add quit and yes
        pem_lines = ca_cert.splitlines()

        
        # Device configuration
        device = {
            'device_type': 'cisco_ios',
            'host': device_ip,
            'username': credentials['username'],
            'password': credentials['password'],
            'timeout': 60,
            'session_timeout': 60,
            'read_timeout_override': 60,
            'fast_cli': True,
            # 'global_delay_factor': 2,
            'session_log': os.path.join('data', 'session_logs', f'netmiko_{device_ip}.log')
        }
        
        print(f"Connecting to device {device_ip}...")
        
        # Connect to device and push configuration
        with ConnectHandler(**device) as conn:
            # Print the detected prompt
            prompt = conn.find_prompt()
            print(f"Detected prompt: {prompt}")
            
            # Disable paging
            print("Disabling paging...")
            conn.send_command('terminal length 0')
            
            # Enter config mode
            print("Entering config mode...")
            conn.config_mode()
            
            # Create trustpoint configuration
            config_commands = [
                'crypto pki trustpoint MY-TRUSTPOINT',
                'enrollment terminal',
                'revocation-check none',
                'exit'
            ]
            
            # Send configuration commands
            print("Sending trustpoint configuration...")
            output = conn.send_config_set(config_commands)
            print(f"Config output: {output}")
            
            # Send certificate manually
            print("Sending CA certificate...")
            
            # Enter config mode
            conn.config_mode()
            # Send the command to start cert input
            conn.send_command_timing("crypto pki authenticate MY-TRUSTPOINT")

            # Send cert line-by-line using send_command_timing
            # for line in pem_lines:
            #     print(f"SENDING: {line}")
            #     conn.send_command_timing(line)
            pem_input = "\n".join(pem_lines)
            conn.send_command_timing(pem_input)

            # Send 'quit' to finish input
            conn.send_command_timing("quit")
            # Send 'yes' to accept the certificate
            conn.send_command_timing("yes")
            # Exit config mode
            conn.exit_config_mode()


            # # Done
            conn.disconnect()
            return {
                "message": "Trustpoint and certificate pushed",
                "output": output
}


            
            # Wait for certificate acceptance
            print("Waiting for certificate acceptance...")
            output += conn.read_until_pattern("Trustpoint CA certificate accepted.")
            print(f"Certificate output: {output}")
            
            # Exit config mode
            print("Exiting config mode...")
            conn.exit_config_mode()
            
            return {"message": "Configuration pushed successfully", "output": output}
            
    except Exception as e:
        print(f"Error pushing configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return FileResponse("static/index.html")

@app.get("/check-credentials")
async def check_credentials():
    if os.path.exists("data/credentials.enc"):
        return {"message": "Credentials are stored."}
    else:
        return {"message": "No credentials stored."}

@app.post("/clear-credentials")
async def clear_credentials():
    if os.path.exists("data/credentials.enc"):
        os.remove("data/credentials.enc")
        return {"message": "Credentials cleared successfully."}
    else:
        return {"message": "No credentials to clear."} 