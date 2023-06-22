import sys
import asyncio
import aiohttp
import time
import json
from decimal import *

server_ports = {"Riley": 12665, "Jaquez": 12666, "Juzang": 12667, "Campbell": 12668, "Bernard": 12669}
server_connections = {
                        "Riley": ["Jaquez", "Juzang"],
                        "Bernard": ["Jaquez", "Juzang", "Campbell"],
                        "Juzang": ["Campbell", "Bernard", "Riley"],
                        "Jaquez": ["Riley", "Bernard"],
                        "Campbell": ["Juzang", "Bernard"]
                     }

class Server:
    def __init__(self, name):
        if name not in server_ports:
            sys.stderr.write("Invalid server name provided.\n")
            sys.exit(1)
        self.server_name = name
        self.client_location = {}
        self.client_time = {}
        self.client_OG_server = {}
        
    
    def write_to_log(self, str):
        logfile.write(str + '\n')
        
    async def run(self):
        global logfile 
        logfile = open(f"{self.server_name}_logfile.txt", "a+")
        server = await asyncio.start_server(self.message_handler, host="127.0.0.1", port=server_ports[self.server_name])
        async with server:
            await server.serve_forever()
        server.close()
        logfile.close()
    async def message_handler(self, reader, writer):
        async def flood(response):
            for neighbor in server_connections[self.server_name]:
                try:
                    reader, writer = await asyncio.open_connection("127.0.0.1", server_ports[neighbor])
                    self.write_to_log(f"CONNECTION: Connection established from {self.server_name} to {neighbor}")
                    writer.write(response)
                    self.write_to_log(f"OUTPUT: {response}")
                    await writer.drain()
                    writer.close()
                    await writer.wait_closed()
                except:
                    self.write_to_log(f"ERROR: Could not establish connection from {self.server_name} to {neighbor}")
                    
        while not reader.at_eof():
            input = await reader.readline()
            input_raw = input.decode()
            input_raw_stripped = input_raw.strip()
            msg_components = input_raw_stripped.split()
            self.write_to_log(f"INPUT: {input_raw}")
            msg_type = self.check_input(msg_components)
            if msg_type == "?":
                writer.write(f"? {input_raw}".encode())
                self.write_to_log(f"OUTPUT: ? {input_raw}")
                await writer.drain()
            elif msg_type == "IAMAT":
                response = self.handle_IAMAT(msg_components)
                self.write_to_log(f"OUTPUT: {response.decode()}")
                writer.write(response)
                await writer.drain()
                await flood(response)
            elif msg_type == "WHATSAT":
                response = await self.handle_WHATSAT(msg_components)
                self.write_to_log(f"OUTPUT: {response.decode()}")
                writer.write(response)
                await writer.drain()
            else:
                #if msg_components[3] not in self.client_time or self.client_time[msg_components[3]] < float(msg_components[5]):
                if msg_components[3] not in self.client_time or self.client_time[msg_components[3]] < Decimal(msg_components[5]):
                    self.handle_AT(msg_components)
                    await flood(input_raw.encode())
    def check_input(self, msg_components):
        if len(msg_components) == 4 and (msg_components[0] == "IAMAT"):
            #return msg_components[0]
            ret_coords_value = self.check_client_coords(msg_components[2])
            if ret_coords_value == "?":
                return "?"
            else:
                self.client_location[msg_components[1]] = ret_coords_value
            ret_time_value = self.check_client_timestamp(msg_components[3])
            if ret_time_value == "?":
                return "?"
            else:
                if (msg_components[1] not in self.client_time) or self.client_time[msg_components[1]] < ret_time_value:
                    self.client_time[msg_components[1]] = ret_time_value
            self.client_OG_server[msg_components[1]] = self.server_name
            return msg_components[0]
        
        elif len(msg_components) == 4 and (msg_components[0] == "WHATSAT"):
            if msg_components[2].isdigit() and msg_components[3].isdigit():
                radius = int(msg_components[2])
                max_items = int(msg_components[3])
                if radius > 50 or radius < 0:
                    return "?"
                if max_items > 20 or max_items <= 0:
                    return "?"
                if msg_components[1] not in self.client_location:
                    return "?"
                else:
                    return msg_components[0]
        elif len(msg_components) == 6 and msg_components[0] == "AT":
            return msg_components[0]
        else:
            return "?"
    def check_client_coords(self, coords):
        enum_tuple = list(enumerate(coords))
        lats_and_longs = []
        for elem in enum_tuple:
            if elem[1] == "+" or elem[1] == "-":
                lats_and_longs.append(elem[0])
        if (len(lats_and_longs) != 2) or (enum_tuple[0][1] != "+" and enum_tuple[0][1] != "-"):
            return "?"
        try:
            return [float(coords[:(lats_and_longs[1])]), float(coords[(lats_and_longs[1]):])]
        except:
            return "?"
    
    def check_client_timestamp(self, timestamp):
        try:
            #return float(timestamp)
            return Decimal(timestamp)
        except:
            return "?"

    def handle_IAMAT(self, msg_components):
        current_time = Decimal(time.time()).quantize(Decimal('.000000001'), rounding=ROUND_DOWN)
        #current_time = time.time()
        time_diff = str(current_time - self.client_time[msg_components[1]])
        if current_time > self.client_time[msg_components[1]]:
            time_diff = f"+{time_diff}"
        response = f"AT {self.server_name} {time_diff} {msg_components[1]} {msg_components[2]} {msg_components[3]}\n".encode()
        return response
        
            
    
    async def handle_WHATSAT(self, msg_components):
        start_time = Decimal(time.time()).quantize(Decimal('.000000001'), rounding=ROUND_DOWN)
        #start_time = time.time()
        radius = int(msg_components[2])
        max_items = int(msg_components[3])
        coordinates = self.client_location[msg_components[1]]
        api_request = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={','.join([str(coordinates[0]), str(coordinates[1])])}&radius={radius*1000}&key={'AIzaSyB1ifRLJQQBaky61LgPGLTORPcI2GW98-M'}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_request) as response:
                #my_print("INFO: Request URL ({})".format(request_URL))
                raw_json = await response.text()
                json_o = json.loads(raw_json)
                json_o["results"] = json_o["results"][:max_items]
                json_s = json.dumps(json_o, indent=4)
                json_s_c = ""
                while (not (json_s_c == json_s)):
                    json_s_c = json_s
                    json_s = json_s.replace("\n\n", "\n")
                difference = start_time - self.client_time[msg_components[1]]
                coords_s = ''.join([str(coordinates[0]), str(coordinates[1])])
                if not (coords_s[0] == '-' or coords_s[0] == "+"):
                    coords_s = f"+{coords_s}"
                if difference > 0:
                    difference = f"+{str(difference)}"
                else:
                    difference = str(difference)
                response = f"AT {self.client_OG_server[msg_components[1]]} {difference} {msg_components[1]} {coords_s} {self.client_time[msg_components[1]]}\n{json_s}\n".encode()
        return response
    def handle_AT(self, msg_components):
        ret_coords_value = self.check_client_coords(msg_components[4])
        ret_time_value = self.check_client_timestamp(msg_components[5])
        self.client_location[msg_components[3]] = ret_coords_value
        self.client_time[msg_components[3]] = ret_time_value
        self.client_OG_server[msg_components[3]] = msg_components[1]
        return
        
            


def main():
    if (len(sys.argv) != 2):
        sys.stderr.write("Invalid arguments to server.py.\n")
        sys.exit(1)
    else:
        server = Server(sys.argv[1])
        try:
            asyncio.run(server.run())
        except KeyboardInterrupt:
            sys.stderr.write("Server terminated due to interrupt.\n")
            sys.exit(1)
            
    sys.exit(0)
    
if __name__ == "__main__":
    main()