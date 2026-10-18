import threading
import time
import json
import ssl
import requests
import hmac
import hashlib
import urllib.parse
import logging
import paho.mqtt.client as mqtt
from datetime import datetime, timezone

from .const import CONF_CLIENT_ID, CONF_POOL_ID, CONF_IOT_HOST, CONF_REGION

_LOGGER = logging.getLogger(__name__)

# Pause nach einer Trennung. Die Maveo App nutzt dieselbe Client-ID, ein schnelles
# Neuverbinden würde sie hinauswerfen und ein ständiges Hin und Her auslösen.
RECONNECT_COOLDOWN = 600
# Befehle, die während einer Trennung kommen, werden nach dem sofortigen Neuverbinden
# nur gesendet, wenn sie nicht älter sind (ein Tor soll nicht verspätet losfahren)
PENDING_COMMAND_MAX_AGE = 30

class MaveoBridge:
    def __init__(self, user, password, device_id):
        self._user = user
        self._pass = password
        self._device_id = device_id
        # Weckt die Bridge aus der Pause, wenn ein Befehl gesendet werden soll
        self._wake_event = threading.Event()
        self._pending_command = None
        self._stop_event = threading.Event()
        self._thread = None
        self._callbacks = [] 
        self._lock = threading.Lock()
        # Letzter bekannter Zustand aus der Cloud, damit spät registrierte Entities
        # nicht auf die nächste Statusänderung warten müssen
        self._last_payload = {}
        self.aws_client = None

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._aws_loop, name="MaveoBridgeThread")
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._wake_event.set()
        if self.aws_client:
            try:
                self.aws_client.disconnect()
            except:
                pass
        if self._thread:
            self._thread.join()

    def register_callback(self, callback):
        """Registriert einen Callback und liefert sofort den zuletzt bekannten Zustand.

        Gibt eine Funktion zurück, die den Callback wieder entfernt.
        """
        with self._lock:
            self._callbacks.append(callback)
            last_payload = dict(self._last_payload)
        if last_payload:
            callback(last_payload)

        def unregister():
            with self._lock:
                if callback in self._callbacks:
                    self._callbacks.remove(callback)

        return unregister

    def request_status(self):
        """Fragt den aktuellen Status beim Stick an (Antwort kommt über /rsp)."""
        if self.aws_client and self.aws_client.is_connected():
            self.send_command({"AtoS_s": 0})

    def send_command(self, command_dict):
        if self.aws_client and self.aws_client.is_connected():
            topic = f"{self._device_id}/cmd"
            try:
                _LOGGER.debug(f"Sende an AWS: {command_dict}")
                self.aws_client.publish(topic, json.dumps(command_dict))
            except Exception as e:
                _LOGGER.error(f"Fehler beim Senden: {e}")
        else:
            # Nicht verbunden (z.B. weil die Maveo App die Verbindung übernommen hat):
            # Befehl merken und sofort neu verbinden statt die Pause abzuwarten
            _LOGGER.info("Nicht verbunden, verbinde neu für Befehl %s", command_dict)
            self._pending_command = (time.monotonic(), command_dict)
            self._wake_event.set()

    def _aws_loop(self):
        while not self._stop_event.is_set():
            try:
                _LOGGER.debug("Hole Auth Headers...")
                headers = self._get_auth_headers()
                
                self.aws_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self._device_id, protocol=mqtt.MQTTv311, transport="websockets")
                self.aws_client.tls_set_context(ssl.create_default_context())
                self.aws_client.ws_set_options(path="/mqtt", headers=headers)
                
                self.aws_client.on_connect = self._on_connect
                self.aws_client.on_message = self._on_message
                
                _LOGGER.info("Verbinde zu Maveo AWS...")
                self.aws_client.connect(CONF_IOT_HOST, 443, 60)
                
                while not self._stop_event.is_set():
                    rc = self.aws_client.loop(timeout=1.0)
                    if rc != 0:
                        _LOGGER.warning(f"Verbindung verloren RC={rc}")
                        break 
                
                try: self.aws_client.disconnect()
                except: pass

                if not self._stop_event.is_set():
                    _LOGGER.info("Warte 10 Minuten (Cooldown), außer ein Befehl kommt...")
                    self._wake_event.wait(timeout=RECONNECT_COOLDOWN)
                    self._wake_event.clear()

            except Exception as e:
                _LOGGER.error(f"Bridge Fehler: {e}")
                self._stop_event.wait(timeout=30)

    def _on_connect(self, client, userdata, flags, rc, props=None):
        if rc == 0:
            _LOGGER.info("Verbunden mit Maveo AWS!")
            # Ein Weckruf aus der Verbindungsphase ist mit dem Verbinden erledigt
            self._wake_event.clear()
            client.subscribe(f"{self._device_id}/rsp")
            client.publish(f"{self._device_id}/cmd", json.dumps({"AtoS_s": 0}))
            self._send_pending_command(client)
        else:
            _LOGGER.error(f"Verbindung abgelehnt RC={rc}")

    def _send_pending_command(self, client):
        pending, self._pending_command = self._pending_command, None
        if pending is None:
            return
        queued_at, command_dict = pending
        if time.monotonic() - queued_at > PENDING_COMMAND_MAX_AGE:
            _LOGGER.warning("Befehl %s verworfen, zu alt", command_dict)
            return
        _LOGGER.debug("Sende an AWS: %s", command_dict)
        client.publish(f"{self._device_id}/cmd", json.dumps(command_dict))

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            if not isinstance(payload, dict):
                return
            with self._lock:
                self._last_payload.update(payload)
                callbacks = list(self._callbacks)
            for callback in callbacks:
                callback(payload)
        except Exception as e:
            _LOGGER.error(f"Parsing Fehler: {e}")

    # --- HIER IST DIE FEHLENDE METHODE ---
    def _get_auth_headers(self):
        url = "https://cognito-idp.eu-central-1.amazonaws.com/?Action=InitiateAuth&Version=2016-04-18"
        headers = {"Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth"}
        # Hier nutzen wir self._user und self._pass
        payload = {"AuthFlow": "USER_PASSWORD_AUTH", "ClientId": CONF_CLIENT_ID, "AuthParameters": {"USERNAME": self._user, "PASSWORD": self._pass}}
        r = requests.post(url, headers=headers, json=payload); r.raise_for_status()
        id_token = r.json()["AuthenticationResult"]["IdToken"]

        url_id = "https://cognito-identity.eu-central-1.amazonaws.com/?Action=GetId&Version=2016-06-30"
        headers = {"Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "AWSCognitoIdentityService.GetId"}
        payload_id = {"IdentityPoolId": CONF_POOL_ID, "Logins": {"cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ozbW8rTAj": id_token}}
        r = requests.post(url_id, headers=headers, json=payload_id); identity_id = r.json()["IdentityId"]
        
        url_cred = "https://cognito-identity.eu-central-1.amazonaws.com/?Action=GetCredentialsForIdentity&Version=2016-06-30"
        headers["X-Amz-Target"] = "AWSCognitoIdentityService.GetCredentialsForIdentity"
        payload_cred = {"IdentityId": identity_id, "Logins": {"cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ozbW8rTAj": id_token}}
        r = requests.post(url_cred, headers=headers, json=payload_cred); creds = r.json()["Credentials"]

        t = datetime.now(timezone.utc)
        amz_date = t.strftime('%Y%m%dT%H%M%SZ'); datestamp = t.strftime('%Y%m%d')
        service = 'iotdata'; algorithm = 'AWS4-HMAC-SHA256'
        credential_scope = f"{datestamp}/{CONF_REGION}/{service}/aws4_request"
        canonical_headers = f"host:{CONF_IOT_HOST}\nx-amz-date:{amz_date}\n"; signed_headers = "host;x-amz-date"
        payload_hash = hashlib.sha256(b'').hexdigest()
        canonical_request = f"GET\n/mqtt\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
        def sign(key, msg): return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()
        k_signing = sign(sign(sign(sign(('AWS4' + creds["SecretKey"]).encode('utf-8'), datestamp), CONF_REGION), service), 'aws4_request')
        string_to_sign = f"{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
        auth_header = f"{algorithm} Credential={creds['AccessKeyId']}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
        
        headers = {"Host": CONF_IOT_HOST, "X-Amz-Date": amz_date, "Authorization": auth_header}
        if creds["SessionToken"]: headers["X-Amz-Security-Token"] = creds["SessionToken"]
        return headers
