# Refactoring the Stream Monitor to Go

This document outlines the steps to rewrite the Python-based stream monitor in Go. The goal is to create a more performant and statically-typed version of the application.

## 1. Project Structure

A typical Go project structure would look like this:

```
stream-monitor-go/
├── go.mod
├── go.sum
├── main.go
├── config/
│   └── config.go
├── internal/
│   ├── discord/
│   │   └── notifier.go
│   └── kick/
│       └── monitor.go
└── pkg/
    └── pusher/  // If a custom Pusher client is needed
```

- **`main.go`**: The entry point of the application.
- **`config/`**: For handling configuration.
- **`internal/`**: For the application's internal packages (Discord notifier, Kick monitor).
- **`pkg/`**: For any reusable packages.

## 2. Configuration

Go applications typically handle configuration using a combination of struct tags and a library to read from environment variables or a configuration file.

**`config/config.go`**:
```go
package config

import (
    "github.com/spf13/viper"
)

type Config struct {
    DiscordWebhookURL      string   `mapstructure:"DISCORD_WEBHOOK_URL"`
    KickUsername           string   `mapstructure:"YOUR_KICK_USERNAME"`
    KickChannelsToMonitor  []string `mapstructure:"KICK_CHANNELS_TO_MONITOR"`
    PusherAppKey           string   `mapstructure:"PUSHER_APP_KEY"`
    PusherCluster          string   `mapstructure:"PUSHER_CLUSTER"`
    KickUserAgent          string   `mapstructure:"KICK_USER_AGENT"`
}

func LoadConfig() (config Config, err error) {
    viper.SetDefault("KICK_CHANNELS_TO_MONITOR", []string{})
    viper.AutomaticEnv()

    err = viper.Unmarshal(&config)
    return
}
```

## 3. Kick Monitor

The Kick monitor will connect to the Pusher WebSocket and listen for chat messages.

**`internal/kick/monitor.go`**:
```go
package kick

import (
    "fmt"
    "log"
    "net/http"
    "encoding/json"

    "github.com/gorilla/websocket"
    "github.com/your-username/stream-monitor-go/config"
    "github.com/your-username/stream-monitor-go/internal/discord"
)

// Function to get chatroom ID from Kick API
func getChatroomID(channelName string, userAgent string) (string, error) {
    // ... implementation to make HTTP GET request to https://kick.com/api/v2/channels/{channel_name}
    // and parse the JSON response to get the chatroom ID.
    return "", nil
}

// Main monitoring function
func MonitorChannel(cfg config.Config, channelName string) {
    chatroomID, err := getChatroomID(channelName, cfg.KickUserAgent)
    if err != nil {
        log.Printf("Error getting chatroom ID for %s: %v", channelName, err)
        return
    }

    wsURL := fmt.Sprintf("wss://ws-%s.pusher.com/app/%s?protocol=7&client=js&version=8.4.0-rc2", cfg.PusherCluster, cfg.PusherAppKey)

    conn, _, err := websocket.DefaultDialer.Dial(wsURL, nil)
    if err != nil {
        log.Fatalf("Error connecting to WebSocket: %v", err)
    }
    defer conn.Close()

    // Subscribe to the channel
    // ...

    for {
        _, message, err := conn.ReadMessage()
        if err != nil {
            log.Println("read:", err)
            return
        }

        // Process the message, check for mentions/replies
        // ...

        // If mention or reply is found, send a notification
        // discord.SendNotification(...)
    }
}
```
A popular WebSocket library in Go is `github.com/gorilla/websocket`. For Pusher, you can either interact with the WebSocket directly or use a community-maintained client library.

## 4. Discord Notifier

The Discord notifier will send a formatted message to the configured webhook URL.

**`internal/discord/notifier.go`**:
```go
package discord

import (
    "bytes"
    "encoding/json"
    "net/http"

    "github.com/your-username/stream-monitor-go/config"
)

type DiscordPayload struct {
    Embeds []Embed `json:"embeds"`
}

type Embed struct {
    // ... struct fields for the Discord embed message
}

func SendNotification(cfg config.Config, payload DiscordPayload) error {
    jsonPayload, err := json.Marshal(payload)
    if err != nil {
        return err
    }

    req, err := http.NewRequest("POST", cfg.DiscordWebhookURL, bytes.NewBuffer(jsonPayload))
    if err != nil {
        return err
    }
    req.Header.Set("Content-Type", "application/json")

    client := &http.Client{}
    resp, err := client.Do(req)
    if err != nil {
        return err
    }
    defer resp.Body.Close()

    // ... handle response
    return nil
}
```

## 5. Concurrency

To monitor multiple channels simultaneously, we can use goroutines.

**`main.go`**:
```go
package main

import (
    "log"
    "sync"

    "github.com/your-username/stream-monitor-go/config"
    "github.com/your-username/stream-monitor-go/internal/kick"
)

func main() {
    cfg, err := config.LoadConfig()
    if err != nil {
        log.Fatalf("Error loading config: %v", err)
    }

    var wg sync.WaitGroup

    for _, channel := range cfg.KickChannelsToMonitor {
        wg.Add(1)
        go func(channelName string) {
            defer wg.Done()
            kick.MonitorChannel(cfg, channelName)
        }(channel)
    }

    wg.Wait()
}
```

## 6. Dependency Management

Go uses modules for dependency management. You would initialize the project with `go mod init github.com/your-username/stream-monitor-go` and then `go get` to add dependencies like `github.com/spf13/viper` and `github.com/gorilla/websocket`.

This document provides a high-level guide. The actual implementation will require more detailed error handling, message parsing, and structuring of the Discord embed.
