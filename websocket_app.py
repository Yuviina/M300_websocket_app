import os
import threading
import time
import socket
import random
import json
import asyncio
import websockets
import logging
from datetime import datetime
from pyModbusTCP.server import ModbusServer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ClientConnection:
    """Class to track individual client connections"""
    def __init__(self, websocket, client_id):
        self.websocket = websocket
        self.client_id = client_id
        self.connected_at = datetime.now()
        self.last_ping = datetime.now()
        self.message_count = 0
        
    def update_activity(self):
        self.last_ping = datetime.now()
        self.message_count += 1

class M300WebSocketSimulator:
    """WebSocket-based M300 IoT Gateway Simulator for Flutter App"""
    
    def __init__(self):
        self.running = True
        self.sensor_data = {}
        self.data_history = []
        self.connected_clients = {}  # Changed to dict for better tracking
        self.loop = None
        self.client_counter = 0
        
        # Setup mock data generation
        self.setup_mock_data()
        
    def setup_mock_data(self):
        """Setup mock data generation in background thread"""
        data_thread = threading.Thread(target=self.generate_mock_data)
        data_thread.daemon = True
        data_thread.start()
    
    def generate_mock_data(self):
        """Generate realistic mock sensor data and broadcast to clients"""
        while self.running:
            try:
                # Generate Modbus sensor data (Water Quality)
                modbus_data = {
                    'pH': round(random.uniform(6.5, 8.5), 2),
                    'TSS': round(random.uniform(20, 120), 1),
                    'COD': round(random.uniform(50, 250), 1),
                    'Ammonia': round(random.uniform(0.5, 8.0), 2),
                    'Flow_Modbus': round(random.uniform(100, 400), 1),
                    'Pressure': round(random.uniform(1.0, 2.5), 2)
                }
                
                # Generate Digital sensor data (Operational)
                digital_data = {
                    'FLOW': f"{random.uniform(25, 45):.1f}L/min",
                    'ACTUATOR': f"{random.uniform(30, 80):.1f}%",
                    'STATUS': random.choice(['OK', 'OK', 'OK', 'WARN', 'FAULT']),
                    'PUMP': random.choice(['ON', 'OFF']),
                    'ALARM': random.choice(['NORMAL', 'NORMAL', 'NORMAL', 'ALARM']),
                    'TIMESTAMP': int(datetime.now().timestamp())
                }
                
                # Update sensor data
                self.sensor_data.update(modbus_data)
                self.sensor_data.update(digital_data)
                
                # Create message for WebSocket clients
                message = {
                    "type": "sensor_update",
                    "timestamp": datetime.now().isoformat(),
                    "sensors": self.sensor_data,
                    "status": "active"
                }
                
                # Add to history
                history_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "sensor_update",
                    "data": dict(self.sensor_data)
                }
                
                self.data_history.append(history_entry)
                
                # Keep only last 1000 records
                if len(self.data_history) > 1000:
                    self.data_history.pop(0)
                
                # Broadcast to all connected WebSocket clients
                if self.connected_clients and self.loop:
                    try:
                        asyncio.run_coroutine_threadsafe(
                            self.broadcast_to_clients(message), 
                            self.loop
                        ).result(timeout=1.0)
                    except Exception as e:
                        logger.error(f"Error broadcasting: {e}")
                
                # Sleep for 3 seconds
                time.sleep(3)
                
            except Exception as e:
                logger.error(f"Error generating mock data: {e}")
                time.sleep(5)
    
    async def broadcast_to_clients(self, message):
        """Broadcast message to all connected WebSocket clients"""
        if not self.connected_clients:
            return
            
        message_str = json.dumps(message)
        disconnected_clients = []
        
        for client_id, client_conn in list(self.connected_clients.items()):
            try:
                await client_conn.websocket.send(message_str)
                client_conn.update_activity()
            except websockets.exceptions.ConnectionClosed:
                logger.info(f"Client {client_id} connection closed during broadcast")
                disconnected_clients.append(client_id)
            except Exception as e:
                logger.error(f"Error sending to client {client_id}: {e}")
                disconnected_clients.append(client_id)
        
        # Remove disconnected clients
        for client_id in disconnected_clients:
            await self.remove_client(client_id)
    
    async def remove_client(self, client_id):
        """Safely remove a client from tracking"""
        if client_id in self.connected_clients:
            client_conn = self.connected_clients[client_id]
            connection_duration = datetime.now() - client_conn.connected_at
            logger.info(f"Removing client {client_id} - Duration: {connection_duration}, Messages: {client_conn.message_count}")
            del self.connected_clients[client_id]
    
    async def add_client(self, websocket):
        """Add a new client to tracking"""
        self.client_counter += 1
        client_id = f"client_{self.client_counter}"
        client_address = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        
        client_conn = ClientConnection(websocket, client_id)
        self.connected_clients[client_id] = client_conn
        
        logger.info(f"New client connected: {client_id} from {client_address} - Total clients: {len(self.connected_clients)}")
        return client_id, client_conn
    
    async def handle_client(self, websocket):
        """Handle new WebSocket client connection"""
        client_id = None
        client_conn = None
        
        try:
            # Add client to tracking
            client_id, client_conn = await self.add_client(websocket)
            
            # Send initial data to new client
            initial_message = {
                "type": "initial_data",
                "timestamp": datetime.now().isoformat(),
                "client_id": client_id,
                "sensors": self.sensor_data,
                "system": {
                    "gateway": "online",
                    "sensors": {
                        "digital": "active" if 'FLOW' in self.sensor_data else "inactive",
                        "modbus": "active" if 'pH' in self.sensor_data else "inactive"
                    },
                    "data_points": len(self.sensor_data),
                    "history_records": len(self.data_history),
                    "connected_clients": len(self.connected_clients)
                },
                "status": "connected"
            }
            
            await websocket.send(json.dumps(initial_message))
            logger.info(f"Sent initial data to {client_id}")
            
            # Listen for messages from client
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.handle_client_message(websocket, data, client_conn)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error from {client_id}: {e}")
                    error_response = {
                        "type": "error",
                        "message": "Invalid JSON format",
                        "timestamp": datetime.now().isoformat()
                    }
                    await websocket.send(json.dumps(error_response))
                except Exception as e:
                    logger.error(f"Error handling message from {client_id}: {e}")
                
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client {client_id} disconnected normally")
        except websockets.exceptions.InvalidMessage as e:
            logger.error(f"Invalid message from {client_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error with client {client_id}: {e}")
        finally:
            # Always cleanup the client
            if client_id:
                await self.remove_client(client_id)
    
    async def handle_client_message(self, websocket, data, client_conn):
        """Handle messages from WebSocket clients"""
        message_type = data.get("type", "unknown")
        client_conn.update_activity()
        
        try:
            if message_type == "get_sensors":
                response = {
                    "type": "sensor_data",
                    "timestamp": datetime.now().isoformat(),
                    "sensors": self.sensor_data,
                    "status": "active"
                }
                await websocket.send(json.dumps(response))
                
            elif message_type == "get_status":
                response = {
                    "type": "system_status",
                    "timestamp": datetime.now().isoformat(),
                    "system": {
                        "gateway": "online",
                        "sensors": {
                            "digital": "active" if 'FLOW' in self.sensor_data else "inactive",
                            "modbus": "active" if 'pH' in self.sensor_data else "inactive"
                        },
                        "data_points": len(self.sensor_data),
                        "history_records": len(self.data_history),
                        "connected_clients": len(self.connected_clients)
                    }
                }
                await websocket.send(json.dumps(response))
                
            elif message_type == "get_history":
                limit = data.get("limit", 100)
                response = {
                    "type": "history_data",
                    "timestamp": datetime.now().isoformat(),
                    "history": self.data_history[-limit:],
                    "total_records": len(self.data_history),
                    "limit": limit
                }
                await websocket.send(json.dumps(response))
                
            elif message_type == "clear_history":
                self.data_history.clear()
                response = {
                    "type": "history_cleared",
                    "message": "History cleared successfully",
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send(json.dumps(response))
                
            elif message_type == "ping":
                response = {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat(),
                    "client_id": client_conn.client_id
                }
                await websocket.send(json.dumps(response))
                
            elif message_type == "get_client_info":
                response = {
                    "type": "client_info",
                    "timestamp": datetime.now().isoformat(),
                    "client_id": client_conn.client_id,
                    "connected_since": client_conn.connected_at.isoformat(),
                    "message_count": client_conn.message_count,
                    "last_activity": client_conn.last_ping.isoformat()
                }
                await websocket.send(json.dumps(response))
                
            else:
                error_response = {
                    "type": "error",
                    "message": f"Unknown message type: {message_type}",
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send(json.dumps(error_response))
                
        except Exception as e:
            logger.error(f"Error handling message type {message_type}: {e}")
    
    def find_available_port(self, start_port=8765):
        """Find an available port starting from start_port"""
        for port in range(start_port, start_port + 100):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    return port
            except OSError:
                continue
        return None
    
    async def periodic_client_check(self):
        """Periodically check client health and log statistics"""
        while self.running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                if self.connected_clients:
                    logger.info(f"Active clients: {len(self.connected_clients)}")
                    for client_id, client_conn in self.connected_clients.items():
                        connection_duration = datetime.now() - client_conn.connected_at
                        last_activity = datetime.now() - client_conn.last_ping
                        logger.debug(f"{client_id}: Duration={connection_duration}, Last activity={last_activity}, Messages={client_conn.message_count}")
                        
            except Exception as e:
                logger.error(f"Error in periodic client check: {e}")
    
    async def start_server(self, host='0.0.0.0', port=None):
        """Start WebSocket server"""
        if port is None:
            port = int(os.environ.get('PORT', 8765))
        
        print(f"🚀 M300 WebSocket Simulator starting...")
        print(f"🔌 WebSocket Server: ws://{host}:{port}")
        print(f"📱 Ready for Flutter app connections")
        print(f"🔄 Mock data generation: Active")
        print(f"📊 Message types supported:")
        print(f"   - sensor_update (auto-broadcast every 3s)")
        print(f"   - get_sensors (request current data)")
        print(f"   - get_status (request system status)")
        print(f"   - get_history (request historical data)")
        print(f"   - get_client_info (request client connection info)")
        print(f"   - clear_history (clear data history)")
        print(f"   - ping/pong (connection test)")
        
        # Store the event loop for broadcasting
        self.loop = asyncio.get_event_loop()
        
        # Start periodic client health check
        health_check_task = asyncio.create_task(self.periodic_client_check())
        
        try:
            # Start WebSocket server
            server = await websockets.serve(
                self.handle_client, 
                host, 
                port,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10,
                max_size=1024*1024  # 1MB max message size
            )
            
            print(f"✅ WebSocket server started successfully!")
            print(f"💡 Connect your Flutter app to: ws://{host}:{port}")
            print(f"🔍 Server info: ping_interval=20s, ping_timeout=10s")
            print(f"📡 Testing with Postman: Create new WebSocket request to ws://{host}:{port}")
            print(f"📈 Client health checks running every 30 seconds")
            
            # Keep server running
            await server.wait_closed()
                
        except Exception as e:
            logger.error(f"Server startup error: {e}")
            raise
        finally:
            health_check_task.cancel()
    
    def run(self, host='0.0.0.0', port=None):
        """Run the WebSocket server"""
        try:
            asyncio.run(self.start_server(host, port))
        except KeyboardInterrupt:
            print("\n🛑 WebSocket server stopped by user")
            self.running = False
            # Log final statistics
            if hasattr(self, 'connected_clients'):
                logger.info(f"Server shutdown - Total clients served: {self.client_counter}")
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise

def main():
    """Main function to start the WebSocket simulator"""
    simulator = M300WebSocketSimulator()
    
    # Check for environment variables
    mode = os.environ.get('MODE', 'production')
    host = os.environ.get('HOST', '0.0.0.0')
    
    if mode == 'development':
        # Development mode with port detection
        port = simulator.find_available_port(8765)
        if port:
            print(f"🔧 Development mode - Using port {port}")
            simulator.run(host=host, port=port)
        else:
            print("❌ No available ports found")
    else:
        # Production mode
        port = int(os.environ.get('PORT', 8765))
        simulator.run(host=host, port=port)

if __name__ == "__main__":
    main()