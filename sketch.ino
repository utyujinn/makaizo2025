
#define SERVICE_UUID "12345678-1234-1234-1234-1234567890ab"
#define CHARACTERISTIC_UUID "abcdefab-1234-5678-1234-abcdefabcdef"

#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <string>  // C++のstring機能も念のためインクルード

// PIN DEFINITIONS
const int PIN_MD_AIN1 = 2;
const int PIN_MD_AIN2 = 3;
const int PIN_MD_BIN1 = 5;
const int PIN_MD_BIN2 = 4;
const int PIN_MD_DENZI = 20;

// PWM SETTINGS
#define PWM_FREQ 5000
#define PWM_RESOLUTION 8

const int jumptime[10] = {20,40,60,80,100,120,140,160,180,200};

// Global Pointers
BLEServer* pServer = nullptr;
BLECharacteristic* pCharacteristic = nullptr;

// Motor control helper function
void control_motor(int speed, int pin_fwd, int pin_rev) {
  if (speed > 0) {
    ledcWrite(pin_fwd, speed);
    ledcWrite(pin_rev, 0);
  } else if (speed < 0) {
    ledcWrite(pin_fwd, 0);
    ledcWrite(pin_rev, -speed);
  } else {
    ledcWrite(pin_fwd, 0);
    ledcWrite(pin_rev, 0);
  }
}

// Characteristic callbacks class
class MyCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* pChar) override {
    //
    // 【最終修正】ここが唯一の変更点です。
    // お使いの環境では、getValue()がstd::stringではなくArduinoのStringを返すため、型をこちらに合わせます。
    //
    String value = pChar->getValue();

    if (value.length() > 0) {
      Serial.print("受信: ");
      Serial.println(value);

      // ArduinoのString型でも .c_str() は使えるため、以下の解析ロジックは変更不要です
      char cmd = value.charAt(0);
      //int cnt=0;
      if (cmd == 'M') {  // Motor command "M,left,right"
        char buffer[30];
        value.toCharArray(buffer, sizeof(buffer));  // Stringをchar配列にコピー

        char* token = strtok(buffer, ",");
        if (token != NULL) {
          token = strtok(NULL, ",");
          if (token != NULL) {
            int left_speed = atoi(token);
            token = strtok(NULL, ",");
            if (token != NULL) {
              int right_speed = atoi(token);

              Serial.printf("左モーター速度: %d, 右モーター速度: %d\n", left_speed, right_speed);
              control_motor(left_speed, PIN_MD_AIN1, PIN_MD_AIN2);
              control_motor(right_speed, PIN_MD_BIN1, PIN_MD_BIN2);
            }
          }
        }
      } else if (cmd == 'J') {  // Jump command
        char buffer[30];
        value.toCharArray(buffer, sizeof(buffer));  // Stringをchar配列にコピー

        char* token = strtok(buffer, ",");
        if (token != NULL) {
          token = strtok(NULL, ",");
          if (token != NULL) {
            int i = atoi(token);
            digitalWrite(PIN_MD_DENZI, LOW);
            delay(jumptime[i-1]);
            digitalWrite(PIN_MD_DENZI, HIGH);
          }
        }
        /**
        Serial.println("ジャンプ動作を実行！");
        digitalWrite(PIN_MD_DENZI, LOW);
        delay(jumptime[cnt]);
        digitalWrite(PIN_MD_DENZI, HIGH);
        cnt++;
        **/
      } else {
        Serial.println("不明なコマンドです。");
      }
    }
  }
};


void setup() {
  Serial.begin(115200);

  // PWM setup
  ledcAttach(PIN_MD_AIN1, PWM_FREQ, PWM_RESOLUTION);
  ledcAttach(PIN_MD_AIN2, PWM_FREQ, PWM_RESOLUTION);
  ledcAttach(PIN_MD_BIN1, PWM_FREQ, PWM_RESOLUTION);
  ledcAttach(PIN_MD_BIN2, PWM_FREQ, PWM_RESOLUTION);
  pinMode(PIN_MD_DENZI, OUTPUT);
  digitalWrite(PIN_MD_DENZI, HIGH);

  // BLE setup
  BLEDevice::init("ESP32_BLE_MAKAIZO");
  pServer = BLEDevice::createServer();
  BLEService* pService = pServer->createService(SERVICE_UUID);
  pCharacteristic = pService->createCharacteristic(
    CHARACTERISTIC_UUID,
    BLECharacteristic::PROPERTY_WRITE);
  pCharacteristic->setCallbacks(new MyCallbacks());
  pService->start();
  BLEAdvertising* pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  BLEDevice::startAdvertising();

  Serial.println("BLE デバイス初期化完了。アドバタイズ中...");
}

void loop() {
  delay(2000);
}
