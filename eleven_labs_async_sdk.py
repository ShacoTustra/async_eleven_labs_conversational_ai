from elevenlabs.client import ElevenLabs
import json
import websockets
import base64
import asyncio
import pyaudio
import time

class AsyncElevenLabsAgent:
    def __init__(
        self,
        client,
        agent_id: str,
        *,
        requires_auth: bool
    ):
        self.client = client
        self.agent_id = agent_id
        self.requires_auth = requires_auth
        self.ws_url = self.get_signed_url() if self.requires_auth else self.get_wss_url()
        self._conversation_id = None
        self._last_interrupt_id = 0
        self.ws = None

        self.t1 = None
        self.t2 = None
        self.t3 = None

    async def connect(self):
        """Установка WebSocket соединения"""
        self.ws = await websockets.connect(self.ws_url)
        return self.ws

    async def send_audio(self, audio):
        """Отправка аудио через существующее соединение"""
        if not self.ws:
            raise RuntimeError("WebSocket connection not established")
        await self.ws.send(
            json.dumps(
                {
                    "user_audio_chunk": base64.b64encode(audio).decode(),
                }
            )
        )

    async def read_message(self):
        """Чтение сообщений через существующее соединение"""
        if not self.ws:
            raise RuntimeError("WebSocket connection not established")
        try:
            received = await self.ws.recv()
            message = json.loads(received)
            await self.handle_message(message)
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed")
            raise

    async def handle_message(self, message):

        if message["type"] == "conversation_initiation_metadata":
            event = message["conversation_initiation_metadata_event"]
            assert self._conversation_id is None
            self._conversation_id = event["conversation_id"]
        elif message["type"] == "audio":
            event = message["audio_event"]
            if int(event["event_id"]) <= self._last_interrupt_id:
                return
            if self.t3:
                print('Audio latency: ', time.time() - self.t3)
            audio = base64.b64decode(event["audio_base_64"])
            # Здесь можно добавить обработку аудио
        elif message["type"] == "agent_response":
            if self.t2:
                print('Response latency: ', time.time() - self.t2)
            self.t3 = time.time()
            print("Agent response:", message["agent_response_event"])
        elif message["type"] == "agent_response_correction":
            print("Correction:", message["agent_response_correction_event"])
        elif message["type"] == "user_transcript":
            print("Transcript:", message["user_transcription_event"])
            if self.t1:
                print('Latency: ',time.time()-self.t1)
            self.t2 = time.time()
        elif message["type"] == "interruption":
            event = message["interruption_event"]
            self.t1 = time.time()
            self.last_interrupt_id = int(event["event_id"])
            print('interruption')
        elif message["type"] == "ping":
            event = message["ping_event"]
            await self.ws.send(
                json.dumps(
                    {
                        "type": "pong",
                        "event_id": event["event_id"],
                    }
                )
            )


    def get_wss_url(self):
        base_url = self.client._client_wrapper._base_url
        base_ws_url = base_url.replace("http", "ws", 1)
        return f"{base_ws_url}/v1/convai/conversation?agent_id={self.agent_id}"

    def get_signed_url(self):
        response = self.client._client_wrapper.httpx_client.request(
            f"v1/convai/conversation/get_signed_url?agent_id={self.agent_id}",
            method="GET",
        )
        return response.json()["signed_url"]
