/*
 *  This sketch demonstrates how to set up a simple HTTP-like server.
 *  The server will set a GPIO pin depending on the request
 *    http://server_ip/gpio/0 will set the GPIO2 low,
 *    http://server_ip/gpio/1 will set the GPIO2 high
 *  server_ip is the IP address of the ESP8266 module, will be 
 *  printed to Serial when the module is connected.
 */

#include <ESP8266WiFi.h>
#include <Adafruit_NeoPixel.h>
#ifdef __AVR__
  #include <avr/power.h>
#endif

// Which pin on the Arduino is connected to the NeoPixels?
// On a Trinket or Gemma we suggest changing this to 1
#define PIN            14

// How many NeoPixels are attached to the Arduino?
#define NUMPIXELS      150

#define BUFSIZE        2048

const char* ssid = "SSID";
const char* password = "PW";

// Create an instance of the server
// specify the port to listen on as an argument
WiFiServer server(10000);

Adafruit_NeoPixel pixels = Adafruit_NeoPixel(NUMPIXELS, PIN, NEO_GRB + NEO_KHZ800);

byte buf[BUFSIZE];

void setAllPixels(uint32_t color) {
  Serial.print("Setting all pixels to ");
  Serial.println(color);
  for (int i = 0; i < pixels.numPixels(); i++) {
    pixels.setPixelColor(i, color);
  }
  pixels.show();
}

void setup() {
  Serial.begin(115200);
  delay(10);

  pixels.begin();
  setAllPixels(pixels.Color(0, 0, 0));

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
  if(!client || !client.connected()) {
    // Check if a client has connected
    WiFiClient newClient = server.available();
    if (!newClient) {
      return;
    }
    Serial.println("new client");
    client = newClient;
  }

  // Wait until the client sends some data
  while(!client.available()) {
    delay(1);
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

