import threading
import time
import json
import ssl
import requests
import hmac
import hashlib
import logging
import paho.mqtt.client as mqtt
from datetime import datetime, timezone

from .const import CONF_CLIENT_ID, CONF_POOL_ID, CONF_IOT_HOST, CONF_REGION

_LOGGER = logging.getLogger(__name__)

class MaveoBridge:
    def __init__(self, user, password, device_id):
        self._user = user
        self._pass = password
        self._device_id = device_id
        self._stop_event = threading.Event()
        self._thread = None
        self._callbacks = [] # Liste von Funktionen (Entitäten), die informiert werden wollen
        self.aws_client = None

    def start(self):
        """Startet den Bridge Thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._aws_loop, name="MaveoBridgeThread")
        self._thread.start()

    def stop(self):
        """Stoppt die Bridge."""
        self._stop_event.set()
        if self.aws_client:
            try:
                self.aws_client.disconnect()
            except:
                pass
        if self._thread:
            self._thread.join()

    def register_callback(self, callback):
        """Entitäten registrieren sich hier für Updates."""
        self._callbacks.append(callback)

    def send_command(self, command_dict):
        """Sendet Befehl an AWS."""
        if self.aws_client and self.aws_client.is_connected():
            topic = f"{self._device_id}/cmd"
            try:
                _LOGGER.debug(f"Sende an AWS: {command_dict}")
                self.aws_client.publish(topic, json.dumps(command_dict))
            except Exception as e:
                _LOGGER.error(f"Fehler beim Senden: {e}")
        else:
            _LOGGER.warning("Kann nicht senden: Nicht verbunden.")

    def _aws_loop(self):
        """Die Hauptschleife (dein bekannter Code)."""
        while not self._stop_event.is_set():
            try:
                _LOGGER.debug("Hole Auth Headers...")
                headers = self._get_auth_headers()
                
                # WICHTIG: Original Device ID nutzen!
                self.aws_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self._device_id, protocol=mqtt.MQTTv311, transport="websockets")
                self.aws_client.tls_set_context(ssl.create_default_context())
                self.aws_client.ws_set_options(path="/mqtt", headers=headers)
                
                self.aws_client.on_connect = self._on_connect
                self.aws_client.on_message = self._on_message
                
                _LOGGER.info("Verbinde zu Maveo AWS...")
                self.aws_client.connect(CONF_IOT_HOST, 443, 60)
                
                # Manueller Loop für Fehlererkennung
                while not self._stop_event.is_set():
                    rc = self.aws_client.loop(timeout=1.0)
                    if rc != 0:
                        _LOGGER.warning(f"Verbindung verloren RC={rc}")
                        break 
                
                try: self.aws_client.disconnect()
                except: pass

                # 10 Minuten Cooldown bei Abbruch
                if not self._stop_event.is_set():
                    _LOGGER.info("Warte 10 Minuten (Cooldown)...")
                    self._stop_event.wait(timeout=600)

            except Exception as e:
                _LOGGER.error(f"Bridge Fehler: {e}")
                self._stop_event.wait(timeout=30)

    def _on_connect(self, client, userdata, flags, rc, props=None):
        if rc == 0:
            _LOGGER.info("Verbunden mit Maveo AWS!")
            client.subscribe(f"{self._device_id}/rsp")
            client.publish(f"{self._device_id}/cmd", json.dumps({"AtoS_s": 0}))
        else:
            _LOGGER.error(f"Verbindung abgelehnt RC={rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            # Wir informieren alle registrierten Entitäten
            for callback in self._callbacks:
                callback(payload)
        except Exception as e:
            _LOGGER.error(f"Parsing Fehler: {e}")

    def get_auth_headers(self):
        url = "https://cognito-idp.eu-central-1.amazonaws.com/?Action=InitiateAuth&Version=2016-04-18"
        headers = {"Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth"}
        payload = {"AuthFlow": "USER_PASSWORD_AUTH", "ClientId": CONF_CLIENT_ID, "AuthParameters": {"USERNAME": self._user, "PASSWORD": self._pass}}
        r = requests.post(url, headers=headers, json=payload); r.raise_for_status()
        id_token = r.json()["AuthenticationResult"]["IdToken"]

        url_id = "https://cognito-identity.eu-central-1.amazonaws.com/?Action=GetId&Version=2016-06-30"
        headers = {"Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "AWSCognitoIdentityService.GetId"}
        payload_id = {"IdentityPoolId": POOL_ID, "Logins": {"cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ozbW8rTAj": id_token}}
        r = requests.post(url_id, headers=headers, json=payload_id); identity_id = r.json()["IdentityId"]
        
        url_cred = "https://cognito-identity.eu-central-1.amazonaws.com/?Action=GetCredentialsForIdentity&Version=2016-06-30"
        headers["X-Amz-Target"] = "AWSCognitoIdentityService.GetCredentialsForIdentity"
        payload_cred = {"IdentityId": identity_id, "Logins": {"cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ozbW8rTAj": id_token}}
        r = requests.post(url_cred, headers=headers, json=payload_cred); creds = r.json()["Credentials"]

        t = datetime.now(timezone.utc)
        amz_date = t.strftime('%Y%m%dT%H%M%SZ'); datestamp = t.strftime('%Y%m%d')
        service = 'iotdata'; algorithm = 'AWS4-HMAC-SHA256'
        credential_scope = f"{datestamp}/{REGION}/{service}/aws4_request"
        canonical_headers = f"host:{IOT_HOST}\nx-amz-date:{amz_date}\n"; signed_headers = "host;x-amz-date"
        payload_hash = hashlib.sha256(b'').hexdigest()
        canonical_request = f"GET\n/mqtt\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
        def sign(key, msg): return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()
        k_signing = sign(sign(sign(sign(('AWS4' + creds["SecretKey"]).encode('utf-8'), datestamp), REGION), service), 'aws4_request')
        string_to_sign = f"{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
        auth_header = f"{algorithm} Credential={creds['AccessKeyId']}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
        
        headers = {"Host": IOT_HOST, "X-Amz-Date": amz_date, "Authorization": auth_header}
        if creds["SessionToken"]: headers["X-Amz-Security-Token"] = creds["SessionToken"]
        return headers