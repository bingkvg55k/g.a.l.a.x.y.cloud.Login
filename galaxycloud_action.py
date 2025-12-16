import asyncio
import json
import os

from aiohttp import ClientSession

WS_URL = "wss://beta.galaxycloud.app/sockjs/455/ngzsq3eg/websocket"
ORIGIN = "https://beta.galaxycloud.app"

GC_USERNAME = os.getenv("GC_USERNAME")
GC_PASSWORD = os.getenv("GC_PASSWORD")
GC_APP_USERNAME = os.getenv("GC_APP_USERNAME")

if not GC_USERNAME or not GC_PASSWORD or not GC_APP_USERNAME:
    raise RuntimeError("GC_USERNAME / GC_PASSWORD / GC_APP_USERNAME not set")

async def send_ddp(ws, payload: dict):
    await ws.send_str(json.dumps([json.dumps(payload)]))

def parse_ddp(raw):
    if raw == "h":
        return None
    if raw.startswith("a"):
        return json.loads(json.loads(raw[1:])[0])
    return None

async def wait_result(ws, method_id, last_msg_holder):
    while True:
        msg = await ws.receive()
        data = parse_ddp(msg.data)
        if not data:
            continue

        last_msg_holder["last"] = data

        if data.get("msg") == "result" and data.get("id") == method_id:
            if "error" in data:
                raise RuntimeError(data["error"])
            return data.get("result")

async def main():
    last_msg = {"last": None}

    async with ClientSession(headers={"Origin": ORIGIN}) as session:
        async with session.ws_connect(WS_URL) as ws:

            # 1️⃣ connect
            await send_ddp(ws, {
                "msg": "connect",
                "version": "1",
                "support": ["1"]
            })

            while True:
                msg = await ws.receive()
                data = parse_ddp(msg.data)
                if data:
                    last_msg["last"] = data
                if data and data.get("msg") == "connected":
                    break

            # 2️⃣ authenticate
            await send_ddp(ws, {
                "msg": "method",
                "id": "login-1",
                "method": "auth.authenticateWithCredentials",
                "params": [{
                    "usernameOrEmail": GC_USERNAME,
                    "password": GC_PASSWORD
                }]
            })

            result = await wait_result(ws, "login-1", last_msg)
            token = result["token"]

            # 3️⃣ resume
            await send_ddp(ws, {
                "msg": "method",
                "id": "login-2",
                "method": "login",
                "params": [{
                    "resume": token
                }]
            })

            await wait_result(ws, "login-2", last_msg)

            # 4️⃣ updateConfiguration
            await send_ddp(ws, {
                "msg": "method",
                "id": "update-1",
                "method": "webapps.updateConfiguration",
                "params": [{
                    "hostname": "eugoogle",
                    "region": "eu-west-1",
                    "username": GC_APP_USERNAME,
                    "configuration": {
                        "buildConfig": {
                            "containerImage": "nodejs22",
                            "installCommand": "npm install",
                            "startCommand": "npm start",
                            "buildCommand": "",
                            "environmentVariables": [
                                {
                                    "key": "PORT",
                                    "value": "3000",
                                    "id": "mantine-eckwjcevv",
                                    "disabled": False
                                }
                            ]
                        },
                        "gitConfig": {
                            "branch": "main"
                        },
                        "healthCheckPath": "/"
                    }
                }]
            })

            await wait_result(ws, "update-1", last_msg)

    print("✅ Last To client message:")
    print(json.dumps(last_msg["last"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
