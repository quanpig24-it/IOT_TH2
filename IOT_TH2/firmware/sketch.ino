
#include <WiFi.h>
#include <PubSubClient.h>
#include <DHTesp.h>
#include <math.h>
#include <time.h>

const char* ssid = "Wokwi-GUEST";
const char* password = "";

// ThingsBoard - Lab 1
const char* tbServer = "mqtt.thingsboard.cloud";
const int tbPort = 1883;
const char* accessToken = "elZPIEpSb1GXEJ0sxflI";

// MQTT public broker - Lab 2
const char* dataMqttServer = "test.mosquitto.org";
const int dataMqttPort = 1883;
const char* dataTopic = "iot-lab2/phn2026/telemetry";

const int dhtPin = 15;
const int trigPin = 5;
const int echoPin = 18;
const int ledPin = 2;
const unsigned long sendInterval = 5000;

WiFiClient tbWifiClient;
PubSubClient tbMqtt(tbWifiClient);

WiFiClient dataWifiClient;
PubSubClient dataMqtt(dataWifiClient);

DHTesp dht;

unsigned long previousSend = 0;
unsigned long sequence = 0;

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password, 6);

  while (WiFi.status() != WL_CONNECTED) {
    Serial.println("Dang ket noi WiFi...");
    delay(500);
  }

  Serial.println("WiFi connected");
}

void connectBroker(PubSubClient& client,
                   const char* clientName,
                   const char* username = nullptr) {
  while (!client.connected()) {
    String clientId = String(clientName) + "-" +
                      String(random(0xffff), HEX);

    bool connected;

    if (username != nullptr) {
      connected = client.connect(clientId.c_str(), username, "");
    } else {
      connected = client.connect(clientId.c_str());
    }

    if (connected) {
      Serial.print(clientName);
      Serial.println(" connected");
    } else {
      Serial.print(clientName);
      Serial.print(" failed, state = ");
      Serial.println(client.state());
      delay(2000);
    }
  }
}

float getDistance() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);

  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);

  digitalWrite(trigPin, LOW);

  unsigned long duration = pulseIn(echoPin, HIGH, 30000);

  if (duration == 0) {
    return NAN;
  }

  return duration * 0.0343f / 2.0f;
}

void sendTelemetry() {
  TempAndHumidity data = dht.getTempAndHumidity();
  float distance = getDistance();

  if (!isfinite(data.temperature) ||
      !isfinite(data.humidity) ||
      !isfinite(distance)) {
    Serial.println("Du lieu cam bien khong hop le");
    return;
  }

  sequence++;

  String payload = "{";
  payload += "\"temperature\":" + String(data.temperature, 2) + ",";
  payload += "\"humidity\":" + String(data.humidity, 2) + ",";
  payload += "\"distance_cm\":" + String(distance, 2) + ",";
  payload += "\"rssi\":" + String(WiFi.RSSI()) + ",";
  payload += "\"sequence\":" + String(sequence) + ",";
  payload += "\"uptime_s\":" + String(millis() / 1000);
  payload += "}";

  Serial.println(payload);

  bool dataOk = false;
  bool tbOk = false;

  if (dataMqtt.connected()) {
    dataOk = dataMqtt.publish(dataTopic, payload.c_str());
  }

  if (tbMqtt.connected()) {
    tbOk = tbMqtt.publish(
      "v1/devices/me/telemetry",
      payload.c_str()
    );
  }

  Serial.print("Lab 2 MQTT publish: ");
  Serial.println(dataOk ? "OK" : "FAILED");

  Serial.print("ThingsBoard publish: ");
  Serial.println(tbOk ? "OK" : "FAILED");

  if (dataOk || tbOk) {
    digitalWrite(ledPin, HIGH);
    delay(100);
    digitalWrite(ledPin, LOW);
  }
}

void setup() {
  Serial.begin(115200);

  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  pinMode(ledPin, OUTPUT);

  dht.setup(dhtPin, DHTesp::DHT22);

  connectWiFi();

  configTime(0, 0, "pool.ntp.org", "time.nist.gov");

  tbMqtt.setServer(tbServer, tbPort);
  tbMqtt.setBufferSize(512);

  dataMqtt.setServer(dataMqttServer, dataMqttPort);
  dataMqtt.setBufferSize(512);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  if (!dataMqtt.connected()) {
    connectBroker(dataMqtt, "PublicMQTT");
  }

  if (strcmp(accessToken, "elZPIEpSb1GXEJ0sxflI") != 0) {
    if (!tbMqtt.connected()) {
      connectBroker(tbMqtt, "ThingsBoard", accessToken);
    }
    tbMqtt.loop();
  }

  dataMqtt.loop();

  unsigned long now = millis();

  if (now - previousSend >= sendInterval) {
    previousSend = now;
    sendTelemetry();
  }
}
