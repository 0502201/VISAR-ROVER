Arduino ESP32 Firmware - VISAR Rover

#include <ESP32Servo.h>
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

// ================= ULTRASONIC =================
#define TRIG_PIN 4
#define ECHO_PIN 5
#define OBSTACLE_DISTANCE 20

// ================= SERVO =================
#define SERVO_PIN 18
Servo scanServo;
bool servoActive = false;

// ================= MODE =================
bool autoMode = false;

// ================= AUTO STATE =================
enum AutoState {
  FORWARD,
  STOPPING,
  LOOK_LEFT,
  LOOK_RIGHT,
  TURN_DECISION,
  TURN,
  RETREAT
};
AutoState state = FORWARD;

unsigned long stateStart = 0;
float leftDist = 0;
float rightDist = 0;
bool turnLeft = true;

// ================= MOTOR =================
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

// ================= ULTRASONIC =================
float getDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  if (duration == 0)
    return -1;

  return duration * 0.034 / 2;
}

// ================= AUTO =================
void handleAuto() {
  unsigned long now = millis();
  float d = getDistanceCm();

  switch (state) {

  case FORWARD:
    if (d > 0 && d < OBSTACLE_DISTANCE) {
      stopMotors();
      state = STOPPING;
      stateStart = now;
    } else {
      forward();
    }
    break;

  case STOPPING:
    if (now - stateStart > 200) {
      state = LOOK_LEFT;
      stateStart = now;
      scanServo.write(150);
    }
    break;

  case LOOK_LEFT:
    if (now - stateStart > 500) {
      leftDist = getDistanceCm();
      if (leftDist <= 0)
        leftDist = 1000;
      state = LOOK_RIGHT;
      stateStart = now;
      scanServo.write(30);
    }
    break;

  case LOOK_RIGHT:
    if (now - stateStart > 600) {
      rightDist = getDistanceCm();
      if (rightDist <= 0)
        rightDist = 1000;
      state = TURN_DECISION;
      stateStart = now;
      scanServo.write(90);
    }
    break;

  case TURN_DECISION:
    if (now - stateStart > 400) {
      if (leftDist < OBSTACLE_DISTANCE && rightDist < OBSTACLE_DISTANCE) {
        state = RETREAT;
        stateStart = now;
      } else {
        turnLeft = (leftDist > rightDist);
        state = TURN;
        stateStart = now;
      }
    }
    break;

  case RETREAT:
    backward();
    if (now - stateStart > 500) {
      state = STOPPING;
      stateStart = now;
      stopMotors();
    }
    break;

  case TURN:
    if (turnLeft)
      left();
    else
      right();

    if (now - stateStart > 500) {
      state = FORWARD;
      stopMotors();
    }
    break;
  }
}

// ================= WEB =================
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

h2 {
  margin-top:20px;
  font-size:28px;
}

.btn {
  width:80px;
  height:80px;
  margin:10px;
  font-size:18px;
  border:none;
  border-radius:20px;
  background:#1e293b;
  color:white;
  box-shadow:0 4px 10px rgba(0,0,0,0.5);
  transition:0.2s;
}

.btn:hover { background:#334155; transform:scale(1.1); }
.btn:active { transform:scale(0.95); }

.row { display:flex; justify-content:center; }

.mode button {
  padding:12px 20px;
  margin:10px;
  font-size:16px;
  border:none;
  border-radius:12px;
}

.auto { background:#22c55e; }
.manual { background:#ef4444; }

.status { margin-top:15px; }
</style>

<script>
function send(cmd){ fetch('/'+cmd); }

function setMode(mode){
  fetch('/mode?m='+mode);
  document.getElementById("modeStatus").innerText = "Mode: " + mode.toUpperCase();
}
</script>
</head>

<body>

<h2>🤖 Smart Rover</h2>

<div class="row">
  <button class="btn" onclick="send('forward')">⬆️</button>
</div>

<div class="row">
  <button class="btn" onclick="send('left')">⬅️</button>
  <button class="btn" onclick="send('stop')">⏹️</button>
  <button class="btn" onclick="send('right')">➡️</button>
</div>

<div class="row">
  <button class="btn" onclick="send('reverse')">⬇️</button>
</div>

<div>
  <button class="auto" onclick="setMode('auto')">AUTO</button>
  <button class="manual" onclick="setMode('manual')">MANUAL</button>
</div>

<div id="modeStatus" class="status">Mode: MANUAL</div>

</body>
</html>
  )rawliteral";

  server.send(200, "text/html", html);
}

// ================= HANDLERS =================
void handleStatus() {
  float d = getDistanceCm();
  String modeStr = autoMode ? "\"auto\"" : "\"manual\"";
  String json = "{\"mode\":" + modeStr + ", \"distance\":" + String(d) + "}";
  server.send(200, "application/json", json);
}

void handleForward() {
  if (!autoMode)
    forward();
  server.send(200);
}
void handleLeft() {
  if (!autoMode)
    left();
  server.send(200);
}
void handleRight() {
  if (!autoMode)
    right();
  server.send(200);
}
void handleReverse() {
  if (!autoMode)
    backward();
  server.send(200);
}
void handleStop() {
  stopMotors();
  server.send(200);
}

// ================= MODE =================
void handleMode() {
  String mode = server.arg("m");

  if (mode == "auto") {
    autoMode = true;
    servoActive = true;

    scanServo.setPeriodHertz(50);
    scanServo.attach(SERVO_PIN, 500, 2400);
    scanServo.write(90);
    delay(300);

    state = FORWARD;
  } else {
    autoMode = false;
    servoActive = false;

    stopMotors();
    scanServo.detach();
  }

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

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

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
void loop() {
  server.handleClient();

  if (autoMode && servoActive) {
    handleAuto();
  }
}
