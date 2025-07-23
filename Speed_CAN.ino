#include <TimerOne.h>
#include <mcp_can.h>
#include <SPI.h>

#define ENCODER_PIN 3
#define CS_PIN 10

MCP_CAN CAN0(CS_PIN); 

int counter = 0;
unsigned long previousMicros = 0;
const int interval_sec = 1;
const int pulsesPerTurn = 40;  // encoder wheel: 20 slots × 2 (rising+falling)
const int wheel_diameter_mm = 64;  // mm
float velocity_kmh = 0;


byte data[8] = {0};

// Setup
void setup() {
  Serial.begin(115200);
  while (!Serial);

  pinMode(ENCODER_PIN, INPUT);
  attachInterrupt(digitalPinToInterrupt(ENCODER_PIN), countPulses, CHANGE);


  Timer1.initialize(interval_sec * 1000000);
  Timer1.attachInterrupt(calculateSpeed);

  Serial.print("Initializing MCP2515... ");
  if (CAN0.begin(MCP_ANY, CAN_500KBPS, MCP_16MHZ) == CAN_OK) {
    Serial.println("✅ Success");
  } else {
    Serial.println("❌ Failed");
    while (1);
  }

  CAN0.setMode(MCP_NORMAL);
  Serial.println("Ready to transmit CAN speed data.");
}


void countPulses() {
  if (micros() - previousMicros >= 700) {
    counter++;
    previousMicros = micros();
  }
}


void calculateSpeed() {
  Timer1.detachInterrupt();

  int rpm = (60 * counter) / pulsesPerTurn;
  float wheel_circ_m = 3.1416 * (wheel_diameter_mm / 1000.0);
  velocity_kmh = (rpm * wheel_circ_m * 60) / 1000.0;

  Serial.print("[INFO] RPM: ");
  Serial.print(rpm);
  Serial.print(" | Speed: ");
  Serial.print(velocity_kmh);
  Serial.println(" km/h");

  int velocity_int = (int)(velocity_kmh * 100);
  data[0] = highByte(velocity_int);
  data[1] = lowByte(velocity_int);

  for (int i = 2; i < 8; i++) data[i] = 0;

  counter = 0;
  Timer1.attachInterrupt(calculateSpeed);
}


void loop() {
  Serial.print("[CAN] Sending velocity... ");
  byte sndStat = CAN0.sendMsgBuf(0x100, 0, 8, data);

  if (sndStat == CAN_OK) {
    Serial.println("✅ Sent");
  } else {
    Serial.println("❌ Failed");
  }

  delay(200);  
}
