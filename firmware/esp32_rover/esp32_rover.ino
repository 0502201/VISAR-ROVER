Arduino ESP32 Firmware - VISAR Rover(Manual Driving Mode)
#include <WebServer.h>
#include <WiFi.h>

    // ================= WIFI =================
    const char *ssid = "sharma";
const char *password = "12345687";

WebServer server(80);

// ================= MOTOR =================
int motor1Pin1 = 14;
int motor1Pin2 = 27;
int enable1Pin = 12;

int motor2Pin1 = 26;
int motor2Pin2 = 25;
int enable2Pin = 13;

// ================= MOTOR FUNCTIONS =================
void stopMotors() {
  digitalWrite(motor1Pin1, LOW);
  digitalWrite(motor1Pin2, LOW);
  digitalWrite(motor2Pin1, LOW);
  digitalWrite(motor2Pin2, LOW);
}

void forward() {
  digitalWrite(motor1Pin1, LOW);
  digitalWrite(motor1Pin2, HIGH);
  digitalWrite(motor2Pin1, LOW);
  digitalWrite(motor2Pin2, HIGH);
}

void backward() {
  digitalWrite(motor1Pin1, HIGH);
  digitalWrite(motor1Pin2, LOW);
  digitalWrite(motor2Pin1, HIGH);
  digitalWrite(motor2Pin2, LOW);
}

void left() {
  digitalWrite(motor1Pin1, LOW);
  digitalWrite(motor1Pin2, LOW);
  digitalWrite(motor2Pin1, LOW);
  digitalWrite(motor2Pin2, HIGH);
}

void right() {
  digitalWrite(motor1Pin1, LOW);
  digitalWrite(motor1Pin2, HIGH);
  digitalWrite(motor2Pin1, LOW);
  digitalWrite(motor2Pin2, LOW);
}

// ================= WEB INTERFACE =================
void handleRoot() {
  String html = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body {
  margin:0;
  font-family: 'Segoe UI', sans-serif;
  background: linear-gradient(135deg,#0f172a,#1e293b);
  color:white;
  text-align:center;
}
h2 { margin-top:20px; font-size:28px; }
.btn {
  width:80px; height:80px; margin:10px; font-size:18px; border:none;
  border-radius:20px; background:#1e293b; color:white;
  box-shadow:0 4px 10px rgba(0,0,0,0.5); transition:0.2s;
}
.btn:hover { background:#334155; transform:scale(1.1); }
.btn:active { transform:scale(0.95); }
.row { display:flex; justify-content:center; }
.status { margin-top:15px; color:#94a3b8; font-size:14px; }
</style>
<script>
function send(cmd){ fetch('/'+cmd); }
</script>
</head>
<body>
<h2>🤖 VISAR Rover</h2>
<div class="row"><button class="btn" onclick="send('forward')">⬆️</button></div>
<div class="row">
  <button class="btn" onclick="send('left')">⬅️</button>
  <button class="btn" onclick="send('stop')">⏹️</button>
  <button class="btn" onclick="send('right')">➡️</button>
</div>
<div class="row"><button class="btn" onclick="send('reverse')">⬇️</button></div>
<div class="status">Mode: MANUAL CONTROL</div>
</body>
</html>
  )rawliteral";

  server.send(200, "text/html", html);
}

// ================= API HANDLERS =================
void handleStatus() {
  server.send(200, "application/json",
              "{\"mode\":\"manual\", \"distance\":-1}");
}

void handleForward() {
  forward();
  server.send(200);
}

void handleLeft() {
  left();
  server.send(200);
}

void handleRight() {
  right();
  server.send(200);
}

void handleReverse() {
  backward();
  server.send(200);
}

void handleStop() {
  stopMotors();
  server.send(200);
}

void handleMode() {
  stopMotors();
  server.send(200);
}

// ================= SETUP =================
void setup() {
  Serial.begin(115200);

  pinMode(motor1Pin1, OUTPUT);
  pinMode(motor1Pin2, OUTPUT);
  pinMode(motor2Pin1, OUTPUT);
  pinMode(motor2Pin2, OUTPUT);

  pinMode(enable1Pin, OUTPUT);
  pinMode(enable2Pin, OUTPUT);
  digitalWrite(enable1Pin, HIGH);
  digitalWrite(enable2Pin, HIGH);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED)
    delay(500);

  server.on("/", handleRoot);
  server.on("/forward", handleForward);
  server.on("/left", handleLeft);
  server.on("/right", handleRight);
  server.on("/reverse", handleReverse);
  server.on("/stop", handleStop);
  server.on("/mode", handleMode);
  server.on("/status", handleStatus);

  server.begin();
}

// ================= LOOP =================
void loop() { server.handleClient(); }
