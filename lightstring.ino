#include <ESP8266WiFi.h>
#include <Adafruit_NeoPixel.h>
#ifdef __AVR__
  #include <avr/power.h>
#endif

// Which pin on the Arduino is connected to the NeoPixels?
// On a Trinket or Gemma we suggest changing this to 1
#define PIN            4

// How many NeoPixels are attached to the Arduino?
#define NUMPIXELS      20

#define BUFSIZE        32768

const char* ssid = "SSID";
const char* password = "PASSWORD";

// Create an instance of the server
// specify the port to listen on as an argument
WiFiServer server(10000);

Adafruit_NeoPixel pixels = Adafruit_NeoPixel(NUMPIXELS, PIN, NEO_GRB + NEO_KHZ800);

byte buf[BUFSIZE];

void setup() {
  Serial.begin(115200);
  delay(10);

  pixels.begin();

  // Connect to WiFi network
  Serial.println();
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.println("WiFi connected");

  // Start the server
  server.begin();
  Serial.println("Server started");

  // Print the IP address
  Serial.println(WiFi.localIP());
}

bool parseCommand(byte* buf, byte** currentCmd, byte** nextCmd) {
    int length = (((int)(buf[0])) << 8) | buf[1];
    if (length == 0) {
        *currentCmd = NULL;
        *nextCmd = NULL;
        return false;
    }

    *currentCmd = buf;
    *nextCmd = buf + length + 2;

    return true;
}

void runCommand(byte *cmd) {
    int length = (((int)(buf[0])) << 8) | buf[1];
    if (length < 1) {
        return;
    }
    byte which = cmd[2];
    if (which == 'w') {
        if (length < 4)
            return;
        int delayb = cmd[3];
        int startIndex = cmd[4];
        int numPixels = cmd[5];
        if (length != numPixels * 3 + 4)
            return;
        byte* pixelData = cmd + 6;
        for (int i = 0; i < numPixels; i++) {
            pixels.setPixelColor(i + startIndex, pixelData[3 * i], pixelData[3 * i + 1], pixelData[3 * i +2]);
        }
        pixels.show();
        delay(delayb);
    }
}

void printCommand(byte *cmd) {
    int length = (((int)(buf[0])) << 8) | buf[1];
    byte which = cmd[2];
    Serial.printf("l=%d w=%c", length, which);
    if (which == 'w')
        Serial.printf(" delay=%d idx=%d pix=%d", cmd[3], cmd[4], cmd[5]);
    Serial.println("");
}

WiFiClient client;

void loop() {
  /*if(!client) {
    // Check if a client has connected
    WiFiClient newClient = server.available();
    if (!newClient) {
      return;
    }
    Serial.println("new client");
    client = newClient;
  }*/

  // Check if a client has connected
  WiFiClient newClient = server.available();
  if (newClient) {
    Serial.println("new client");
    //WiFiClient::stopAllExcept(&newClient);
    client = newClient;
  }

  if (!client || !client.connected() || !client.available()) {
    delay(1);
    return;
  }

  int bytesRead = client.read(buf, BUFSIZE);
  Serial.print("Bytes read: ");
  Serial.println(bytesRead);

  byte* nextCmd;
  byte* currentCmd;

  nextCmd = buf;
  while(parseCommand(nextCmd, &currentCmd, &nextCmd)) {
    printCommand(currentCmd);
    runCommand(currentCmd);
  }

  client.flush();

  // Send the response to the client
  client.print("ok\r\n");
}

