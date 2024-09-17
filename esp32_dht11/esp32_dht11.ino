#include <WiFi.h>
#include <WiFiClient.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <DHT.h>

const char *ssid = "KimTung";
const char *password = "kimtung1080";

const uint16_t port = 8090;
const char * host = "192.168.1.32";

int state = -1;

WebServer server(80);
DHT dht(25, DHT11);

void handleRoot() {
  char msg[2000];  // Increased buffer size to accommodate the additional buttons

  snprintf(msg, 2000,
         "<html>\
    <head>\
      <meta http-equiv='refresh' content='4'/>\
      <meta charset='UTF-8'>\
      <meta name='viewport' content='width=device-width, initial-scale=1'>\
      <link rel='stylesheet' href='https://use.fontawesome.com/releases/v5.7.2/css/all.css' integrity='sha384-fnmOCqbTlWIlj8LyTjo7mOUStjsKC4pOpQbqyi7RrhN7udi9RwhKkMHpvLbHG9Sr' crossorigin='anonymous'>\
      <title>Smart Light System</title>\
      <style>\
      html { font-family: Arial; display: inline-block; margin: 0px auto; text-align: center;}\
      h2 { font-size: 3.0rem; }\
      p { font-size: 3.0rem; }\
      .units { font-size: 1.2rem; }\
      .dht-labels{ font-size: 1.5rem; vertical-align:middle; padding-bottom: 15px;}\
      .buttons { display: flex; flex-direction: column; align-items: center; gap: 10px; justify-content: center; }\
      .button { width: 280px; height: 60px; font-size: 1.8rem; }\
      </style>\
      <script>\
          function updateState(newState) {\
            var xhr = new XMLHttpRequest();\
            xhr.open('GET', '/updateState?state=' + newState, true);\
            xhr.send();\
          }\
    </script>\
    </head>\
    <body>\
        <h2>ESP32 DHT Server!</h2>\
        <p>\
          <i class='fas fa-thermometer-half' style='color:#ca3517;'></i>\
          <span class='dht-labels'>Temperature</span>\
          <span>%.2f</span>\
          <sup class='units'>&deg;C</sup>\
        </p>\
        <p>\
          <i class='fas fa-tint' style='color:#00add6;'></i>\
          <span class='dht-labels'>Humidity</span>\
          <span>%.2f</span>\
          <sup class='units'>&percnt;</sup>\
        </p>\
        <div class='buttons'>\
          <button class='button' onclick='updateState(0)'>Tắt đèn</button>\
          <button class='button' onclick='updateState(1)'>Đèn bình thường</button>\
          <button class='button' onclick='updateState(2)'>Đèn nhiệt độ</button>\
          <button class='button' onclick='updateState(3)'>Đèn an toàn</button>\
          <button class='button' onclick='updateState(4)'>An toàn</button>\
        </div>\
    </body>\
  </html>",
         readDHTTemperature(), readDHTHumidity()
        );
  server.send(200, "text/html; charset=utf-8", msg);
}

void setup(void) {

  Serial.begin(115200);
  dht.begin();
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  Serial.println("");

  // Wait for connection
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.print("Connected to ");
  Serial.println(ssid);
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  if (MDNS.begin("esp32")) {
    Serial.println("MDNS responder started");
  }
  server.on("/", handleRoot);
    // Route for updating state
  server.on("/updateState", HTTP_GET, []() {
    String stateParam = server.arg("state");
    if (stateParam != "") {
      state = stateParam.toInt();
      Serial.print("Updated state to ");
      Serial.println(state);
    }
    server.send(200, "text/plain", "OK");
  });
  server.begin();
  Serial.println("HTTP server started");
}

void loop(void) {
  server.handleClient();
  delay(2);//allow the cpu to switch to other tasks
  //send temperature to client
  WiFiClient client;
 
    if (!client.connect(host, port)) {
 
        Serial.println("Connection to host failed");
        delay(1000);
        return;
    }
    Serial.println("Connected to server successful!");
    Serial.println(state);
    int temperature = int(readDHTTemperature());
    int res = temperature * 10 + 1 + state;
    if (temperature !=-1)
    {
      client.print(res);
    }
    state = -1;
    delay(100);
    //Serial.println("Disconnecting...");
    client.stop();
    delay(1000);
}


float readDHTTemperature() {
  // Sensor readings may also be up to 2 seconds
  // Read temperature as Celsius (the default)
  float t = dht.readTemperature();
  if (isnan(t)) {    
    Serial.println("Failed to read from DHT sensor!");
    return -1;
  }
  else {
    Serial.println(t);
    return t;
  }
}

float readDHTHumidity() {
  // Sensor readings may also be up to 2 seconds
  float h = dht.readHumidity();
  if (isnan(h)) {
    Serial.println("Failed to read from DHT sensor!");
    return -1;
  }
  else {
    Serial.println(h);
    return h;
  }
}

void updateState(int i)
{
  state = i;
}
