# Hera Home Automation

A comprehensive home automation GUI built with Node.js, Vue.js, and a modular adapter architecture. This system provides a unified interface for controlling various smart home devices including lights, Spotify players, and more.

## Architecture Overview

The project follows a modular architecture with clear separation between configuration, device adapters, backend API, and frontend interface:

```
hera/
├── config/                 # YAML configuration files
│   ├── app.yaml            # Main application settings
│   ├── rooms.yaml          # Room definitions and device groupings
│   ├── devices/            # Device-specific configurations
│   ├── services/           # Service configurations (LLM, etc.)
│   └── scenes/             # Scene definitions
├── backend/                # Node.js Express API server
│   └── src/
│       ├── server.js       # Main server file
│       ├── routes/         # API route handlers
│       └── utils/          # Utilities and helpers
├── frontend/               # Vue.js web interface
│   └── src/
│       ├── views/          # Page components
│       ├── components/     # Reusable components
│       ├── stores/         # Pinia state management
│       └── router/         # Vue Router configuration
├── adapters/               # Device adapter layer
│   ├── base-adapter.js     # Base adapter class
│   ├── lights-adapter.js   # Lights control adapter
│   ├── spotify-adapter.js  # Spotify control adapter
│   └── adapter-manager.js  # Adapter management
├── shared/                 # Shared utilities
│   └── config-loader.js    # Configuration management
└── modules/                # Git submodules (your device modules)
```

## Key Features

### 🏠 **Room-Based Organization**
- Organize devices by rooms (living room, bedroom, kitchen, etc.)
- Control all devices in a room with single commands
- Room groups for multi-room operations

### 🔌 **Device Management**
- Modular adapter system for different device types
- Currently supports lights and Spotify players
- Easy to extend for new device types
- Real-time device status monitoring

### 🎬 **Scene Control**
- Pre-configured scenes (morning, evening, party, etc.)
- Time and day-based conditions
- Batch device operations
- Scene preview and activation

### 🌐 **Modern Web Interface**
- Responsive Vue.js frontend
- Real-time updates via WebSocket
- Mobile-friendly design
- Tailwind CSS styling

### ⚡ **Real-Time Communication**
- WebSocket integration for live updates
- Device status synchronization
- Command result feedback
- Activity monitoring

### 🔧 **Configuration-Driven**
- YAML-based configuration
- Hot-reload configuration changes
- Validation and error checking
- Modular config structure

## Quick Start

### Prerequisites
- Node.js 18+ 
- npm or yarn

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd hera
   ```

2. **Install dependencies**
   ```bash
   npm run install:all
   ```

3. **Configure your devices**
   Edit the configuration files in the `config/` directory:
   - `config/devices/lights.yaml` - Configure your light devices
   - `config/devices/spotify.yaml` - Configure Spotify devices
   - `config/rooms.yaml` - Define rooms and device groupings

4. **Add your device modules**
   Add your existing device modules as git submodules:
   ```bash
   git submodule add <your-lights-module-url> modules/lights-module
   git submodule add <your-spotify-module-url> modules/spotify-module
   ```

5. **Start the development servers**
   ```bash
   npm run dev
   ```

   This starts both the backend API server (port 3001) and frontend dev server (port 3000).

6. **Access the interface**
   Open http://localhost:3000 in your browser

## Configuration

### Device Configuration

**Lights** (`config/devices/lights.yaml`):
```yaml
lights:
  living_light_1:
    name: "Living Room Main Light"
    type: "smart_bulb"
    brand: "philips_hue"
    capabilities: ["power", "brightness", "color", "temperature"]
    settings:
      default_brightness: 80
      default_color: "#ffffff"
    connection:
      protocol: "zigbee"
      address: "192.168.1.100"
```

**Spotify** (`config/devices/spotify.yaml`):
```yaml
spotify:
  living_spotify:
    name: "Living Room Speaker"
    device_id: "spotify_device_123"
    capabilities: ["play", "pause", "skip", "volume"]
    settings:
      default_volume: 50
      max_volume: 80
```

### Room Configuration

**Rooms** (`config/rooms.yaml`):
```yaml
rooms:
  living_room:
    name: "Living Room"
    devices:
      - type: "light"
        id: "living_light_1"
      - type: "spotify"
        id: "living_spotify"
```

### Scene Configuration

**Scenes** (`config/scenes/morning.yaml`):
```yaml
scene:
  name: "Morning"
  description: "Gentle wake-up lighting and music"

actions:
  lights:
    living_light_1:
      power: true
      brightness: 60
      color: "#fff4e6"
  spotify:
    living_spotify:
      action: "play"
      playlist: "morning"
      volume: 25
```

## API Endpoints

### Devices
- `GET /api/v1/devices` - List all devices
- `GET /api/v1/devices/:id` - Get device details
- `POST /api/v1/devices/:id/command` - Execute device command

### Rooms
- `GET /api/v1/rooms` - List all rooms
- `GET /api/v1/rooms/:id` - Get room details
- `POST /api/v1/rooms/:id/command` - Execute room command

### Scenes
- `GET /api/v1/scenes` - List all scenes
- `POST /api/v1/scenes/:id/activate` - Activate scene

### Status
- `GET /api/v1/status` - System status
- `GET /api/v1/status/devices` - Device status overview
- `POST /api/v1/status/test` - Run system tests

## WebSocket Events

### Client → Server
- `device:command` - Execute device command
- `room:command` - Execute room command
- `status:request` - Request status update

### Server → Client
- `device:status:update` - Device status changed
- `room:status:update` - Room status changed
- `scene:activated` - Scene was activated

## Extending the System

### Adding New Device Types

1. **Create an adapter** in `adapters/`:
   ```javascript
   class NewDeviceAdapter extends BaseAdapter {
     async executeCommand(command, params) {
       // Implement device-specific logic
     }
   }
   ```

2. **Register the adapter** in `adapter-manager.js`:
   ```javascript
   this.adapterTypes = {
     lights: LightsAdapter,
     spotify: SpotifyAdapter,
     newdevice: NewDeviceAdapter  // Add here
   };
   ```

3. **Add configuration** in `config/devices/newdevice.yaml`

4. **Update the frontend** to handle the new device type

### Integrating Your Modules

The adapter system is designed to work with your existing device modules. Update the TODO comments in the adapter files to integrate your actual modules:

```javascript
// In lights-adapter.js
async initialize() {
  // TODO: Replace with actual module initialization
  const LightsModule = require('../modules/lights-module');
  this.lightsModule = new LightsModule(this.deviceConfig);
  await this.lightsModule.connect();
}
```

## Development

### Backend Development
```bash
npm run backend:dev  # Start backend with nodemon
```

### Frontend Development
```bash
npm run frontend:dev  # Start frontend with Vite
```

### Building for Production
```bash
npm run build  # Build frontend for production
npm start      # Start production server
```

## Future Enhancements

- **Voice Control**: LLM-powered voice commands (configuration already in place)
- **Mobile App**: React Native or Flutter mobile interface
- **Scheduling**: Time-based automation and scheduling
- **Analytics**: Usage analytics and energy monitoring
- **Security**: Authentication and authorization
- **Cloud Integration**: Remote access and cloud synchronization

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details.
